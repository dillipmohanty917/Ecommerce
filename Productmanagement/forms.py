from django import forms


class ProductDealsForm(forms.Form):
    search_query = forms.CharField(max_length=100, required=False)
    partner_name = forms.CharField(max_length=100, required=False)