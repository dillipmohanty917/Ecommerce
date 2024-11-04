from django.db import models
from Productmanagement.models import DistProductMaster
from Usermanagement.models import KYC, Distributor, Retailer

from b2b2 import settings

# Create your models here.


ISSUE_TYPE_CHOICES=[ ('damage', 'Damage'),
        ('missing', 'Missing'),
        ('short_expiry', 'Short_Expiry'),
        ('not_delivered', 'Not_Delivered'),
        ('Others', 'Others')
]

GST_SLAB_CHOICES = (
    (0.00, '0%'),
    (5.00, '5%'),
    (12.00, '12%'),
    (18.00, '18%'),
    (28.00, '28%'),
)


GST_HALF_SLAB_CHOICES = (
    (0.00, '0%'),
    (2.50, '2.5%'),
    (6.00, '6%'),
    (9.00, '9%'),
    (14.00, '14%'),
)

PENDING = 'Pending'
ACCEPTED = 'Accepted'
PROCESSED = 'Processed'
BILLED = 'Billed'
CANCELLED = 'Cancelled'

ORDER_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (ACCEPTED, 'Accepted'),
        (PROCESSED, 'Processed'),
        (BILLED, 'Billed'),
        (CANCELLED,'Cancelled')
    ]
class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='orders',null=True, blank=True)
    distributor = models.ForeignKey(Distributor,on_delete = models.CASCADE,null=True, blank=True, related_name='distributor_orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    order_date = models.DateTimeField(auto_now_add=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    order_status = models.CharField(max_length=50,choices=ORDER_STATUS_CHOICES, default=PENDING)  # Adjust the max_length as needed
    status = models.CharField(max_length=50, default='active')  # Adjust the max_length as needed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPE_CHOICES, default='', null = True)
    description = models.TextField(default="", null = True)
    issue_status = models.CharField(max_length=50, default='', null=True)
    placed_by =  models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name='placed_orders',null=True, blank=True)



    def __str__(self):
        return f"{self.user} - {self.order_date}"
    
    @property
    def get_order_item_number(self):
        number_of_items = OrderedItem.objects.filter(order=self).count()
        return number_of_items
    
    @property
    def retailer_store_name(self):
        try:
            # Assuming each order is associated with a retailer
            retailer = Retailer.objects.get(user=self.user)
            return retailer.store_name
        except Retailer.DoesNotExist:
            return "Retailer Not Found"
    
    @property
    def get_address(self):
        retailer = Retailer.objects.get(user=self.user)
        retailer_details = [retailer.store_pharmacist_name,retailer.store_name,
                retailer.address,retailer.city,
                retailer.postal_code,retailer.state]
        foramtter_retailer_details = [attr for attr in retailer_details if attr]
        return ",".join(foramtter_retailer_details)
    @property
    def get_invoices(self):
        # from Paymentmanagement.models import Invoice
        # invoices = Invoice.objects.filter(order=self)
        return self.invoices.all()
    
    @property
    def retailer_city(self):
        try:
            retailer = Retailer.objects.get(user=self.user)
            return retailer.city
        except Retailer.DoesNotExist:
            return "Retailer Not Found"

    
    
class OrderedItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey(DistProductMaster, on_delete=models.CASCADE,null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    max_retail_price = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    distributor_id = models.ForeignKey(Distributor,on_delete = models.CASCADE,null=True, blank=True)  # Adjust the field type based on your requirements
    batch = models.CharField(max_length=50,default='')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    scheme_billed = models.PositiveIntegerField(default=0)
    scheme_qty = models.PositiveIntegerField(default=0)
    build_qty = models.PositiveIntegerField(default=0)
    build_free = models.PositiveIntegerField(default=0)
    gst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    hsn = models.CharField(max_length=20,default='')
    expiry = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, default='active')  # Adjust the max_length as needed
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.order} - {self.product} - {self.quantity}"
    @property
    def get_total_price(self):
        return self.unit_price * self.build_qty


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    order_date = models.DateTimeField(auto_now_add=True)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=50, default='pending')  # Adjust the max_length as needed
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.user} - {self.order_date}"
    
    @property
    def get_total_amount(self):
        cart_items = CartItem.objects.filter(cart=self)
        total_cart_amount = sum([item.quantity*item.product.ptr for item in cart_items ])
        return total_cart_amount
    
    
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey(DistProductMaster, on_delete=models.CASCADE,null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,on_delete=models.CASCADE, related_name='cart_added',null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    
    @property
    def distributor_name(self):
        return self.product.distributor.name
    @property
    def distributor_cart_value(self):
        return self.product.distributor.cart_value
    
    
