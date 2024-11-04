from decimal import Decimal
from http.client import HTTPResponse
import locale
import logging
import os
import re
import uuid
from xml.dom import ValidationErr
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db.models import Sum, F, ExpressionWrapper, FloatField
from Activitylog.models import ActivityLog
from Paymentmanagement.models import Invoice
from Productmanagement.forms import ProductDealsForm
from Productmanagement.models import Deal, DistProductMaster, DistributorStock
from django.db import transaction
from django.db.models import Q
from Usermanagement.forms import DistributorOrderFilter 
from .utils import active_admin_required
from django.shortcuts import render,redirect
from django.template.response import TemplateResponse
from .models import OTP,User,Retailer, Organisation, KYC
from Ordermanagement.models import Order,OrderedItem
import datetime
from .utils import *
from Usermanagement.api.serializers import SendOTPSerializer
from django.contrib import messages, auth
import requests
from b2b2.settings import  CURRENCY, S3_LINK, SHOW_OTP_PHONE_NUMBERS, TEXTLOCAL_API_KEY, WEB_VERSION
from .filters import *
from . import get_paginator_items, paginate_items
from django.utils.translation import pgettext_lazy,pgettext 
import pandas as pd
from datetime import datetime
from django.utils import timezone
from .forms import CaptchaTestForm, DashboardForm
from django.http import HttpResponse
import csv
from django.contrib.auth import get_user_model
from dateutil.parser import parse as parse_date
# from Usermanagement.authentication import CustomAuthentication
from django.contrib.auth import authenticate, login
from django.core.exceptions import MultipleObjectsReturned
from django.views.decorators.csrf import csrf_exempt
from b2b2.env import *

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def home(request):
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_admin):
        return redirect('dashboard')
    elif request.user.is_authenticated and request.user.is_distributor:
        return redirect ('distributor_home')
    elif request.user.is_authenticated and request.user.is_marketing:
        return redirect ('marketing_dashboard')
    elif request.user.is_authenticated:
        return redirect ('account_logout')   
    return TemplateResponse(
			request, 'medley_home.html')
    
@active_admin_or_sub_admin_required
def dashboard(request):
    orders = Order.objects.all().order_by("-created_at")
    total_order_count = orders.count()
    retailers = Retailer.objects.all().count()
    form = DashboardForm(request.GET)
    from django.db.models import Sum
    today = timezone.now().date()

    # Filter orders created today
    today_orders = orders.filter(created_at__date=today)

    # Aggregate the total_amount for the filtered orders
    total_order_amount_today = today_orders.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'] or 0.00    
    amount_percentage_growth, orers_percentage_growth, retailer_percentage_growth = calculate_growth_percentage(orders, float(total_order_amount_today))




    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        date_range = form.cleaned_data.get('daterange')

        if search_query:
            try:
                search_query_int = int(search_query)
                orders = Order.objects.filter(id=search_query_int)
            except ValueError:
                # Handle the case where search_query is not a valid integer
                orders = Order.objects.filter(
                    Q(user__retailer__store_name__icontains=search_query) |
                    Q(distributor__name__icontains=search_query)
                )
            # orders = paginate_items(request,orders,10)
        if date_range:
            start_date, end_date = date_range.split(' - ')
            start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
            end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
            orders = orders.filter(created_at__date__range=[start_date, end_date])
            
        orders = paginate_items(request,orders,10)
        
    ctx = {"orders": orders,'retailers':retailers,
           'daterange':date_range,
           "form": form,'today_order_amount':total_order_amount_today,
           'currency':CURRENCY,
           'total_order_count':total_order_count,
           'amount_percentage_growth':amount_percentage_growth,
           'orers_percentage_growth': orers_percentage_growth,
           'retailer_percentage_growth': retailer_percentage_growth}
    return render(request, 'dashboard.html', ctx)
    
@login_required
def logout(request):
    auth.logout(request)
    # messages.success(request,('You have been successfully logged out.'))
    return redirect('home')

def validate_phone(phone):
    if len(phone) != 10:
            return False
    return True
def validate_phone_again(phone):
    if len(phone) != 12:
        return False
    return True

def email_login(request):
    form = CaptchaTestForm()
    if request.method == 'POST':
        form  = CaptchaTestForm(request.POST)
        ctx={"form":form}
        email_or_phone = request.POST.get('email')
        password = request.POST.get('password')
        if form.is_valid():
            user = authenticate(username=email_or_phone, password=password)
            if not user:
                ctx.update({"email":email_or_phone,"password":password,"error":"Please enter a correct email/phone number and password!"})
                return render(request,"email_login.html",ctx)
            elif user and not user.is_active:
                ctx.update({"error":"Your Inactive please contact SuperAdmin"})
                return render(request,"email_login.html",ctx)
            elif user and not user.is_distributor and not user.is_admin:
                ctx.update({"error":"You are not registered as a distributor/admin!"})
                return render(request,"email_login.html",ctx)
            elif user and (user.is_distributor or user.is_admin):
                auth.login(request, user)
                messages.success(request, ('You have been logged in.'))
                return redirect('home')
            # else:
            #     ctx={"error":"You are not registered with us contact admin!"}
            #     return render(request,"email_login.html",ctx)
        else:
           ctx.update({"email":email_or_phone,"password":password,"error":"Wrong captcha entered try again"})
           return render(request,"email_login.html",ctx)
    ctx={"form":form}
    return render(request,'email_login.html',ctx)

def register(request):
    if request.method == 'POST':
        data = request.POST.get('phone')
        is_phone_validated = validate_phone(data)
        if is_phone_validated:
            data = '91'+data
        else:
            context = {'message' : 'Please enter a valid phone number' , 'class' : 'danger' }
            return render(request,'login.html' , context)
        print (data,"asasas")
        is_user_exists = is_exists(User, {'username': data})
        print (is_user_exists,"is_user_existsis_user_exists")
        if is_user_exists:
            user = get_object(User,{"username":data})
            if user.is_distributor:
                context = {'message' : 'You registered as distributor please login through Email.' , 'class' : 'danger' }
                return render(request,'login.html' , context)
            elif user.is_admin:
                context = {'message' : 'You registered as admin please login through Email.' , 'class' : 'danger' }
                return render(request,'login.html' , context)

        is_otp_exists = is_exists(OTP, {'phone': data})
        request.session['phone'] = data
        
        new_otp = OTP.generate_otp(data)
        # data['otp'] = new_otp

        # For signup users
        if not is_user_exists and not is_otp_exists:
            
            context = {'message' : 'This number is not registered' , 'class' : 'danger' }
            return render(request,'login.html' , context)
            
        elif is_user_exists and is_otp_exists:
            request.session['phone'] = data
            smsOTP(data,new_otp)
            update_user = update(OTP,{'phone':data},{
                'otp_code': new_otp,
                'created_at': timezone.now(),
                'expires_at': timezone.now() + timezone.timedelta(minutes=10),
                'is_otp_verified': False})

            #trigger email
            
            #mailing code
            if update_user:
                serialized_data = OTP.objects.filter(phone=data)
                serialized_data,"88888"
                return redirect('otp')

        elif is_user_exists and not is_otp_exists:
            smsOTP(data,new_otp)
            store_user_otp = store(OTP, {'phone':data,'otp_code': new_otp,'is_otp_verified': False,'created_at': timezone.now(),'expires_at': timezone.now() + timezone.timedelta(minutes=10)})
            if store_user_otp:
                serialized_data = OTP.objects.filter(phone=data)
                request.session['phone'] = data
                return redirect('otp')

        # cond 3: "not a registered user" but already has otp and trying to send again
        else:
            # check otp status
            store_user_otp = update(OTP, {'phone':data},{'otp_code': new_otp,'created_at': timezone.now(),'expires_at': timezone.now() + timezone.timedelta(minutes=10),'is_otp_verified': False})
            serialized_data = OTP.objects.filter(phone=data)
           
            return redirect('otp')

    
    return render(request,'login.html')



def otp(request):
    data = request.session['phone']
    if request.method == "POST":
        data1 = data
        otp = request.POST.get('otp')
        is_phone_validated = validate_phone_again(data)
        if is_phone_validated:
            data = data
        else:
            context = {'message' : 'please enter valid phone number' , 'class' : 'danger' }
            return render(request,'otp.html' , context)
           
        
        try:
            is_user_exists = is_exists(User, {'username': data})
            is_otp_exists = is_exists(OTP, {'phone': data, 'otp_code': otp})
            otp_object = filter_attribute(OTP, {'phone': data, 'otp_code': otp}).first()
        except Exception as e:
            return render(request,'otp.html')
        if data and otp:
            if  request.user.is_authenticated :
                return redirect('home')
            validation_result = validate_user_otp_web(data,otp)
            if validation_result:
                    #check otp in db
                    check_otp = filter_by_attribute(OTP, {'phone':data}).otp_code
                    if check_otp == otp:
                        OTP_status = OTP_Validity(data)
                    
                        # Login User - update OTP status & Redirect to Dashboard
                        if OTP_status and is_user_exists:
                                serializer = SendOTPSerializer(otp_object, data={'is_otp_verified': True}, partial=True)
                                if serializer.is_valid():
                                    serializer.save()
                            
                                # update password with OTP
                                update_user = filter_by_attribute(User, {'username': data})
                                update_user.set_password(otp)
                                update_user.save()

                                serialized_data = serializer.data
                                
                                user = auth.authenticate(username=data, password=otp)
                                if user:
                                    auth.login(request, user)
                                    messages.success(request, ('You have been logged in.'))
                                    return redirect('home')
                                # return redirect('register_successfully')

                        # New User and OTP is sent and now verifying
                        # elif OTP_status and not is_user_exists:
                        #         # # create a user
                        #         create_user = store(
                        #             User, {'username':data})
                        #         create_user.set_password(otp)
                        #         create_user.save()
                        #         verifyotp = update(OTP, {'phone': data, 'otp_code': otp}, {'is_otp_verified': True})
                        #         request.session['phone'] = data
                        #         request.session['otp'] = otp
                        #         messages.success(request,('Your account has been created.'))
                        #         password = otp
                        #         # email = form.cleaned_data.get('email')
                        #         phone = data
                        #         username = phone
                        #         if username and password :
                        #             user = auth.authenticate(username=username, password=password)
                        #             if user:
                        #                 auth.login(request, user)
                        #                 # messages.success(request, ('You have been logged in.'))
                        #                 return redirect('home')
                        else:
                            context = {'message' : 'OTP has expired.Please generate new OTP' , 'class' : 'danger','data':data }
                            return render(request,'otp.html' , context)
                    else:
                        context = {'message' : 'Invalid OTP' , 'class' : 'danger', 'data':data}
                        return render(request,'otp.html' , context)
            else:
            # return redirect('register_successfully')     
                context = {'message' : 'validation failedInvalid OTP/Phone' , 'class' : 'danger','data':data }
                return render(request,'otp.html' , context)
    context = {'data':data}
    return render(request,'otp.html',context)


def resendotp(request):  
    if request.method == "GET":
        data = request.session['phone']
        is_otp_exists = is_exists(OTP, {'phone': data})
        new_otp = str(random.randint(100000, 999999))
        if   is_otp_exists:
            smsOTP(data,new_otp)
            store_user_otp = update(OTP,{'phone':data},
            {'otp_code': new_otp,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timezone.timedelta(minutes=10),
            'is_otp_verified': False})

            serialized_data = OTP.objects.filter(phone=data)
            if serialized_data:
                request.session['phone'] = data
                return redirect('otp')
    
    return render(request,'otp.html')

def notifyUsers(numbers, details=None, receiverType=None):
    return True

def smsOTP(data,otp):

    sendername='MEDLEY'

    msg='Dear user, your login attempt has been recorded. Please verify your account using OTP - '+otp+' Note: The OTP will be expired in 10 minutes.Regards,Team MedleyMed'

    url ='https://api.textlocal.in/send/?apikey='+settings.TEXTLOCAL_API_KEY+'&sender='+sendername+'&numbers='+data+'&message='+msg

    f=requests.get(url)
    
def get(url, params=None, **kwargs):
    """Sends a GET request.

    :param url: URL for the new :class:`Request` object.
    :param params: (optional) Dictionary or bytes to be sent in the query string for the :class:`Request`.
    :param \*\*kwargs: Optional arguments that ``request`` takes.
    :return: :class:`Response <Response>` object
    :rtype: requests.Response
    """

    kwargs.setdefault('allow_redirects', True)
    return request('get', url, params=params, **kwargs)



@active_admin_or_sub_admin_required
def partner_summary(request,serviceblepincodes=None):
    try:
        if serviceblepincodes == "all":
            distributors = Distributor.objects.all()
            if not distributors.exists():
                messages.error(request, 'No Distributors found.')
                return redirect('your_redirect_url')

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="all_partners_pincodes.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Distributor Id','Distributor Name', 'Pincode'])  # Write headers

            for distributor in distributors:
                pincodes_list = ServiceablePincode.objects.filter(distributor=distributor)
                for pincode in pincodes_list:
                    writer.writerow([distributor.id,distributor.name, pincode.pincode])

            # Logging and activity logging can be added here as needed
            return response
        customers = Distributor.objects.all().order_by("-id")

        mobile_number = request.GET.get('mobile_number')
        partner_name = request.GET.get('partner_name')
        city = request.GET.get('city')
        partner_id = request.GET.get('selectedPartnerId')
        
        if mobile_number:
            customers = customers.filter(user__username__icontains=mobile_number)
        if partner_name:
            customers = customers.filter(name__icontains=partner_name)
        if city:
            customers = customers.filter(city__icontains=city)
        if partner_id:
            customers = customers.filter(id=partner_id)

        customer_filter = CustomerFilter(request.GET, queryset=customers)
        customers = paginate_items(request,customers,20)
        ctx = {
            'customers': customers,
            'user': request.user,
            'customer_filter': customer_filter,
            'currency':CURRENCY
        }
        logger.info('Customer list retrieved successfully by user: %s', request.user.username)
        if serviceblepincodes:
            return TemplateResponse(request, 'partner_pincode_distributor_list.html', ctx)
        return TemplateResponse(request, 'partner-summary.html', ctx)
    except Exception as e:
        # Log an error message if an exception occurs
        logger.error('Error fetching customer list: %s', str(e))
        

@active_admin_required
def customer_details(request, pk):
    try:
        customer = User.objects.get(pk=pk)
        distributor = Distributor.objects.get(user=pk)
        start_datetime = request.GET.get('start_datetime')
        end_datetime = request.GET.get('end_datetime')

        distributor_products = DistributorStock.objects.filter(distributor__user=pk).select_related('product').order_by('product__name')
        product_filter =  ProductFilter(request.GET, queryset=distributor_products)
        page_number = request.GET.get('page')
        products_data_final = get_paginator_items(product_filter.qs,10,page_number)
        products_totalpage = products_data_final.paginator.num_pages
        orders = Order.objects.filter(user=pk)
        order_filter =  OrderFilter(request.GET, queryset=orders)
        page_number = request.GET.get('order_page')
        orders_data_final = get_paginator_items(order_filter.qs,10,page_number)
        orders_totalpage = orders_data_final.paginator.num_pages
        ctx = {
            'orders':orders_data_final,
            'customer': customer,
            'distributor': distributor,
            "dist_id":pk,
            "distributor_products":products_data_final,
            "servicedata":products_data_final,
            "totalpagelist":[n+1 for n in range(products_totalpage)],
            "orderpagelist":[n+1 for n in range(orders_totalpage)],
            'pro_filter' : product_filter,
            'order_filter':order_filter
            
        }
    except Exception as e:
        logger.error("exception occcured in customer details", str(e))
    return TemplateResponse(request, 'customer_details.html', ctx)

@active_admin_or_sub_admin_required
def new_customer_list(request): 
    try: 
        retailer = Retailer.objects.filter(user__is_deleted = False).order_by('-id')
        serviceable_pincode=ServiceablePincode.objects.all().values_list("pincode",flat=True)
     
        mobile_number = request.GET.get('mobile_number')
        customer_name = request.GET.get('customer_name')
        medley_id = request.GET.get('medley_id')
        status_id = request.GET.get('status_id')
        
        if mobile_number:
            retailer = retailer.filter(user__username__icontains=mobile_number)
        if customer_name:
            retailer = retailer.filter(store_name__icontains=customer_name)
        if medley_id:
            retailer = retailer.filter(medleyId__icontains=medley_id)
        if status_id:
            retailer = retailer.filter(kyc_status__icontains=status_id)
        retailer = paginate_items(request,retailer,20)
        
        ctx = {
            'status_id':status_id,
            'retailer': retailer,
            'user': request.user,
            'serviceable_pincode':serviceable_pincode,
        }
        return TemplateResponse(request, 'new_customer.html',ctx)
    except Exception as e:
        logger.error("exception occcured in new_customer_list", str(e))

def generate_medley_id():
    try:
        last_used_medley_id = Retailer.objects.order_by('-medleyId').first()
        if  last_used_medley_id and last_used_medley_id.medleyId[3:].isdigit():
            last_digits = int(last_used_medley_id.medleyId[3:])
            new_digits = last_digits + 1
        else:
            new_digits = 1
        new_medley_id = 'MED{:04}'.format(new_digits)
        return new_medley_id
    except Exception as e:
        logger.error("exception occcured in generating the medley Id", str(e))



@active_admin_required
def reject_action_retailer(request,pk):
    reject_status = Retailer.objects.filter(id=pk).first()
    action = request.POST.get('action')
    if request.method == "POST":
        if action == "reject":
           reject_status.is_rejected = True
           reject_status.is_activated = False
           reject_status.kyc_status= "rejected"
           reject_status.save()
           logger.warning('Retailer Rejected Successfully')
           return redirect('new_customer_list')
        else:
            return redirect('new_customer_list')    
            
    return TemplateResponse(request, 'new_customer.html')

@active_admin_or_sub_admin_required
def action_partner(request,pk):
    reject_status = Distributor.objects.filter(id=pk).first()
    action = request.POST.get('action')
    if request.method == "POST":
        if action == "activate":
           dist_user_obj = reject_status.user
           dist_user_obj.is_active = True
           dist_user_obj.save()
           
           reject_status.is_activated = True
           reject_status.save()  
           logger.info('Partner Activated Successfully by user: %s', request.user.username)
           ActivityLog.log_activity(user=request.user, action="Activate", details=f"Partner '{reject_status.name}' has been successfully Activated by {request.user.username}.", to_user=reject_status.user)
           messages.success(request,"Partner Activated Successfully")
           return redirect('partner-summary')
        elif action == "deactivate":
            dist_user_obj = reject_status.user
            dist_user_obj.is_active = False
            dist_user_obj.save()
           
            reject_status.is_activated = False
            reject_status.save()
            logger.info('Partner Deactivated Successfully by user: %s', request.user.username)
            ActivityLog.log_activity(user=request.user, action="Deactivate", details=f"Partner '{reject_status.name}' has been Deactivated by {request.user.username}.", to_user=reject_status.user)
            messages.success(request,"Partner Deactivated Successfully")
            return redirect('partner-summary')
           
        else:
            return redirect('partner-summaryt')  
        
            
    return TemplateResponse(request, 'partner-summary.html')


@active_admin_or_sub_admin_required
def edit_retailer(request, pk):
    instance = get_object_or_404(Retailer, id=pk)
    ret_user = User.objects.get(id=instance.user_id)
    kyc_data,created = KYC.objects.get_or_create(user_id=instance.user_id)
    documents,created = Document.objects.get_or_create(uploaded_by_id=instance.user_id)
    document_urls = {}
    if documents.drug_license_form20:
        document_urls['drug_license_form20'] = generate_presigned_url(documents.drug_license_form20.name)
    if documents.drug_license_form21:
        document_urls['drug_license_form21'] = generate_presigned_url(documents.drug_license_form21.name)
    if documents.gst_image:
        document_urls['gst_image'] = generate_presigned_url(documents.gst_image.name)
    if documents.store_image:
        document_urls['store_image'] = generate_presigned_url(documents.store_image.name)
    ctx = {
            'instance': instance,
            'kyc_data': kyc_data, 
            'ret_user':ret_user,
            'document_urls':document_urls,
            }
    
    def render_error(error_message):
        ctx['error_message'] = error_message
        return render(request, 'edit_retailer.html', ctx)

    try:
        if request.method == 'POST':
            action = request.POST.get('action')
            store_name=request.POST.get('store_name')
            owner_name=request.POST.get('owner_name')
            postal_code=request.POST.get('postal_code')
            # email=request.POST.get('store_email')
            gstnumber=request.POST.get('gstnumber')
            licence=request.POST.get('licence')
            address=request.POST.get('address')
            city = request.POST.get('city')
            state = request.POST.get('state')
        
            if "cancel" in request.POST:
                return redirect('new_customer_list')
            
            if "act" in request.POST:
                if action == "active":
                    if not instance.medleyId:
                            instance.medleyId = generate_medley_id()
                    instance.is_activated = True
                    instance.kyc_status = "completed"
                    instance.is_rejected = False
                    instance.save()
                    logger.info('Customer Activated Successfully by user: %s', request.user.username)
                    logger.warning('Retailer Activated Successfully')
                    messages.success(request, ('Retailer Activated Successfully'))
                    ActivityLog.log_activity(user=request.user, action="Activate", details=f"Retailer '{instance.store_name}' has been Activated by {request.user.username}.", to_user=instance.user)
                    return redirect('new_customer_list')
                if action == "deactivate":
                    instance.is_activated = False
                    instance.kyc_status = "pending"
                    instance.is_rejected = True
                    instance.save()
                    logger.info('Customer Deactivated Successfully by user: %s', request.user.username)
                    messages.success(request, ('Retailer Deactivated Successfully'))
                    ActivityLog.log_activity(user=request.user, action="Deactivate", details=f"Retailer '{instance.store_name}' has been Deactivated by {request.user.username}.", to_user=instance.user)
                    return redirect('new_customer_list')
                        
                
            new_phone_number = request.POST.get('phone_number')
            if len(new_phone_number) == 10 :
                new_phone_number = '91' + new_phone_number
                ret_user.phone_number = new_phone_number
                ret_user.save()
            elif new_phone_number.startswith('91') and len(new_phone_number) == 12:
                ret_user.phone_number = new_phone_number
                ret_user.save()
            else:
                return render_error('Invalid Phone Number format.')
                
            
                
            # if not all(char.isalpha() or char.isspace() for char in owner_name):
            #         return render_error('Invalid Owner Name format.')
            
            # if not all(char.isalpha() or char.isspace() for char in store_name):
            #         return render_error('Invalid  Store Name format.')
            
            if not postal_code.isdigit() or len(postal_code) != 6:
                        return render_error('Invalid Pincode format. Please enter a 6-digit numeric pincode.')
            instance.postal_code = postal_code
            instance.store_name = store_name
            instance.owner_name = owner_name
            instance.address = address
            instance.country = "India"
            instance.city = city
            instance.state = state
            instance.save()
            if request.POST.get('valid_from'):
                kyc_data.valid_from = request.POST.get('valid_from')
            if request.POST.get('valide_to'):
                kyc_data.valid_to = request.POST.get('valide_to')
            kyc_data.gst_number = gstnumber
            kyc_data.drug_license_number = licence
            logger.info('Customer Kyc data updated: %s', request.user.username)
            kyc_data.save()

            if request.FILES.get('gstcertificate'):
                documents.gst_image = get_unique_doc(request.FILES.get('gstcertificate'))
            if request.FILES.get('doc_licence20'):
                documents.drug_license_form20 =get_unique_doc(request.FILES.get('doc_licence20'))
            if request.FILES.get('doc_licence21'): 
                documents.drug_license_form21 =get_unique_doc(request.FILES.get('doc_licence21'))
            if request.FILES.get('store_image'):
                documents.store_image =get_unique_doc(request.FILES.get('store_image'))
            documents.name="Retailer Kyc Documents"
            logger.info('Customer Documents data updated: %s', request.user.username)
            documents.save()
            messages.success(request,"Successfully Updated")
            ActivityLog.log_activity(user=request.user, action="Updated", details=f"'{instance.store_name}' details has been Successfully Updated.", to_user=instance.user)
            return redirect('edit_retailer',instance.id)
        else:
            logger.warning('error on post request')
            
            
    except Exception as e:
        logger.warning('error on post request')    
    return TemplateResponse(request, 'edit_retailer.html', ctx)

@active_admin_or_sub_admin_required
def edit_partner(request, pk):
    instance = get_object_or_404(Distributor, id=pk)
    partner_user = User.objects.get(id=instance.user_id)
    kyc_data,created = KYC.objects.get_or_create(user_id=instance.user_id)
    documents,created = Document.objects.get_or_create(uploaded_by_id=instance.user_id)
    document_urls = {}
    if documents.drug_license_form20:
        document_urls['drug_license_form20'] = generate_presigned_url(documents.drug_license_form20.name)
    if documents.drug_license_form21:
        document_urls['drug_license_form21'] = generate_presigned_url(documents.drug_license_form21.name)
    if documents.gst_image:
        document_urls['gst_image'] = generate_presigned_url(documents.gst_image.name)
    if instance.logo:
       document_urls['logo'] = generate_presigned_url(instance.logo.name)
    

    ctx = {
            'instance': instance,
            'kyc_data': kyc_data, 
            'partner_user':partner_user,
            # 'local_s3':S3_LINK,
            'document_urls':document_urls,
            }
    
    def render_error(error_message):
        ctx['error_message'] = error_message
        return render(request, 'edit_partner.html', ctx)

    try:
        if request.method == 'POST':
            name=request.POST.get('name')
            postal_code=request.POST.get('postal_code')
            email=request.POST.get('email')
            gstnumber=request.POST.get('gstnumber')
            licence=request.POST.get('licence')
            address=request.POST.get('address')
            city=request.POST.get('city')
            state=request.POST.get('state')
            pan_number=request.POST.get('pan_number')
            aadhaar=request.POST.get('aadhaar')
            cart_value=request.POST.get('hreshold_value','')

            if "cancel" in request.POST:
                return redirect('partner-summary')
            
            new_phone_number = request.POST.get('phone_number')
            if len(new_phone_number) == 10 :
                new_phone_number = '91' + new_phone_number
                partner_user.phone_number = new_phone_number
                partner_user.username = new_phone_number
                partner_user.save()
            elif new_phone_number.startswith('91') and len(new_phone_number) == 12:
                partner_user.phone_number = new_phone_number
                partner_user.username = new_phone_number
                partner_user.save()
            else:
                return render_error('Invalid Phone Number format.')
                
             
            
            if not postal_code.isdigit() or len(postal_code) != 6:
                        return render_error('Invalid Pincode format. Please enter a 6-digit numeric pincode.')
          
            instance.postal_code = postal_code
            # instance.user.email = email
            instance.name = name
            instance.cart_value=cart_value if cart_value.isdigit() else 0
            instance.address = address
            instance.city = city
            instance.Payment_term=request.POST.get('payment_term')
            instance.discount=request.POST.get('discount')
            instance.speciality=request.POST.get('speciality')
            instance.state = state
            instance.country = "India"
            if request.FILES.get('logo'): 
                instance.logo =get_unique_doc(request.FILES.get('logo'))
            instance.save()
    
            if email:
                    if User.objects.filter(email=email).exclude(id=partner_user.id).exists():
                        return render_error('This email address is already in use. Please choose a different one.')        
                    else:
                        partner_user.email=email
                        partner_user.save()
            if request.POST.get('valide_from'):
                kyc_data.valid_from = request.POST.get('valide_from')
            if request.POST.get('valide_to'):
                kyc_data.valid_to = request.POST.get('valide_to')
            kyc_data.gst_number = gstnumber
            kyc_data.drug_license_number = licence
            kyc_data.aadhaar_number=aadhaar
            kyc_data.pan_number=pan_number
            logger.info('Partner Kyc data updated: %s', request.user.username)
            logger.warning('Partner Kyc data updated')
            kyc_data.save()
            
            
            if request.FILES.get('gstcertificate'):
                documents.gst_image = get_unique_doc(request.FILES.get('gstcertificate'))
            if request.FILES.get('doc_licence20'):
                documents.drug_license_form20 =get_unique_doc(request.FILES.get('doc_licence20'))
            if request.FILES.get('doc_licence21'): 
                documents.drug_license_form21 =get_unique_doc(request.FILES.get('doc_licence21'))
            documents.name="Partner Kyc Documents"
            logger.info('Partner Documents data updated: %s', request.user.username)
            documents.save()
            messages.success(request,"Successfully Updated")
            ActivityLog.log_activity(user=request.user, action="Updated", details=f"Partner '{instance.name}' details has been Successfully Updated.", to_user=instance.user)
            return redirect('partner-summary')
        else:
            logger.warning('error on post request')
            
            
    except Exception as e:
        logger.warning('error on post request')    
    return TemplateResponse(request, 'edit_partner.html', ctx)



def get_distributor_orders(request, pk):
    customer_orders = Order.objects.filter(user=pk).order_by('-order_date')
    return customer_orders


@active_admin_or_sub_admin_required
def add_partner(request):
        try:
            if request.method == 'POST':
                organisation = Organisation.objects.get(id = 1)
                name = request.POST.get('name')
                phonee = request.POST.get('phone')
                address= request.POST.get('address')
                state= request.POST.get('state')
                city= request.POST.get('city')
                pincode = request.POST.get('pincode')
                email = request.POST.get('email')
                bdname = request.POST.get('bdname')
                pan_number = request.POST.get('pan_number')
                aadhar = request.POST.get('aadhaar')
                gstnumber = request.POST.get('gstnumber')
                licence = request.POST.get('licence')
                valide_from = request.POST.get('valide_from')
                valide_to = request.POST.get('valide_to')
                cart_value=request.POST.get('cart_value')
                payment_term=request.POST.get('payment_term')
                discount=request.POST.get('discount')
                speciality=request.POST.get('speciality')
                gst_document=request.FILES.get('gstcertificate')
                drug_license_form20=request.FILES.get('doc_licence20')
                drug_license_form21=request.FILES.get('doc_licence21')
                # pan_document=request.FILES.get('pan_document')
                # adhar_document=request.FILES.get('adhar_document')
                logo=request.FILES.get('logo')
                
                
                ctx={'name': name,'phonee':phonee,'address':address,'state': state,'city': city,'pincode':pincode,'email':email,'gstnumber':gstnumber,'licence':licence,
                     'bdname':bdname,'pan_number':pan_number,'aadhaar':aadhar,'valide_from':valide_from,'valide_to':valide_to,'gst_document':gst_document,'drug_license_form20':drug_license_form20,
                     'drug_license_form21':drug_license_form21,'logo':logo,'hreshold_value':cart_value,'payment_term':payment_term,'discount':discount,'speciality':speciality
                }
                def render_error(error_message):
                    ctx['error_message'] = error_message
                    return render(request, 'add_new_partner.html', ctx)
                
                try:
                    # if not all(char.isalpha() or char.isspace() for char in name):
                    #     return render_error('Invalid Name format.')
                    
                    if not all(char.isalpha() or char.isspace() for char in state):
                        return render_error('Invalid State format.')
                
                    if not all(char.isalpha() or char.isspace() for char in city):
                        return render_error('Invalid City format.')

                    if not pincode.isdigit() or len(pincode) != 6:
                        return render_error('Invalid Pincode format. Please enter a 6-digit numeric pincode.')

                    # if not gstnumber.isalnum():
                    #     return render_error('Invalid GST Number format. Please enter an alphanumeric GST Number.')
                    
                    # if not hreshold_value.isdigit():
                    #     return render_error('Invalid Cart Value.')

                    if len(phonee) == 10:
                        phonee = '91' + phonee
                        username = phonee
                    elif phonee.startswith('91') and len(phonee) == 12:
                        username = phonee
                    else:
                        return render_error('Invalid phone number format. Please enter a valid number.')

                    if User.objects.filter(username=username).exists():
                        return render_error('Mobile Number already exists. Please choose a different one.')
                    if User.objects.filter(email=email).exists():
                        return render_error('Email already exists. Please choose a different one.')

                    user = User.objects.create(
                        username=username,
                        is_distributor=True,
                        email=email,
                        phone_number=username,
                    )
                except ValidationErr as e:
                    print(f"Validation error: {e}")
                distributor = Distributor.objects.create(
                    user=user,
                    name=name,
                    country="India",
                    city=city,
                    cart_value=int(cart_value),
                    organisation=organisation,
                    address=address,
                    state=state,
                    Payment_term=payment_term,
                    discount=discount,
                    speciality=speciality,
                    postal_code=pincode,
                    logo=get_unique_doc(logo),
                )

                doc = Document.objects.create(
                    name="Distributor Kyc Documents",
                    drug_license_form20=get_unique_doc(drug_license_form20),
                    drug_license_form21=get_unique_doc(drug_license_form21),
                    gst_image=get_unique_doc(gst_document),
                    uploaded_by=user
                )

                kyc = KYC.objects.create(
                    user=user,
                    document=doc,
                    gst_number=gstnumber,
                    drug_license_number=licence,
                    pan_number=pan_number,
                    aadhaar_number=aadhar,
                    valid_from=valide_from,
                    valid_to=valide_to
                )
                ActivityLog.log_activity(user=request.user, action="Created", details=f"New partner '{distributor.name}' has been created by {request.user.username}.", to_user=distributor.user)
                logger.info('Partner Added successfully by : %s', request.user.username)
                return redirect('partner-summary')
        except Exception as e:
                logger.error("exception occcured in Adding the partner function", str(e))
        return render(request, 'add_new_partner.html')
    

@login_required
def distributor_home(request):
    distributor = get_object_or_404(Distributor,user_id=request.user.pk)
    orders = Order.objects.filter(distributor_id=distributor.id).order_by('-created_at')
    total_orders = orders.count()
    pincode_list = ServiceablePincode.objects.filter(distributor=distributor).values("pincode")
    retailer_count=Retailer.objects.filter( Q(postal_code__in=pincode_list) & Q(is_activated=True)).count()
    
    
    from django.db.models import Sum
    today = timezone.now().date()
    # Filter orders created today
    today_orders = orders.filter(created_at__date=today)
    # Aggregate the total_amount for the filtered orders
    total_order_amount_today = today_orders.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum']
    
    orders = paginate_items(request,orders,10)
    ctx={'orders':orders,'S3_LINK':S3_LINK,'distributor':distributor,'today_order_amount':total_order_amount_today,'retailer_count':retailer_count,"currency":CURRENCY,'total_orders':total_orders} 
    
    return render(request, 'distributor_home.html',ctx)


@active_admin_or_sub_admin_required
def dist_serviceble_picodes_list(request,pk):
    distributor = get_object_or_404(Distributor,user_id=pk)
    if request.method=="POST":
        uploaded_file = request.FILES['file'] if 'file' in request.FILES else False
        pincode = request.POST.get('pincode',"")
        
        if uploaded_file :
            if uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.csv') or uploaded_file.name.endswith('.xls'):
                if uploaded_file.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file)
                else:
                    df = pd.read_csv(uploaded_file)
                df.columns = [col.strip() for col in df.columns]
                if 'Pincode' not in df.columns:
                    messages.error(request, '"Pincode" Column Is Missing In File.')
                else:
                    def is_numeric(s):
                        return s.isdigit()
                    df['is_numeric'] = df['Pincode'].astype(str).apply(is_numeric)
                    df['pincode_length'] = df['Pincode'].astype(str).apply(len)
                    # invalid_pincodes = df[~((df['is_numeric']) & (df['pincode_length'] == 6))][['Pincode']]
                    df = df[(df['is_numeric']) & (df['pincode_length'] == 6)][['Pincode']]
                    
                    unique_pincodes_list = df['Pincode'].unique()
                    existing_pincodes = ServiceablePincode.objects.filter(distributor=distributor).values_list('pincode', flat=True)                    
                    pincodes_to_create = [pincode for pincode in unique_pincodes_list if str(pincode) not in existing_pincodes]                    
                    serviceable_pincodes_to_create = [ServiceablePincode(pincode=pincode, distributor=distributor) for pincode in pincodes_to_create]
                    # Bulk create new pincodes
                    ServiceablePincode.objects.bulk_create(serviceable_pincodes_to_create, ignore_conflicts=True)
                    messages.success(request, 'File Uploaded Successfully')
                    ActivityLog.log_activity(user=request.user, action="Created", details=f"Bulk of serviceble pincode uploaded by {request.user.username}.", to_user=distributor.user)
                    
                    # response = HttpResponse(content_type='text/csv')
                    # response['Content-Disposition'] = f'attachment; filename="{distributor.name}_wrong_pincodes_data.csv"'
                    # writer = csv.writer(response)
                    # writer.writerow(['Pincode'])  # Write headers
                    # for i, row in invalid_pincodes.iterrows():
                    #     writer.writerow([row['Pincode']])                        
                    # logger.info(f'{distributor.name} Distributor Pincodes Downloaded By: {request.user.username}')
                    # return response
            else:
                    messages.error(request, 'Please Upload a valid File.')   
        elif 'delete_pincode' in request.POST:
            delete_pincode = request.POST.get('delete_distributor_pincode')
            dist_pincode_obj = ServiceablePincode.objects.filter(distributor=distributor,pincode=delete_pincode).first()
            if dist_pincode_obj:
                dist_pincode_obj.delete()
                ActivityLog.log_activity(user=request.user, action="Deleted", details=f"Pincode '{delete_pincode}' successfully deleted by {request.user.username}.", to_user=distributor.user)
        elif 'download_partner_pincodes' in request.POST:
            
            pincodes_list=ServiceablePincode.objects.filter(distributor=distributor)  
            if not pincodes_list:
                messages.error(request, 'No Pincodes available for the selected Partner.')
                return redirect('dist-serviceble-picodes-list',pk)
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{distributor.name}_pincodes.csv"'
            
            # Write the data to the CSV response
            writer = csv.writer(response)
            writer.writerow(['Distributor Name', 'Pincode'])  # Write headers
            for pincode in pincodes_list:
                writer.writerow([distributor.name, pincode.pincode])
                
            logger.info(f'{distributor.name} Distributor Pincodes Downloaded By: {request.user.username}')
            # ActivityLog.log_activity(user=request.user, action="Downloaded", details=f" '{distributor.name}' pincode has been downloaded by {request.user.username}.", to_user=distributor.user)
            return response     
        else:
            is_pincode_exists = is_exists(ServiceablePincode, {'pincode': pincode, 'distributor': distributor})
            if len(pincode) != 6:
                messages.error(request, 'Please Enter a valid Pincode.')
            elif not is_pincode_exists:
                serviceablepincode_obj, created = ServiceablePincode.objects.update_or_create(
                    pincode=pincode,
                    distributor=distributor
                )
                messages.success(request, 'Pincode added successfully.')
                ActivityLog.log_activity(user=request.user, action="Created", details=f"New serviceble pincode '{pincode}' added by {request.user.username}.", to_user=distributor.user)
            else:
                messages.error(request, 'Pincode already exists for this Partner.')
    search_pincode = request.GET.get('search_query')
    serviceble_pincodes = distributor.serviceble_pincodes.all().order_by('-id')
    
    if search_pincode:
        serviceble_pincodes = serviceble_pincodes.filter(pincode__icontains=search_pincode)
    serviceble_pincodes = paginate_items(request,serviceble_pincodes,10)
    ctx={
        'Serviceble_pincodes' : serviceble_pincodes,
        'distributor_name':distributor.name,
        "dist_id":pk
    }
    return TemplateResponse(request,'partner_coverage_pincodes_list.html',ctx)

@active_admin_or_sub_admin_required    
def commissions_list(request):
    try:
        if request.method == "POST":
            if 'singleUpdate' in request.POST:
                commission_id = request.POST.get('commissionId')
                base_discount = request.POST.get('base_discount_modal')
                base_discount_lt = request.POST.get('base_discount_lt_modal')
                base_discount_gt = request.POST.get('base_discount_gt_modal')
                mmc_cash = request.POST.get('mmc_cash_modal')
                mmc_credit = request.POST.get('mmc_credit_modal')
                dbc_commn = request.POST.get('dbc_commn_modal')
                deals_commn = request.POST.get('deals_commn_modal')
        
                commission_obj, created = Commission.objects.update_or_create(
                    id=commission_id,
                    defaults={
                        'base_discount': float(base_discount),
                        'base_discount_lt': float(base_discount_lt),
                        'base_discount_gt': float(base_discount_gt),
                        'mmc_cash': float(mmc_cash),
                        'mmc_credit': float(mmc_credit),
                        'dbc_commn': float(dbc_commn),
                        'deals_commn': float(deals_commn)
                    }
                )
                
                messages.success(request, f'{commission_obj.distributor.name} Partner Commission has been successfully updated.')
                logger.info(f'{commission_obj.distributor.name} Partner Commission has been successfully updated.')
                return redirect('commissions-list')
                 
            elif request.FILES.get('file'):
                file = request.FILES.get('file')
                try:
                    if file.content_type == "text/csv":
                        df = pd.read_csv(file)
                    else:
                        df = pd.read_excel(file)
                    if len(df) <= 0:
                        messages.warning(request, 'Please upload the file with data as it appears to be empty.')
                        return redirect('commissions-list')
                except:
                    messages.error(request, 'Invalid file format.')
                    return redirect('commissions-list')
                required_columns = ["distributor_id", "base_discount", 
                                    "base_discount_less_than", 
                                    "base_discount_greater_than", "mmc_cash", "mmc_credit", 
                                    "dbc_commn", "deals_commn"]
                cols_stripped = [col.strip() for col in df.columns]
                df.columns = cols_stripped
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    messages.error(request, f'Columns {missing_columns} not found in the Uploaded file.')
                    return redirect('commissions-list')
                    
                update_data = []
                create_data = []
                for i, row in df.iterrows():
                    distributor = Distributor.objects.filter(id=row['distributor_id']).first()
                    if not distributor:
                        continue
                    existing_commission = Commission.objects.filter(distributor=distributor).first()
                    try:
                        base_discount = float(row['base_discount'])
                        base_discount_lt = float(row['base_discount_less_than'])
                        base_discount_gt = float(row['base_discount_greater_than'])
                        mmc_cash = float(row['mmc_cash'])
                        mmc_credit = float(row['mmc_credit'])
                        dbc_commn = float(row['dbc_commn'])
                        deals_commn = float(row['deals_commn'])
                        
                        if any(value < 0 for value in [base_discount, base_discount_lt, base_discount_gt, mmc_cash, mmc_credit, dbc_commn, deals_commn]):
                            messages.error(request, 'Fields must contain positive values only.')
                            logger.info('Partner Commissions upload successfully')
                            return redirect('commissions-list')
                    
                    except ValueError as e:
                        messages.error(request, str(e))
                        return redirect('commissions-list')
                    if existing_commission:
                        # existing_commission.commission_rate = row['commission_rate']
                        existing_commission.base_discount = float(row['base_discount'])
                        # existing_commission.base_discount_check = row['base_discount_check']
                        existing_commission.base_discount_lt = float(row['base_discount_less_than'])
                        existing_commission.base_discount_gt = float(row['base_discount_greater_than'])
                        existing_commission.mmc_cash = float(row['mmc_cash'])
                        existing_commission.mmc_credit = float(row['mmc_credit'])
                        existing_commission.dbc_commn = float(row['dbc_commn'])
                        existing_commission.deals_commn = float(row['deals_commn'])
                        update_data.append(existing_commission)
                        
                    else:
                        create_data.append(Commission(
                            distributor=distributor,
                            # commission_rate=row['commission_rate'],
                            base_discount = float(row['base_discount']),
                            # base_discount_check = row['base_discount_check'],
                            base_discount_lt = float(row['base_discount_less_than']),
                            base_discount_gt = float(row['base_discount_greater_than']),
                            mmc_cash = float(row['mmc_cash']),
                            mmc_credit = float(row['mmc_credit']),
                            dbc_commn = float(row['dbc_commn']),
                            deals_commn = float(row['deals_commn'])
                        ))  
                # Creating Bulk Upload and Update.        
                with transaction.atomic():
                    if update_data:
                        Commission.objects.bulk_update(update_data, ['base_discount', 'base_discount_lt', 'base_discount_gt', 'mmc_cash', 'mmc_credit', 'dbc_commn', 'deals_commn'])
                    if create_data:
                        Commission.objects.bulk_create(create_data)
                messages.success(request, 'The Partner Commission has been successfully uploaded or updated.')
                logger.info('Partner Commissions upload successfully')
                return redirect('commissions-list')
            
        commissions = Commission.objects.select_related('distributor').all().order_by("-created_at")
        form = ProductDealsForm(request.GET)
        if form.is_valid():
            search_query = form.cleaned_data.get('search_query')
            if search_query:
                commissions = commissions.filter(
                    distributor__name__icontains=search_query
                    )
        commissions = paginate_items(request,commissions,10)
        ctx = {"commissions":commissions}
        return TemplateResponse(request, 'commissions_list.html',ctx)
    
    except Exception as e:
        logger.error("exception occcured in commissions upload", str(e))
        messages.error(request,f'Exception occcured in commissions upload :{str(e)}')
        return redirect('commissions-list')
        
@active_admin_or_sub_admin_required
def get_commission_details(request):
    if request.method == 'POST':
        commission_id = request.POST.get('pk')  # Assuming 'pk' is passed as parameter
        commission_obj = Commission.objects.filter(id = commission_id).first()
        commission_details = {"commission_id": commission_obj.id,
                              "partner_name": commission_obj.distributor.name,
                              "base_discount": commission_obj.base_discount,
                              "base_discount_lt": commission_obj.base_discount_lt,
                              "base_discount_gt": commission_obj.base_discount_gt,
                              "mmc_cash": commission_obj.mmc_cash,
                              "mmc_credit": commission_obj.mmc_credit,
                              "dbc_commn": commission_obj.dbc_commn,
                              "deals_commn": commission_obj.deals_commn} 
        return JsonResponse(commission_details, safe=False)
    else:
        return JsonResponse({'error': 'Only POST requests are allowed'})
        
@active_admin_required
def add_new_partner(request):
    return TemplateResponse(request,'add_new_partner.html')


@active_admin_required        
def upload_mobile_app_banner(request):
    if request.method == 'POST':
        if 'delete_banner' in request.POST:
            delete_banner_id = request.POST.get('delete_banner_id')
            delete_banner = Banner.objects.get(id=delete_banner_id)
            if delete_banner:
                delete_banner.delete()
        else:   
            image_file = request.FILES.get('uploaded_banner')
            if image_file:
                new_banner = Banner()
                new_banner.title = image_file.name
                new_banner.image = get_unique_doc(image_file)
                new_banner.uploaded_by = request.user
                new_banner.save()
                messages.success(request,'Banner Upload Successfully.')
            else:
                messages.error(request,'Please Upload a Banner.')
                
            return redirect ('upload-mobile-app-banner')
              
    all_banners = Banner.objects.all()
    document_urls = []

    for banner in all_banners:
        if banner.image:
            image_path = str(banner.image)  # Ensure the image path is a string
            presigned_url = generate_presigned_url(image_path)
            document_urls.append({
                'id': banner.id,
                'title': banner.title,
                'created_at': banner.created_at,
                'uploaded_by': banner.uploaded_by,
                'image_name': banner.image.name,
                'presigned_url': presigned_url,
            })
    ctx={'banners':all_banners,
        #  's3_link':S3_LINK,
         'document_urls':document_urls}
    return TemplateResponse(request,'upload_banner.html', ctx)


@active_admin_required        
def organization(request):
        if request.method == 'POST':
            if 'delete_organiztions' in request.POST:
                delete_organization_id = request.POST.get('delete_organiztions_id')
                delete_org = Organisation.objects.get(id=delete_organization_id)
                if delete_org:
                    delete_org.delete()
                    messages.success(request,'Deleted  Successfully.')
            if request.POST.get('name'):
                new_org = Organisation()
                new_org.name = request.POST.get('name')
                new_org.address = request.POST.get('address')
                new_org.email = request.POST.get('email')
                if request.FILES.get('logo'):
                   new_org.logo = get_unique_doc(request.FILES.get('logo',''))
                
                new_org.save()
                messages.success(request,'Added Successfully.')
            
        organization = Organisation.objects.all()
        document_urls = []

        for org in organization:
            if org:
                if org.logo:
                    image_path = str(org.logo)  # Ensure the image path is a string
                    presigned_url = generate_presigned_url(image_path)
                    document_urls.append({
                        'id': org.id,
                        'name': org.name,
                        'address': org.address,
                        'email': org.email,
                        'presigned_url': presigned_url,
                    })
                else:
                    document_urls.append({
                        'id': org.id,
                        'name': org.name,
                        'address': org.address,
                        'email': org.email,
                    })
                    
        
        ctx={'document_urls':document_urls}
        return TemplateResponse(request,'organization.html', ctx)
    
          

@active_admin_or_sub_admin_required       
def feedback_list(request):
    feedbacks = Feedback.objects.all().order_by('-created_at')
    search_query = request.GET.get('search_feedback')
    if search_query:
        feedbacks = feedbacks.filter(
            Q(description__icontains=search_query) |
            Q(retailer__store_name__icontains=search_query)|
            Q(retailer__user__username__icontains=search_query)
        )
    feedbacks = paginate_items(request, feedbacks, 10)
    ctx = {'feedbacks':feedbacks}
    return TemplateResponse(request,'feedbacks_list.html', ctx)

# @active_admin_or_sub_admin_required        
def master_order_list(request):
    
    orders = Order.objects.all().order_by("-created_at")
    distributor=Distributor.objects.all()
    partner_id = request.GET.get('selectedPartnerId')
    partner_name = request.GET.get('partner_name')
    order_id = request.GET.get('order_id')
    retailer_name = request.GET.get('retailer_name')
    local_tz = pytz.timezone('Asia/Kolkata')
    
    
    if partner_id and partner_name:
        orders = orders.filter(distributor__id=partner_id,distributor__name__icontains=partner_name)
    if order_id:
        orders = orders.filter(id__icontains=order_id)
        
    if retailer_name:
        orders = orders.filter(user__retailer__store_name__icontains=retailer_name)
    
    orders = paginate_items(request, orders, 20)
    
    if request.GET.get('download'):
        master_orders = Order.objects.all()
        from django.db.models import Prefetch
        from datetime import datetime
        
        # date_range = request.GET.get('datetimes')
        start_date = request.GET.get('datetimes_start')
        end_date = request.GET.get('datetimes_end')

        if start_date and end_date:

            # Filter orders based on date range
            master_orders = Order.objects.all().select_related('distributor')
            if start_date and end_date:
                master_orders = master_orders.filter(created_at__date__range=(start_date, end_date))
            elif start_date:
                master_orders = master_orders.filter(created_at__date__gte=start_date)
            elif end_date:
                master_orders = master_orders.filter(created_at__date__lte=end_date)

        else:
            # No date range provided, get all orders
            master_orders = Order.objects.all().select_related('distributor')

            master_orders = master_orders.prefetch_related(
            Prefetch('ordereditem_set', queryset=OrderedItem.objects.select_related('product')),
            Prefetch('invoice_set'),
            Prefetch('distributor'),
            Prefetch('user')
        )
        if master_orders:
            csv_filename = str(start_date)+" to "+str(end_date) +"_Item_Wise_Report.csv"
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename={}'.format(csv_filename)
        
       
            writer = csv.writer(response)
            writer.writerow(['order_id', 'order_date', 'order_time', 'distributor_name', 'distributor_id',
                            'retailer_store_name', 'retailer_medley_id', 'product_name', 'product_sku', 'order_quantity',
                            'MRP', 'PTR', 'order_status', 'Is Deal item','invoice_number', 'invoice_date',
                            'Invoice MRP', 'Inovice PTR', 'Invoice Discount', 'Invoice Qty', 'Invoice GST '])
            
            for order in master_orders:
                retailer = Retailer.objects.filter(user=order.user).first() if order.user else None
                # ordered_items = OrderedItem.objects.filter(order=order)
                invoice = Invoice.objects.filter(order=order).first()
            

                for item in order.ordereditem_set.all():  
                    order_date_obj = order.order_date
                    order_date_obj = order_date_obj.astimezone(local_tz)
                    order_date = str(order_date_obj).split(" ")[0]
                    order_time = order_date_obj.time().strftime("%H:%M:%S")   
                    writer.writerow([
                                    order.id,
                                    order_date,
                                    order_time,
                                    order.distributor.name if order.distributor else "Retailer Not Found",
                                    order.distributor.id if order.distributor else "Retailer Not Found",
                                    order.user.get_retailer_name if order.user else "Distributor Not Found",
                                    retailer.medleyId if retailer else "",
                                    item.product.name,
                                    item.product.distributor_sku,
                                    item.quantity,
                                    item.product.mrp,
                                    item.product.ptr,
                                    order.order_status,
                                    1 if item.product.deal.all().first() else 0,
                                    invoice.invoice_number if invoice else "",
                                    invoice.invoice_date if invoice else "",
                                    item.max_retail_price,
                                    item.unit_price if order.order_status =="Billed" else 0,
                                    invoice.discount_amount if invoice else "",
                                    item.build_qty,
                                    invoice.gst_amount if invoice else "",
                            ])
            


            return response
        else:
            messages.error(request, 'No Data to download')
            return redirect('master_order_list')
    
    # download order wise data
    
    if request.GET.get('download_order_wise'):
        master_orders = Order.objects.all()
        from django.db.models import Prefetch
        from datetime import datetime
        
        datetimes_start = request.GET.get('datetimes_start')
        datetimes_end = request.GET.get('datetimes_end')


        if datetimes_start and datetimes_end:
            master_orders = Order.objects.all().select_related('distributor')
            if datetimes_start and datetimes_end:
                master_orders = master_orders.filter(created_at__date__range=(datetimes_start, datetimes_end))
            elif datetimes_start:
                master_orders = master_orders.filter(created_at__date__gte=datetimes_start)
            elif datetimes_end:
                master_orders = master_orders.filter(created_at__date__lte=datetimes_end)

        else:
            # No date range provided, get all orders
            master_orders = Order.objects.all().select_related('distributor')

            master_orders = master_orders.prefetch_related(
            Prefetch('ordereditem_set', queryset=OrderedItem.objects.select_related('product')),
            Prefetch('invoice_set'),
            Prefetch('distributor'),
            Prefetch('user')
        )
        if master_orders:
            csv_filename = str(datetimes_start)+" to "+str(datetimes_end) +"_Order_Wise_Report.csv"
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename={}'.format(csv_filename)

            writer = csv.writer(response)
            writer.writerow(['order_id','order_date','order_time','distributor_name','distributor_id','retailer_store_name',
                            'retailer_medley_id','No of Items','Quantity of Items','order_value','order_status','invoice_number',
                            'invoice_date','invoice count of items','gross_amount','invoice_discount','invoice GST','invoice_amount','invoice_quantity'
                        ])
            
            for order in master_orders:
                retailer = Retailer.objects.filter(user=order.user).first() if order.user else None
                # ordered_items = OrderedItem.objects.filter(order=order)
                invoice = Invoice.objects.filter(order=order).first()
            
                
                # for item in order.ordereditem_set.all():  
                order_date_obj = order.order_date
                order_date_obj = order_date_obj.astimezone(local_tz)
                order_date = str(order_date_obj).split(" ")[0]
                order_time = order_date_obj.time().strftime("%H:%M:%S")
                # total_mrp = order.order_bill_details.annotate(total_mrp=ExpressionWrapper(F('max_retail_price') * F('billed_quantity'), output_field=FloatField())).aggregate(Sum('total_mrp'))['total_mrp__sum'] or 0
                # total_ptr = order.order_bill_details.annotate(total_mrp=ExpressionWrapper(F('unit_price_net') * F('billed_quantity'), output_field=FloatField())).aggregate(Sum('total_mrp'))['total_mrp__sum'] or 0
                # mrp = order.ordereditem_set.annotate(total_mrp=ExpressionWrapper(F('max_retail_price') * F('quantity'), output_field=FloatField())).aggregate(Sum('total_mrp'))['total_mrp__sum'] or 0
                # ptr = order.ordereditem_set.annotate(total_mrp=ExpressionWrapper(F('unit_price') * F('quantity'), output_field=FloatField())).aggregate(Sum('total_mrp'))['total_mrp__sum'] or 0
                
                writer.writerow([
                            order.id,
                            order_date,
                            order_time,
                            order.distributor.name if order.distributor else "Distributor Not Found",
                            order.distributor.id if order.distributor else "Distributor Not Found",
                            order.user.get_retailer_name if order.user else "Customer Not Found",
                            retailer.medleyId if retailer else "Customer Not Found",
                            order.ordereditem_set.all().count(),
                            order.ordereditem_set.aggregate(Sum('quantity'))['quantity__sum'] or 0,
                            order.total_amount,
                            order.order_status,
                            invoice.invoice_number if invoice else "",
                            invoice.invoice_date if invoice else "",
                            order.order_bill_details.all().count(),
                            invoice.gross_amount if invoice else 0,
                            invoice.discount_amount if invoice else 0,
                            invoice.gst_amount if invoice else 0, 
                            invoice.invoice_amount if invoice else 0,
                            order.ordereditem_set.aggregate(Sum('build_qty'))['build_qty__sum'] or 0   
                        ])

            return response
        else:
            messages.error(request, 'No Data to download')
            return redirect('master_order_list')
        

    ctx = {'orders':orders,'distributor':distributor}
    return TemplateResponse(request,'master_order.html',ctx)

def web_version(request):
    data = {'web_version': WEB_VERSION}
    return HttpResponse(json.dumps(data), content_type="application/json")


def terms_and_conditions_web(request):
	return TemplateResponse(request,'terms_conditions.html')

def privacy_web(request):
    return TemplateResponse(request,'privacy_policy.html')


def about_us(request):
	return TemplateResponse(request,'about_us.html')

def contact_us(request):
	return TemplateResponse(request,'contact_us.html')

@active_admin_or_sub_admin_required  
def partycode_list(request):
    partner_id = request.GET.get('selectedPartnerId')
    partner_name = request.GET.get('partner_name',)
    partycode = request.GET.get('partycode')
    retailer_store_name = request.GET.get('search_retailer')

    filter_expression = Q()
    if partner_id:
        filter_expression &= Q(distributor_id=partner_id)
    if partner_name:
        filter_expression &= Q(distributor__name__icontains=partner_name)
    if partycode:
        filter_expression &= Q(party_code=partycode)
    if retailer_store_name:
        filter_expression &= Q(retailer__store_name__icontains=retailer_store_name)

    partycodes = PartyCode.objects.filter(filter_expression).order_by('-created_at') 
    partycodes = paginate_items(request, partycodes, 10)
    ctx = {
        "partycodes":partycodes
    }
    return TemplateResponse(request,'party_codes.html',ctx)


@active_admin_or_sub_admin_required
def get_partner_names(request):
    if request.method == 'GET' and 'filter' in request.GET:
        filter_text = request.GET.get('filter')
        filtered_objects = Distributor.objects.filter(name__icontains=filter_text)
        filtered_data = [{"name":obj.name,"id":obj.id,"city":obj.city} for obj in filtered_objects]
        return JsonResponse(filtered_data, safe=False)
    else:
        return JsonResponse({'error': 'Invalid request'})

@active_admin_or_sub_admin_required  
def open_issues(request):
    open_issues = Order.objects.filter(Q(issue_status="Open") | Q(issue_status="Close")).order_by('-created_at')
    search_query = request.GET.get('issue_status')
    if search_query:
        open_issues = open_issues.filter(issue_status__icontains=search_query)
    open_issues = paginate_items(request, open_issues, 15)
    
    ctx = {'issues': open_issues}
    return TemplateResponse(request, 'dashboard_open_issues.html',ctx)


@active_backendTechAdmin_required    
def new_otp_list(request):
    current_time = datetime.now()
    otp_lists = OTP.objects.filter(expires_at__gte=current_time).order_by('-created_at')    
    ctx={'otp_lists':otp_lists}
    return TemplateResponse(request,'otp_list.html', ctx)

@active_admin_or_sub_admin_required       
def dashbord_activity_logs(request):
    
    seven_days_ago = timezone.now() - timedelta(days=7)

    # Retrieve activity logs from the last 7 days
    activity_logs = ActivityLog.objects.filter(timestamp__gte=seven_days_ago).order_by('-timestamp')
    date_range = request.GET.get('daterange') 
    mobile_number = request.GET.get('mobile_number')
    
    if mobile_number:
        activity_logs = activity_logs.filter(user__username__icontains=mobile_number)
    
    if date_range:
        start_date, end_date = date_range.split(' - ')
        start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
        end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
        activity_logs = activity_logs.filter(timestamp__date__range=[start_date, end_date])
    activity_logs = paginate_items(request, activity_logs, 20)
    ctx = {'activity_logs':activity_logs}
    return TemplateResponse(request,'activity_logs.html', ctx)


@active_distributor_required
def add_sales_executive(request):
    distributor = Distributor.objects.filter(user=request.user).first()
    sales_executive = SalesExecutive.objects.filter(user__is_sales=True,distributor=distributor)
    # sales_executive=SalesExecutive.objects.filter(distributor=distributor)
    
    
    search_query = request.GET.get('search_query')
    if search_query:
        sales_executive = sales_executive.filter(user__first_name__icontains=search_query)
    
    if request.method == 'POST':
        phone = request.POST.get('formData[phone]')
        name = request.POST.get('formData[name]')
        email = request.POST.get('formData[email]')
        
        # Username exists
        if User.objects.filter(username="91"+phone).exists():
            return JsonResponse({'exist': True})
        if User.objects.filter(email=email).exists():
            return JsonResponse({'status': 409})
        else:
            # Username does not exist
            user =User.objects.create(first_name=name,
                        username="91"+phone,
                        phone_number="91"+phone,
                        email=email,
                        is_sales=True
                        )
            # Create the sales executive associated with the distributor
            sales_executive = SalesExecutive.objects.create(user=user, distributor=distributor)
            messages.success(request, 'sales added successfully')
            return JsonResponse({'exist': False})
        
    sales_executive = paginate_items(request, sales_executive, 20)
       
    ctx ={
        'sales_executive':sales_executive
    }
    return TemplateResponse(request, 'distributor_add_executive.html', ctx)


@active_distributor_required
def assigned_retailer(request,pk):
    sales_executive = SalesExecutive.objects.filter(id=pk).first()
       
    if sales_executive is not None:
        retailers_list = sales_executive.retailer.all()
    else:
        retailers_list=[]
        
    search_query = request.GET.get('search_query')
    if search_query:
        retailers_list = retailers_list.filter(store_name__icontains=search_query)
    
    if request.method == 'POST':  
        retailer_id = request.POST.get('retailer_id')
        sfa_pk = request.POST.get('pk')
   
        if retailer_id == "":
            messages.error(request, 'Customer not found')
            return JsonResponse({"message":"error","status":200})
            
        
        if retailer_id: 
            # Proceed with retrieving objects and updating the database
            retailer_obj = Retailer.objects.filter(id=retailer_id).first()
            sales_executive = SalesExecutive.objects.filter(id=sfa_pk).first()
            
            if retailer_obj and sales_executive:
                # Check if the retailer is already associated with any sales executives
                if SalesExecutive.objects.filter(retailer=retailer_obj.id).exists():
                    # Retailer is Alredy associated with sales executive
                    messages.error(request,'Customer is already associated with another sales executive')
                    # return redirect('assigned-retailer',pk=sales_executive.id)
                    return JsonResponse({"message":"error","status":200})
                else:
                    # Add the retailer to the sales executive
                    sales_executive.retailer.add(retailer_obj)
                    
                    messages.success(request,'Customer Added Sucessfully')
                    # return redirect('assigned-retailer',pk=sales_executive.id)
                    return JsonResponse({"message":"success","status":200})
            else:
                messages.error(request, 'Customer or sales executive not found')
                return redirect('assigned-retailer',pk=sfa_pk)
        # retailer  remove action code 
        
        if request.POST.get('action'):
           action = request.POST.get('action')
           if action == 'remove':
            retailer_id = request.GET.get('retailer_id')
            try:
                # Fetch the retailer to remove based on the given pk
                retailer_to_remove = get_object_or_404(Retailer, id=retailer_id)
                sales_executives = SalesExecutive.objects.filter(id=pk,retailer=retailer_to_remove).first().retailer.remove(retailer_to_remove)
                messages.success(request, 'Customer Removed Successfully')
                return redirect('assigned-retailer',pk=pk)
            except:
                pass
                messages.error(request, 'Customer not found')
                return redirect('assigned-retailer',pk=pk)
        else:
            # Handle other actions if needed
            pass
        
    retailers_list = paginate_items(request, retailers_list, 20)
    ctx={
        'retailers_list':retailers_list,
        'sales_person_pk':pk
    }
    
    return TemplateResponse(request, 'distributor_retailer_assigne.html',ctx)


@active_admin_or_distributor_required
def get_retailer_names(request):
    
    if request.method == 'GET' and 'filter' in request.GET:
        filter_text = request.GET.get('filter')
        filtered_objects = Retailer.objects.filter(store_name__icontains=filter_text,is_activated=True)
        filtered_data = [{"name":obj.store_name, "id":obj.id,"user":obj.user.username} for obj in filtered_objects]
        return JsonResponse(filtered_data, safe=False)
   
        


@active_admin_or_sub_admin_required    
def onboard_retailers(request):
    if request.method == 'POST' and request.FILES.get('file'):
        csv_file = request.FILES['file']

        # Check if the uploaded file is a CSV file
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return TemplateResponse(request, 'onboard_retailers.html')

        User = get_user_model()
        organisation_obj = Organisation.objects.all().first()

        # Display a message indicating that retailer details are being uploaded
        messages.info(request, 'Uploading retailer details...')

        retailers_added = False  # Flag to track if any retailers were added successfully

        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            for row in reader:

                # Ensure that the username is treated as a string
                username = str(row.get('username', ''))
                phone_number = username  # Set phone_number to username

                # Check if the 'username' key exists and if it's empty
                if not username:
                    messages.error(request, 'Username not found or empty in CSV row. Skipping this row.')
                    continue

                # Check if the username already exists
                if User.objects.filter(username=username).exists():
                    messages.error(request, f'Username "{username}" already exists. Skipping this row.')
                    continue

                # Create a new user
                user = User.objects.create_user(
                    username=username,
                    phone_number=phone_number,  # Set phone_number to username
                    is_retailer=True,
                    last_login=datetime.now()
                )

                # Attempt to parse dates with flexibility
                try:
                    valid_from = parse_date(row.get('valid_from', ''))
                    valid_to = parse_date(row.get('valid_to', ''))
                except ValueError:
                    # Handle the case where date parsing fails
                    valid_from = None
                    valid_to = None

                # Create a new KYC entry
                kyc = KYC.objects.create(
                    user=user,
                    gst_number=row.get('gst_number', '')[:50],  # Limit to 50 characters
                    drug_license_number=row.get('drug_license_number', '')[:50],  # Limit to 50 characters
                    valid_from=valid_from, 
                    valid_to=valid_to,
                )

                # Ensure that the postal code is treated as a string
                postal_code = str(row.get('postal_code', ''))

                # Create a new retailer
                retailer = Retailer.objects.create(
                    user=user,
                    organisation=organisation_obj,
                    owner_name=row.get('owner_name', '')[:255],  # Limit to 255 characters
                    address=row.get('address', '')[:1000],  # Limit to 1000 characters (example limit)
                    state=row.get('state', '')[:50],  # Limit to 50 characters
                    city=row.get('city', '')[:50],  # Limit to 50 characters
                    postal_code=postal_code[:20],  # Limit to 20 characters
                    store_name=row.get('store_name', '')[:255],  # Limit to 255 characters
                    country='India',
                    is_activated=False,
                    kyc_status='not started',
                )

                retailers_added = True  # Set the flag indicating that a retailer was added successfully

            if retailers_added:
                messages.success(request, 'Retailers added successfully')
            else:
                messages.error(request, 'No retailers were added from the CSV file.')

        except Exception as e:
            messages.error(request, f'Error: {e}')

    return TemplateResponse(request, 'onboard_retailers.html')


@active_admin_or_distributor_required 
def download_file(request,param=None):
    if param == "download_partner_pincodes":
        filename = "Serviceable pincodes.csv"
        data = [['Pincode']]

    elif param == "download_format_retailer":
        filename = "download_format_customers.csv"
        data = [['Store Name','Phone Number']]
    elif param == "download_product_deals_format":
        filename = "Deals format.csv"
        data = [['Distributor Product Id','Distributor Product Name','Qty','Discount Percentage','Description']]
    elif param == "credit line":
        filename = "credit line format.csv"
        data = [['Customer Name','Phone Number','Credit Amount']]
    elif param == "commission discount":
        filename = "higher base discount format.csv"
        data = [['Customer Name','Phone Number','Discount']]
    elif param == "download_commission_upload_format":
        filename = "Distributor Commissions Upload Format.csv"
        data = [["distributor_id", "base_discount","base_discount_less_than", "base_discount_greater_than", 
                "mmc_cash", "mmc_credit", "dbc_commn", "deals_commn"]]
    elif param == "upload_sfa":
        filename = "Upload_by_Partner_Format.csv"
        data = [['Distributor Phone Number', 'SFA Phone Number', 'Retailer Phone Number']]
    elif param == "upload_sfa_with_override":
        filename = "Upload_by_Medley_Format.csv"
        data = [['SFA Phone Number', 'Retailer Phone Number']]
    else:
        # Handle unknown parameter values or no parameter provided
        return HttpResponse("Invalid parameter", status=400)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    for row in data:
        writer.writerow(row)

    return response

@active_admin_required
@csrf_exempt
def create_and_update_user(request):
    try:
        if request.method == 'POST':
            with transaction.atomic():
                def data_update_or_create(data,phone_no):
                    user,created = User.objects.update_or_create(username=phone_no,defaults=data)
                    return user
                form_data = json.loads(request.body)
                phone_no = form_data.get('phone_no')
                user_email = form_data.get('email')
                phone_no = "91"+str(phone_no)
                is_new_user = form_data.get('is_new_user')
                # user_id = form_data.get('user_id')
                
                if User.objects.filter(username=phone_no).exists() and is_new_user:
                    return JsonResponse({'message': 'Phone number already exists.', 'error_field': 'phone_no', 'status': 409})

                if is_new_user:
                    if User.objects.filter(email=user_email).exists():
                        return JsonResponse({'message': 'Email already exists.', 'error_field': 'email', 'status': 409})
                else:
                    if User.objects.filter(email=user_email).exclude(username=phone_no).exists():
                        return JsonResponse({'message': 'Email already exists.', 'error_field': 'email', 'status': 409})
         
                
                    
                data = {
                    "first_name": form_data.get('first_name'),
                    "last_name": form_data.get('last_name'),
                    "username": phone_no,
                    "email": form_data.get('email'),
                    "phone_number": phone_no,
                }
                if not is_new_user:
                    user_obj = User.objects.filter(username=phone_no).first()
                    user_exist_role = fetch_user_role(user_obj)
                    data.update({"is_"+str(user_exist_role):False})

                role_type = form_data.get('role_type')
                if role_type == "admin":
                    data["is_admin"] = True
                    user = data_update_or_create(data,phone_no)
                elif role_type == "callex":
                    data["is_callex"] = True
                    user = data_update_or_create(data,phone_no)
                elif role_type == "operation":
                    data["is_operation"] = True
                    user = data_update_or_create(data,phone_no)
                elif role_type == "marketing":
                    data["is_marketing"] = True
                    user = data_update_or_create(data,phone_no)
                elif role_type == "sales":
                    data["is_sales"] = True
                    user = data_update_or_create(data,phone_no)

                    if form_data.get('partner_id'):
                        distributor = Distributor.objects.get(id=form_data.get('partner_id'))
                        se,created = SalesExecutive.objects.update_or_create(user=user,defaults={"distributor":distributor})
                    else:
                        se,created = SalesExecutive.objects.update_or_create(user=user,defaults={"distributor":None})
                if is_new_user:
                    messages.success(request, ('User added successfully.'))
                else:
                    messages.success(request, ('Updated  successfully.'))
                return JsonResponse({'message': 'User added/updated successfully'}, status=200)
    except Distributor.DoesNotExist:
        return JsonResponse({'message': "Distributor not found.",'status':404})
    except Exception as e:
        return JsonResponse({'message': str(e),'status':400})
    
@active_admin_required 
def user_list(request,pk=None):
    if request.method=="POST":
        status = request.POST.get('action')
        user = User.objects.get(id=pk)
        if status == "activate":
            user.is_active=1
        elif status == 'deactivate':
            user.is_active=0
        user.save()
        return redirect('user-list')
    role_type = request.GET.get('user_role')
    mobile_number = request.GET.get('mobile_number')
    users = User.objects.filter(is_deleted=False).exclude(Q(is_superuser=True) | Q(is_distributor=True) | Q(is_retailer=True)).order_by('id')
    if role_type:
        if role_type == "admin":
            users = users.filter(is_admin=True)
        elif role_type == "callex":
            users = users.filter(is_callex=True)
        elif role_type == "operation":
            users = users.filter(is_operation=True)
        elif role_type == "sales":
            users = users.filter(is_sales=True)
        elif role_type == "marketing":
            users = users.filter(is_marketing=True)
    if mobile_number:
        users = users.filter(username__icontains=mobile_number)
    users = paginate_items(request, users, 20)
    ctx={
        "users":users
    }
    return TemplateResponse(request,'user_list.html',ctx)

@active_admin_or_sub_admin_required 
def sfa_admin_dashboard(request,pk=None):
    sales_executive=SalesExecutive.objects.filter(user__is_sales=True)
    distributor = Distributor.objects.all()
    
    
    if request.method=="POST":
        distributor_id = request.POST.get('distributor')
        retailer_id = request.POST.get('selectedRetailerId')
        retailer_obj = Retailer.objects.filter(id=retailer_id).first()
        distributor1=Distributor.objects.filter(id=distributor_id).first()
        sales_executive1 = SalesExecutive.objects.filter(id=pk).first()
        
        if SalesExecutive.objects.filter(retailer=retailer_id).exists():
            messages.error(request, ('Customer Already Mapped For Another Distributor'))
            
        else:
                    # Add the retailer to the sales executive
            sales_executive.create(distributor=distributor1)
            sales_executive1.retailer.add(retailer_obj)
            
            messages.success(request,'Customer Added Sucessfully')
            
    partner_name = request.GET.get('partner_name')
    executive_name = request.GET.get('executive_name')
    
    
    if partner_name:
        sales_executive = sales_executive.filter(distributor__name__icontains=partner_name)
    if executive_name:
        sales_executive = sales_executive.filter(user__first_name__icontains=executive_name)
            
    
    ctx={
       'distributors':distributor,
       'sales_executive':sales_executive 
    }
    
    return TemplateResponse(request,'dashboard_sales_executive.html',ctx)

@active_admin_required 
def retailer_assignment(request,pk):
    sales_executive = SalesExecutive.objects.filter(id=pk).first()
    if sales_executive is not None:
        retailers_list = sales_executive.retailer.all()
    else:
        retailers_list=[]
        
    search_query = request.GET.get('search_query')
    if search_query:
        retailers_list = retailers_list.filter(store_name__icontains=search_query)
    
    if request.method == 'POST':  
        retailer_id = request.POST.get('selectedRetailerId')
        sfa_pk = request.POST.get('pk') #dist_pk


        if retailer_id == "":
            messages.error(request, 'Customer not found')
            return redirect('retailer-assignment',pk=pk)
            
        
        if retailer_id: 
            # Proceed with retrieving objects and updating the database
            retailer_obj = Retailer.objects.filter(id=retailer_id).first()
            sales_executive = SalesExecutive.objects.filter(id=sfa_pk).first()
            
            if retailer_obj and sales_executive:
                # Check if the retailer is already associated with any sales executives
                if SalesExecutive.objects.filter(retailer=retailer_obj.id).exists():
                    # Retailer is Alredy associated with sales executive
                    messages.error(request,'Customer is already associated with another sales executive')
                    # return redirect('assigned-retailer',pk=sales_executive.id)
                    return redirect('retailer-assignment',pk=pk)
                else:
                    # Add the retailer to the sales executive
                    sales_executive.retailer.add(retailer_obj)
                    
                    messages.success(request,'Customer Added Sucessfully')
                    # return redirect('assigned-retailer',pk=sales_executive.id)
                    return redirect('retailer-assignment',pk=pk)
            else:
                messages.error(request, 'Customer or sales executive not found')
                return redirect('retailer-assignment',pk=sfa_pk)
            
        # retailer  remove action code 
        
        if request.POST.get('action'):
           action = request.POST.get('action')
           if action == 'remove':
            retailer_id = request.GET.get('retailer_id')
            try:
                # Fetch the retailer to remove based on the given pk
                retailer_to_remove = get_object_or_404(Retailer, id=retailer_id)
                sales_executives = SalesExecutive.objects.filter(id=pk,retailer=retailer_to_remove).first().retailer.remove(retailer_to_remove)
                messages.success(request, 'Customer Removed Successfully')
                return redirect('retailer-assignment',pk=pk)
            except:
                pass
                messages.error(request, 'Customer not found')
                return redirect('retailer-assignment',pk=pk)
        elif request.FILES['file']:
            uploaded_file = request.FILES['file']
            if uploaded_file.content_type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)  
                
            df.columns = [col.strip() for col in df.columns]
            required_columns = ['Retailer Phone Number']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return JsonResponse({'error': 'The file does not have mandatory columns.'}, status=400)
            extra_columns = [col for col in df.columns if col not in required_columns]
            if extra_columns:
                return JsonResponse({'error': 'The file contains extra columns.'}, status=400)
            
            nan_data = df[df[['Retailer Phone Number']].isnull().any(axis=1)].reset_index(drop=True)
            nan_data['Comment'] = 'Phone Number Not Available'
            duplicate_df = df[df.duplicated(subset='Retailer Phone Number', keep=False)]
            duplicate_df['Comment'] = 'Duplicate Retailer Phone Number'
            df['Retailer Phone Number'] = df['Retailer Phone Number'].astype('Int64', errors='ignore')
            wrong_data = pd.DataFrame()
            sales_executive = SalesExecutive.objects.filter(id=pk).first()
            for index, row in df.iterrows():
                retailer = Retailer.objects.filter(Q(user__username=row['Retailer Phone Number']) | Q(user__phone_number=row['Retailer Phone Number']),
                            user__is_active=True,
                            is_activated=True
                            ).first()
                if not retailer:
                    wrong_retailer_data = df[df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                    wrong_retailer_data['Comment'] = 'Invalid Retailer Number or Retailer Not Activated'
                    wrong_data = wrong_data._append(wrong_retailer_data, ignore_index=True)
                else:
                    sales_executive_for_retailer = SalesExecutive.objects.filter(retailer=retailer).first()                            
                    if not sales_executive_for_retailer:
                        sales_executive.retailer.add(retailer)
                        
                    elif sales_executive_for_retailer.user != sales_executive.user:                                
                        retailer_assign_to_other = df[df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                        retailer_assign_to_other['Comment'] = 'Retailer already Assignend to other Sales Person.'
                        wrong_data = wrong_data._append(retailer_assign_to_other, ignore_index=True)
                    else:
                        retailer_assign_to_self = df[df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                        retailer_assign_to_self['Comment'] = 'Retailer already Assignend to this Sales Person.'
                        wrong_data = wrong_data._append(retailer_assign_to_self, ignore_index=True)
            
            if len(wrong_data.index) or len(nan_data.index) or len(duplicate_df.index):
                wrong_data = pd.concat([wrong_data, nan_data], ignore_index=True)
                wrong_data = pd.concat([wrong_data, duplicate_df], ignore_index=True)
                wrong_data_csv_content = wrong_data.to_csv(index=False)
                response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename=Medley_SFA_Wrong_Data.csv'
                return response
            else: 
                return JsonResponse({'message': 'File uploaded successfully'}, status=200)
            
        else:
            # Handle other actions if needed
            pass
        
    store_name = request.GET.get('store_name')
    user_name = request.GET.get('user_name')
    medley_id=request.GET.get('medley_id')
    
    
    if store_name:
        retailers_list = retailers_list.filter(store_name__icontains=store_name)
    if user_name:
        retailers_list = retailers_list.filter(user__username__icontains=user_name)
    if medley_id:
        retailers_list = retailers_list.filter(medleyId__icontains=medley_id)
        
    retailers_list = paginate_items(request, retailers_list, 20)
    ctx={
        'retailers_list':retailers_list,
        'sales_person_pk':pk,
        'sales_executive':sales_executive
    }
    
    return TemplateResponse(request,'dashboard_retailer_assignment.html',ctx)
    
@active_admin_required 
def edit_user(request):
    try:
        user_id = request.GET.get('user_id')
        user = User.objects.get(id=user_id)
        data={}
        role = fetch_user_role(user)
        if role == 'sales':
            se = SalesExecutive.objects.filter(user=user).first()
            if se.distributor:
                data.update({"dist_name":se.distributor.name,'dist_id':se.distributor.id})
        data.update({
            "first_name":user.first_name,"last_name":user.last_name,
            "username":user.username,"email":user.email,"role":role
        })
        return JsonResponse({"data":data})
    except User.DoesNotExist:
        return JsonResponse({"message":'User not found','status':404})

# @active_admin_required
# def download_onboard_retailers(request):
#     try:
#         daterange = request.GET.get('daterange')

#         if daterange is None:
#             messages.error(request, 'Please select a date range.')
#             return redirect('download-onboard-retailers')

#         start_date, end_date = map(lambda x: datetime.strptime(x, '%m/%d/%Y').date(), daterange.split(' - '))
#         end_date = datetime.combine(end_date, datetime.max.time())
 
#         retailers_count = Retailer.objects.filter(created_at__range=[start_date, end_date]).count()

#         if retailers_count == 0:
#             return render(request, 'onboard_retailers.html', {'no_data': True})

#         retailers_created = Retailer.objects.filter(created_at__range=[start_date, end_date])

#         data = []

#         for retailer in retailers_created:
#             owner_name = retailer.owner_name
#             address = retailer.address
#             country = retailer.country
#             state = retailer.state
#             city = retailer.city
#             postal_code = retailer.postal_code
#             store_name = retailer.store_name
#             store_email = retailer.store_email
#             is_activated = retailer.is_activated
#             kyc_status = retailer.kyc_status

#             kyc_data = retailer.user.kyc_details

#             data.append({
#                 "Retailer Name": owner_name,
#                 "Address": address,
#                 "Country": country,
#                 "State": state,
#                 "City": city,
#                 "Postal Code": postal_code,
#                 "Store Name": store_name,
#                 "Store Email": store_email,
#                 "Is Activated": is_activated,
#                 "KYC Status": kyc_status,
#                 "Drug License Number": kyc_data.drug_license_number if kyc_data else "",
#                 "Valid From": kyc_data.valid_from.strftime('%Y-%m-%d') if kyc_data and kyc_data.valid_from else "",
#                 "Valid To": kyc_data.valid_to.strftime('%Y-%m-%d') if kyc_data and kyc_data.valid_to else "",
#                 "GST Number": kyc_data.gst_number if kyc_data else "",
#                 "Phone Number": retailer.user.phone_number,
#             })

#         df = pd.DataFrame(data)

#         if not df.empty:
#             response = HttpResponse(content_type='text/csv')
#             response['Content-Disposition'] = f'attachment; filename="Retailers_Onboarding_Report_{start_date}-{end_date}.csv"'
#             df.to_csv(response, index=False)

#             return response

#     except Exception as e:
#         messages.error(request, f'Error: {e}')
#         return redirect('download-onboard-retailers')



@active_admin_or_sub_admin_required
def download_onboard_retailers(request):
    date_range = request.GET.get('daterange')
    if date_range:
        start_date, end_date = date_range.split(' - ')
        start_date = datetime.strptime(start_date, '%m/%d/%Y')
        end_date = datetime.strptime(end_date, '%m/%d/%Y')

        # Make start_date timezone-aware
        start_date = timezone.make_aware(start_date, timezone.get_current_timezone())

        # Adjust end_date to include the end of the day (23:59:59)
        end_date = end_date + timedelta(days=1) - timedelta(seconds=1)
        end_date = timezone.make_aware(end_date, timezone.get_current_timezone())
        retailers = Retailer.objects.filter(created_at__range=[start_date, end_date])
            
        if not retailers:
            messages.error(request,'No data exists for the selected date range')
            return render(request, 'onboard_retailers.html')

    data = []
    for retailer in retailers:
        data.append({
            'user_id': retailer.user_id,
            'medleyId': retailer.medleyId,
            'organisation_id': retailer.organisation_id,
            'owner_name': retailer.owner_name,
            'address': retailer.address,
            'country': retailer.country,
            'state': retailer.state,
            'city': retailer.city,
            'postal_code': retailer.postal_code,
            'store_name': retailer.store_name,
            'phone_number': retailer.user.username,
            'store_pharmacist_name': retailer.store_pharmacist_name,
            'store_email': retailer.store_email,
            'store_geo_location': retailer.store_geo_location,
            'is_activated': retailer.is_activated,
            'kyc_status': retailer.kyc_status,
            'is_rejected': retailer.is_rejected,
            'created_at': retailer.created_at.strftime('%Y-%m-%d %H:%M:%S')  
        })
 
    df = pd.DataFrame(data)

    csv_data = df.to_csv(index=False)

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="retailers.csv"'

    return response
    
    
@active_backendTechAdmin_required 
def setting_configuration(request):
    if request.method == 'POST':
        if 'delete' in request.POST:
            setting_id = request.POST.get('delete')
            setting_delete = Settings.objects.filter(id = setting_id).first().delete()
            messages.success(request, 'Successfully Deleted.')
            return redirect('settings-configuration')
        else:  
            key = request.POST.get('key').strip()
            type = request.POST.get('type')
            value = request.POST.get('value').strip()
            is_active = True if request.POST.get('is_active')=='on' else False
            new_setting, created = Settings.objects.get_or_create(key=key, defaults={'type':type, 'value':value, 'is_active':is_active})
            msg = "Successfully Created."
            if not created:
                new_setting.type = type
                new_setting.value = value
                new_setting.is_active = is_active
                new_setting.updated_at = datetime.now()
                new_setting.save()
                msg = "Update Successfully."
            messages.success(request, f'"{key}" {msg}')
            return redirect('settings-configuration')
            
            
            # settings = Settings.objects.all().order_by('-updated_at')
            # ctx = {'settings':settings}
            # return TemplateResponse(request, 'settings.html', ctx)
    
    settings = Settings.objects.all().order_by('-updated_at')
    ctx = {'settings':settings}
    return TemplateResponse(request, 'settings.html', ctx)

@active_backendTechAdmin_required 
def retailer_enable(request):
    if request.method=='POST':
        userId = request.POST.get('user_id')
        userObj = User.objects.get(id=userId)
        userObj.is_deleted=False
        userObj.is_active=True
        userObj.save()
        return redirect('retailer-enable')
    
    disabled_retailers = User.objects.filter(is_deleted=True)
    disabled_retailers = paginate_items(request, disabled_retailers, 10)
    context = {'disabled_retailers': disabled_retailers}
    return TemplateResponse(request, 'retailer_enable.html', context)

@active_admin_required 
def reset_password(request):
    if request.method == "POST":
        password = request.POST.get('password') 
        user_id = request.POST.get("user_id")
        update_user = filter_by_attribute(User, {'id': user_id})
        update_user.set_password(password)
        update_user.save()
        messages.success(request,"Password updates successfully!")
        return redirect('reset-password')

    email_or_phone = request.GET.get('email_or_phone')
    if email_or_phone:
        if "@" in email_or_phone:
            is_user_exists = is_exists(User, {'email': email_or_phone})
            username = "email"
        else:
            if len(email_or_phone)==10:
                email_or_phone = "91" + email_or_phone
            is_user_exists = is_exists(User, {'username': email_or_phone})
            username="username"
            
        if is_user_exists:
            try:
                # user = get_object(User,{username:email_or_phone})
                filter_keys = {username:email_or_phone}
                user = User.objects.get(**filter_keys)
            except MultipleObjectsReturned:
                ctx={"error":"Multiple users found with the email/phone"}
                return render(request,"reset_password.html",ctx)
            if user.is_distributor or user.is_admin:
                ctx={
                    "user_id":user.id
                }
                return TemplateResponse(request,'password.html',ctx)
            else:
                ctx = {"error":"You are not registered as distributor!"}
                return render(request,'reset_password.html',ctx)
        else:
            ctx = {"error":"You are not registered with us!"}
            return render(request,'reset_password.html',ctx)
    return TemplateResponse(request,'reset_password.html')

@csrf_exempt
def upload_sfa_file_by_admin(request):
    if request.method == 'POST' and 'true' in request.POST.get('data') and request.FILES['file']:
        try:
            uploaded_file = request.FILES['file']
            if uploaded_file.content_type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)    
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['SFA Phone Number', 'Retailer Phone Number']
            missing_columns = [col for col in cols if col not in df.columns]
            if missing_columns:
                    return JsonResponse({'error': 'The file does not have mandatory columns.'}, status=400)
        except:
            return JsonResponse({'error': 'Somthing Wrong with File.'}, status=400)
        
        wrong_data = pd.DataFrame()
        for sales_phone_number in df['SFA Phone Number'].unique():
            sfa_user = User.objects.filter(username = sales_phone_number, is_sales = True, is_active = True).first() 
            
            if sfa_user:
                main_df_of_sales_person = df[df['SFA Phone Number'] == sales_phone_number]
                sales_executive = SalesExecutive.objects.filter(user=sfa_user, distributor__isnull=True).first()
                
                if sales_executive:
                    for index, row in main_df_of_sales_person.iterrows():
                        retailer = Retailer.objects.filter(Q(user__username=row['Retailer Phone Number']) | Q(user__phone_number=row['Retailer Phone Number']),
                                            user__is_active=True,
                                            is_activated=True
                                            ).first()
                        if not retailer:
                            wrong_retailer_data = main_df_of_sales_person[main_df_of_sales_person['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                            wrong_retailer_data['Comment'] = 'Invalid Retailer Number or Retailer Not Activated'
                            wrong_data = wrong_data._append(wrong_retailer_data, ignore_index=True)
                        else:
                            sales_executive_for_retailer = SalesExecutive.objects.filter(retailer=retailer).first() 
                            
                            if not sales_executive_for_retailer:
                                sales_executive.retailer.add(retailer)
                            else:
                                is_distributor_null = sales_executive_for_retailer.distributor is None
                                if is_distributor_null:
                                    sales_executive_for_retailer.retailer.remove(retailer)
                                    sales_executive.retailer.add(retailer)
                                else:
                                    wrong_df_of_retailer_sfa = main_df_of_sales_person[main_df_of_sales_person['Retailer Phone Number'] == row['Retailer Phone Number']]
                                    wrong_df_of_retailer_sfa['Comment'] = 'This sales person is not associated with Medley.'
                                    wrong_data = wrong_data._append(wrong_df_of_retailer_sfa,ignore_index=True)              
                else:
                    main_df_of_sales_person['Comment'] = 'This sales person is not associated with Medley.'
                    wrong_data = wrong_data._append(main_df_of_sales_person,ignore_index=True)  
                
            else:
                wrong_sales_phone_number = df[df['SFA Phone Number'] == sales_phone_number].copy()
                wrong_sales_phone_number['Comment'] = 'Wrong Sales Person No.'
                wrong_data = wrong_data._append(wrong_sales_phone_number, ignore_index=True)
            
            
        
        if len(wrong_data.index):
            wrong_data_csv_content = wrong_data.to_csv(index=False)
            response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=wrong_data.csv'
            return response
        else: 
            return JsonResponse({'message': 'File uploaded successfully'}, status=200)
    
    elif request.method == 'POST' and 'false' in request.POST.get('data') and request.FILES['file']:
        try:
            uploaded_file = request.FILES['file']
            correct_file, main_df, nan_data, duplicate_df = data_filtering(uploaded_file, is_super=True)
            if not correct_file:
                return JsonResponse({'error': 'The file does not have mandatory columns.'}, status=400)
        except:
            return JsonResponse({'error': 'Somthing Wrong with File.'}, status=400)
        
        wrong_data = pd.DataFrame()
        for dist_phone_number in main_df['Distributor Phone Number'].unique():
            distributor = User.objects.filter(username = dist_phone_number, is_distributor = True, is_active = True).first().distributor 
            if distributor:
                main_df_of_dist_person = main_df[main_df['Distributor Phone Number'] == dist_phone_number]                
                # Get Distributor's data and trying to save this.
                for sales_phone_number in main_df_of_dist_person['SFA Phone Number'].unique():
                    user = User.objects.filter(username = sales_phone_number, is_sales = True, is_active = True).first() 
                    if user:
                        main_df_of_sales_person = main_df_of_dist_person[main_df_of_dist_person['SFA Phone Number'] == sales_phone_number]
                        # main Df of sales person.
                        sales_executive, created = SalesExecutive.objects.get_or_create(user=user, distributor=distributor)
                        
                        if sales_executive:
                            for index, row in main_df_of_sales_person.iterrows():
                                retailer = Retailer.objects.filter(Q(user__username=row['Retailer Phone Number']) | Q(user__phone_number=row['Retailer Phone Number']),
                                            user__is_active=True,
                                            is_activated=True
                                            ).first()
                                if not retailer:
                                    wrong_retailer_data = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                                    wrong_retailer_data['Comment'] = 'Invalid Retailer Number or Retailer Not Activated'
                                    wrong_data = wrong_data._append(wrong_retailer_data, ignore_index=True)
                                else:
                                    sales_executive_for_retailer = SalesExecutive.objects.filter(retailer=retailer).first()                            
                                    if not sales_executive_for_retailer:
                                        sales_executive.retailer.add(retailer)
                                    elif sales_executive_for_retailer.user != user :                                
                                        retailer_assign_to_other = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                                        retailer_assign_to_other['Comment'] = 'Retailer already Assignend to other Sales Person.'
                                        wrong_data = wrong_data._append(retailer_assign_to_other, ignore_index=True)
                                    else:
                                        retailer_assign_to_self = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                                        retailer_assign_to_self['Comment'] = 'Retailer already Assignend to this Sales Person.'
                                        wrong_data = wrong_data._append(retailer_assign_to_self, ignore_index=True)
                        else:
                            main_df_of_sales_person['Comment'] = 'Not your Sales Person.'
                            wrong_data = wrong_data._append(main_df_of_sales_person,ignore_index=True)                          
                    else:
                        wrong_sales_phone_number = main_df_of_dist_person[main_df_of_dist_person['SFA Phone Number'] == sales_phone_number].copy()
                        wrong_sales_phone_number['Comment'] = 'Wrong Sales Person No.'
                        wrong_data = wrong_data._append(wrong_sales_phone_number, ignore_index=True)
                                         
            else:
                wrong_dist_phone_number = main_df[main_df['SFA Phone Number'] == dist_phone_number].copy()
                wrong_dist_phone_number['Comment'] = 'Wrong Distributor No.'
                wrong_data = wrong_data._append(wrong_dist_phone_number, ignore_index=True)

        if len(wrong_data.index) or len(nan_data.index) or len(duplicate_df.index):
            wrong_data = pd.concat([wrong_data, nan_data], ignore_index=True)
            wrong_data = pd.concat([wrong_data, duplicate_df], ignore_index=True)
            wrong_data_csv_content = wrong_data.to_csv(index=False)
            response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=wrong_data.csv'
            return response
        else: 
            return JsonResponse({'message': 'File uploaded successfully'}, status=200)
        
    else:
        return JsonResponse({'error': 'Somthing went Wrong.'}, status=400)


@csrf_exempt
def upload_sfa_file(request):
    if request.method == 'POST' and request.FILES['file']:
        try:
            uploaded_file = request.FILES['file']
            distributor = request.user.distributor
            correct_file, main_df, nan_data, duplicate_df = data_filtering(uploaded_file)
            if not correct_file:
                return JsonResponse({'error': 'The file does not have mandatory columns.'}, status=400)
        except:
            return JsonResponse({'error': 'Somthing Wrong with File.'}, status=400)

        wrong_data = pd.DataFrame()
        for sales_phone_number in main_df['SFA Phone Number'].unique():
            user = User.objects.filter(username = sales_phone_number, is_sales = True, is_active = True).first() 
            if user:
                main_df_of_sales_person = main_df[main_df['SFA Phone Number'] == sales_phone_number]
                sales_executive = SalesExecutive.objects.filter(user=user, distributor=distributor).first()
                if sales_executive:
                    for index, row in main_df_of_sales_person.iterrows():
                        retailer = Retailer.objects.filter(Q(user__username=row['Retailer Phone Number']) | Q(user__phone_number=row['Retailer Phone Number']),
                                    user__is_active=True,
                                    is_activated=True
                                    ).first()
                        if not retailer:
                            wrong_retailer_data = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                            wrong_retailer_data['Comment'] = 'Invalid Retailer Number or Retailer Not Activated'
                            wrong_data = wrong_data._append(wrong_retailer_data, ignore_index=True)
                        else:
                            sales_executive_for_retailer = SalesExecutive.objects.filter(retailer=retailer).first()                            
                            if not sales_executive_for_retailer:
                                sales_executive.retailer.add(retailer)
                            elif sales_executive_for_retailer.user != user :                                
                                retailer_assign_to_other = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                                retailer_assign_to_other['Comment'] = 'Retailer already Assignend to other Sales Person.'
                                wrong_data = wrong_data._append(retailer_assign_to_other, ignore_index=True)
                            else:
                                retailer_assign_to_self = main_df[main_df['Retailer Phone Number'] == row['Retailer Phone Number']].copy()
                                retailer_assign_to_self['Comment'] = 'Retailer already Assignend to this Sales Person.'
                                wrong_data = wrong_data._append(retailer_assign_to_self, ignore_index=True)                       
                else:
                    main_df_of_sales_person['Comment'] = 'Not your Sales Person.'
                    wrong_data = wrong_data._append(main_df_of_sales_person,ignore_index=True)                          
            else:
                wrong_sales_phone_number = main_df[main_df['SFA Phone Number'] == sales_phone_number].copy()
                wrong_sales_phone_number['Comment'] = 'Wrong Sales Person No.'
                wrong_data = wrong_data._append(wrong_sales_phone_number, ignore_index=True)

        if len(wrong_data.index) or len(nan_data.index) or len(duplicate_df.index):
            wrong_data = pd.concat([wrong_data, nan_data], ignore_index=True)
            wrong_data = pd.concat([wrong_data, duplicate_df], ignore_index=True)
            wrong_data_csv_content = wrong_data.to_csv(index=False)
            response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=wrong_data.csv'
            return response
        else: 
            return JsonResponse({'message': 'File uploaded successfully'}, status=200)
    else:
        return JsonResponse({'error': 'Somthing went Wrong.'}, status=400)


@active_distributor_required 
def distributor_retailers_list(request):
    if request.method == "POST":
        if 'store_name' in request.POST:
            storeName = request.POST.get('store_name')
            phoneNumber = request.POST.get('phone_number')
            phoneNumber = "91"+phoneNumber
            dist_retailer = DistributorMappedRetailer.objects.filter(phone_number=phoneNumber).first()
            if dist_retailer: 
                if request.user.distributor == dist_retailer.distributor:
                    # Phone number is registered with the current distributor
                    messages.warning(request, f'Sorry, "{phoneNumber}" is already registered with you.')
                    return redirect('distributor-retailers-list')
                else:
                    # Phone number is registered with another distributor
                    messages.warning(request, f'Sorry, "{phoneNumber}" is already registered with another distributor.')
                    return redirect('distributor-retailers-list')           
            else:
                user = User.objects.filter(Q(username=phoneNumber) | Q(phone_number=phoneNumber)).first()
                if user and not user.is_retailer: #Phone number already exists with another role
                    messages.warning(request, f'Sorry, "{phoneNumber}" already exists with another role.')
                    return redirect('distributor-retailers-list')            
                else:
                    medley_id = user.retailer.medleyId if user else "N/A"
                    dist_new_retailer = DistributorMappedRetailer.objects.create(
                                        distributor=request.user.distributor, 
                                        store_name = storeName, 
                                        phone_number = phoneNumber, 
                                        medleyId = medley_id  
                                        )
                    messages.success(request, f'"{storeName}" Successfully Created.')
                    return redirect('distributor-retailers-list')
            
        
        if request.FILES['file']:            
            uploaded_file = request.FILES['file']
            if uploaded_file.content_type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file) 
            if len(df) <= 0:
                return JsonResponse({'error': 'The file does not have Data.'}, status=409)
                
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['Store Name', 'Phone Number']
            missing_columns = [col for col in cols if col not in df.columns]
            if missing_columns:
                return JsonResponse({'error': 'The file does not have mandatory columns.'}, status=400)
            
            nan_data_df = df[df[['Store Name', 'Phone Number']].isnull().any(axis=1)].reset_index(drop=True)
            nan_data_df['Comment'] = 'Phone number/Store name Not Available'
            duplicate_data_df = df[df.duplicated(subset='Phone Number', keep=False)]
            duplicate_data_df['Comment'] = 'Duplicate Retailer Phone Number'
            
            df['Phone Number'] = df['Phone Number'].astype(str)
        
            invalid_phone_df = df[df['Phone Number'].astype(str).str.strip().str.match('^\d+$') == False].reset_index(drop=True)
            invalid_phone_df['Comment'] = 'Invalid Phone Number'
            
            df = df[df['Phone Number'].str.isdigit()]
            
            df = df.drop_duplicates(subset='Phone Number', keep=False)
            df = df.dropna()
            df = df.reset_index(drop=True)                
            df['Phone Number'] = df['Phone Number'].astype('Int64', errors='ignore') 
            wrong_data = pd.DataFrame()
            
            #------------------------start----------
            for index, row in df.iterrows():
                user = User.objects.filter(Q(username=row['Phone Number']) | Q(phone_number=row['Phone Number'])).first()
                if user and not user.is_retailer:
                    wrong_phone_number = df[df['Phone Number'] == row['Phone Number']].copy()
                    wrong_phone_number['Comment'] = 'Phone number already exists with another role.'
                    wrong_data = wrong_data._append(wrong_phone_number, ignore_index=True)
                else:
                    medley_id = user.retailer.medleyId if user else "N/A"
                    existing_retailer, created = DistributorMappedRetailer.objects.get_or_create(
                        phone_number=row['Phone Number'],
                        defaults={
                            'distributor': request.user.distributor,
                            'store_name': row['Store Name'],
                            'medleyId': medley_id
                        }
                    )
                    
                    if not created:
                        existing_retailer.store_name = row['Store Name']
                        existing_retailer.medleyId = medley_id
                        existing_retailer.save()
                        
                        already_assigned_to_other_dist = df[df['Phone Number'] == row['Phone Number']].copy()
                        already_assigned_to_other_dist['Comment'] = 'This Retailer already assigned to other Distributor.'
                        wrong_data = wrong_data._append(already_assigned_to_other_dist, ignore_index=True)
                        
            #---------------------end------------------
            
            wrong_data = pd.concat([wrong_data, nan_data_df], ignore_index=True)
            wrong_data = pd.concat([wrong_data, duplicate_data_df], ignore_index=True)
            wrong_data = pd.concat([wrong_data, invalid_phone_df], ignore_index=True)
            if len(wrong_data.index):
                wrong_data_csv_content = wrong_data.to_csv(index=False)
                response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename=wrong_data.csv'
                return response
            else:
                return JsonResponse({'message': 'File uploaded successfully'}, status=200)
    
    distributor = request.user.distributor
    data = DistributorMappedRetailer.objects.filter(distributor=distributor).order_by("-id")
    search_query = request.GET.get('search_query')

    if search_query:
       data = data.filter(Q(store_name__icontains=search_query) | Q(phone_number__icontains=search_query))

    retailers_list = paginate_items(request, data, 20)
    ctx = {'retailers_list':retailers_list}
    return TemplateResponse(request, 'distributor_retailers.html', ctx)


@active_admin_required
def commissions_report(request):
    if request.method == "POST":
        distributor_id = request.POST.get('distributors')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
             
        if distributor_id == 'select':
            messages.warning(request,"Please select at least one Distributor.")
            return redirect('commission-report-dashboard')
        elif distributor_id == 'all':
            distributor_ids = Commission.objects.values_list('distributor', flat=True).distinct()
            distributors = Distributor.objects.filter(id__in=distributor_ids)
            distributor_name ="All_Partners"
        else:        
            distributors = Distributor.objects.filter(id = distributor_id)
            distributor_name =distributors.first().name
            
        data_written = False

        for distributor in distributors:
            orders = Order.objects.filter(distributor=distributor, created_at__range=(start_date, end_date))
            if orders.exists():
                data_written = True
                break

        if not data_written:
            messages.warning(request, "No data available for the given date range and Partners.")
            return redirect('commission-report-dashboard')
            
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}_commission_report_from_{}_to_{}.csv"'.format(
           distributor_name, start_date, end_date)
        writer = csv.writer(response)
        writer.writerow(['Order ID','Order Date' , 'Store Name','Distibutor Name', 'Product SKU', 'Product Name', 
                         'PTR', 'MRP','Ordered Qty' ,'Billed Qty','Billed PTR' , 'Gross Amount', 'Invoice Number','Discount Amount','Final Gross Amount',
                         'Base Commission(%)', ' Deals Commission(%)',
                         'Base Commission on Amount', 'Deals Commission On Amount',
                         'Final Commisiosn',
                         'GST(%)', 'Final Payable'])
        
        for distributor in distributors:
            orders = Order.objects.filter(distributor = distributor,created_at__range=(start_date, end_date)).exclude(order_status__in=["Pending", "Cancelled"])
            
            for order in orders:
                retailer = order.user.retailer
                commission = 0
                order_trigger_date = order.created_at.date()
                                
                commission_obj = Commission.objects.filter(distributor = distributor).first()
                dist_maper = DistributorMappedRetailer.objects.filter(phone_number = order.user.username).exists()
                
                if dist_maper:
                    commission = commission_obj.dbc_commn if commission_obj else 0
                    
                # Get base_discount_gt or base_discount_lt
                elif commission_obj:
                    discount = CommissionDiscount.objects.filter(Q(end_date__gte=order_trigger_date) | Q(end_date__isnull=True),
                                                                 distributor=distributor,
                                                                 retailer=retailer, 
                                                                 start_date__lte=order_trigger_date
                                                                 ).first()

                    if discount and discount.base_discount >= commission_obj.base_discount:
                        commission = commission_obj.base_discount_gt
                    elif discount and discount.base_discount < commission_obj.base_discount:
                        commission = commission_obj.base_discount_lt
                    # Checking Credit Line of retailer
                    else:
                        credit_line_obj = CreditLine.objects.filter(Q(end_date__gte=order_trigger_date) | Q(end_date__isnull=True),
                                                                    distributor=distributor,
                                                                    retailer=retailer,
                                                                    start_date__lte=order_trigger_date
                                                                    ).first()
                        if credit_line_obj:
                            commission = commission_obj.mmc_credit
                        else:
                            commission = commission_obj.mmc_cash
                    
                # getting item wise deals
                invoice = order.invoices.all().first()
                items = order.ordereditem_set.all()
                for item in items:
                    product = item.product
                    deals_obj = Deal.objects.filter(Q(end_date__gte=order_trigger_date) | Q(end_date__isnull=True),
                                                    distributor=distributor, 
                                                    product=product,
                                                    start_date__lte=order_trigger_date
                                                    ).first() 
                               
                    if deals_obj and item.quantity >= deals_obj.quantity:
                        item_commission = commission_obj.deals_commn
                    else:
                        item_commission = 0
                    if item.build_qty:
                        gross_amount = item.unit_price*item.build_qty
                    else:
                        gross_amount = item.unit_price*item.quantity
                    discount = (float(item.unit_price * item.discount)/ 100 )* item.build_qty
                    # print (discount)
                    base_commission = commission 
                    deals_commission = item_commission 
                    # invoice_amount = invoice.invoice_amount if invoice else 0
                    final_gross_amount = Decimal(gross_amount) - Decimal(discount)
                    base_commission_amount = (final_gross_amount*base_commission)/100
                    deals_commission_amount = (final_gross_amount*deals_commission)/100
                    final_commission = base_commission_amount+deals_commission_amount
                    
                    writer.writerow([order.id, 
                                    order.order_date,
                                    retailer.store_name, 
                                    distributor.name, 
                                    product.distributor_sku,
                                    product.name,
                                    product.ptr,
                                    product.mrp,
                                    item.quantity,
                                    item.build_qty,
                                    item.unit_price,
                                    gross_amount,
                                    invoice.invoice_number if invoice else "",
                                    discount,
                                    final_gross_amount,
                                    base_commission,
                                    deals_commission, 
                                    base_commission_amount,
                                    deals_commission_amount,
                                    # invoice_amount,
                                    # order.total_amount if invoice_amount == 0 else 0,
                                    final_commission,
                                    0 if final_commission==0 else 18,
                                    final_commission * (Decimal(1) + Decimal(18) / Decimal(100))
                                    ])
            
        return response
    all_commission_distributor = Commission.objects.all()
    ctx = {'distributors':all_commission_distributor}
    return TemplateResponse(request, 'commission_report.html', ctx)

@active_admin_or_sub_admin__distributor_required
def credit_line(request):
    if request.method == "POST":
        #BULK DELETE AND SINGLE DELETE 
        # if 'bulk_delete' in request.POST:
        #     deal_ids = request.POST.getlist('selected_products[]')
        #     if deal_ids:
        #         distributor = get_object_or_404(Distributor, user=request.user)
        #         for retailer_id in deal_ids:
        #             commission_discount = get_object_or_404(CreditLine, distributor=distributor, retailer=retailer_id)
        #             commission_discount.delete()
        #         messages.success(request, 'Selected Credit Amount deleted successfully.')
        #         return redirect('credit-line')
        #     else:
        #         messages.warning(request, 'Please select atleast one')
        #         return redirect('credit-line')
                
        # if 'delete_ratailer_credit' in request.POST:
        #     delete_retailer = request.POST.get('delete_ratailer_credit')
        #     distributor = get_object_or_404(Distributor, user=request.user)
        #     credit = get_object_or_404(CreditLine, distributor=distributor, retailer=delete_retailer)
        #     credit.delete()
        #     messages.success(request,'Deleted Successfully.')
        #     return redirect('credit-line')
        
        if request.FILES['file']:            
            uploaded_file = request.FILES['file']
            if uploaded_file.content_type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            if df.empty:
                return JsonResponse({'error': 'The file is empty.'}, status=400)
            df = df.dropna(subset=['Phone Number', 'Credit Amount'], how='all')
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['Phone Number','Credit Amount']
            missing_columns = [col for col in cols if col not in df.columns]
            if missing_columns:
                return JsonResponse({'error': 'The file does not have '+",".join(missing_columns)+ ' column.'}, status=400)
            
            nan_data_df = df[df[['Phone Number','Credit Amount']].isnull().any(axis=1)].reset_index(drop=True)
            df = df.dropna(subset=['Phone Number', 'Credit Amount']).reset_index(drop=True)
            nan_data_df['Comment'] = 'Phone number/Credit Amount Not Available'
            duplicate_data_df = df[df.duplicated(subset='Phone Number', keep=False)]
            duplicate_data_df['Comment'] = 'Duplicate Retailer Phone Number'
            
            negative_creditline_amount_df = df[df['Credit Amount'] < 0].copy()
            negative_creditline_amount_df['Comment'] = "Credit amount with negative value found."
            df = df[df['Credit Amount'] >= 0]
            df = df.drop_duplicates(subset=['Phone Number'])
            # df = df.dropna()
            df = df.reset_index(drop=True)                
            if request.user.is_superuser or request.user.is_admin:  
                distributor_id = request.POST.get('partner_id') 
                end_date = request.POST.get('end_date')
                if distributor_id:
                    distributor = Distributor.objects.filter(id=int(distributor_id)).first()
                else:
                    return JsonResponse({'error': 'Please select the Partner.'}, status=400)
                    
            else:
                distributor = Distributor.objects.filter(user=request.user).first()
            if not distributor:
                return JsonResponse({'error': 'Please provide valid partner ID.'}, status=400)
            df['Phone Number'] = df['Phone Number'].astype('Int64', errors='ignore') 
            wrong_data = pd.DataFrame()
            bulk_credit_obj_create=[]
            bulk_credit_obj_update=[] 
            update_or_create = False
            
            for index, row in df.iterrows():
                user = User.objects.filter(Q(username=row['Phone Number']) | Q(phone_number=row['Phone Number'])).first()
                if distributor and user and user.is_retailer:
                    retailer = Retailer.objects.filter(user=user).first()
                    credit_line = CreditLine.objects.filter(Q(is_expired=False) | Q(is_expired__isnull=True), distributor=distributor, retailer=retailer).first()
                    if credit_line:
                        if credit_line.start_date == datetime.now().date()+timedelta(days=1):
                            wrong_phone_number = df[df['Phone Number'] == row['Phone Number']].copy()
                            wrong_phone_number['Comment'] = 'This data already exists for the same date.'
                            wrong_data = wrong_data._append(wrong_phone_number, ignore_index=True)
                            continue
                        
                        if credit_line.start_date is None and credit_line.end_date is None:
                            credit_line.start_date = credit_line.created_at.date()
                            credit_line.end_date = datetime.now().date()
                            credit_line.is_expired = True
                            bulk_credit_obj_update.append(credit_line)
                            
                        elif credit_line.start_date is not None:
                            credit_line.end_date = datetime.now().date() if credit_line.end_date is None else datetime.now().date()
                            credit_line.is_expired = True
                            bulk_credit_obj_update.append(credit_line)
                        
                        new_credit_line = CreditLine(
                            distributor=distributor,
                            retailer=retailer,
                            credit_amount=row['Credit Amount'],
                            end_date = end_date if end_date else None
                        )
                        bulk_credit_obj_create.append(new_credit_line)
                        
                    else:
                        new_credit_line = CreditLine(
                            distributor=distributor,
                            retailer=retailer,
                            credit_amount=row['Credit Amount'],
                            end_date = end_date if end_date else None
                        )
                        bulk_credit_obj_create.append(new_credit_line)
                else:
                    wrong_phone_number = df[df['Phone Number'] == row['Phone Number']].copy()
                    wrong_phone_number['Comment'] = 'Not valid Phone number / Phone number already exists with another role.'
                    wrong_data = wrong_data._append(wrong_phone_number, ignore_index=True)
            if bulk_credit_obj_create:
                update_or_create = True
                CreditLine.objects.bulk_create(bulk_credit_obj_create)

            if bulk_credit_obj_update:
                update_or_create = True
                CreditLine.objects.bulk_update(bulk_credit_obj_update, ['credit_amount','created_at','start_date' ,'end_date','is_expired'])
            
            wrong_data = pd.concat([wrong_data, nan_data_df, duplicate_data_df, negative_creditline_amount_df], ignore_index=True)
            if len(wrong_data.index):
                wrong_data_csv_content = wrong_data.to_csv(index=False)
                response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename=wrong_creditline_data.csv'
                return response
            elif update_or_create:
                return JsonResponse({'message': 'File uploaded successfully'}, status=200)
            else:
                return JsonResponse({'error': 'Something went wrong.'}, status=400)
    today = date.today()
    credit_line_details = CreditLine.objects.prefetch_related('retailer__user').filter((Q(end_date__gte=today) | Q(end_date__isnull=True))).all()
    template_to_extend = "dashboard.html"
    filter_expression = Q()
    retailer_name = request.GET.get('retailer_name')
    if retailer_name:
        filter_expression &= Q(retailer__store_name__icontains=retailer_name)
    if request.user.is_distributor:
        template_to_extend = "distributor_base.html"
        distributor = Distributor.objects.filter(user=request.user).first()
        credit_line_details = credit_line_details.filter(distributor=distributor)
    else:
        partner_id = request.GET.get('selectedPartnerId')
        partner_name = request.GET.get('partner_name')
        if partner_id:
            filter_expression &= Q(distributor_id=partner_id)
        if partner_name:
            filter_expression &= Q(distributor__name__icontains=partner_name)
            
    credit_line_details = credit_line_details.filter(filter_expression).order_by('-created_at')
    credit_line_details = paginate_items(request, credit_line_details, 20)
    ctx={
        "credit_line_details":credit_line_details,
        "template_to_extend":template_to_extend
    }
    return TemplateResponse(request,'credit_line_details.html',ctx)


@active_admin_or_sub_admin__distributor_required
def commission_discount(request):
    if request.method == "POST":
        retailer_id = request.POST.get('retailerId')
        distributor_id = request.POST.get('distributorId')
        if request.POST.get("retailerId"):
            distributor = get_object_or_404(Distributor, user=request.user)
            commission_discount = get_object_or_404(CommissionDiscount, distributor=distributor, retailer=retailer_id)
            new_discount = request.POST.get('editDiscount')
            commission_discount.base_discount = new_discount
            commission_discount.save()
            messages.success(request,"Discount Updated Successfully.")
            return redirect('commission-discount')
        
        #BULK DELETE AND SINGLE DELETE 
        # if 'bulk_delete' in request.POST:
        #     deal_ids = request.POST.getlist('selected_products[]')
        #     if deal_ids:
        #         distributor = get_object_or_404(Distributor, user=request.user)
        #         for retailer_id in deal_ids:
        #             commission_discount = get_object_or_404(CommissionDiscount, distributor=distributor, retailer=retailer_id)
        #             commission_discount.delete()
        #         messages.success(request, 'Selected deals deleted successfully.')
        #         return redirect('commission-discount')
        #     else:
        #         messages.warning(request, 'Please select atleast one')
        #         return redirect('commission-discount')
                   
        # if 'delete_ratailer_discount' in request.POST:
        #     delete_retailer = request.POST.get('delete_ratailer_discount')
        #     distributor = get_object_or_404(Distributor, user=request.user)
        #     commission_discount = get_object_or_404(CommissionDiscount, distributor=distributor, retailer=delete_retailer)
        #     commission_discount.delete()
        #     messages.success(request,'Deleted Successfully.')
        #     return redirect('commission-discount')
            
        if request.FILES['file']:            
            uploaded_file = request.FILES['file']
            if uploaded_file.content_type == "text/csv":
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file) 
            if df.empty:
                return JsonResponse({'error': 'The file is empty.'}, status=400)
            df = df.dropna(subset=['Phone Number', 'Discount'], how='all')
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['Phone Number','Discount']
            missing_columns = [col for col in cols if col not in df.columns]
            if missing_columns:
                return JsonResponse({'error': 'The file does not have '+",".join(missing_columns)+ ' column.'}, status=400)
            
            nan_data_df = df[df[['Phone Number','Discount']].isnull().any(axis=1)].reset_index(drop=True)
            df = df.dropna(subset=['Phone Number', 'Discount']).reset_index(drop=True)
            
            nan_data_df['Comment'] = 'Phone number/Discount Not Available'
            duplicate_data_df = df[df.duplicated(subset='Phone Number', keep=False)]
            duplicate_data_df['Comment'] = 'Duplicate Retailer Phone Number'
            
            negative_higherbase_discount_df = df[df['Discount'] < 0].copy()
            negative_higherbase_discount_df['Comment'] = "Discount with negative value found."
            df = df[df['Discount'] >= 0]
            df = df.drop_duplicates(subset=['Phone Number'])
            # df = df.dropna()
            df = df.reset_index(drop=True)
            if request.user.is_superuser or request.user.is_admin:  
                distributor_id = request.POST.get('partner_id') 
                end_date = request.POST.get('end_date')
                if distributor_id:
                    distributor = Distributor.objects.filter(id=int(distributor_id)).first()
                else:
                    return JsonResponse({'error': 'Please select the Partner'}, status=400)           
            else:
                distributor = Distributor.objects.filter(user=request.user).first()
            if not distributor:
                return JsonResponse({'error': 'Please provide valid partner ID.'}, status=400)
            df['Phone Number'] = df['Phone Number'].astype('Int64', errors='ignore') 
            wrong_data = pd.DataFrame()
            bulk_credit_obj_create=[]
            bulk_credit_obj_update=[] 
            update_or_create = False 
            
            for index, row in df.iterrows():
                user = User.objects.filter(Q(username=row['Phone Number']) | Q(phone_number=row['Phone Number'])).first()
                if distributor and user and user.is_retailer:
                    retailer = Retailer.objects.filter(user=user).first()
                    commission_disc = CommissionDiscount.objects.filter(Q(is_expired=False) | Q(is_expired__isnull=True),distributor=distributor, retailer=retailer).first()
                    if commission_disc:
                        if commission_disc.start_date == datetime.now().date()+timedelta(days=1):
                            wrong_phone_number = df[df['Phone Number'] == row['Phone Number']].copy()
                            wrong_phone_number['Comment'] = 'This data already exists for the same date.'
                            wrong_data = wrong_data._append(wrong_phone_number, ignore_index=True)
                            continue
                        
                        if commission_disc.start_date is None and commission_disc.end_date is None:
                            commission_disc.start_date = commission_disc.created_at.date()
                            commission_disc.end_date = datetime.now().date()
                            commission_disc.is_expired = True
                            bulk_credit_obj_update.append(commission_disc)
                            
                        elif commission_disc.start_date is not None:
                            commission_disc.end_date = datetime.now().date() if commission_disc.end_date is None else commission_disc.end_date
                            commission_disc.is_expired = True
                            bulk_credit_obj_update.append(commission_disc)
                        
                        new_credit_line = CommissionDiscount(
                            distributor=distributor,
                            retailer=retailer,
                            base_discount=row['Discount'],
                            end_date = end_date if end_date else None
                        )
                        bulk_credit_obj_create.append(new_credit_line)
                                   
                    else:
                        new_credit_line = CommissionDiscount(
                            distributor=distributor,
                            retailer=retailer,
                            base_discount=row['Discount'],
                            end_date = end_date if end_date else None
                        )
                        bulk_credit_obj_create.append(new_credit_line)
                else:
                    wrong_phone_number = df[df['Phone Number'] == row['Phone Number']].copy()
                    wrong_phone_number['Comment'] = 'Not valid Phone number / Phone number already exists with another role.'
                    wrong_data = wrong_data._append(wrong_phone_number, ignore_index=True)

            if bulk_credit_obj_create:
                update_or_create = True
                CommissionDiscount.objects.bulk_create(bulk_credit_obj_create)

            if bulk_credit_obj_update:
                update_or_create = True
                CommissionDiscount.objects.bulk_update(bulk_credit_obj_update, ['base_discount','created_at','start_date' ,'end_date','is_expired'])
            
            wrong_data = pd.concat([wrong_data, nan_data_df, duplicate_data_df, negative_higherbase_discount_df], ignore_index=True)
            if len(wrong_data.index):
                wrong_data_csv_content = wrong_data.to_csv(index=False)
                response = HttpResponse(wrong_data_csv_content, content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename=wrong_higherbase_discount_data.csv'
                return response
            elif update_or_create:
                return JsonResponse({'message': 'File uploaded successfully'}, status=200)
            else:
                return JsonResponse({'error': 'Something went wrong.'}, status=400)
    today = date.today()
    commission_discount_list = CommissionDiscount.objects.prefetch_related('retailer__user').filter((Q(end_date__gte=today) | Q(end_date__isnull=True))).all()
    template_to_extend = "dashboard.html"
    filter_expression = Q()
    retailer_name = request.GET.get('retailer_name')
    if retailer_name:
        filter_expression &= Q(retailer__store_name__icontains=retailer_name)
    if request.user.is_distributor:
        template_to_extend = "distributor_base.html"
        distributor = Distributor.objects.filter(user=request.user).first()
        commission_discount_list = commission_discount_list.filter(distributor=distributor)
    else:
        partner_id = request.GET.get('selectedPartnerId')
        partner_name = request.GET.get('partner_name')
        if partner_id:
            filter_expression &= Q(distributor_id=partner_id)
        if partner_name:
            filter_expression &= Q(distributor__name__icontains=partner_name)
    commission_discount_list = commission_discount_list.filter(filter_expression).order_by('-created_at')
    commission_discount_list = paginate_items(request, commission_discount_list, 20)
    ctx={
        "commission_discount":commission_discount_list,
        "template_to_extend":template_to_extend
    }
    return TemplateResponse(request,'commission_discount.html',ctx)

@active_backendTechAdmin_required 
def delete_users(request):
    if request.method=='POST':
        user_id = request.POST.get('user_id')
        user = get_object_or_404(User, id=user_id)
        user.is_deleted = True
        user.is_active = False
        user.save()
        messages.success(request, f' User ID "{user_id}" Successfully Deleted.')
        return JsonResponse({'status': 'success'})
    
    phone_no = request.GET.get('mobile_number')
    status = request.GET.get('status')
    users = User.objects.filter(is_retailer = True, is_deleted = False).order_by('id')
    # user_role = request.GET.get('user_role')
    # if user_role=="on":
    #     users = users.filter(is_deleted=1)
    if phone_no:
        users = users.filter(username__icontains=phone_no)
        
    users = paginate_items(request, users, 10)
    ctx = {
        "users":users
    }
    return TemplateResponse(request,'all_users_list.html',ctx)
    
def chatbot_index(request):
    return TemplateResponse(request,'index.html')

@marketing_admin_required
def marketing_dashboard(request):
    return render(request, 'marketing_dashboard.html')

@marketing_admin_required        
def marketing_upload_mobile_app_banner(request):
    if request.method == 'POST':
        if 'delete_banner' in request.POST:
            delete_banner_id = request.POST.get('delete_banner_id')
            delete_banner = Banner.objects.get(id=delete_banner_id)
            if delete_banner:
                delete_banner.delete()
        else:   
            image_file = request.FILES.get('uploaded_banner')
            if image_file:
                new_banner = Banner()
                new_banner.title = image_file.name
                new_banner.image = get_unique_doc(image_file)
                new_banner.uploaded_by = request.user
                new_banner.save()
                messages.success(request,'Banner Upload Successfully.')
            else:
                messages.error(request,'Please Upload a Banner.')
                
            return redirect ('marketing-upload-mobile-app-banner')
              
    all_banners = Banner.objects.all()
    document_urls = []

    for banner in all_banners:
        if banner.image:
            image_path = str(banner.image)  # Ensure the image path is a string
            presigned_url = generate_presigned_url(image_path)
            document_urls.append({
                'id': banner.id,
                'title': banner.title,
                'created_at': banner.created_at,
                'uploaded_by': banner.uploaded_by,
                'image_name': banner.image.name,
                'presigned_url': presigned_url,
            })
    ctx={'banners':all_banners,
         'document_urls':document_urls}
    return TemplateResponse(request,'marketing_upload_banner.html', ctx)


from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
import smtplib


def contact_us_form(request):
    if request.method == 'POST':
    
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        message = request.POST.get('message')

        # Create the email
        sender_email = EMAIL_HOST_USER
        sender_pass = EMAIL_HOST_PASSWORD
        msg = MIMEMultipart()
        body = f"""
        
        Hi Team,
            
            Please find the contact details form Medleymed Network:

            Name: {name}
            Phone: {phone}
            Message: {message}
        
        Thanks,
        support@medleymednetwork
        
        """
        body_part = MIMEText(body, 'plain')
        msg['Subject'] = "Contact Details"
        msg['From'] = sender_email
        msg['To'] = ', '.join(MAIL_TO)
        msg['Cc'] = ', '.join(CC_TO)
        msg.attach(body_part)
        
        # Send the email
        try:
            smtp_obj = smtplib.SMTP(host=EMAIL_HOST, port=EMAIL_PORT)
            smtp_obj.ehlo()
            smtp_obj.starttls()
            smtp_obj.login(sender_email, sender_pass)
            smtp_obj.sendmail(msg['From'], MAIL_TO + CC_TO, msg.as_string())
            smtp_obj.quit()
            messages.success(request, 'Sent Successfully.')
        except Exception as e:
            print(f"Error sending email: {e}")
            messages.error(request, 'Failed to send email. Please try again later.')
    
    return TemplateResponse(request,'contact_us.html')

