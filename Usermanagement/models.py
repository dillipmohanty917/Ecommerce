import json
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import random
import string
from django.utils.translation import pgettext_lazy
from django.db.models import Sum
from b2b2.settings import S3_LINK


class User(AbstractUser):
    is_retailer = models.BooleanField(default=False)
    is_distributor = models.BooleanField(default=False)
    is_callex = models.BooleanField(default=False)
    is_sales = models.BooleanField(default=False)
    is_operation = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_marketing = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, default=None, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.username
    
    
    # def save(self, *args, **kwargs):
    #     if self.is_deleted and not self.username.endswith('_deleted'):
    #         self.username = f"{self.username}_deleted_{self.pk}"
    #         self.phone_number = f"{self.phone_number}_deleted"
    #     super(User, self).save(*args, **kwargs)

    @property
    def kyc_details(self):
        kyc_details = KYC.objects.get(user_id=self.id)
        return kyc_details
    @property
    def documents(self):
        kyc_documents = Document.objects.get(uploaded_by_id=self.id)
        return kyc_documents

    
    @property
    def get_retailer_name(self):
        retailer_name = Retailer.objects.get(user=self).store_name
        return retailer_name
    
    @property
    def get_distributor_name(self):
        distributor_name = Distributor.objects.get(user=self).name
        return distributor_name
    
    @property
    def get_distributor_logo_with_s3_link(self):
        distributor_logo_path = Distributor.objects.get(user=self).logo
        if distributor_logo_path:
            return str(S3_LINK)+""+str(distributor_logo_path)
        else:
            return False

class Organisation(models.Model):
    name = models.CharField(max_length=255,default="")
    address = models.TextField(default=None, blank=True, null=True)
    email = models.EmailField(default=None, blank=True, null=True)
    logo = models.ImageField(
        upload_to="global_settings/", null=True, blank=True, default=None
    )
    header_bg = models.CharField(max_length=255, default="#ffffff")  # Default color
    footer_bg = models.CharField(max_length=255, default="#ffffff")  # Default color
    background_bg = models.CharField(max_length=255, default="#ffffff")  # Default color
    timezone = models.CharField(max_length=50, blank=True, null=True, default=None)
    currency = models.CharField(max_length=50, blank=True, null=True, default=None)
    language = models.CharField(max_length=50, default="en")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.timezone:
            self.timezone = timezone.get_current_timezone_name()

        if not self.currency:
            self.currency = self.get_default_currency()

        super().save(*args, **kwargs)

    def get_default_currency(self):
        timezone_currency_mapping = {
            "America/New_York": "USD",
            "Europe/London": "GBP",
            "Europe/Paris": "EUR",
            "Asia/Kolkata": "INR",
        }

        current_timezone = timezone.get_current_timezone_name()

        return timezone_currency_mapping.get(current_timezone, "USD")

RETAILER_KYC_CHOICES = [
    ('not started', 'Not Started'),
    ('pending', 'Pending'),
    ('rejected', 'Rejected'),
    ('completed', 'Completed')
]
class Retailer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,null=True, blank=True)
    medleyId = models.CharField(max_length=20, blank=True, default="")
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE,null=True, blank=True)
    owner_name = models.CharField(max_length=255, blank=True, default="", null=True)
    address = models.TextField(blank=True, default="", null=True)
    country = models.CharField(max_length=50, blank=True, default="")
    state = models.CharField(max_length=50, blank=True, default="")
    city = models.CharField(max_length=50, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="", null=True)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    store_pharmacist_name = models.CharField(max_length=50, null=True, blank=True)
    store_email = models.EmailField(blank=True, default="")
    store_geo_location = models.CharField(max_length=50, null=True, blank=True)
    is_activated = models.BooleanField(default=False)
    kyc_status = models.CharField(choices=RETAILER_KYC_CHOICES,default='not started')
    is_rejected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class Distributor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, default=None
    )
    name = models.CharField(max_length=255, blank=True, default="")
    address = models.TextField(blank=True, default="")
    country = models.CharField(max_length=50, blank=True, default="")
    state = models.CharField(max_length=50, blank=True, default="")
    city = models.CharField(max_length=50, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    is_activated = models.BooleanField(default=False)
    logo = models.ImageField(
        upload_to="distributor_logo/", null=True, blank=True, default=None
    )
    cart_value = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    Payment_term = models.CharField(max_length=50, blank=True, default="")
    speciality = models.CharField(max_length=100, blank=True, default="")
    discount = models.CharField(max_length=120, blank=True, default="")
    

    def __str__(self):
        return self.name
    
    def get_user_id(self):
        return self.user.id
    
    @property
    def get_distributor_sku_count(self):
        from Productmanagement.models import DistProductMaster
        get_distributor_sku_count = DistProductMaster.objects.filter(distributor=self).count()
        return get_distributor_sku_count
    
    @property
    def get_distributor_total_orders(self):
        from Ordermanagement.models import Order
        total_orders = Order.objects.filter(distributor=self).count()
        return total_orders

    @property
    def get_distributor_total_ordered_amount(self):
        from Ordermanagement.models import Order  # Import Order model at the top of the file
        total_orders = Order.objects.filter(distributor=self).aggregate(total_amount=Sum('total_amount'))
        return total_orders['total_amount'] if total_orders['total_amount'] else 0


class ServiceablePincode(models.Model):
    pincode = models.CharField(max_length=10)
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE,null=True, blank=True,related_name='serviceble_pincodes')

    def __str__(self):
        return self.pincode

class Document(models.Model):
    name = models.CharField(max_length=255)
    store_image = models.FileField(upload_to="documents/", blank=True, default=None)
    drug_license_form20 = models.FileField(
        upload_to="documents/", blank=True, default="", null=True
    )
    drug_license_form21 = models.FileField(
        upload_to="documents/", blank=True, default="", null=True
    )
    gst_image = models.FileField(upload_to="documents/", blank=True, default=None)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return self.name

class KYC(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Identity Documents
    id_document_type = models.CharField(max_length=50,default="")
    id_document_number = models.CharField(max_length=50,default="")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True)

    # Additional KYC Information
    registration_number = models.CharField(max_length=50, null=True, blank=True)
    gst_number = models.CharField(max_length=50, null=True, blank=True)
    drug_license_number = models.CharField(
        max_length=50, blank=True, default="", null=True
    )

    # KYC Status
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateTimeField(blank=True, null=True)
    valid_to = models.DateTimeField(blank=True, null=True)
    pan_number = models.CharField(max_length=50, null=True, blank=True)
    aadhaar_number = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"KYC for {self.user.username}"


class OTP(models.Model):
    phone = models.CharField(max_length=15, default="")
    otp_code = models.CharField(max_length=10,default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_otp_expired = models.BooleanField(default=False, blank=True)
    is_otp_verified = models.BooleanField(default=False, blank=True)

    @classmethod
    def generate_otp(cls, phone):
        # Generate a random 6-digit OTP
        otp_code = str(random.randint(100000, 999999))
        return otp_code

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
            
        if not self.expires_at:
            self.expires_at = self.created_at + timezone.timedelta(minutes=2)
        super().save(*args, **kwargs)


class UserToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    access_token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField(default=datetime.now() + timedelta(days=5))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.access_token


class Settings(models.Model):
    TYPE_CHOICES = [
        ("JSON", "JSON"),
        ("LIST", "LIST"),
        ("STRING", "STRING"),
        ("INTEGER", "INTEGER"),
        ("BOOLEAN", "BOOLEAN"),
    ]
    key = models.CharField(max_length=255, blank=False, default="")
    type = models.CharField(
        max_length=100, choices=TYPE_CHOICES, blank=False, default=""
    )
    value = models.CharField(max_length=400, blank=False, default="")
    is_active = models.BooleanField(default=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

    def get_value_based_on_type(key_name):
        setting = Settings.objects.filter(key=key_name).first()
        try:
            value = setting.value
        except:
            return "You Entered Wrong Key Name OR it's 'is_active' False"
        try:
            if setting.type == "JSON":
                replaced_value = value.replace("'", '"')
                json_data_ = json.loads(replaced_value)
                return json_data_
            elif setting.type == "LIST":
                replaced_value = value.replace("'", '"')
                list_data = json.loads(replaced_value)
                return list_data
            elif setting.type == "INTEGER":
                return int(value)
            elif setting.type == "STRING":
                return str(value)
            elif setting.type == "BOOLEAN":
                return False if value == "False" else bool(value)
        except:
            return "An error occurred during the conversion process."


class Commission(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE,null=True, blank=True)
    commission_rate = models.CharField(max_length=10,default="")
    created_at = models.DateTimeField(auto_now_add=True)
    base_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    base_discount_check = models.BooleanField(default=False)
    base_discount_lt = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    base_discount_gt = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    mmc_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mmc_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dbc_commn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deals_commn = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self):
        return self.distributor.name
    

class Feedback(models.Model):
    retailer = models.ForeignKey(Retailer, on_delete=models.CASCADE,null=True, blank=True)
    description = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Description: {self.description[:50]}"

class Banner(models.Model):
    title = models.CharField(max_length=100)
    image = models.ImageField(upload_to='banners/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
    
class PartyCode(models.Model):
    retailer = models.ForeignKey(Retailer,on_delete=models.CASCADE,null=True,blank=True)
    distributor = models.ForeignKey(Distributor,on_delete=models.CASCADE,null=True,blank=True)
    party_code  = models.CharField(max_length=20,null=True,blank=True,default="")
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.party_code

class SalesExecutive(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, null=True)
    retailer =  models.ManyToManyField(Retailer, related_name="sales_retailer", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user)
    
    @property
    def get_retailer_count(self):
        retailer_count =self.retailer.all().count()
        return retailer_count
     

class DistributorMappedRetailer(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, null=False, blank=False)
    store_name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=20, default=None, null=True, blank=True)
    optional_phone_number = models.CharField(max_length=20, default=None, null=True, blank=True)
    medleyId = models.CharField(max_length=20, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.distributor)

class CreditLine(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, null=False, blank=False)
    retailer = models.ForeignKey(Retailer, on_delete=models.CASCADE, null=False, blank=False)
    credit_date = models.DateField(null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(default=datetime.now().date() + timedelta(days=1))
    end_date = models.DateField(blank=True, null=True, default=None)
    is_expired = models.BooleanField(default=False)
         
    def __str__(self):
        return str(self.distributor)
    
class CommissionDiscount(models.Model):
    distributor = models.ForeignKey(Distributor, on_delete=models.CASCADE, null=False, blank=False)
    retailer = models.ForeignKey(Retailer, on_delete=models.CASCADE, null=False, blank=False)
    base_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(default=datetime.now().date() + timedelta(days=1))
    end_date = models.DateField(blank=True, null=True, default=None)
    is_expired = models.BooleanField(default=False)
    
    def __str__(self):
        return str(self.distributor)