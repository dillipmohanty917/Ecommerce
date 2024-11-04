import uuid
import bcrypt
from Usermanagement.models import ServiceablePincode, User, OTP, UserToken, Retailer, Organisation
import requests
from django.contrib.auth import authenticate
from datetime import datetime, timedelta
from django.utils import timezone
import re
import secrets
import boto3
from b2b2 import settings
from b2b2.settings import AWS_STORAGE_BUCKET_NAME,AWS_ACCESS_KEY_ID,AWS_SECRET_ACCESS_KEY
from Productmanagement.models import Deal, DistProductMaster
from b2b2.settings import SHOW_OTP_PHONE_NUMBERS,SHOW_OTP,TEXTLOCAL_API_KEY
    
""" Generate OTP, Storing OTP and Sending SMS """
def generate_store_and_send_otp(mobile):
    otp = OTP.generate_otp(mobile)
    if mobile in SHOW_OTP_PHONE_NUMBERS:
        otp = SHOW_OTP
    store_user_otp, created = OTP.objects.get_or_create(phone=mobile, defaults={'otp_code': otp, 'is_otp_verified': False})
    if not created:
        store_user_otp.otp_code = otp
        store_user_otp.is_otp_verified = False
        store_user_otp.created_at = timezone.now()
        store_user_otp.expires_at = timezone.now()+timezone.timedelta(minutes=2)
        store_user_otp.save()
    sendername='MEDLEY'
    msg='Dear user, your login attempt has been recorded. Please verify your account using OTP - '+otp+' Note: The OTP will be expired in 10 minutes.Regards,Team MedleyMed'
    url ='https://api.textlocal.in/send/?apikey='+TEXTLOCAL_API_KEY+'&sender='+sendername+'&numbers='+mobile+'&message='+msg
    f=requests.get(url)
    return otp

""" Phone Number Validating """
def is_valid_phone_number_and_otp(phone_number, otp=None):
    valied_otp = False
    pattern = re.compile(r'^\d{10}$')
    match = pattern.match(phone_number)
    if otp and len(otp)==6:
        valied_otp = True
    return bool(match), valied_otp

""" Validating User Role """
def validate_user_role(phone):
    try:
        user=User.objects.filter(username=phone).first()
        if user and (user.is_superuser or user.is_distributor or user.is_admin):
            return False
        return True
    except:
        return True

""" Validating TO OTP """   
def OTP_Validity(otp_obj):
    current_time = timezone.now()
    expire_time_str = otp_obj.expires_at
    is_not_Expired = current_time < expire_time_str #  811 < 826
    return True if is_not_Expired else False

""" Creating New User And Retailer """
def create_new_user_and_retailer(phone, otp):
    create_new_user = User(username=phone,
                        is_active=True,
                        phone_number=phone,
                        is_retailer=True,
                        last_login=datetime.now())
    create_new_user.set_password(otp)
    create_new_user.save()
    organisation_obj = Organisation.objects.all().first()
    create_new_retailer = Retailer(user=create_new_user, organisation=organisation_obj)
    create_new_retailer.save()
    return create_new_user

""" Creating Token And also giving Authenticate """
def autologin(request, phone, otp, user):
    if authenticate(username=phone, password=otp):
        try:
            random_number = secrets.randbelow(10**6)
            token = bcrypt.hashpw(str(random_number).encode(), bcrypt.gensalt(rounds=12))
            token_str = token.decode('utf-8')
            store_user_token, created = UserToken.objects.get_or_create(user=user, defaults={'access_token': token_str})
            if not created:
                store_user_token.access_token = token_str
                store_user_token.created_at = datetime.now()
                store_user_token.expires_at = datetime.now() + timedelta(days=5)
                store_user_token.save()
            return  token_str  
        except:
            return False
    return False

def get_user(access_token):
    user  = UserToken.objects.get(access_token=access_token).user
    return user

def generate_unique_code():
    return uuid.uuid4()
    
def get_unique_doc(doc):
    file_extn = '.' + doc.content_type.split('/')[1]
    doc.name = doc.name.rstrip(file_extn)
    doc.name = str(generate_unique_code()) + file_extn
    return doc


def upload_image_to_s3(file_name, file_data):
    s3_client = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    try:
        file_path = f"notification/{file_name}"
        response = s3_client.put_object(
            Bucket=AWS_STORAGE_BUCKET_NAME,
            Key=file_path,
            Body=file_data.read(),
            ContentType=file_data.content_type  
        )
        return response['ResponseMetadata']['HTTPStatusCode'] == 200
    except Exception as e:
        print(f"Error uploading image to S3: {e}")
        return False

def send_push_notification(notification, image_url=None):
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Basic {settings.ONESIGNAL_API_KEY}"
    }

    payload = {
        "app_id": settings.ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "contents": {"en": notification}
    }

    if image_url:
        payload["big_picture"] = image_url
        payload["ios_attachments"] = {"id1": image_url}

    response = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, json=payload)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"Error response: {response.text}")
        # raise err