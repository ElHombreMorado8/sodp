from django.shortcuts import render
from django.views import generic
from sodp.reports.models import report
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from reports.forms import ReportCreateForm




class ReportListView(generic.ListView):
    model = report
    context_object_name = 'reportsList'
    template_name = 'reports/reportslist.html'

    
report_list_view = ReportListView.as_view()

    #model = report
    #template_name = 'reportscreate.html'
    #fields = ['name','project','dateFrom','dateTo']


    #model = report
    #form_class = ReportCreateForm
    #success_url = '/home/'
    #template_name = 'reports/reportscreate.html'
    #fields = ('name','project','dateFrom','dateTo')

    #def get(self, request, *args, **kwargs):
    #    context = {'form': ReportCreateForm()}
    #    return render(request, 'reports/reportscreate.html', context)

  


    #def post(self, request, *args, **kwargs):
        #form = ReportCreateForm(request.POST)
    #    if form.is_valid():
        #    report = form.save()
        #    report.save()
    #        self.object = form.save(commit=False)
            #self.object.user_id = self.request.user.id
    #        self.object.save()
    #        return super(ReportCreateView, self).form_valid(form)

            #return HttpResponseRedirect(reverse_lazy('report:detail', args=[report.id]))
        #return render(request, 'reports/reportscreate.html', {'form': form})




class ReportCreateView(CreateView):
    template_name = 'reports/reportscreate.html'
    form_class = ReportCreateForm

    def get_initial(self):
        super(ReportCreateView, self).get_initial()
        date_format = '%d/%m/%Y'
  
        auxDateTo = date.today() - timedelta(1)

        n = 1
        auxDateFrom = auxDateTo - relativedelta(months=n)

        self.initial = {"dateFrom":auxDateFrom.strftime(date_format), "dateTo":auxDateTo.strftime(date_format)}
        return self.initial



    def post(self, request, *args, **kwargs):
        form = ReportCreateForm(request.POST)
        if form.is_valid():
            report = form.save()
            report.save()
            return HttpResponseRedirect(reverse_lazy('report:detail', args=[book.id]))
        return render(request, 'reports/reportscreate.html', {'form': form})

    #def post(self, request, *args, **kwargs):
        #form = ReportCreateForm(request.POST)
    #    if form.is_valid():
        #    report = form.save()
        #    report.save()
    #        self.object = form.save(commit=False)
            #self.object.user_id = self.request.user.id
    #        self.object.save()
    #        return super(ReportCreateView, self).form_valid(form)

            #return HttpResponseRedirect(reverse_lazy('report:detail', args=[report.id]))
        #return render(request, 'reports/reportscreate.html', {'form': form})