from django.apps import AppConfig


class ProductmanagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Productmanagement'


from b2b2.apscheduler import start_scheduler
start_scheduler()