from django import forms

from Ordermanagement.models import Order
from captcha.fields import CaptchaField


class DistributorOrderFilter(forms.ModelForm):

    start_datetime = forms.CharField(widget=forms.widgets.TextInput(attrs={'type': 'text', 'class': 'c-btn c-datepicker-btn'}))
    end_datetime = forms.CharField(widget=forms.widgets.TextInput(attrs={'type': 'text', 'class': 'c-btn c-datepicker-btn'}))


    class Meta:
        model = Order
        fields=[]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super(DistributorOrderFilter, self).__init__(*args, **kwargs)
        self.fields['start_datetime'].label = "Start Date"
        self.fields['end_datetime'].label = "End Date"
        try:
            self.fields['start_datetime'].initial = self.request.GET.get('start_datetime')
        except:
            pass
        try:
            self.fields['end_datetime'].initial = self.request.GET.get('end_datetime')
        except:
            pass

class DashboardForm(forms.Form):
    search_query = forms.CharField(max_length=100, required=False)
    daterange = forms.CharField(required=False)
    
    

class CaptchaTestForm(forms.Form):
    captcha = CaptchaField()