from datetime import datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
import pandas as pd

from Ordermanagement.models import Order, OrderedItem
from Paymentmanagement.models import Invoice, UploadedBillDetails
from Productmanagement.models import UploadedBillDetailsFields
from Usermanagement.models import Distributor, PartyCode, Retailer
from django.contrib import messages
from django.db import transaction
from decimal import Decimal

from Usermanagement.utils import active_distributor_required
from .utils import *
import logging

# Create your views here.

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

@active_distributor_required
def upload_bill_details(request, order_id):
    if request.method == 'POST':
        file = request.FILES.get('details_doc')
        if not file:
            messages.success(request, 'Please select a file first')
            return redirect('dist-order-details', odrer_id=order_id)
        with transaction.atomic():
            if validate_file_type(str(file)):
                try:
                    error,msg = new_save_uploaded_bill_details_auto_fill_bill(request,order_id , file)
                    if error:
                        messages.error(request, msg)
                        return redirect('dist-order-details', order_id=order_id)
                    messages.success(request, 'file has been uploaded successfully')
                    return redirect('dist-order-details', order_id=order_id)
                except Exception as e:
                # in exception variable e we are getting the data as unicode so we are splitting to remove u'
                    logger.error('Exception occured "{}"'.format(str(e)))
                    messages.error(request, 'Exception occured "{}"'.format(str(e)))
                    return redirect('dist-order-details', order_id=order_id)
            else:
                messages.error(request, 'Please choose a CSV or xlxs file')
                return redirect('dist-order-details', odrer_id=order_id)

def new_save_uploaded_bill_details_auto_fill_bill(request,order_id, file):
    order = Order.objects.get(id=order_id)
    try:
        distributor = order.distributor
        field = UploadedBillDetailsFields.objects.get(user=distributor.user)
        if str(file).lower().endswith('.csv'):
            df = pd.read_csv(file,dtype={field.hsn_code:'object',field.distributor_sku:str,field.partycode:str})
        if str(file).lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file, dtype={field.hsn_code: 'object', field.distributor_sku: str,field.partycode:str})
            
        df.columns = df.columns.str.strip()
        columns_to_check = [field.expiry, field.billed_quantity,  field.max_retail_price,field.batch, field.product_name,field.cgst_amount]
        df = df.dropna(subset=columns_to_check, how='all')
        required_columns = [field.cgst_amount, field.batch,field.distributor_sku,
                            field.product_name, field.discount,field.price_to_retail, field.max_retail_price, field.billed_quantity, 
                            field.expiry, field.pts, field.billed_free]
        null_columns = df[required_columns].isnull().any()
        if null_columns.any():
            null_column_names = null_columns[null_columns].index.tolist()
            null_column_names = ', '.join(null_column_names)
            return True,"{0} columns containing empty values".format(null_column_names)
        if df.empty:
            logging.warning('File is empty')
            return True,'File is empty'
        gst_amount = gross_amount = discount_amount = invoice_amount = 0
        invoice_no = df[field.invoice_no].iloc[0]
        party_code = df[field.partycode].iloc[0]
        is_invoice_number_exist = Invoice.objects.exclude(order__id=order_id).filter(invoice_number=invoice_no).first()
        if is_invoice_number_exist:
            logger.error('invoice already existed with other order')
            return True,'invoice already existed with other order'
        df = df.sort_values(by=field.distributor_sku, ascending=True)
        prcode_list = df[field.distributor_sku].tolist()
        df[field.expiry] = df[field.expiry].astype(str)
        retailer = Retailer.objects.filter(user=order.user).first()
        is_new_party_code = True
        if PartyCode.objects.filter(retailer=retailer,distributor=order.distributor).exists():
            party_code_instance = PartyCode.objects.filter(retailer=retailer,distributor=order.distributor).first()
            is_new_party_code = False
            if party_code_instance and str(party_code)!=party_code_instance.party_code:
                logger.error('The provided party code does not match..')
                return True,'The provided party code does not match.'
            
        party_match = PartyCode.objects.filter(party_code = party_code,distributor=distributor).first()
        if party_match and party_match.retailer != retailer:
            logger.error('Party code already exist')
            return True,'Party code already exist with other customer'
        
        last_prcode= ""
        sku_exists=False
        with transaction.atomic():
            UploadedBillDetails.objects.filter(order_id=order_id).delete()
            if field.cgst not in df.columns:
                field.cgst = "cgst"
                df[field.cgst] = 0
            else:
                df[field.cgst] =  df[field.cgst].fillna(0)
            if field.sgst not in df.columns:
                field.sgst = "sgst"
                df[field.sgst] = 0
            else:
                df[field.cgst] =  df[field.cgst].fillna(0)
            if field.igst not in df.columns:
                field.igst = "igst"
                df[field.igst] = 0
            else:
                df[field.igst] =  df[field.igst].fillna(0)
            for idx, row in df.iterrows():
                csgst = Decimal(row[str(field.sgst)])  + Decimal(row[str(field.cgst)])
                if csgst > 0:
                    gst = csgst
                    igst = 0
                else:
                    if field.igst != '':
                        gst = Decimal(row[field.igst])
                        igst = gst
                    else:
                        gst, igst = 0, 0
                if row[field.barcode] != '':
                    barcode = row[field.barcode]
                else:
                    barcode = None
                order_bill = OrderedItem.objects.select_related('product').filter(order_id=order_id,product__distributor_sku=row[field.distributor_sku]).first()
                if order_bill:
                    sku_exists = True
                    try:
                        date_object = datetime.strptime(row[field.expiry], "%Y-%m-%d")
                    except ValueError:
                        try:
                            date_object = datetime.strptime(row[field.expiry], "%d-%m-%Y")
                        except ValueError:
                            logger.error(f'Date string does not match any accepted format {str(e)}')
                            return True,f'Please check issue in {str(e)}'
                    formatted_date = date_object.strftime("%Y-%m-%d")
                    gst_amount+= float(row[field.cgst_amount])
                    gross_amount+= float(row[field.gross_amount])
                    invoice_amount = float(row[field.invoice_amount])
                    if last_prcode == row[field.distributor_sku]:
                        order_bill.build_qty += row[field.billed_quantity]
                        order_bill.build_free+=row[field.billed_free]
                        discount_amount+=((float(row[field.price_to_retail])*row[field.discount])/100)*row[field.billed_quantity]
                    else:
                        order_bill.build_qty = row[field.billed_quantity]
                        order_bill.build_free=row[field.billed_free]
                        discount_amount+=((float(row[field.price_to_retail])*row[field.discount])/100)*row[field.billed_quantity]
                    last_prcode = row[field.distributor_sku]
                    order_bill.max_retail_price=row[field.max_retail_price]
                    order_bill.unit_price = row[field.price_to_retail]
                    order_bill.batch = row[field.batch]
                    order_bill.hsn = str(row[field.hsn_code]).split(' ')[0]
                    order_bill.gst = Decimal(row[field.cgst]) + Decimal(row[field.sgst])
                    order_bill.cgst = row[field.cgst]
                    order_bill.sgst = row[field.sgst]
                    order_bill.igst = row[field.igst]
                    order_bill.discount = row[field.discount]
                    order_bill.expiry = formatted_date
                    order_bill.pts = row[field.pts]
                    order_bill.order_status = "Processed"
                    order_bill.save() 
                    
                    UploadedBillDetails.objects.create(order_id=order_id, product_name=row[field.product_name],
                        billed_quantity=row[field.billed_quantity], billed_free=row[field.billed_free], 
                        unit_price_net=row[field.price_to_retail], 
                        max_retail_price=row[field.max_retail_price], goods_service_tax=gst, barcode=barcode,
                        discount=row[field.discount], expiry=row[field.expiry], batch=row[field.batch], 
                        hsn_code=str(row[field.hsn_code]).split(' ')[0],
                        cgst=Decimal(row[field.cgst]), 
                        sgst=Decimal(row[field.sgst]),
                        igst=igst,
                        pts = row[field.pts])
            if not sku_exists:
                OrderedItem.objects.select_related('product').filter(order_id=order_id).exclude(product__distributor_sku__in=prcode_list).update(build_qty=0, build_free=0)
                log_activity(request,"No products found matching the provided SKUs in the file uploaded",order)
                return True,"No products found matching the provided SKUs in the file."
            invoice, created = Invoice.objects.update_or_create(
                                            defaults={
                                                'invoice_number':invoice_no,
                                                'gross_amount': round(gross_amount,2),
                                                'gst_amount': round(gst_amount*2,2),
                                                'invoice_amount':invoice_amount,
                                                'discount_amount':round(discount_amount,2),
                                                'distributor':distributor
                                            },
                                            order=order
                                        )
            
            OrderedItem.objects.select_related('product').filter(order_id=order_id).exclude(product__distributor_sku__in=prcode_list).update(build_qty=0, build_free=0)
            if not Invoice.objects.filter(order=order).exists():
                order.order_status = "Processed"
                order.save()
                log_activity(request,"Bill Details uploaded",order)
            else:
                log_activity(request,"Bill Details uploaded",order)
            if is_new_party_code:
                PartyCode.objects.create(retailer=retailer,distributor=distributor,party_code=str(party_code))
                
        return False,""
            
    except KeyError as e:
        error_message = str(e)
        column_not_found = error_message.split("'")[1]
        logger.error(f"{column_not_found}: Column not found. Please check the uploaded file or configuration.")
        return True,f"{column_not_found}: Column not found. Please check the uploaded file or configuration."             
    except Distributor.DoesNotExist:
        logger.error('Distributor does not exist with this order')
        return True,'Distributor does not exist with this order'
    except UploadedBillDetailsFields.DoesNotExist:
        logger.error('Upload configuration not found for this partner')
        return True,'Upload configuration not found for this partner'
    except Exception as e:
        logger.error(f'exception occred in {str(e)}')
        return True,f'Please check issue in {str(e)}'

@active_distributor_required
def update_invoice_details(request,order_id):
    try:
        order = get_object_or_404(Order, pk=order_id)
        if request.method == "POST":
            form_fields = ['gross_amount', 'gst_amount', 'invoice_amount', 'discount_amount']
            invoice_no = request.POST.get('invoice_number')
            form_data = extract_form_data(request, *form_fields)
            form_data['invoice_amount'] = float(form_data['gross_amount']) - float(form_data['discount_amount']) + float(form_data['gst_amount'])        
            invoice_no = request.POST.get('invoice_number')
            invoice_file = request.FILES.get('invoice_file')
            form_data.update({'invoice_number':invoice_no,"invoice_file": invoice_file,
                        "issued_date":timezone.now().strftime('%Y-%m-%d'),
                        'invoice_date':timezone.now().strftime('%Y-%m-%d'),'status':'billed'})
            invoice, created = Invoice.objects.update_or_create(
                defaults=form_data,order=order
            )
            order.order_status = "Billed"
            order.save()
            log_activity(request,f"invoice no:{invoice_no} verified and uploaded",order)
            if created:
                messages.success(request,"Invoice created successfully")
            else:
                messages.success(request,"Invoice updated successfully")
            return redirect('dist-order-details',order_id)
    except Exception as e:
        logger.error(f'exception occred in {str(e)}')
        return redirect('dist-order-details',order_id)
        
            
