from django.urls import path
from .views import *

urlpatterns = [
    path('dashboard/orders/',order_details,name='dashboard-orders'),
    path('dashboard/order/<str:order_id>/',dashboard_order_details,name='dashboard-order-details'),
    
    path('distributor/',order_details,name='order-details'),
    path('distributor/orders/list/',order_list,name='dist-order-list'),
    path('distributor/orders/<str:order_id>/',dist_order_details,name='dist-order-details'),
    path('distributor/',order_details,name='order-details'),
    path('distributor/upload_deals',upload_deals,name='distributor-upload-deals'),
    path('distributor/raised_issues',raised_issues,name='distributor-raised-issue'),
    path('distributor/order-details/download/<str:order_id>/',download_order_details,name='download-order-details')
    # Add more API endpoints as needed
]