from Ordermanagement.models import Cart
from rest_framework import serializers
from Productmanagement.models import DistProductMaster, Deal, DistributorStock
from datetime import date
from django.db.models import Q

class DistProductMasterSerializer(serializers.ModelSerializer): 
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    delivery_time = serializers.CharField(default="Delivery in 2 days", read_only=True)
    class Meta:
        model = DistProductMaster
        fields = '__all__'

class DealSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = ['description','quantity']
        

class DistProductDealMasterSerializer(serializers.ModelSerializer):
    deals = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    count = serializers.SerializerMethodField()
    # scheme_billed = serializers.SerializerMethodField()
    # stock = serializers.SerializerMethodField()
    # scheme_free = serializers.SerializerMethodField()
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    delivery_time = serializers.CharField(default="Delivery in 2 days", read_only=True)

    class Meta:
        model = DistProductMaster
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
    def get_deals(self, instance):
        # deals = instance.deal.all()
        today = date.today()
        deals = instance.deal.filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)), is_expired=False)
        return ", ".join([deal.description for deal in deals])
    
    def get_quantity(self, instance):
        today = date.today()
        deals = instance.deal.filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)), is_expired=False)
        total_quantity = sum(deal.quantity for deal in deals)
        return total_quantity
    
    def get_count(self, instance):
        cart = Cart.objects.filter(user=self.user).first()
        if cart:
            cart_item = instance.cartitem_set.filter(cart=cart).first()
            if cart_item:
                return cart_item.quantity
        return 0

    # def get_scheme_billed(self, instance):
    #     try:
    #         distributor_stock = DistributorStock.objects.get(distributor=instance.distributor, product=instance)
    #         return distributor_stock.scheme_billed
    #     except DistributorStock.DoesNotExist:
    #         return None

    def get_scheme_free(self, instance):
        try:
            distributor_stock = DistributorStock.objects.get(distributor=instance.distributor, product=instance)
            return distributor_stock.scheme_free
        except DistributorStock.DoesNotExist:
            return None
        
    # def get_stock(self, instance):
    #     try:
    #         distributor_stock = DistributorStock.objects.get(distributor=instance.distributor, product=instance)
    #         return distributor_stock.quantity
    #     except DistributorStock.DoesNotExist:
    #         return None

class DealSerializer(serializers.ModelSerializer):
    distributor_name = serializers.CharField(source='distributor.name', read_only=True)
    name = serializers.CharField(source='product.name', read_only=True)
    scheme_billed = serializers.CharField(source='product.scheme_billed', read_only=True)
    scheme_free = serializers.CharField(source='product.scheme_free', read_only=True)
    product_category = serializers.CharField(source='product.product_category', read_only=True)
    ptr = serializers.CharField(source='product.ptr', read_only=True)
    mrp = serializers.CharField(source='product.mrp', read_only=True)
    count = serializers.SerializerMethodField()
    products = DistProductMasterSerializer(many=True, read_only=True)
    deals = serializers.SerializerMethodField()
    class Meta:
        model = Deal
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
    def get_count(self, instance):
        cart = Cart.objects.filter(user=self.user).first()
        if cart:
            cart_item = instance.cartitem_set.filter(cart=cart).first()
            if cart_item:
                return cart_item.quantity
        return 0
    
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['scheme_billed'] = int(rep['scheme_billed'])
        rep['scheme_free'] = int(rep['scheme_free'])
        return rep
    def get_deals(self, instance):
        return instance.description