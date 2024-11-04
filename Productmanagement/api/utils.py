from decimal import Decimal
from django.db import connections
from Usermanagement.models import SalesExecutive, ServiceablePincode, Retailer
from Productmanagement.models import DistProductMaster
from rest_framework.pagination import PageNumberPagination


def products_search(user, q):
        retailer = Retailer.objects.get(user_id = user)
        serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code)
        dists = [sp.distributor for sp in serviceable_pincodes]
        products = []

        products = DistProductMaster.objects.using('replica').filter( 
            name__istartswith=q,
            distributor__in=dists,  
            distributor__is_activated = True,
            distributorstock__quantity__gt=0
                        
        )
        return products
    
def category_products_search(user, category=None,name=None):
    retailer = Retailer.objects.get(user_id=user)

    serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code)
    dists = [sp.distributor for sp in serviceable_pincodes]

    products = DistProductMaster.objects.using('replica').filter(
        distributor__in=dists,
        distributor__is_activated = True,
        distributorstock__quantity__gt=0
    ).order_by('name')

    if category:
        products = products.filter(product_category__icontains=category).order_by('distributor_sku').distinct('distributor_sku')
    if name:
        products = products.filter(name__istartswith=name)

    return products

def scheme_products(user,sfa,category=None,name=None):
    retailer = Retailer.objects.get(user_id=user)
    serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code)
    dists = [sp.distributor for sp in serviceable_pincodes]
    if sfa:
        sales_executive = SalesExecutive.objects.filter(retailer=retailer).first()
        distributor = sales_executive.distributor
        if distributor:
            products = DistProductMaster.objects.using('replica').filter(
            distributor=distributor,
            distributor__is_activated = True,
            scheme_billed__gt = 0
            ).order_by('name')
            if name:
                products = products.filter(name__istartswith=name)
        else:
            products = DistProductMaster.objects.using('replica').filter(
            distributor__in=dists,
            distributor__is_activated = True,
            scheme_billed__gt = 0
        ).order_by('name')
        if name:
            products = products.filter(name__istartswith=name)
        return products

    products = DistProductMaster.objects.using('replica').filter(
        distributor__in=dists,
        distributor__is_activated = True,
        scheme_billed__gt = 0
    ).order_by('name')
    if name:
        products = products.filter(name__istartswith=name)
    return products

class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def callex_products_search(user):
        retailer = Retailer.objects.get(id = user)
        serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code)
        dists = [sp.distributor for sp in serviceable_pincodes]
        products = []

        products = DistProductMaster.objects.using('replica').filter( 
            distributor__in=dists,  
            distributor__is_activated = True,
            distributorstock__quantity__gt=0
            
        )
        return products
    
def fetch_from_second_db(query, params=None):
    with connections['product'].cursor() as cursor:
        cursor.execute(query, params)
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for result in results:
            for key, value in result.items():
                if isinstance(value, Decimal):
                    result[key] = str(value)
    return results