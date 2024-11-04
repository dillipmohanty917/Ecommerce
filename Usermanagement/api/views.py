import logging
from Paymentmanagement.models import Invoice, Payment
from Usermanagement.api.serializers import (
    DistProductMasterSerializer,
    SendOTPSerializer,
)
from django.db.models import Q
from Activitylog.models import ActivityLog
from Usermanagement.utils import generate_presigned_url
from rest_framework.decorators import (
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from Productmanagement.models import Deal, DistProductMaster
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from Usermanagement.api.serializers import SendOTPSerializer, VerifyOTPSerializer
from Usermanagement.models import Banner, Commission, Distributor, SalesExecutive, User, OTP, ServiceablePincode, Settings
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .serializers import DistributorSerializer, FeedbackSerializer, MyProfileSerializer, OTPSerializer, RetailerSerializer, SalesExecutiveSerializer, SendOTPSerializer, VerifyAccessTokenSerializer, VerifyAccessTokenSerializercallex
from Ordermanagement.models import Cart, Order, OrderedItem
from django.db.models import Sum, F
from .utils import (
    get_unique_doc,
    get_user,
    is_valid_phone_number_and_otp,
    upload_image_to_s3,
    validate_user_role,
    generate_store_and_send_otp,
    OTP_Validity,
    autologin,
    create_new_user_and_retailer,
)
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from Usermanagement.models import Retailer, KYC, Document, User
from rest_framework.permissions import AllowAny
import logging
from django.db import transaction

from b2b2.settings import S3_LINK, CONTACT_US, version, VERSION_CHECK
from b2b2.env import *
from django.http import HttpResponse
import pandas as pd
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from django.core.mail import EmailMultiAlternatives
from datetime import date, timedelta



logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def SendLoginOTP(request):
    if request.method == "POST":
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data["phone"]
        is_phone_validated, is_valied_otp = is_valid_phone_number_and_otp(phone_number)
        if is_phone_validated:
            phone_number = "91" + phone_number
        else:
            return Response(
                {"message": "Please enter valid phone number"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if phone_number:
            user = User.objects.filter(username=phone_number).first()
            if user:
                if user.is_active == False or user.is_deleted ==True:
                    return Response({"message": f"Your account is deleted or inactive. Please contact at {CONTACT_US.get('email')} for assistance."},
                                    status=status.HTTP_400_BAD_REQUEST)
            
        is_retailer_user = validate_user_role(phone_number)
        if is_retailer_user != True:
            return Response(
                {"message": "You are not a retailer.Kindly login in our web portal"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            otp_code = generate_store_and_send_otp(phone_number)
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {str(e)}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        response_data = OTPSerializer({"phone": phone_number, "otp": otp_code}).data
        return Response(response_data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def VerifyOTP(request):
    if request.method == "POST":
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number, entered_otp = (
            serializer.validated_data["phone"],
            serializer.validated_data["otp"],
        )

        is_phone_validated, is_valied_otp = is_valid_phone_number_and_otp(
            phone_number, entered_otp
        )  # Phone no will be 10 digit and otp will be 6 digit, then it will valied.
        if not is_phone_validated and not is_valied_otp:
            return Response(
                {"message": "Invalid OTP/Phone"}, status=status.HTTP_400_BAD_REQUEST
            )
        phone_number = "91" + phone_number
        try:
            otp_object = (
                OTP.objects.filter(phone=phone_number)
                .order_by("created_at")
                .first()
            )
            wrong_otp_or_not = False if otp_object.otp_code==entered_otp else True
            if wrong_otp_or_not:
                return Response({"message": "Wrong OTP entered."}, status=status.HTTP_400_BAD_REQUEST)
            OTP_status = OTP_Validity(otp_object) if otp_object else False
            if OTP_status:
                is_retailer_exists = User.objects.filter(
                    username=phone_number,is_retailer = True
                ).first()
                is_sales_exists = User.objects.filter(
                    username=phone_number,is_sales = True
                ).first()
                if is_retailer_exists:
                    is_retailer_exists.set_password(entered_otp)
                    is_retailer_exists.save()
                    user_access_token = autologin(
                        request, phone_number, entered_otp, is_retailer_exists
                    )
                    response_data = VerifyAccessTokenSerializer(
                        {
                            "phone": phone_number,
                            "access_token": user_access_token,
                            "role" : "retailer",
                            "is_retailer": True,
                            "message": "Login Successful",
                        }
                    ).data
                    logger.info("Retailer OTP verification successful")
                    return Response(response_data, status=status.HTTP_200_OK)
                elif is_sales_exists:
                    is_sales_exists.set_password(entered_otp)
                    is_sales_exists.save()
                    user_access_token = autologin(
                        request, phone_number, entered_otp, is_sales_exists
                    )
                    response_data = VerifyAccessTokenSerializercallex(
                        {
                            "phone": phone_number,
                            "access_token": user_access_token,
                            "role" : "sales",
                            "is_sales": True,
                            "message": "Login Successful",
                        }
                    ).data
                    logger.info("Retailer OTP verification successful")
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    new_user = create_new_user_and_retailer(phone_number, entered_otp)
                    user_access_token = autologin(
                        request, phone_number, entered_otp, new_user
                    )
                    response_data = VerifyAccessTokenSerializer(
                        {
                            "phone": phone_number,
                            "access_token": user_access_token,
                            "role" : "retailer",
                            "is_retailer": True,
                            "message": "Login Successful",
                        }
                    ).data
                    logger.info("Retailer OTP verification successful")
                    return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"message": "The OTP has expired"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {str(e)}")
            return Response(
                {"message": f"OOPS.. Something Went Wrong, Please Try Again."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@csrf_exempt
@permission_classes([AllowAny])
def retailer_kyc(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 

    try:
            retailer, created = Retailer.objects.get_or_create(user=user)
            kyc, kyc_created = KYC.objects.get_or_create(user=user)
            document, document_created = Document.objects.get_or_create(
                uploaded_by=user
            )

            existing_kyc_status = retailer.kyc_status if retailer else None

            updated_data = {}

            if 'owner_name' in request.POST:
                retailer.owner_name = request.POST['owner_name']
                updated_data['owner_name'] = retailer.owner_name
            if 'store_name' in request.POST:
                retailer.store_name = request.POST['store_name']
                updated_data['store_name'] = retailer.store_name
            if 'address' in request.POST:
                retailer.address = request.POST['address']
                updated_data['address'] = retailer.address
            if 'city' in request.POST:
                retailer.city = request.POST['city']
                updated_data['city'] = retailer.city
            if 'state' in request.POST:
                retailer.state = request.POST['state']
                updated_data['state'] = retailer.state
            if 'postal_code' in request.POST:
                retailer.postal_code = request.POST['postal_code']
                updated_data['postal_code'] = retailer.postal_code
            if 'phone_number' in request.POST:
                user.phone_number = request.POST['phone_number']
                new_phone_number = user.phone_number
                if len(new_phone_number) == 10 :
                    user.phone_number = '91' + new_phone_number
                elif new_phone_number.startswith('91') and len(new_phone_number) == 12:
                    user.phone_number = new_phone_number
                else:
                    return JsonResponse({"message": "Invalid Phone Number Format."}, status=401)

                user.save()
                updated_data['phone_number'] = user.phone_number

            retailer.save()

            if 'valid_from' in request.POST:
                kyc.valid_from = request.POST['valid_from']
                updated_data['valid_from'] = kyc.valid_from
            if 'valid_to' in request.POST:
                kyc.valid_to = request.POST['valid_to']
                updated_data['valid_to'] = kyc.valid_to
            if 'drug_license_number' in request.POST:
                kyc.drug_license_number = request.POST['drug_license_number']
                updated_data['drug_license_number'] = kyc.drug_license_number
            if 'gst_number' in request.POST:
                kyc.gst_number = request.POST['gst_number']
                updated_data['gst_number'] = kyc.gst_number

            kyc.save()

            if any(updated_data):
                retailer.kyc_status = 'pending'
                retailer.save()

            if request.FILES.get('store_image') :
                document.store_image = get_unique_doc(request.FILES['store_image'])
                # upload_image_to_s3(document.store_image, request.FILES['store_image'])
            if request.FILES.get('drug_license_form20'):
                document.drug_license_form20 = get_unique_doc(request.FILES['drug_license_form20'])
                # upload_image_to_s3(document.drug_license_form20, request.FILES['drug_license_form20'])
            if request.FILES.get('drug_license_form21'):
                document.drug_license_form21 = get_unique_doc(request.FILES['drug_license_form21'])
                # upload_image_to_s3(document.drug_license_form21, request.FILES['drug_license_form21'])
            if request.FILES.get('gst_image'):
                document.gst_image = get_unique_doc(request.FILES['gst_image'])
                # upload_image_to_s3(document.gst_image, request.FILES['gst_image'])
            document.save()

            if any(request.FILES):
                retailer.kyc_status = 'pending'
                retailer.save()

            response_data = {
                "message": "Retailer data updated successfully",
                "data": {
                    "owner_name": retailer.owner_name,
                    "store_name": retailer.store_name,
                    "address": retailer.address,
                    "city": retailer.city,
                    "state": retailer.state,
                    "postal_code": retailer.postal_code,
                    "phone_number": user.phone_number,
                    "valid_from": kyc.valid_from,
                    "valid_to": kyc.valid_to,
                    "drug_license_number": kyc.drug_license_number,
                    "gst_number": kyc.gst_number,
                    
                    "store_image_url":  generate_presigned_url(str(document.store_image)) if document.store_image else None,
                    "drug_license_form20_url":  generate_presigned_url(str(document.drug_license_form20)) if document.drug_license_form20 else None,
                    "drug_license_form21_url": generate_presigned_url(str(document.drug_license_form21)) if document.drug_license_form21 else None,
                    "gst_image_url": generate_presigned_url(str(document.gst_image)) if document.gst_image else None,
                    
                    # "store_image_url": S3_LINK+str(document.store_image) if document.store_image else None,
                    # "drug_license_form20_url": S3_LINK+str(document.drug_license_form20) if document.drug_license_form20 else None,
                    # "drug_license_form21_url": S3_LINK+str(document.drug_license_form21) if document.drug_license_form21 else None,
                    # "gst_image_url": S3_LINK+str(document.gst_image) if document.gst_image else None,
                    "kyc_status": retailer.kyc_status if any(updated_data) or any(request.FILES) else existing_kyc_status
                }
            }
            ActivityLog.log_activity(user=user, action="New KYC", details=f"New KYC submited successfully by retailer:-'{user.username}'.", to_user=user)
            logger.info("Retailer data updated successfully")
            return JsonResponse(response_data, status=200)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return JsonResponse({"message": "Internal Server Error"}, status=500)

    
@api_view(["PUT"])
@permission_classes([AllowAny])
def edit_retailer_kyc(request):
    try:
        access_token = request.META.get("HTTP_ACCESSTOKEN")
        retailer_id = request.headers.get("retailer-id")
        
        if retailer_id:
            ret = Retailer.objects.get(id = retailer_id)
            user = ret.user
        else:
            user = get_user(access_token)
    except KeyError:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 

    try:
        # with transaction.atomic():
            retailer, created = Retailer.objects.get_or_create(user=user)
            kyc, kyc_created = KYC.objects.get_or_create(user=user)
            document, document_created = Document.objects.get_or_create(
                uploaded_by=user
            )

            existing_kyc_status = retailer.kyc_status if retailer else None

            updated_data = {}

            if 'owner_name' in request.POST:
                retailer.owner_name = request.POST['owner_name']
                updated_data['owner_name'] = retailer.owner_name
            if 'store_name' in request.POST:
                retailer.store_name = request.POST['store_name']
                updated_data['store_name'] = retailer.store_name
            if 'address' in request.POST:
                retailer.address = request.POST['address']
                updated_data['address'] = retailer.address
            if 'city' in request.POST:
                retailer.city = request.POST['city']
                updated_data['city'] = retailer.city
            if 'state' in request.POST:
                retailer.state = request.POST['state']
                updated_data['state'] = retailer.state
            if 'postal_code' in request.POST:
                retailer.postal_code = request.POST['postal_code']
                updated_data['postal_code'] = retailer.postal_code
            if 'phone_number' in request.POST:
                user.phone_number = request.POST['phone_number']
                new_phone_number = user.phone_number
                if len(new_phone_number) == 10 :
                    user.phone_number = '91' + new_phone_number
                elif new_phone_number.startswith('91') and len(new_phone_number) == 12:
                    user.phone_number = new_phone_number
                else:
                    return JsonResponse({"message": "Invalid Phone Number Format."}, status=401)

                user.save()
                updated_data['phone_number'] = user.phone_number

            retailer.save()

            if 'valid_from' in request.POST:
                kyc.valid_from = request.POST['valid_from']
                updated_data['valid_from'] = kyc.valid_from
            if 'valid_to' in request.POST:
                kyc.valid_to = request.POST['valid_to']
                updated_data['valid_to'] = kyc.valid_to
            if 'drug_license_number' in request.POST:
                kyc.drug_license_number = request.POST['drug_license_number']
                updated_data['drug_license_number'] = kyc.drug_license_number
            if 'gst_number' in request.POST:
                kyc.gst_number = request.POST['gst_number']
                updated_data['gst_number'] = kyc.gst_number

            kyc.save()

            if any(updated_data):
                retailer.kyc_status = 'pending'
                retailer.save()

            if request.FILES.get('store_image') :
                document.store_image = get_unique_doc(request.FILES['store_image'])
                # upload_image_to_s3(document.store_image, request.FILES['store_image'])
            if request.FILES.get('drug_license_form20'):
                document.drug_license_form20 = get_unique_doc(request.FILES['drug_license_form20'])
                # upload_image_to_s3(document.drug_license_form20, request.FILES['drug_license_form20'])
            if request.FILES.get('drug_license_form21'):
                document.drug_license_form21 = get_unique_doc(request.FILES['drug_license_form21'])
                # upload_image_to_s3(document.drug_license_form21, request.FILES['drug_license_form21'])
            if request.FILES.get('gst_image'):
                document.gst_image = get_unique_doc(request.FILES['gst_image'])
                # upload_image_to_s3(document.gst_image, request.FILES['gst_image'])
            document.save()

            if any(request.FILES):
                retailer.kyc_status = 'pending'
                retailer.save()

            response_data = {
                "message": "Retailer data updated successfully",
                "data": {
                    "owner_name": retailer.owner_name,
                    "store_name": retailer.store_name,
                    "address": retailer.address,
                    "city": retailer.city,
                    "state": retailer.state,
                    "postal_code": retailer.postal_code,
                    "phone_number": user.phone_number,
                    "valid_from": kyc.valid_from,
                    "valid_to": kyc.valid_to,
                    "drug_license_number": kyc.drug_license_number,
                    "gst_number": kyc.gst_number,
                                     
                    "store_image_url":  generate_presigned_url(str(document.store_image)) if document.store_image else None,
                    "drug_license_form20_url":  generate_presigned_url(str(document.drug_license_form20)) if document.drug_license_form20 else None,
                    "drug_license_form21_url": generate_presigned_url(str(document.drug_license_form21)) if document.drug_license_form21 else None,
                    "gst_image_url": generate_presigned_url(str(document.gst_image)) if document.gst_image else None,
                    
                    # "store_image_url": S3_LINK+str(document.store_image) if document.store_image else None,
                    # "drug_license_form20_url": S3_LINK+str(document.drug_license_form20) if document.drug_license_form20 else None,
                    # "drug_license_form21_url": S3_LINK+str(document.drug_license_form21) if document.drug_license_form21 else None,
                    # "gst_image_url": S3_LINK+str(document.gst_image) if document.gst_image else None,
                    "kyc_status": retailer.kyc_status if any(updated_data) or any(request.FILES) else existing_kyc_status
                }
            }
            ActivityLog.log_activity(user=user, action="KYC Edited", details=f"Edit KYC data submited successfully by retailer:-'{user.username}'.", to_user=user)
            logger.info("Retailer data updated successfully")
            return JsonResponse(response_data, status=200)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return JsonResponse({"message": "Internal Server Error"}, status=500)
    
    
    
    
@api_view(["POST"])
@csrf_exempt
@permission_classes([AllowAny])
def register_retailer(request):
    try:
        owner_name = request.data.get("owner_name")
        store_name = request.data.get("store_name")
        address = request.data.get("address")
        city = request.data.get("city")
        state = request.data.get("state")
        postal_code = request.data.get("postal_code")
        phone_number = request.data.get("phone_number")
        valid_from = request.data.get("valid_from")
        valid_to = request.data.get("valid_to")
        drug_license_number = request.data.get("drug_license_number")
        gst_number = request.data.get("gst_number")
        
        user_exists = User.objects.filter(username = '91' +phone_number).first()
        if user_exists:
            return Response({"message":"Phone number already exists"}, status=400) 
        with transaction.atomic():
            user = User.objects.create(
                username= '91' +phone_number,  
                phone_number= '91' +phone_number,
                is_retailer=True 
            )

            retailer = Retailer.objects.create(
                user=user,
                owner_name=owner_name,
                store_name=store_name,
                address=address,
                city=city,
                state=state,
                postal_code=postal_code
            )

            kyc = KYC.objects.create(
                user=user,
                valid_from=valid_from,
                valid_to=valid_to,
                drug_license_number=drug_license_number,
                gst_number=gst_number
            )

            document = Document.objects.create(
                uploaded_by=user
            )

            for field_name, file_name in [
                ('store_image', 'store_image'),
                ('drug_license_form20', 'drug_license_form20'),
                ('drug_license_form21', 'drug_license_form21'),
                ('gst_image', 'gst_image'),
            ]:
                if request.FILES.get(field_name):
                    setattr(document, file_name, get_unique_doc(request.FILES[field_name]))

            document.save()

        response_data = {
            "message": "Retailer data created successfully",
            "data": {
                "owner_name": owner_name,
                "store_name": store_name,
                "address": address,
                "city": city,
                "state": state,
                "postal_code": postal_code,
                "phone_number": phone_number,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "drug_license_number": drug_license_number,
                "gst_number": gst_number,
                "store_image_url":  generate_presigned_url(str(document.store_image)) if document.store_image else None,
                "drug_license_form20_url":  generate_presigned_url(str(document.drug_license_form20)) if document.drug_license_form20 else None,
                "drug_license_form21_url": generate_presigned_url(str(document.drug_license_form21)) if document.drug_license_form21 else None,
                "gst_image_url": generate_presigned_url(str(document.gst_image)) if document.gst_image else None,
                "kyc_status": "pending"  
            }
        }

        ActivityLog.log_activity(user=user, action="New Retailer KYC", details=f"New retailer KYC created for user: {user.username}", to_user=user)
        logger.info("Retailer data created successfully")
        return JsonResponse(response_data, status=201)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return JsonResponse({"message": "Internal Server Error"}, status=500)



@api_view(['GET'])
def distributor_list(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 
    try:
        #distributors = Distributor.objects.all()
        retailer = Retailer.objects.get(user_id = user)
        serviceable_pincodes = ServiceablePincode.objects.filter(pincode=retailer.postal_code, distributor__is_activated=True)
        dists = [sp.distributor for sp in serviceable_pincodes]
        serializer = DistributorSerializer(dists, many=True)
        logger.info("Distributor list retrieved successfully")
        return Response(serializer.data)
    
    except Distributor.DoesNotExist:
        logger.error("Distributors not found")
        return JsonResponse({"message": "distributors not found"}, status=404)

    except Exception as e:
        logger.exception("Internal Server Error: %s", str(e))
        return JsonResponse({"message": "Internal Server Error"}, status=500)
    

@api_view(['POST'])
def feedback(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406) 

    try:
        retailer = Retailer.objects.get(user=user)
        description = request.data.get('description')  
        if not description:
            logger.error("Description is required")
            return Response({"message": "Description is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        request.data['retailer'] = retailer.id

        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info("Feedback saved successfully")
            return Response({"message": "Your Feedback has been Successfully Received! Thank you."}, status=status.HTTP_200_OK)
        else:
            logger.error("Invalid serializer data")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.exception("Internal Server Error: %s", str(e))
        return Response({"message": "Internal Server Error"}, status=500)


@api_view(["GET"])
def dashboard_api(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Access Token Missing")
        return Response({"message":"Access Token Missing Or Mismatch"}, status=406)
    try:
        cart = Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        cart = None

    # distributor = Distributor.objects.filter(user=user).first()
    # if distributor:
    #     deals = Deal.objects.filter(distributor=distributor)
    # else:
    #     deals = None
    
    try:
        retailer = Retailer.objects.get(user = user.id)
    except:
        retailer = None

    if retailer.is_activated:
        serviceable_pincode_list = ServiceablePincode.objects.filter(pincode=retailer.postal_code, distributor__is_activated = True)
        dist_list = [ pincode.distributor for pincode in serviceable_pincode_list]
        today = date.today()
        deals = Deal.objects.using('replica').filter(Q(start_date__lte=today) & (Q(end_date__gte=today) | Q(end_date__isnull=True)), distributor__in=dist_list, is_expired=False)
    else:
        deals = []

    banners_queryset = Banner.objects.all().values("image")
    kyc_obj = KYC.objects.filter(user=user).first()
    banners_link_list = [generate_presigned_url(str(banner['image'])) for banner in banners_queryset]
    if retailer:
        distributor_data_list = ServiceablePincode.objects.filter(pincode=retailer.postal_code).values(
                                                            dist_id=F('distributor__id'),dist_name=F('distributor__name'),
                                                            dist_address=F('distributor__address'),dist_logo=F('distributor__logo'),
                                                            dist_organisation_id=F('distributor__organisation__id')).distinct('distributor__id')
    else:
        distributor_data_list = Distributor.objects.all().values(dist_id=F('id'),dist_name=F('name'),
                                                            dist_address=F('address'),dist_logo=F('logo'),
                                                            dist_organisation_id=F('organisation__id'))
    distributor_list = [
        {
            'dist_id': item['dist_id'],
            'name': item['dist_name'],
            'address': item['dist_address'],
            'organisation_id': item['dist_organisation_id'],
            'logo': generate_presigned_url(str(item['dist_logo'])) if item['dist_logo'] else ""
        }
        for item in distributor_data_list
    ]
    dashboard_data = {
        "name": retailer.owner_name if kyc_obj else "User",
        "mobile_num": user.username,
        "cart_count": cart.cartitem_set.count() if cart else 0,
        "contact_us": CONTACT_US,
        "banner_images": banners_link_list,  
        "kyc_status": retailer.kyc_status if retailer else None,
        "deals": [{"dist_name": deal.distributor.name, "prod_name": deal.product.name,
                    "description": deal.description}
                  for deal in deals] if deals else [],
        "distributorList": distributor_list
    }
    return Response(dashboard_data)



@api_view(["GET"])
@permission_classes([AllowAny])
def get_retailer_kyc_data(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return JsonResponse({"message":"Access Token Missing Or Mismatch"}, status=406)

    try:
        retailer = Retailer.objects.get(user=user)
    except:
        logger.info("Retailer not found")
        return JsonResponse({"message": "Retailer not found"}, status=200)    
        
    try:
        kyc = KYC.objects.get(user=user)
    except:
        logger.info("kYC not found")
        return JsonResponse({"message": "Complete Your KYC Documents"}, status=200)  
        
    try:
        document = Document.objects.get(uploaded_by=user.id)
    except:
        logger.info("Document not found")
        return JsonResponse({"message": "Document not found"}, status=200)   


    try:
        response_data = {
            "data": {
                "owner_name": retailer.owner_name,
                "store_name": retailer.store_name,
                "address": retailer.address,
                "city": retailer.city,
                "state": retailer.state,
                "postal_code": retailer.postal_code,
                "valid_from": kyc.valid_from.strftime('%Y-%m-%d'),
                "valid_to": kyc.valid_to.strftime('%Y-%m-%d'),
                "drug_license_number": kyc.drug_license_number,
                "gst_number": kyc.gst_number,
                "phone_number": retailer.user.phone_number,
                "store_image_url":  generate_presigned_url(str(document.store_image)) if document.store_image else None,
                "drug_license_form20_url":  generate_presigned_url(str(document.drug_license_form20)) if document.drug_license_form20 else None,
                "drug_license_form21_url": generate_presigned_url(str(document.drug_license_form21)) if document.drug_license_form21 else None,
                "gst_image_url": generate_presigned_url(str(document.gst_image)) if document.gst_image else None,
                
                # "store_image_url": S3_LINK+str(document.store_image) if document.store_image else None,
                # "drug_license_form20_url": S3_LINK+str(document.drug_license_form20) if document.drug_license_form20 else None,
                # "drug_license_form21_url": S3_LINK+str(document.drug_license_form21) if document.drug_license_form21 else None,
                # "gst_image_url": S3_LINK+str(document.gst_image) if document.gst_image else None,             
                "kyc_status": retailer.kyc_status if retailer.kyc_status else None

            }
        }

        return JsonResponse(response_data)

    except:
        logger.error("Retailer or KYC data not found")
        return JsonResponse({"message": "Retailer or KYC data not found."}, status=200)


@api_view(["GET"])
@permission_classes([AllowAny])
def MyAccount(request):
    if request.method == "GET":
        try:
            user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
        except:
            return Response({"message":"Access Token Missing Or Mismatch"}, status=406)  
        try:
            orders = user.orders.all()
            total_number_of_orders = orders.count()
            total_number_of_invoices = Invoice.objects.filter(order__in = orders ).count()
            total_number_of_order_delivered = orders.filter(order_status="delivered").count()
            total_purchase_amount = orders.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'] or 0
            total_paid_amount = Payment.objects.filter(order__in = orders).aggregate(paid_amount = Sum('amount'))['paid_amount'] or 0
            total_out_standing_amount = total_purchase_amount-total_paid_amount    
            logger.info(f"Data successfully retrieved in the My Account API")
                   
        except Exception as e:
            logger.exception(f"An unexpected error occurred in the My Account API, Error is : {str(e)}.")
            return JsonResponse({"message": "Retailer not found"}, status=404)
        
        serializer = MyProfileSerializer({
                            "total_number_of_orders": total_number_of_orders,
                            "total_number_of_invoices": total_number_of_invoices,
                            "total_number_of_order_delivered":total_number_of_order_delivered,
                            "total_purchase_amount":total_purchase_amount, 
                            "total_paid_amount":total_paid_amount,
                            "total_out_standing_amount":total_out_standing_amount
                        })
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response({"message": "POST Method not allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)



def daily_sales_report(*args, **kwargs):
    # Get yesterday's date
    yesterday_date = date.today()
    data = []
    orders = Order.objects.filter(order_date__date=yesterday_date)

    for order in orders:
        distributor = Distributor.objects.filter(user=order.distributor.user).first() if order.distributor else None
        retailer = Retailer.objects.filter(user=order.user).first() if order.user else None
        kyc = KYC.objects.filter(user=retailer.user).first() if retailer else None
        ordered_items = OrderedItem.objects.filter(order=order)
        invoice = Invoice.objects.filter(order=order).first()

        for item in ordered_items:
            row = {
                'product_name': item.product.name,
                'distributor_name': distributor.name if distributor else "",
                'order_id': order.id,
                'order_date': order.order_date,
                'order_status': order.order_status,
                'total_amount': order.total_amount,
                'discount': order.discount,
                'commission_rate': "",
                'retailer_store_name': retailer.store_name if retailer else "",
                'postal_code': retailer.postal_code if retailer else "",
                'gst_number': kyc.gst_number if kyc else "",
                'gst': item.gst,
                'cgst': item.cgst,
                'igst': item.igst,
                'sgst': item.sgst,
                'quantity': item.quantity,
                'retailer_medley_id': retailer.medleyId if retailer else "",
                'invoice_number': invoice.invoice_number if invoice else "",
                'invoice_amount': invoice.invoice_amount if invoice else "",
                'invoice_date': invoice.invoice_date if invoice else "",
                'invoice_file': invoice.invoice_file.url if invoice and invoice.invoice_file else ''
            }

            commission = Commission.objects.filter(retailer=retailer, distributor=distributor).first()
            if commission:
                row['commission_rate'] = commission.commission_rate

            data.append(row)

    columns = ['product_name', 'distributor_name', 'order_id', 'order_date', 'order_status', 'total_amount', 'discount',
               'commission_rate', 'retailer_store_name', 'postal_code', 'gst_number', 'gst', 'cgst', 'igst',
               'sgst', 'quantity', 'retailer_medley_id', 'invoice_number', 'invoice_amount', 'invoice_date', 'invoice_file']

    df = pd.DataFrame(data, columns=columns)

    file_path = f'Daily_sales_report_{yesterday_date}.csv'

    try:
        df.to_csv(file_path, index=False)
        print("CSV file saved to:", file_path)

        # Create the email message
        subject = f"Daily Sales Report - {yesterday_date}"
        body = "Please find the attached sales report file for today's sales report."
        from_email = EMAIL_HOST_USER
        to_emails = MAIL_TO
        cc_emails = CC_TO
        print (from_email ,
        to_emails ,
        cc_emails )
        msg = EmailMultiAlternatives(subject, body, from_email, to_emails, cc=cc_emails)

        # Attach the CSV file to the email
        with open(file_path, 'rb') as file:
            msg.attach(f'Daily_sales_report_{yesterday_date}.csv', file.read(), 'text/csv')

        # Send the email
        msg.send()

        print("Email sent successfully")
        response_data = {'message': f'Daily Sales Report for {yesterday_date} sent successfully'}
        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        print("Error:", str(e))
        response_data = {'error': str(e)}
        return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Removing the saved file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} removed")


def monthly_sales_report(*args, **kwargs):
    # Get the current month and year
    current_date = timezone.now()
    current_month = current_date.month
    current_year = current_date.year

    # Calculate the number of days in the current month
    days_in_month = (date(current_year, current_month + 1, 1) - date(current_year, current_month, 1)).days

    # Calculate the first and last days of the current month
    first_day_of_month = date(current_year, current_month, 1)
    last_day_of_month = date(current_year, current_month, days_in_month)

    data = []
    orders = Order.objects.filter(order_date__range=[first_day_of_month, last_day_of_month])

    for order in orders:
        distributor = Distributor.objects.filter(user=order.distributor.user).first() if order.distributor else None
        retailer = Retailer.objects.filter(user=order.user).first() if order.user else None
        kyc = KYC.objects.filter(user=retailer.user).first() if retailer else None
        ordered_items = OrderedItem.objects.filter(order=order)
        invoice = Invoice.objects.filter(order=order).first()

        for item in ordered_items:
            row = {
                'product_name': item.product.name,
                'distributor_name': distributor.name if distributor else "",
                'order_id': order.id,
                'order_date': order.order_date,
                'order_status': order.order_status,
                'total_amount': order.total_amount,
                'discount': order.discount,
                'commission_rate': "",
                'retailer_store_name': retailer.store_name if retailer else "",
                'postal_code': retailer.postal_code if retailer else "",
                'gst_number': kyc.gst_number if kyc else "",
                'gst': item.gst,
                'cgst': item.cgst,
                'igst': item.igst,
                'sgst': item.sgst,
                'quantity': item.quantity,
                'retailer_medley_id': retailer.medleyId if retailer else "",
                'invoice_number': invoice.invoice_number if invoice else "",
                'invoice_amount': invoice.invoice_amount if invoice else "",
                'invoice_date': invoice.invoice_date if invoice else "",
                'invoice_file': invoice.invoice_file.url if invoice and invoice.invoice_file else ''
            }

            commission = Commission.objects.filter(retailer=retailer, distributor=distributor).first()
            if commission:
                row['commission_rate'] = commission.commission_rate

            data.append(row)

    columns = ['product_name', 'distributor_name', 'order_id', 'order_date', 'order_status', 'total_amount', 'discount',
               'commission_rate', 'retailer_store_name', 'postal_code', 'gst_number', 'gst', 'cgst', 'igst',
               'sgst', 'quantity', 'retailer_medley_id', 'invoice_number', 'invoice_amount', 'invoice_date', 'invoice_file']

    df = pd.DataFrame(data, columns=columns)

    file_path = f'Monthly_sales_report_{current_month}_{current_year}.csv'

    try:
        df.to_csv(file_path, index=False)
        print("CSV file saved to:", file_path)

        # Create the email message
        subject = f"Monthly Sales Report - {current_month}/{current_year}"
        body = "Please find the attached sales report file for the current month."
        from_email = EMAIL_HOST_USER
        to_emails = MAIL_TO
        cc_emails = CC_TO

        msg = EmailMultiAlternatives(subject, body, from_email, to_emails, cc=cc_emails)

        # Attach the CSV file to the email
        with open(file_path, 'rb') as file:
            msg.attach(f'Monthly_sales_report_{current_month}_{current_year}.csv', file.read(), 'text/csv')

        # Send the email
        msg.send()

        print("Email sent successfully")
        response_data = {'message': f'Monthly Sales Report for {current_month}/{current_year} sent successfully'}
        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        print("Error:", str(e))
        response_data = {'error': str(e)}
        return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    finally:
        # Removing the saved file
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} removed")


@api_view(['GET'])
def Configuration(request):
    colors = {
        "BACKGROUND": hex(0xFFFFFFFF),
        "FOOTER": hex(0xfff5f5f5),
        "TEXT": hex(0xff3a3a3a),
        "TEXTINFO": hex(0xff949FAE),
        "ELEVATEDBUTTON": hex(0xff0a0a26),
        "COLOR3": hex(0xffe5672f),
        "COLOR4": hex(0xffb73d99),
        "COLOR5": hex(0xff00db72),
        "OUTLINEBUTTON": hex(0xff02b6ce),
        "WHITE": hex(0xFFFFFFFF),
        "LIGHTWHITE": hex(0xfff5f5f5),
        "TEXTCOLORLIGHT": hex(0xff738999),
        "SECONDARY": hex(0xFF0EC8D5),
        "SECONDARY1": hex(0xFF0EC8D5),
    }
    VERSION = Settings.get_value_based_on_type("VERSION")
    VERSION_CHECK = Settings.get_value_based_on_type("VERSION_CHECK")
    data = {
        'colors': colors,
        'version': VERSION,
        'versionCheck':VERSION_CHECK,
        'chatBot' : 'https://b2b2qa.medleymed.com/chatbot_index'
    }

    return Response(data, status=200)


@api_view(["GET"])
def retailer_delete(request):
    if request.method == "GET":
        try:
            user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
        except:
            return Response({"message": "Access Token Missing Or Mismatch"}, status=status.HTTP_404_NOT_FOUND)
        user.is_active = False
        user.is_deleted = True
        user.save()
        # retailer = user.retailer
        # retailer.is_activated = False
        # retailer.kyc_status = "pending"
        # retailer.save()
        return Response({"message": "Your account has been successfully deleted."}, status=status.HTTP_200_OK)
    return Response({"message": "Only GET Method allowed"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)



@api_view(['GET'])
def callex_dashboard(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message": "Access Token Missing Or Mismatch"}, status=406)

    try:
        sales_executive = SalesExecutive.objects.get(user=user)

        serializer = SalesExecutiveSerializer(sales_executive)

        return Response(serializer.data, status=status.HTTP_200_OK)

    except SalesExecutive.DoesNotExist:
        logger.warning("Sales executive not found")
        return Response({"message": "Sales executive not found"}, status=404)

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({'error': "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def callex_search_retailer(request):
    try:
        user = get_user(request.META.get("HTTP_ACCESSTOKEN"))
    except:
        logger.error("Invalid access token")
        return Response({"message": "Access Token Missing Or Mismatch"}, status=406)
    try:
        key = request.query_params.get('filter_key')
        if key:
            try:
                sales_executive = SalesExecutive.objects.get(user=user)
                retailers = sales_executive.retailer.filter(
                Q(store_name__icontains=request.query_params.get('filter_key')) |
                Q(user__phone_number__icontains=request.query_params.get('filter_key'))
            )
            except:
                logger.error("NO Retailer Found")
                return Response({"message": "SFA Not Found"}, status=406)
            serializer = RetailerSerializer(retailers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            sales_executive = SalesExecutive.objects.get(user=user)
            retailers = sales_executive.retailer.all()
            serializer = RetailerSerializer(retailers, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
            

    except Exception as e:
        logger.exception(f"An unexpected error occurred: {str(e)}")
        return Response({'error': "Internal Server Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)