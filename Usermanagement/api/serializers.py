from django.utils import timezone 
from rest_framework import serializers
from Usermanagement.models import OTP, Distributor, Feedback, Retailer, SalesExecutive
from Productmanagement.models import DistProductMaster, Deal
from Ordermanagement.models import Cart, CartItem, Order, OrderedItem
from Usermanagement.utils import generate_presigned_url
from b2b2.settings import S3_LINK
from datetime import datetime, timedelta
from django.db.models import Sum




class SendOTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ['phone', 'created_at', 'expires_at', 'is_otp_verified']
        read_only_fields = ['created_at', 'expires_at', 'is_otp_verified']

    def create(self, validated_data):
        validated_data['created_at'] = timezone.now()
        otp_code = OTP.generate_otp(validated_data.get('phone'))
        print (otp_code,"otp_codeotp_code")
        validated_data['otp_code'] = otp_code
        return super().create(validated_data)

class DistProductMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistProductMaster
        fields = '__all__'
        
class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15, required=True)
    otp = serializers.CharField(max_length=6, required=True)


class OTPSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp = serializers.CharField()
    
class VerifyAccessTokenSerializer(serializers.Serializer):
    phone = serializers.CharField()
    access_token = serializers.CharField()
    is_retailer = serializers.BooleanField()
    message = serializers.CharField()
    role = serializers.CharField()

class VerifyAccessTokenSerializercallex(serializers.Serializer):
    phone = serializers.CharField()
    access_token = serializers.CharField()
    message = serializers.CharField()
    is_sales = serializers.BooleanField()
    role = serializers.CharField()


class DistributorSerializer(serializers.ModelSerializer):
    distributor_logo = serializers.SerializerMethodField()
    class Meta:
        model = Distributor
        # fields = '__all__'
        exclude = ['logo']
    def get_distributor_logo(self, obj):
        if obj.logo:
            cdn_link = generate_presigned_url(str(obj.logo))
            return cdn_link
        return None

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = '__all__'
               
class MyProfileSerializer(serializers.Serializer):
    total_number_of_orders = serializers.IntegerField()
    total_number_of_invoices = serializers.IntegerField()
    total_number_of_order_delivered = serializers.IntegerField()
    total_purchase_amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_paid_amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    total_out_standing_amount = serializers.DecimalField(max_digits=20, decimal_places=2)


class SalesExecutiveSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    distributor_id = serializers.CharField(source='distributor.id', read_only=True)
    user_name = serializers.CharField(source='user.first_name', read_only=True)
    retailer_count = serializers.SerializerMethodField()
    order_value = serializers.SerializerMethodField()
    order_count = serializers.SerializerMethodField()
    retailer_details = serializers.SerializerMethodField()
    

    class Meta:
        model = SalesExecutive
        # fields = '__all__'
        exclude = ['retailer']

    def get_retailer_details(self, instance):
        retailers = instance.retailer.all()
        retailer_details = []
        for retailer in retailers:
            cart = Cart.objects.filter(user=retailer.user).first()  # Get the first Cart instance for the retailer
            if cart:
                cart_item_count = CartItem.objects.filter(cart=cart).count()
            else:
                cart_item_count = 0
            retailer_data = {
                'id': retailer.id,
                'name': retailer.store_name,
                'mid': retailer.medleyId,
                'address': retailer.address,
                'cart_count': cart_item_count
            }
            retailer_details.append(retailer_data)
        sorted_retailer_details = sorted(retailer_details, key=lambda x: x['name'])
        return sorted_retailer_details[:10]
    
    def get_retailer_count(self, instance):
        return instance.retailer.count()
    
    def get_order_value(self, instance):
        retailers = instance.retailer.all()
        total_order_value = 0
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        end_of_month = start_of_month.replace(month=start_of_month.month + 1, day=1) - timedelta(days=1)
        for retailer in retailers:
            orders = Order.objects.filter(user=retailer.user, created_at__range=(start_of_month, end_of_month))
            order_value = orders.aggregate(total_amount=Sum('total_amount'))['total_amount'] or 0
            total_order_value += order_value
        return float(total_order_value)

    def get_order_count(self, instance):
        retailers = instance.retailer.all()
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        end_of_month = start_of_month.replace(month=start_of_month.month + 1, day=1) - timedelta(days=1)
        total_order_count = Order.objects.filter(user__in=[retailer.user for retailer in retailers], created_at__range=(start_of_month, end_of_month)).count()
        return total_order_count

class RetailerSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='store_name')
    mid = serializers.CharField(source='medleyId')
    cart_count = serializers.SerializerMethodField()

    class Meta:
        model = Retailer
        fields = ['id', 'name', 'mid', 'address', 'cart_count']

    def get_cart_count(self, retailer_instance):
        cart = Cart.objects.filter(user=retailer_instance.user).first()
        if cart:
            return cart.cartitem_set.count()
        else:
            return 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data