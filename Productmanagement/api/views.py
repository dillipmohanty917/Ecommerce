import logging
from Productmanagement.models import Deal, DistProductMaster
from rest_framework.response import Response
from rest_framework.decorators import api_view
from Usermanagement.models import Distributor, SalesExecutive, Settings, User, ServiceablePincode
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ParseError
from rest_framework.pagination import  InvalidPage
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import APIView
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q

from Usermanagement.api.utils import get_user
from .serializers import DealSerializer, DistProductDealMasterSerializer, DistProductMasterSerializer
from Ordermanagement.models import Cart, CartItem
from .utils import (
    CustomPagination,
    callex_products_search,
    category_products_search,
    fetch_from_second_db,
    products_search,
    scheme_products,
)
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view
from Usermanagement.models import Retailer, KYC, Document, User
from rest_framework.permissions import AllowAny
import logging
from datetime import date


logger = logging.getLogger(__name__)


@api_view(["GET"])
def category_product_search(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
            sfa = get_user(access_token)
        else:
            user = get_user(access_token)
            sfa = None
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 
    try:
        product_category = request.query_params.get("category", None)
        product_category = product_category.strip().lower()
        product_name = request.query_params.get("name", None) 
        user = user.id
        if not product_category:
            logger.warning("Product category parameter is required.")
            return Response({"message": "productname parameter is required"}, status=400)
        if 'schemes'.__eq__(product_category):
            drugs = scheme_products(user,sfa, product_category,product_name)
        else:
            drugs = category_products_search(user, product_category,product_name)
        if not drugs.exists():
            logger.warning("No products found for the given category")
            return Response(
                {"message": "No products found for the given category"}, status=200
            )

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(drugs, request)
        serializer = DistProductMasterSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)
    
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)


@api_view(["GET"])
def products_with_deals(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 
    try:
        retailer = Retailer.objects.get(user_id = user)
        if not retailer.is_activated:
            return Response({"message": "You are not activated. Please try again later."}, status=200)
        
        serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code, distributor__is_activated = True)
        dists = [sp.distributor for sp in serviceable_pincodes]
        name = request.query_params.get("name")
        today = date.today()
        deals = Deal.objects.using('replica').filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)), distributor__in=dists, is_expired=False)
        if name:
            deals = deals.filter(product__name__istartswith=name)
        if not deals.exists():
            logger.warning("No deals found for the given query parameters")
            return Response(
                {"message": "No products found"}, status=200
            )
        paginator = CustomPagination()
        paginated_deals = paginator.paginate_queryset(deals, request)
        serializer = DealSerializer(paginated_deals, many=True, context={'user': retailer})
        return paginator.get_paginated_response(serializer.data)
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)
    
@api_view(['GET'])
def deals_filter(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except Exception:
        logger.error("Invalid access token")
        return Response({"message": "Access Token Missing Or Mismatch"}, status=406)

    try:
        retailer = Retailer.objects.get(user_id=user)
        if not retailer.is_activated:
            return Response({"message": "You are not activated. Please try again later."}, status=402)

        serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code, distributor__is_activated=True)
        dists = [sp.distributor for sp in serviceable_pincodes]

        name = request.query_params.get("name")
        category = request.query_params.get('category')
        distributor = request.query_params.get('distributor')
        discount_slab = request.query_params.get('discount_slab')
        sort_by = request.query_params.get('sort_by', 'Discount')
        today = date.today()
        deals = Deal.objects.using('replica').filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)),distributor__in=dists, is_expired=False)
        query_conditions = Q()

        if name:
            query_conditions &= Q(product__name__istartswith=name)
        if category:
            query_conditions &= Q(product__product_category__icontains=category)
        if distributor:
            query_conditions &= Q(distributor_id=distributor)
        if discount_slab:
            if discount_slab == '05-20%':
                query_conditions &= Q(discount_percentage__gte=5, discount_percentage__lt=20)
            elif discount_slab == '20-40%':
                query_conditions &= Q(discount_percentage__gte=20, discount_percentage__lt=40)
            elif discount_slab == '40-60%':
                query_conditions &= Q(discount_percentage__gte=40, discount_percentage__lt=60)
            elif discount_slab == '60% Above':
                query_conditions &= Q(discount_percentage__gte=60)

        if query_conditions:
            deals = deals.filter(query_conditions)
        if not deals.exists():
            logger.warning("No deals found for the given query parameters")
            return Response({"message": "No products found"}, status=200)

        if sort_by == 'Discount':
            deals = deals.order_by('-discount_percentage')
        elif sort_by == 'Ascending':
            deals = deals.order_by('product__name')
        elif sort_by == 'Descending':
            deals = deals.order_by('-product__name')

        paginator = CustomPagination()
        paginated_deals = paginator.paginate_queryset(deals, request)
        serializer = DealSerializer(paginated_deals, many=True, context={'user': retailer})
        return paginator.get_paginated_response(serializer.data)

    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)

@api_view(["GET"])
def callex_products_with_deals(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        retailer_id = request.headers.get("retailer-id")
        retailer = Retailer.objects.get(id=retailer_id)
    except:
        logger.error("Retailer id not found in headers")
        return Response({"message":"Retailer id not found"}, status=406) 
    try:
        sales_executive = SalesExecutive.objects.filter(retailer=retailer).first()
        if not sales_executive:
            logger.warning("Sales executive not found for the retailer")
            return Response({"message": "Sales executive not found for the retailer"}, status=404)

        distributor = sales_executive.distributor
        name = request.query_params.get("name")
        if distributor:
            today = date.today()
            deals = Deal.objects.using('replica').filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)),distributor=distributor, is_expired=False)
            if name:
                deals = deals.filter(product__name__istartswith=name)
        else:
            deals = Deal.objects.using('replica').all()
            if name:
                deals = deals.filter(product__name__istartswith=name)
        if not deals.exists():
            logger.warning("No deals found for the given query parameters")
            return Response(
                {"message": "No products found"}, status=200
            )
        paginator = CustomPagination()
        paginated_deals = paginator.paginate_queryset(deals, request)
        serializer = DealSerializer(paginated_deals, many=True, context={'user': retailer})
        return paginator.get_paginated_response(serializer.data)
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)
    except ParseError:
        logger.error("Invalid query parameters")
        return Response({"message": "Invalid query parameters"}, status=400)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)
   

@api_view(["GET"])
def product_search_api(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 


    try:
        product_name = request.query_params.get("name", None)

        drugs = products_search(user, product_name)
        if not drugs.exists():
            logger.warning("No products found for the given pincode and query.")
            return Response(
                {"message": "No products found for the given pincode"}, status=200
            )

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(drugs, request)
        serializer = DistProductDealMasterSerializer(result_page, user=user,  many=True)
 
        return paginator.get_paginated_response(serializer.data)

    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)
    
@api_view(["GET"])
def callex_product_search_api(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        retailer_id = request.headers.get("retailer-id")
        retailer = Retailer.objects.get(id=retailer_id)
    except:
        logger.error("Retailer id not found in headers")
        return Response({"message":"Retailer id not found"}, status=406)

    try:
        sales_executive = SalesExecutive.objects.filter(retailer=retailer).first()
        if not sales_executive:
            logger.warning("Sales executive not found for the retailer")
            return Response({"message": "Sales executive not found for the retailer"}, status=404)

        distributor = sales_executive.distributor
        
        product_name = request.query_params.get("name", None)
        if distributor:
            products = DistProductMaster.objects.using('replica').filter(distributor=distributor,distributorstock__quantity__gt = 0)
            if product_name:
                products = products.filter(name__icontains=product_name)
        else:
            products = callex_products_search(retailer_id)
            if product_name:
                products = products.filter(name__icontains=product_name)
        

        # serializer = DistProductDealMasterSerializer(products, many=True, context={'user': retailer.user})
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(products, request)
        serializer = DistProductDealMasterSerializer(result_page, user=retailer.user,  many=True)
 
        return paginator.get_paginated_response(serializer.data)
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)

@api_view(["POST"])
def grab_deal(request):
    if request.method == "POST":
        try:
            try:
                access_token = request.META.get("HTTP_ACCESSTOKEN")
                user = get_user(access_token)
            except:
                logger.error("Access Token Missing")
                return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
            retailer_id = request.headers.get("retailer-id")
            if retailer_id:
                ret = Retailer.objects.get(id = retailer_id)
                user = ret.user
            else:
                user = get_user(access_token)
            cart, _ = Cart.objects.get_or_create(user=user)
            product_id = request.data.get("product_id")
            action = request.data.get("action")
            quantity = request.data.get("quantity")
            try:
                today = date.today()
                deal = Deal.objects.filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)),product_id=product_id).first()
                if quantity is not None and action is not None:
                    cart_item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
                    cart_item.quantity = quantity * deal.quantity
                    cart_item.save()
                elif action == "grab":
                    if quantity:
                        quantity *= deal.quantity
                    else:
                        quantity = deal.quantity

                    cart_item, created = CartItem.objects.get_or_create(cart=cart, product_id=product_id)
                    if created:
                        cart_item.quantity = quantity
                    else:
                        cart_item.quantity += quantity
                    cart_item.save()
                elif action == "release":
                    if quantity:
                        quantity *= deal.quantity
                    else:
                        quantity = deal.quantity

                    cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
                    cart_item.quantity -= quantity
                    cart_item.save()
                    if cart_item.quantity <= 0:
                        cart_item.delete()
                
                
                else:
                    return JsonResponse({"message": "Invalid action"}, status=400)
                
                cart_count = cart.cartitem_set.count() if cart else 0
                return JsonResponse({"message": f"Deal {action}ed successfully", "cart_count":cart_count}, status=200)
            except Deal.DoesNotExist:
                return JsonResponse({"message": "No deal available for the product"}, status=404)
            except CartItem.DoesNotExist:
                return JsonResponse({"message": "Cart item not found"}, status=404)
            except Exception as e:
                return JsonResponse({"message": str(e)}, status=500)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=401)
    else:
        return JsonResponse({"message": "Method not allowed"}, status=405)
    
    
@api_view(["GET"])
def distributor_products_with_search(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message": "Access Token Missing Or Mismatch"}, status=406)

    try:
        dist_id = request.query_params.get("dist_id")
        name = request.query_params.get("name")
        try:
            distributor = Distributor.objects.get(id=dist_id)
        except:
            return Response(
                {"message": "Distributor Not Found"}, status=200
            )

        products = DistProductMaster.objects.using('replica').filter(distributor=distributor,distributorstock__quantity__gt=0)
        if name:
            products = products.filter(name__istartswith=name)

        if not name:
            paginator = CustomPagination()
            result_page = paginator.paginate_queryset(products, request)
            serializer = DistProductDealMasterSerializer(result_page, many=True, context={'user': user})
            return paginator.get_paginated_response(serializer.data)
        
        if not products.exists():
            logger.warning("No deals found for the given query parameters")
            return Response(
                {"message": "No products found"}, status=200
            )
        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(products, request)
        serializer = DistProductDealMasterSerializer(result_page, many=True, context={'user': user})
        return paginator.get_paginated_response(serializer.data)
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)
    except ParseError:
        logger.error("Invalid query parameters")
        return Response({"message": "Invalid query parameters"}, status=400)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=500)
    
@api_view(['POST'])
def product_search_bot(request):
    # try:
    #     user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    # except:
    #     logger.error("Invalid access token")
    #     return Response({"message": "Access Token Missing Or Mismatch"}, status=406)
    try:
        limit = request.data.get('limit', 10)
        page = int(request.data.get('page', 1))
        per_page = (page - 1) * limit
        searchname = request.data.get('searchname', '')
        form = request.data.get('form', '')
        if not form:
            query = """
                SELECT name, strength, packing, max_retail_price, composition, medicine_type, manufacturer, form
                FROM product_product
                WHERE name ILIKE %s OR composition ILIKE %s
                ORDER BY max_retail_price
                LIMIT %s OFFSET %s
            """
            params = [f'{searchname}%', f'{searchname}%', limit, per_page]
        else:
            query = """
                SELECT name, strength, packing, max_retail_price, composition, medicine_type, manufacturer, form
                FROM product_product
                WHERE (name ILIKE %s OR composition ILIKE %s) AND form = %s
                ORDER BY max_retail_price
                LIMIT %s OFFSET %s
            """
            params = [f'{searchname}%', f'{searchname}%', form, limit, per_page]

        data = fetch_from_second_db(query, params)

        if len(data) == 1:
            key_searchname = data[0]['composition'].strip()
            if form:
                query2 = """
                    SELECT name, strength, packing, max_retail_price, composition, medicine_type, manufacturer, form
                    FROM product_product
                    WHERE composition ILIKE %s AND form = %s
                    ORDER BY max_retail_price
                    LIMIT %s OFFSET %s
                """
                params2 = [f'{key_searchname}%', form, limit, per_page]
            else:
                query2 = """
                    SELECT name, strength, packing, max_retail_price, composition, medicine_type, manufacturer, form
                    FROM product_product
                    WHERE composition ILIKE %s
                    ORDER BY max_retail_price
                    LIMIT %s OFFSET %s
                """
                params2 = [f'{key_searchname}%', limit, per_page]

            data2 = fetch_from_second_db(query2, params2)
            new_array = [item for item in data2 if item['name'].lower() != searchname.lower()]
            return JsonResponse({'data': new_array}, status=status.HTTP_200_OK)

        return JsonResponse({'data': data}, status=status.HTTP_200_OK)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)