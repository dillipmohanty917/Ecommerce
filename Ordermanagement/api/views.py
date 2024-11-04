from Activitylog.models import ActivityLog
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from Ordermanagement.models import Cart, CartItem, Order
from Productmanagement.models import DistProductMaster
from Usermanagement.models import Distributor, Retailer, User
from Usermanagement.api.utils import get_user
from Productmanagement.api.utils import CustomPagination
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer, OrderedItemSerializer, RaiseIssueSerializer
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import logging
logger = logging.getLogger(__name__)

@api_view(['POST'])
def add_to_cart(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        user = get_user(access_token)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 
    try:
        user = User.objects.get(id=user.id)
        products_data = request.data.get('products', [])
        cart, created = Cart.objects.get_or_create(user=user)
        cart_items = []

        for product_data in products_data:
            try:
                product_id = product_data.get('product_id')
                quantity = product_data.get('quantity')
                existing_cart_item = CartItem.objects.filter(cart=cart, product__id=product_id).first()
                if quantity==0 and existing_cart_item:
                    existing_cart_item.delete()  
                    continue
                total_amount = product_data.get('total_amount')
                logger.info(f"Total amount for product {product_id}: {total_amount}")

                if existing_cart_item:
                    existing_cart_item.quantity = quantity
                    existing_cart_item.save()
                    cart_item = existing_cart_item
                else:
                    serializer = CartItemSerializer(data={'cart': cart.id, 'product': product_id, 'quantity': quantity})
                    if serializer.is_valid():
                        serializer.save()
                        cart_item = serializer.instance
                    else:
                        logger.error(f"Error creating cart item: {serializer.errors}")
                        return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

                cart_items.append(CartItemSerializer(cart_item).data)

            except DistProductMaster.DoesNotExist:
                logger.warning(f"Product with ID {product_id} does not exist.")
                return Response({'error': f'Product with ID {product_id} does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        cart.total_amount = cart.get_total_amount
        cart.save()
        cart_serializer = CartSerializer(cart, data=request.data)
        if cart_serializer.is_valid():
            cart_serializer.save()
            cart_data = cart_serializer.data
            cart_data['cart_items'] = cart_items
            cart_data['cart_count'] = cart.cartitem_set.count() if cart else 0
            return Response(cart_data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Error creating cart: {cart_serializer.errors}")
            return Response({'error': cart_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    except User.DoesNotExist:
        logger.error(f"User with ID {user} does not exist.")
        return Response({'error': f'User with ID {user} does not exist.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])       
def get_cart(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        try:
            user = get_user(access_token)
        except:
            logger.error("Access Token Missing")
            return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
        cart = Cart.objects.filter(user=user).first()

        if cart:
            # cart_items = CartItem.objects.filter(cart=cart)
            cart_serializer = CartSerializer(cart)
            # cart_items_serializer = CartItemSerializer(cart_items, many=True)
            
            response_data = {
                "cart": cart_serializer.data,
                'cart_count': cart.cartitem_set.count() if cart else 0
                # "cart_items": cart_items_serializer.data
            }
            return Response(response_data, status=200)
        else:
            return Response({}, status=200)
    except Exception as e:
        return Response({"message": str(e)}, status=500)


@api_view(['POST'])
def clear_cart(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        user = get_user(access_token)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        distributor_id = request.data.get('distributor_id')
        product_id = request.data.get('product_id')

        # if distributor_id is None:
        #     return Response({'message': 'distributor_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        cart = Cart.objects.get(user_id = user.id)
        if product_id:
            cart_item = CartItem.objects.filter(product_id=product_id, cart=cart.id)
            if cart_item:
                cart_item.delete()
                return Response({'message': 'Cart item deleted successfully.'}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Cart item not found.'}, status=status.HTTP_404_NOT_FOUND)

        else:
            CartItem.objects.filter(cart=cart.id,product__distributor = distributor_id).delete()
            return Response({'message': 'Cart cleared successfully.'}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
def update_quantity_in_cart(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        user =  user = get_user(access_token)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        cart = Cart.objects.filter(user=user).first()
        products_data_list = request.data.get('products', [])
        if cart and products_data_list:
            for product in products_data_list:
                existing_cart_item = CartItem.objects.filter(cart=cart, product__id=product.get('product_id')).first()
                if existing_cart_item:
                    existing_cart_item.quantity = product.get('quantity')
                    existing_cart_item.save()
            cart.total_amount = cart.get_total_amount
            cart.save()
            cart_serializer = CartSerializer(cart)
            response_data = {
                "cart": cart_serializer.data,
                'cart_count': cart.cartitem_set.count() if cart else 0
            }
            logger.info(f"Cart Updated Successfully For User ID : {user.id}")
            return Response(response_data, status=200)
        else:
            return Response({"message": "Cart not found for this user"}, status=404)
    except Exception as e:
        logger.exception("An error occurred in update quantity in cart function, exeption is : %s", str(e))
        return Response({"message": str(e)}, status=500)


@api_view(['POST'])
@transaction.atomic
def place_order(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        user = get_user(access_token)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    
    distributor_id = request.data.get('distributor_id', None)
    products = request.data.get('products', [])

    if distributor_id is None:
        logger.error("Distributor ID is missing in the payload.")
        return Response({'error': 'Distributor ID is required in the payload.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = user
        cart = Cart.objects.get(user=user)
        cart_items_for_distributor = cart.cartitem_set.filter(product__distributor_id=distributor_id)

        if not cart_items_for_distributor.exists():
            logger.warning(f'No products found for distributor ID {distributor_id} in the cart.')
            return Response({'error': f'No products found for distributor ID {distributor_id} in the cart.'}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate total amount for the selected distributor
        total_amount_for_distributor = sum(cart_item.product.ptr * cart_item.quantity for cart_item in cart_items_for_distributor)
        # Create an order for the selected distributor
        order_data = {
            'user': user.id,
            'total_amount': total_amount_for_distributor,
            'distributor':distributor_id
            # Add any other required fields for order model
        }
        order_serializer = OrderSerializer(data=order_data)
        if order_serializer.is_valid():
            order = order_serializer.save()
            # Create OrderedItem instances for the selected distributor and associate them with the order
            ordered_items_data = []
            for cart_item in cart_items_for_distributor:
                ordered_item_data = {
                    'order': order.id,
                    'product': cart_item.product.id,
                    'quantity': cart_item.quantity,
                    'unit_price': cart_item.product.ptr,
                    'distributor_id': cart_item.product.distributor.id,
                    
                }
                ordered_items_data.append(ordered_item_data)
            ordered_items_serializer = OrderedItemSerializer(data=ordered_items_data, many=True)
            if ordered_items_serializer.is_valid():
                ordered_items_serializer.save()

                # Remove cart items for the selected distributor from the cart
                cart_items_for_distributor.delete()

                response_data = {
                    'order': order_serializer.data,
                    'ordered_items': ordered_items_serializer.data,
                }
                ActivityLog.log_activity(user=user, action="New Order", details=f"Order placed successfully by retailer:-'{user.username}'.", to_user=user)
                return Response({'message': 'Order placed successfully'}, status=status.HTTP_201_CREATED)
            else:
                order.delete()  # Rollback the order creation if there's an issue with ordered items
                logger.error(f"Ordered items serializer errors: {ordered_items_serializer.errors}")
                return Response({'error': ordered_items_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        else:
            logger.error(f"Order serializer errors: {order_serializer.errors}")
            return Response({'error': order_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    except User.DoesNotExist:
        logger.error(f'User with ID does not exist.')
        return Response({'error': f'User with ID {user} does not exist.'}, status=status.HTTP_404_NOT_FOUND)
    except Cart.DoesNotExist:
        logger.error(f'Cart not found for user the current user ID.')
        return Response({'error': f'Cart not found for user with ID {user}.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_user_orders(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        user = get_user(access_token)
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
        
    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        cart = None
    try:
        orders = Order.objects.filter(user=user.id).order_by('-id')
        paginator = CustomPagination()
        paginated_orders = paginator.paginate_queryset(orders, request)
        orders_data = []

        for order in paginated_orders:
            order_serializer = OrderSerializer(order)
            ordered_items_serializer = OrderedItemSerializer(order.ordereditem_set.all(), many=True)

            order_data = order_serializer.data
            order_data['ordered_items'] = ordered_items_serializer.data

            orders_data.append(order_data)
            
        response_data = {
        "orders": orders_data,
        "cart_count": cart.cartitem_set.count() if cart else 0
        }
        return paginator.get_paginated_response(response_data)
    except (NotFound, ValidationError):
        return Response({"message": "You reached the maximum page"}, status=403)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
def raise_issue(request):
    try:
        user = get_user(request.META["HTTP_ACCESSTOKEN"])
    except KeyError:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    
    serializer = RaiseIssueSerializer(data=request.data)
    if serializer.is_valid():
        order_id = serializer.validated_data['orderId']
        issue_type = serializer.validated_data['issueType']
        description = serializer.validated_data['description']

        try:
            order = Order.objects.get(id=order_id, user=user.id)
            order.issue_type = issue_type
            order.description = description
            order.issue_status = "Open"
            order.save()
            
            logger.info(f"Issue raised successfully for order ID: {order_id}")
            return Response({'message': 'Issue raised successfully'}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            logger.warning(f"Order not found for ID: {order_id}")
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
    else:
        logger.error(f"Invalid data received for raising issue: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(["POST"])
def order_status_api(request):
    # try:
    #     user = get_user(request.META["HTTP_ACCESSTOKEN"])
    # except KeyError:
    #     logger.error("Access Token Missing")
    #     return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        order_id = request.data.get("order_id")
        print("Received order ID:", order_id)
        order = Order.objects.get(id=order_id)
        order_status = order.order_status
        return Response({"order_id": order_id, "status": order_status}, status=200)
    except Order.DoesNotExist:
        return Response({"message": "Order not found"}, status=404)
    except Exception as e:
        return Response({"message": str(e)}, status=500)

@api_view(['POST'])
def cancel_order(request):
    try:
        user = get_user(request.META["HTTP_ACCESSTOKEN"])
    except KeyError:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        order_id = request.data.get("order_id")
        if not order_id:
            return Response({"message": "Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"message": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        
        order.order_status = 'Cancelled'
        order.save()
        
        logger.info(f"Order {order_id} has been cancelled.")
        return Response({"message": "Order has been cancelled"}, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception(f"An error occurred while cancelling the order: {str(e)}")
        return Response({"message": "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)