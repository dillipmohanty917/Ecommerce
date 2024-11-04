# serializers.py
from collections import OrderedDict
from rest_framework import serializers
from Ordermanagement.models import Cart, CartItem, DistProductMaster, Order,OrderedItem
from Paymentmanagement.models import Invoice
from Usermanagement.utils import generate_presigned_url
from b2b2.settings import S3_LINK

class DistProductMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = DistProductMaster
        fields = '__all__'

class CartItemSerializer(serializers.ModelSerializer):
    product_details = DistProductMasterSerializer(source='product', read_only=True)
    class Meta:
        model = CartItem
        fields = ['cart', 'product', 'quantity', 'added_by', 'created_at', 'distributor_name','product_details']
        
        
class CartSerializer(serializers.ModelSerializer):
    cart_items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = '__all__'
        read_only_fields = ['user']
        
    def to_representation(self, instance):
        grouped_cart_items = {}
        cart_items = instance.cartitem_set.all().order_by('id')
        for cart_item in cart_items:
            distributor_name = cart_item.distributor_name
            cart_value = cart_item.distributor_cart_value
            total_cost = cart_item.quantity * cart_item.product.ptr
            if distributor_name not in grouped_cart_items:
                grouped_cart_items[distributor_name] = {
                    'total_amount': 0,
                    'distributor_name': distributor_name,
                    'cart_value': cart_value,
                    'placeorder': True if total_cost > cart_value else False,
                    'items': []
                }
            grouped_cart_items[distributor_name]['total_amount'] += total_cost
            grouped_cart_items[distributor_name]['items'].append({
                'product': DistProductMasterSerializer(cart_item.product).data,
                'quantity': cart_item.quantity,
                'added_by': cart_item.added_by,
                'created_at': cart_item.created_at,
                'distributor_name': distributor_name
            })

        sorted_grouped_cart_items = sorted(grouped_cart_items.values(), key=lambda x: x['distributor_name'])
        return {
            'user': instance.user.id,
            'cart_items': sorted_grouped_cart_items,
        }


class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = '__all__' 

class OrderSerializer(serializers.ModelSerializer):
    invoices = InvoiceSerializer(source='invoice_set', read_only=True)
    invoice_url = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    distributor_name = serializers.SerializerMethodField()
    total_gst = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    store_name = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    cash_discount = serializers.SerializerMethodField()
    # payment_mode = serializers.SerializerMethodField()
    
    
    def get_invoice_url(self, obj):
        invoices = getattr(obj, 'invoices', None)
        if invoices:
            for invoice in invoices.all():
                if invoice.invoice_file:
                    s3_link = generate_presigned_url(str(invoice.invoice_file))
                    return s3_link
        return None
    
    def get_invoice_number(self, obj):
        invoice = obj.invoices.all().first()
        return invoice.invoice_number if invoice else None
    
    def get_distributor_name(self, obj):
        if obj.distributor:
            return obj.distributor.name
        return None
    
    def get_total_gst(self, obj):
        invoice = obj.invoices.all().first()
        return invoice.gst_amount if invoice else 0.00
    
    def get_grand_total(self, obj):
        invoice = obj.invoices.all().first()
        return str(invoice.invoice_amount) if invoice else str(obj.total_amount)
    
    def get_store_name(self, obj):
        retailer = obj.user.retailer
        return retailer.store_name.capitalize()
    
    def get_address(self, obj):
        retailer = obj.user.retailer
        return retailer.address + ", " + retailer.postal_code
    
    def get_mobile_number(self, obj):
        phone_number = obj.user.username
        return phone_number
    
    def get_item_count(self, obj):
        item_count = obj.ordereditem_set.all().count()
        return item_count
    
    def get_cash_discount(self, obj):
        invoice = obj.invoices.all().first()
        return str(invoice.discount_amount) if invoice else "0.00"
    
    # def get_payment_mode(self, obj):
    #     payment_mode = obj.invoices.filter(payment_type__isnull=False).values_list('payment_type__payment_mode', flat=True).first()
    #     return payment_mode

    
    
    class Meta:
        model = Order
        fields = '__all__'

class OrderedItemSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    
    def get_amount(self, ordered_item):
        if ordered_item.build_qty == 0:
            amt = ordered_item.unit_price * ordered_item.quantity
        else:
            amt = ordered_item.unit_price * ordered_item.build_qty
        return str(amt) if amt else str(0.00)
    
    def get_name(self, ordered_item):
        name = ordered_item.product.name.capitalize()
        return name
    
    class Meta:
        model = OrderedItem
        fields = '__all__'
        
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if ret['max_retail_price'] == '0.00':
            product = instance.product
            if product:
                ret['max_retail_price'] = str(product.mrp)
        return ret

    

class RaiseIssueSerializer(serializers.Serializer):
    orderId = serializers.IntegerField()
    issueType = serializers.CharField()
    description = serializers.CharField(required=False,allow_blank=True)

    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass
