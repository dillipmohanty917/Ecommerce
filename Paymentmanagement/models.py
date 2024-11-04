from django.db import models

from Ordermanagement.models import Order
from Usermanagement.models import Distributor
from b2b2 import settings



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

class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    payment_date = models.CharField(default="")
    payment_mode = models.CharField(max_length=50,default="")  # Adjust the max_length as needed
    payment_type = models.CharField(max_length=50, default="")  # Adjust the max_length as needed
    transaction_id = models.CharField(max_length=255, default="")  # Adjust the max_length as needed
    cheque_no = models.CharField(max_length=50, default="")  # Adjust the max_length as needed
    description = models.TextField(blank=True, null=True)
    payment_status = models.CharField(max_length=50, default='pending')  # Adjust the max_length as needed
    status = models.CharField(max_length=50, default='active')  # Adjust the max_length as needed

    

    def __str__(self):
        return f"{self.order} - {self.payment_date}"



class Invoice(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,null=True, blank=True,related_name='invoices')
    invoice_number = models.CharField(max_length=255,default="")
    issued_date = models.CharField(default="")
    invoice_file = models.FileField(upload_to='invoices/')  # Adjust the upload_to path as needed
    invoice_status = models.CharField(max_length=50, default='issued')  # Adjust the max_length as needed
    invoice_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    distributor = models.ForeignKey(Distributor,on_delete=models.CASCADE,null=True, blank=True, related_name='invoices')
    invoice_date = models.CharField(default="")
    payment_type = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=50, default='active')  # Adjust the max_length as needed
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    

    def __str__(self):
        return f"{self.order} - {self.invoice_number}"


class Return(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE,null=True, blank=True)
    reason = models.TextField(default="")
    return_date = models.CharField(default="")
    return_amount = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    return_invoice_number = models.CharField(max_length=255,default="")
    invoice_number = models.ForeignKey(Invoice, on_delete=models.CASCADE,null=True, blank=True) 
    return_status = models.CharField(max_length=50, default='pending')
    status = models.CharField(max_length=50, default='active') 

    

    def __str__(self):
        return f"{self.order} - {self.return_date}"
    
    
    
class UploadedBillDetails(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,null=True, blank=True, related_name='order_bill_details')
    product_name = models.CharField(max_length=128,default="")
    billed_quantity = models.FloatField(null=True, default=0.0)
    billed_free = models.FloatField(null=True, default=0.0)
    unit_price_net = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    max_retail_price = models.DecimalField(max_digits=12, decimal_places=2,  default=0.00)
    goods_service_tax = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, choices=GST_SLAB_CHOICES)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expiry = models.CharField(max_length=128, null=True, blank=True)
    batch = models.CharField(max_length=32,  null=True, blank=True)
    barcode = models.CharField(max_length=32,  null=True, blank=True)
    hsn_code =  models.CharField(max_length=8, null=True,blank=True)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, choices=GST_HALF_SLAB_CHOICES)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, choices=GST_HALF_SLAB_CHOICES)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, choices=GST_SLAB_CHOICES)
    pts = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return self.id

    def __repr__(self):
        return str(self.id)
    
    
    
    