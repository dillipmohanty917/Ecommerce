
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Fetches and processes Medica products'

    def handle(self, *args, **kwargs):
        from Productmanagement.views import get_medica_products
        get_medica_products()
        self.stdout.write(self.style.SUCCESS('Medica products fetched successfully'))
    
    def handle_monthlysalesreports(self, *args, **kwargs):
        from Usermanagement.api.views import monthly_sales_report
        monthly_sales_report()
        self.stdout.write(self.style.SUCCESS('Monthly Sales Reports Sent successfully'))
    def handle_dailysalesreports(self, *args, **kwargs):
        from Usermanagement.api.views import daily_sales_report
        daily_sales_report()
        self.stdout.write(self.style.SUCCESS('Daily Sales Reports Sent successfully'))
