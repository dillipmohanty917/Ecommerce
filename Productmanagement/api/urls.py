from django.urls import path
from .views import *

urlpatterns = [
    path("product-search/", product_search_api, name="product-search"),
    path("callex-product-search/", callex_product_search_api, name="callex-product-search"),
    path("category-search/", category_product_search, name="category-search"),
    path('product-deals/', products_with_deals, name='product-deals'),
    path('dealsfilter/', deals_filter, name='dealsfilter'),
    path('callex-product-deals/', callex_products_with_deals, name='callex-product-deals'),
    path('grab_deal/', grab_deal, name='grab_deal'),
    path('distributor_products/', distributor_products_with_search, name='distributor_products_with_search'),
    path('product-search-bot/', product_search_bot, name='product-search-bot'),
    
    # Add more API endpoints as needed
]
