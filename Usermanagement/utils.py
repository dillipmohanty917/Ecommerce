# from statistics import mode
import pytz
from b2b2.settings import TIME_ZONE,AWS_STORAGE_BUCKET_NAME,AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY,backendTechAdmin,AWS_REGION

from .models import *
from django.core import serializers
from django.contrib.auth.decorators import login_required ,user_passes_test
from django.http import JsonResponse
from datetime import date
import pandas as pd
import uuid
from botocore.config import Config
import logging
import boto3
from botocore.exceptions import ClientError
from django.http import JsonResponse
logger = logging.getLogger(__name__)

""" Filter by attributes"""
def filter_by_attribute(modelName, filterKeys):
    return modelName.objects.get(**filterKeys)
"""Filter"""
def filter_attribute(modelName, filterKeys):
    return modelName.objects.filter(**filterKeys)
    
"""Authenticate access token"""
def authenticate_token(modelName, access_token):
    return modelName.objects.filter(access_token=access_token)

"""Authenticate admin"""
def authenticate_admin(modelName, user_id):
    return modelName.objects.filter(id=user_id)



"""Update"""
def update(modelName, filterKeys, updateWith):
    # updateWith.update({'updated_at':datetime.datetime.now()})
    return modelName.objects.filter(**filterKeys).update(**updateWith) 

"""Fetch all"""
def fetch_all(modelName):
    return modelName.objects.all()

""" Create"""
def store(modelName, values):
    return modelName.objects.create(**values)

""" Delete"""
def delete(modelName, filterKeys):
    return modelName.objects.filter(**filterKeys).delete()

def filter_with_values(modelName, filterKeys):
    return modelName.objects.filter(**filterKeys).values()

""" check is exists """
def is_exists(modelName, filterKeys):
    return modelName.objects.filter(**filterKeys).exists()

""" check object count """
def obj_count(modelName, filterKeys):
    return modelName.objects.filter(**filterKeys).count()

def get_object(modelName, filterKeys):
    return modelName.objects.get(**filterKeys)

def validate_user_otp_web(data,otp):
    if len(data)==12 and len(otp)==6:
        return True
    else:
        return False
    
def OTP_Validity(phone):  
    otp_obj = filter_by_attribute(OTP,{'phone':phone})
    if otp_obj:
        send_time = otp_obj.created_at.replace(tzinfo=pytz.UTC)  # Assuming created_at is a datetime object with UTC timezone
        indian_timezone = pytz.timezone(TIME_ZONE)
        send_time = send_time.astimezone(indian_timezone)
        current_time = datetime.now(indian_timezone)
        time_difference = (current_time - send_time).total_seconds() / 60  # Convert seconds to minutes
        if time_difference <= 10:
            return True
        else:
            return False
    else:
        return None
    
admin_login_required = user_passes_test(lambda user: user.is_superuser)

def active_admin_required(view_func):
    decorated_view_func = login_required(admin_login_required(view_func))
    return decorated_view_func

admin_or_sub_admin_login_required = user_passes_test(lambda user: user.is_superuser or user.is_admin and user.is_active)

def active_admin_or_sub_admin_required(view_func):
    decorated_view_func = login_required(admin_or_sub_admin_login_required(view_func))
    return decorated_view_func

marketing_admin_login_required = user_passes_test(lambda user: user.is_marketing and user.is_active )

def marketing_admin_required(view_func):
    decorated_view_func = login_required(marketing_admin_login_required(view_func))
    return decorated_view_func

distributor_login_required = user_passes_test(lambda user: user.is_distributor and user.is_active)

def active_distributor_required(view_func):
    decorated_view_func = login_required(distributor_login_required(view_func))
    return decorated_view_func


admin_or_distributor_login_required = user_passes_test(
    lambda user: user.is_superuser or user.is_distributor or user.is_admin)

def active_admin_or_distributor_required(view_func):
    decorated_view_func = login_required(admin_or_distributor_login_required(view_func))
    return decorated_view_func

backendTechAdmin_login_required = user_passes_test(lambda user: user.username==backendTechAdmin and user.is_active)

def active_backendTechAdmin_required(view_func):
    decorated_view_func = login_required(backendTechAdmin_login_required(view_func))
    return decorated_view_func

admin_or_sub_admin__distributor_login_required = user_passes_test(lambda user: user.is_superuser or user.is_admin or user.is_distributor and user.is_active)

def active_admin_or_sub_admin__distributor_required(view_func):
    decorated_view_func = login_required(admin_or_sub_admin__distributor_login_required(view_func))
    return decorated_view_func

def process_form_data(request,**kwargs):
    form_data = {}
    for field_name in request.POST:
        value = request.POST.get(field_name)
        form_data[field_name] = value
    return form_data


def process_uploaded_file(field,file,required_columns, columns_to_convert,filter_expected_columns):
    if str(file).lower().endswith('.csv'):
        file_data = pd.read_csv(file, dtype=columns_to_convert, parse_dates=[])
    elif str(file).lower().endswith('.xlsx'):
        file_data = pd.read_excel(file, dtype=columns_to_convert, parse_dates=[])
    elif str(file).lower().endswith('.xls'):
        file_data = pd.read_excel(file, dtype=columns_to_convert, parse_dates=[])
    # else:
    #     return JsonResponse({"error": True, "status": 400, "message": "Invalid file format"})
    file_data = file_data.dropna(how='all')
    all_unused_columns = [col for col in file_data.columns if "Unnamed" in str(col)] + [col for col in file_data.columns if col not in filter_expected_columns]
    file_data = file_data.drop(all_unused_columns, axis=1)
    # if len(file_data) == 0 or len(file_data) == "":
    #     return JsonResponse({"error": True, "status": 204})
    # if len(file_data) >= 40001:
    #     return JsonResponse({"error": True, "status": 400, "message": "File exceeds maximum allowed rows"})
    columns_partial_fillna_with_empty = []
                    
    if field.product_category not in file_data.columns:
        field.product_category = "product_category"
        file_data[field.product_category] = 'Branded'
    else:
        file_data[field.product_category] = file_data[field.product_category].where(pd.notna(file_data[field.product_category]), 'Branded')
    if field.product_composition not in file_data.columns:
        field.product_composition = 'product_composition'
        file_data[field.product_composition] = ""
    else:
        columns_partial_fillna_with_empty.append(field.product_composition)
    if field.manufacturer not in file_data.columns:
        field.manufacturer = "manufacturer"
        file_data[field.manufacturer] = ""
    else:
        columns_partial_fillna_with_empty.append(field.manufacturer)
    if field.scheme_billed not in file_data.columns:
        field.scheme_billed = "scheme_billed"
        file_data[field.scheme_billed] = 0
    else:
        file_data[field.scheme_billed] = file_data[field.scheme_billed].fillna(0)
    if field.scheme_free not in file_data.columns:
        field.scheme_free = "scheme_free"
        file_data[field.scheme_free] = 0
    else:
        file_data[field.scheme_free] = file_data[field.scheme_free].fillna(0)
    if field.hsncode not in file_data.columns:
        field.hsncode = "hsn"
        file_data[field.hsncode] = ""
    else:
        columns_partial_fillna_with_empty.append(field.hsncode)
    if field.packing not in file_data.columns:
        field.packing = "packing"
        file_data[field.packing] = ""
    else:
        columns_partial_fillna_with_empty.append(field.packing)
    
    if field.batch_number not in file_data.columns:
        field.batch_number = "batch_number"
        file_data[field.batch_number] = ""
    else:
        columns_partial_fillna_with_empty.append(field.batch_number)
    
    if field.expiry_date not in file_data.columns:
        field.expiry_date = "expiry_date"
        file_data[field.expiry_date] = ""
    else:
        columns_partial_fillna_with_empty.append(field.expiry_date)
        
    if field.discount not in file_data.columns:
        field.discount = "discount"
        file_data[field.discount] = 0
    else:
        file_data[field.discount] = file_data[field.discount].fillna(0)
    
    if field.gst not in file_data.columns:
        field.gst = "gst"
        file_data[field.gst] = 0
    else:
        file_data[field.gst] = file_data[field.gst].fillna(0)
    
    
    columns_partial_fillna_with_empty=list(set(columns_partial_fillna_with_empty))
    if columns_partial_fillna_with_empty:
        file_data[columns_partial_fillna_with_empty] = file_data[columns_partial_fillna_with_empty].where(pd.notna(file_data[columns_partial_fillna_with_empty]), "")
    
    columns_to_check = required_columns
    file_data = file_data.dropna(subset=columns_to_check, how='any')
    return file_data

def generate_unique_code():
    return uuid.uuid4()

def get_unique_doc(doc):
    try:
        file_extn = '.' + doc.content_type.split('/')[1]
        doc.name = doc.name.rstrip(file_extn)
        doc.name = str(generate_unique_code()) + file_extn
        return doc
    except Exception as e:
            logger.error("exception occcured in get_unique_doc function", str(e))



def generate_presigned_url(file_key):
    try:
        s3_client = boto3.client('s3',
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                             config=Config(signature_version='s3v4', region_name=AWS_REGION))

        presigned_url = s3_client.generate_presigned_url('get_object',
                                                             Params={'Bucket': AWS_STORAGE_BUCKET_NAME, 'Key': file_key},
                                                             ExpiresIn=3600)  # URL expires in 1 hour
        return presigned_url

    except ClientError as e:
        # Handle exceptions
        return JsonResponse({'error': str(e)}, status=500)

def calculate_growth_percentage(orders_query, today_total):
    today_date = date.today()
    yesterday = datetime.now() - timedelta(days=1)
    
    yesterday_orders = orders_query.filter(order_date__date=yesterday.date())
    yesterday_total_amount_sum = float(yesterday_orders.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'] or 0.00) 
    try:
        amount_percentage_growth = ((today_total - yesterday_total_amount_sum) / yesterday_total_amount_sum) * 100
    except:
        amount_percentage_growth=0.00
    
    
    today_orders_count = orders_query.filter(order_date__date=today_date).count()
    try:
        orers_percentage_growth = ((today_orders_count - yesterday_orders.count()) / yesterday_orders.count()) * 100
    except:
        orers_percentage_growth=0.00

    retailers = Retailer.objects.all()
    today_retailers_count = retailers.filter(created_at = today_date).count()
    yesterday_retailers_count = retailers.filter(created_at = yesterday.date()).count()
    try:
        retailer_percentage_growth = ((today_retailers_count - yesterday_retailers_count) / yesterday_retailers_count) * 100
    except:
        retailer_percentage_growth=0.00
    
    return amount_percentage_growth, orers_percentage_growth, retailer_percentage_growth


def fetch_user_role(user):
    if user.is_admin:
        role = 'admin'
    elif user.is_callex:
        role = 'callex'
    elif user.is_operation:
        role = 'operation'
    elif user.is_sales:
        role = 'sales'
    elif user.is_marketing:
        role = 'marketing'
    return role
    
def data_filtering(uploaded_file, is_super=None):
    if uploaded_file.content_type == "text/csv":
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)    
    cols_stripped = [col.strip() for col in df.columns]
    df.columns = cols_stripped
    cols = ['Distributor Phone Number', 'SFA Phone Number', 'Retailer Phone Number'] if is_super else ['SFA Phone Number', 'Retailer Phone Number']
    missing_columns = [col for col in cols if col not in df.columns]
    
    if not missing_columns:  
        main_df = df[['Distributor Phone Number', 'SFA Phone Number', 'Retailer Phone Number']] if is_super else df[['SFA Phone Number', 'Retailer Phone Number']]
        
        if is_super:
            nan_data = main_df[main_df[['Distributor Phone Number', 'SFA Phone Number', 'Retailer Phone Number']].isnull().any(axis=1)].reset_index(drop=True)
            nan_data['Comment'] = 'Phone Number Not Available'
        else:
            nan_data = main_df[main_df[['SFA Phone Number', 'Retailer Phone Number']].isnull().any(axis=1)].reset_index(drop=True)
            nan_data['Comment'] = 'Phone Number Not Available'
        
        duplicate_df = main_df[main_df.duplicated(subset='Retailer Phone Number', keep=False)]
        duplicate_df['Comment'] = 'Duplicate Retailer Phone Number'
        
        main_df = main_df.drop_duplicates(subset='Retailer Phone Number', keep=False)
        main_df = main_df.dropna()
        main_df = main_df.reset_index(drop=True)
        
        if is_super:
            main_df['Distributor Phone Number'] = main_df['Distributor Phone Number'].astype('Int64', errors='ignore') 
        main_df['SFA Phone Number'] = main_df['SFA Phone Number'].astype('Int64', errors='ignore')
        main_df['Retailer Phone Number'] = main_df['Retailer Phone Number'].astype('Int64', errors='ignore')         
        return True, main_df, nan_data, duplicate_df
    else:
        return False, None, None, None

