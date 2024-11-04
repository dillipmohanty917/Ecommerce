from Ordermanagement.models import Order
from Usermanagement.models import Distributor, Retailer
from Productmanagement.models import DistProductMaster, DistributorStock

import django_filters

from django import forms




class ProductFilter(django_filters.FilterSet):
	product__name = django_filters.CharFilter(lookup_expr='icontains')
	product__distributor_sku = django_filters.CharFilter(lookup_expr='icontains')
	class Meta:
		model = DistributorStock
		fields = ['product__name', 'product__distributor_sku']
  
class OrderFilter(django_filters.FilterSet):
	class Meta:
		model = Order
		fields = ['id']

class CustomerFilter(django_filters.FilterSet):
	organisation = django_filters.CharFilter(lookup_expr='icontains')
	class Meta:
		model = Distributor
		fields = ['organisation']
  
class RetailerFilter(django_filters.FilterSet):
	organisation = django_filters.CharFilter(lookup_expr='icontains')
	class Meta:
		model = Retailer
		fields = ['organisation']



