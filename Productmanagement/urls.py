from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/products/',product_list,name='dashboard-products'),
    path('dashboard/product/create/',product_creation,name='product-creation'),
    path('dashboard/product/<int:prod_id>/',product_edit,name='product-edit'),
    path('dashboard/distributor/add-stock/<int:pk>/',distributor_add_stock,name='dist-add-stock'),
    path('dashboard/distributor/sku/',distributorSKUBatch_existance,name='distributor-sku'),
    path('dashboard/distributor/upload-stock/', distrubutor_uploadstock, name='distrubutor-upload-stock'),
    path('dashboard/product/deals/<int:dist_id>/', distributor_deals, name='distrubutor-deals'),
    path('dashboard/product/deals/', deals_list, name='deals-list'),
    path('dashboard/<str:form_type>/configuration/partners/', upload_configuration_partners, name='upload-configuration-partners'),
    path('dashboard/<str:form_type>/configuration/<int:dist_id>/', dashboard_upload_configurations, name='dashboard-upload-configuration'),


# distrubutor_urls
path('distributor/<str:form_type>/configuration/', distributor_upload_configurations, name='distributor-upload-configuration'),
path('distributor/products/',distributor_product_list,name='distributor-products'),
path('distributor/product/create/',distributor_product_creation,name='dist-product-creation'),
path('distributor/products/<int:prod_id>',distributor_product_edit,name='distributor-product-edit'),
# path('distributor/get_medica_products',get_medica_products,name='get_medica_products'),

]