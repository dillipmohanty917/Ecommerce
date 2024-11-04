from django.db import models
from Usermanagement.models import Distributor, Organisation, ServiceablePincode, User
from django.utils.translation import pgettext_lazy
from b2b2 import settings
from datetime import datetime, timedelta

# Create your models here.


PRODUCT_TYPE_CHOICES = [
    ('pharma', 'Pharmaceutical'),
    ('cosmetic', 'Cosmetic'),
]
PRODUCT_CATEGORY_CHOICES = [
    ('Branded', 'Branded'),
    ('Generic', 'Generic'),
    ('OTC', 'OTC'),
     ('Surgicals', 'Surgicals')
]

class DistProductMaster(models.Model):
    name = models.CharField(max_length=255,default="")
    distributor_sku = models.CharField(max_length=128,default="")
    description = models.TextField(default="")
    hsn = models.CharField(max_length=20,default="")
    ptr = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    mrp = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    packing = models.CharField(max_length=50,default="")
    scheme_billed = models.PositiveIntegerField(default=0)
    scheme_free = models.PositiveIntegerField(default=0)
    product_category = models.CharField(max_length=50,choices=PRODUCT_CATEGORY_CHOICES, default='Branded')
    product_class = models.CharField(max_length=50,default="")
    product_salt = models.CharField(max_length=255,default="")
    product_type = models.CharField(max_length=50, choices=PRODUCT_TYPE_CHOICES, default='pharma')
    product_composition = models.TextField(default="")
    is_returnable = models.BooleanField(default=False, help_text='Check if the product is returnable.')
    is_discountable = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    distributor = models.ForeignKey(Distributor, on_delete=models.SET_NULL, null=True, blank=True)    
        
    def __str__(self):
        return self.name

    # Property to concatenate scheme_billed and scheme_free
    @property
    def concatenated_scheme(self):
        return f"{self.scheme_billed}+{self.scheme_free}" if self.scheme_billed != 0 else ""
    
    @property
    def product_category_choices(self):
        return self._meta.get_field('product_category').choices

class DistributorStock(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE,null=True, blank=True)
    product = models.ForeignKey(DistProductMaster, on_delete=models.CASCADE,null=True, blank=True)
    batch_number = models.CharField(max_length=50,default="")
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.CharField(default="")
    ptr = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    mrp = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    manufacturer = models.CharField(max_length=255,default="")
    gst = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    

    

class Deal(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE,null=True,blank=True)
    product = models.ForeignKey(DistProductMaster, on_delete=models.CASCADE,null=True,blank=True,related_name='deal')
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    description = models.TextField(default="")
    quantity = models.PositiveIntegerField(default=0)
    is_value = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(default=datetime.now().date() + timedelta(days=1))
    end_date = models.DateField(blank=True, null=True, default=None)
    is_expired = models.BooleanField(default=False)
    

    def __str__(self):
        return f"{self.distributor} - {self.product} Deal"
    
    
class UploadedBillDetailsFields(models.Model):
    product_name = models.CharField(max_length=32,  null=True, blank=True)
    distributor_sku = models.CharField(max_length=32,  null=True, blank=True)
    billed_quantity = models.CharField(max_length=32,  null=True, blank=True)
    billed_free = models.CharField(max_length=32,  null=True, blank=True)
    billed_free_half = models.CharField(max_length=32,  null=True, blank=True)
    price_to_retail = models.CharField(max_length=32,  null=True, blank=True)
    max_retail_price =models.CharField(max_length=32,  null=True, blank=True)
    goods_service_tax =models.CharField(max_length=32,  null=True, blank=True)
    discount =models.CharField(max_length=32,  null=True, blank=True)
    expiry =models.CharField(max_length=32,  null=True, blank=True)
    batch = models.CharField(max_length=32,  null=True, blank=True)
    packing = models.CharField(max_length=32,  null=True, blank=True)
    barcode = models.CharField(max_length=32,  null=True, blank=True)
    hsn_code = models.CharField(max_length=32,  null=True, blank=True)
    cgst = models.CharField( max_length=32,  null=True, blank=True)
    sgst = models.CharField( max_length=32,  null=True, blank=True)
    igst = models.CharField( max_length=32,  null=True, blank=True)
    cgst_amount = models.CharField( max_length=32,  null=True, blank=True)
    invoice_amount = models.CharField( max_length=32,  null=True, blank=True)
    invoice_no = models.CharField( max_length=32,  null=True, blank=True)
    partycode = models.CharField( max_length=32,  null=True, blank=True)
    gross_amount = models.CharField( max_length=32,  null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='upload_bill_fields', null=True, blank=True,on_delete=models.CASCADE)
    pts = models.CharField(max_length=32,  null=True, blank=True)



class UploadProductDetailsFields(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='upload_product_fields', null=True, blank=True,on_delete=models.CASCADE)
    product_name = models.CharField(max_length=255, blank=True, null=True)
    product_sku = models.CharField(max_length=50, blank=True, null=True)
    hsncode = models.CharField(max_length=20, blank=True, null=True)
    ptr = models.CharField(max_length=32,blank=True, null=True)
    mrp = models.CharField(max_length=32,blank=True, null=True)
    packing = models.CharField(max_length=32, blank=True, null=True)
    product_category = models.CharField(max_length=32, blank=True, null=True)
    product_composition = models.CharField(max_length=32,blank=True, null=True)
    batch_number = models.CharField(max_length=20, blank=True, null=True)
    quantity = models.CharField(max_length=20,blank=True, null=True)
    expiry_date = models.CharField(max_length=20, blank=True, null=True)
    discount = models.CharField(max_length=20, blank=True, null=True)
    scheme_billed = models.CharField(max_length=20,blank=True, null=True)
    scheme_free = models.CharField(max_length=20,blank=True, null=True)
    manufacturer = models.CharField(max_length=20, blank=True, null=True)
    gst = models.CharField(max_length=20,blank=True, null=True)

    def __str__(self):
        return self.product_name

    

