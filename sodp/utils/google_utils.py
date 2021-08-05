import httplib2
import google.oauth2.credentials
import google_auth_oauthlib.flow

import json
import os
import pandas as pd
import tempfile

from apiclient.discovery import build
from pprint import pprint

from datetime import datetime
from oauth2client import GOOGLE_REVOKE_URI, GOOGLE_TOKEN_URI, client
from django.conf import settings
from django.urls import reverse

from datetime import date
from google.cloud import bigquery
from google.oauth2 import service_account

from sodp.views.models import view as modelview

DIMS = ['ga:segment']
METRICS = ['ga:pageViews', 'ga:uniquePageViews', 'ga:timeOnPage', 'ga:entrances', 'ga:bounceRate', 'ga:exitRate', 'ga:pageValue']
SEGMENTS = ['gaid::-1','gaid::-5']
MAX_RESULTS = 100000

def getGoogleConfig(request):
    return {
        "installed": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [ request.build_absolute_uri('/')+"users/~googlecredentials/", "urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://accounts.google.com/o/oauth2/token"
        }
    }

def getScopes():
    return [
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/userinfo.email',
        'openid'        
    ]
def generateGoogleURL(request):

    # Use the client_secret.json file to identify the application requesting
    # authorization. The client ID (from that file) and access scopes are required.
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        client_config=getGoogleConfig(request),
        scopes=getScopes())

    # Indicate where the API server will redirect the user after the user completes
    # the authorization flow. The redirect URI is required. The value must exactly
    # match one of the authorized redirect URIs for the OAuth 2.0 client, which you
    # configured in the API Console. If this value doesn't match an authorized URI,
    # you will get a 'redirect_uri_mismatch' error.
    flow.redirect_uri = request.build_absolute_uri('/')+"users/~googlecredentials/"

    # Generate URL for request to Google's OAuth 2.0 server.
    # Use kwargs to set optional request parameters.
    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        prompt='consent',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    return authorization_url    

def getUserCredentials(request):
    os.environ['AUTHLIB_INSECURE_TRANSPORT'] = '1'

    try:
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config=getGoogleConfig(request),
            scopes=getScopes())
        flow.redirect_uri = request.build_absolute_uri('/')+"users/~googlecredentials/"
        authorization_response = request.build_absolute_uri(request.get_full_path()).replace("http:", "https:", 1)
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        return credentials
    except Exception as e:
        return False

def getOfflineCredentials(auth_token, refresh_token):
    try:
        credentials = client.OAuth2Credentials(
            access_token=None,  # set access_token to None since we use a refresh token
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            refresh_token=refresh_token,
            token_expiry=None,
            token_uri=GOOGLE_TOKEN_URI,
            user_agent=None,
            revoke_uri=GOOGLE_REVOKE_URI)
        return credentials       
    except Exception as e:
        return False        

# get all the projects that the user has with that credentials
def getProjectsFromCredentials(credentials):
    if settings.USE_DUMMY_GOOGLE_DATA:
        projects = {
            "1": { "name": "Account 1 - Project 1", "url": "http://sodp-test.herokuapp.com"},
            "2": { "name": "Account 1 - Project 2", "url": "http://www.google.com"},
            "3": { "name": "Account 2 - Project 1", "url": "http://www.ysoft.biz"},
        }
    else:
        analytics = build('analytics', 'v3', credentials=credentials)
        accounts = analytics.management().accounts().list().execute()

        projects = {}
        if accounts.get('items'):
            for item in accounts.get('items'):
                account_id = item["id"]
                
                # now lets retrieve all the views
                profiles = analytics.management().profiles().list(accountId=account_id,
                                                        webPropertyId='~all'
                                                        ).execute()

                for profile in profiles.get('items'):
                    projects[profile["id"]] = { "name": item["name"]+" - "+profile["name"], "url": profile["websiteUrl"] }

    return projects

# create google analytics table if does not exist
def createTable(bq, table, view_id, report_id):
    # create table inside dataset
    table_id = "%s.sodp.%s_%s_%d" % (bq.project, table, view_id, report_id)
    bq.delete_table(table_id, not_found_ok=True)

    schema = [
        bigquery.SchemaField("page_path", "STRING"),
        bigquery.SchemaField("segment", "STRING"),
        bigquery.SchemaField("date", "DATE"),
        bigquery.SchemaField("pageViews", "INTEGER"),
        bigquery.SchemaField("uniquePageViews", "INTEGER"),
        bigquery.SchemaField("timeOnPage", "NUMERIC"),
        bigquery.SchemaField("entrances", "NUMERIC"),
        bigquery.SchemaField("bounceRate", "NUMERIC"),
        bigquery.SchemaField("exitRate", "NUMERIC"),
        bigquery.SchemaField("pageValue", "NUMERIC")
    ]

    table = bigquery.Table(table_id, schema=schema)
    table = bq.create_table(table)  # Make an API request.

    return table_id

# inserts the row
def insertBigTable(bq, table_id, entries):
    try:
        errors = bq.insert_rows_json(table_id, entries,  row_ids=[None] * len(entries))
    except Exception as e:
        print(str(e))
        return False

# returns a date object depending on the interval
def getDateFromGA(datestr, period):
    # get date from month or week
    if period == "ga:yearmonth":
        final_date = date(int(datestr[:4]), int(datestr[4:]), 1)
    elif period == "ga:yearweek":
        year, week = int(datestr[:4]), int(datestr[4:])
        start_of_year = date(year, 1, 1)
        days = 7 * (week - 1) - (start_of_year.isoweekday() % 7)    
        days = max(0, days)  # GA restarts yearWeek on a new year 
        final_date = start_of_year + datetime.timedelta(days=days)
    else:
        final_date = datetime.strptime(datestr, '%Y%m%d')

    return final_date.strftime("%Y-%m-%d")

# returns a dump of the desired stats for the specific credentials and view
def getStatsFromView(credentials, bq, view_id, report_id, url, startDate, endDate, table_id):
    analytics = build('analyticsreporting', 'v4', credentials=credentials)

    # retrieve date interval: 6-12 months grouped monthly, 3-6 months grouped weekly, <3 months grouped daily
    dimensions = list(DIMS)
    diff_months = (endDate.year - startDate.year) * 12 + endDate.month - startDate.month
    if diff_months>=6:
        period = "ga:yearmonth"
    elif diff_months>=3:
        period = "ga:yearweek"
    else:
        period = "ga:date"
    dimensions.append(period)

    latest_organic_traffic = {}
    latest_traffic = {}

    data = analytics.reports().batchGet(
    body={
        'reportRequests': [
        {
        'viewId': view_id,
        'dateRanges': [{'startDate': startDate.strftime("%Y-%m-%d"), 'endDate': endDate.strftime("%Y-%m-%d")}],
        'metrics':  [{'expression': exp} for exp in METRICS],
        'dimensions': [{'name': name} for name in dimensions],
        'segments':  [{"segmentId": segment} for segment in SEGMENTS],   # organic traffic
        'orderBys': [{"fieldName":period, "sortOrder": "ASCENDING"}],
        'pageSize': MAX_RESULTS,
        'dimensionFilterClauses': [
            {
                'filters': [
                    {
                        "operator": "EXACT",
                        "dimensionName": "ga:pagePath",
                        "expressions": [ url ]
                    }
                ]
            }
        ]
        }]
    }).execute()

    # get the latest entry for each page path/organic traffic
    entries = []
    pageViews = 0
    organicViews = 0

    for report in data.get('reports', []):
        pageToken = report.get('nextPageToken')
        columnHeader = report.get('columnHeader', {})
        dimensionHeaders = columnHeader.get('dimensions', [])
        metricHeaders = columnHeader.get('metricHeader', {}).get('metricHeaderEntries', [])

        for row in report.get('data', {}).get('rows', []):
            entry = {}
            entry['page_path'] = url
            entry['segment'] = row['dimensions'][0]
            entry['date'] = getDateFromGA(row['dimensions'][1], period)

            entry['pageViews'] = row['metrics'][0]['values'][0]
            entry['uniquePageViews'] = row['metrics'][0]['values'][1]
            entry['timeOnPage'] = round(float(row['metrics'][0]['values'][2]), 5)
            entry['entrances'] = round(float(row['metrics'][0]['values'][3]), 5)
            entry['bounceRate'] = round(float(row['metrics'][0]['values'][4]), 5)
            entry['exitRate'] = round(float(row['metrics'][0]['values'][5]), 5)
            entry['pageValue'] = round(float(row['metrics'][0]['values'][6]), 5)

            if entry['segment'] == "All Users":
                pageViews = entry['pageViews']
            else:
                organicViews = entry['pageViews']

            entries.append(entry)

    # create entry in big table
    insertBigTable(bq, table_id, entries)

    return pageViews, organicViews

# fills views table
def fillViews(projects, user):
    for project in projects.items():
        # create entry for each project if it does not exist
        if not modelview.objects.filter(id = project[0]).filter( user=user):
            modelview.objects.create(id=project[0], user=user, name=project[1]["name"], url=project[1]["url"])


# authentication with big query
def authenticateBigQuery():
    # load json config and write to temporary file
    tfile = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    tfile.write(settings.GOOGLE_JSON)
    tfile.flush()
    credentials = service_account.Credentials.from_service_account_file(
        tfile.name, scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    try:
        client = bigquery.Client(credentials=credentials, project=credentials.project_id,)
    except Exception as e:
        return False
    return client
    
# gets a dump of all the stored stats for that table
def getStoredStats(view_id, report_id):
    google_big = authenticateBigQuery()
    if google_big:
        # Download query results
        table_id = "%s.sodp.%s_%s_%d" % (google_big.project, "stats", view_id, report_id)

        query_string = """
        SELECT page_path, pageViews FROM %s
        WHERE segment='Organic Traffic' AND `date`=(select max(date) FROM %s) ORDER BY pageViews DESC         
        """ % (table_id, table_id)

        dataframe = (
            google_big.query(query_string)
            .result()
            .to_dataframe(
                # Optionally, explicitly request to use the BigQuery Storage API. As of
                # google-cloud-bigquery version 1.26.0 and above, the BigQuery Storage
                # API is used by default.
                create_bqstorage_client=True,
            )
        )
        return dataframe

    return False

# gets a dump of invidisual stats
def getStatsFromURL(view_id, report_id, url):
    google_big = authenticateBigQuery()
    if google_big:
        # Download query results
        table_id = "%s.sodp.%s_%s_%d" % (google_big.project, "stats", view_id, report_id)

        query_string = """
        SELECT `date`, pageViews FROM %s
        WHERE segment='Organic Traffic' AND page_path='%s' ORDER BY `date`         
        """ % (table_id, url)

        dataframe = (
            google_big.query(query_string)
            .result()
            .to_dataframe(
                # Optionally, explicitly request to use the BigQuery Storage API. As of
                # google-cloud-bigquery version 1.26.0 and above, the BigQuery Storage
                # API is used by default.
                create_bqstorage_client=True,
            )
        )
        return dataframe

    return False

