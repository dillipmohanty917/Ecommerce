from django.urls import path
from django.conf.urls.static import static

from b2b2 import settings
from .views import *

urlpatterns = [
    path('send_notification/',send_notification,name='send_notification'),
    path('marketing/send_notification/',marketing_send_notification,name='marketing_send_notification'),
]
