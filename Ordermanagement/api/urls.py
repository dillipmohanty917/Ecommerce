from django.urls import path
from .views import *

urlpatterns = [
    path('add_to_cart/', add_to_cart, name='add_to_cart'),
    path('get_cart/', get_cart, name='get_cart'),
    path('clear_cart/', clear_cart, name='clear_cart'),
    path('update_cart/', update_quantity_in_cart, name='update_cart'),
    path('place_order/', place_order, name='place_order'),
    path('orders/', get_user_orders, name='user-order-list'),
    path('raise_issue/', raise_issue, name='raise_issue'),
    path('order_status/', order_status_api, name='order_status'),
    path('cancel_order/', cancel_order, name='cancel_order'),
    

]
