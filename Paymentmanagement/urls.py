from django.urls import path
from .views import *

urlpatterns = [
    
    # distributor urls start from here
    path('distributor/<str:order_id>/bill/upload/',upload_bill_details, name='upload-bill-details'),
    path('distributor/<str:order_id>/update/invoice/',update_invoice_details, name='dist-update-invoice-details')



]