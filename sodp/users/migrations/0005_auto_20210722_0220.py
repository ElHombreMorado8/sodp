# Generated by Django 3.1.12 on 2021-07-22 02:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_auto_20210722_0218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='google_api_token',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='google_api_token'),
        ),
        migrations.AlterField(
            model_name='user',
            name='google_refresh_token',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='google_refresh_token'),
        ),
    ]