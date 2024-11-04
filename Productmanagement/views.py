import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import transaction
import requests
from Activitylog.models import ActivityLog
from Paymentmanagement.utils import extract_form_data
from Productmanagement.models import DistProductMaster, DistributorStock,Deal, UploadProductDetailsFields, UploadedBillDetailsFields
from Productmanagement.utils import get_product_edit_context, get_product_list_context, process_upload_configurations, upload_medica_products
from Usermanagement.filters import ProductFilter
from Usermanagement.models import Distributor
from Usermanagement.utils import active_admin_required
from django.shortcuts import render,redirect
from django.template.response import TemplateResponse
import datetime
import logging
from Usermanagement.utils import *
from b2b2.settings import CURRENCY, REMOTE_API_URL, UPLOAD_FOLDER
from b2b2.settings import TEXTLOCAL_API_KEY
from Usermanagement.filters import *
from  Usermanagement import get_paginator_items, paginate_items
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
import pandas as pd

from .forms import ProductDealsForm

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



# Create your views here.

@active_admin_or_sub_admin_required
def product_creation(request):
    """Creates or edits products for a distributor."""
    try:
        product_category_choices = DistProductMaster._meta.get_field('product_category').choices
        product_type_choices = DistProductMaster._meta.get_field('product_type').choices
        distributors = Distributor.objects.all()
        # distributor = Distributor.objects.get(user=pk)
        if request.method == 'POST':
            with transaction.atomic():
                distributor = Distributor.objects.filter(id=request.POST.get('partner')).first()
                obj={
                "name":request.POST.get('name'),
                "distributor_sku":request.POST.get('distributor_sku'),
                "description":request.POST.get('description',""),
                "hsn":request.POST.get('hsn'),
                "ptr":request.POST.get('ptr'),
                "mrp":request.POST.get('mrp'),
                "packing":request.POST.get('packing'),
                "product_category":request.POST.get('product_category'),
                "product_class":request.POST.get('product_class'),
                "product_salt":request.POST.get('product_salt'),
                "product_type":request.POST.get('product_type'),
                "product_composition":request.POST.get('product_composition'),
                "distributor":distributor
                }
                dist_product, created = DistProductMaster.objects.update_or_create(
                distributor_sku=obj['distributor_sku'],distributor=distributor,
                defaults=obj)
                obj_2 = {
                "distributor":distributor,
                "product": dist_product,
                "expiry_date":request.POST.get('expiry_date'),
                "gst":request.POST.get('gst'),
                "ptr":request.POST.get('ptr'),
                "mrp":request.POST.get('mrp'),
                "discount":request.POST.get('discount') if request.POST.get('discount') else 0,
                "batch_number":request.POST.get('batch_number'),
                "manufacturer":request.POST.get('manufacturer'),
                "quantity": request.POST.get('quantity', 0)
                }
                dist_stock, created = DistributorStock.objects.update_or_create(
                    product=dist_product,distributor=distributor,
                    defaults=obj_2
                )
                messages.success(request,'Product created successfully')
                logger.info('Product created successfully by user: %s', request.user.username)
                url = reverse('dashboard-products')
                return redirect(url)
        ctx = {
            "product_category_choices":product_category_choices,
            "product_type_choices":product_type_choices,
            'distributors':distributors,
            'template_to_extend' :'dashboard.html'
        }
        return TemplateResponse(request,'product_creation.html',ctx)
    except Exception as e:
        logger.warning('Error during product update/creation by user %s: %s', request.user, str(e))
        return redirect('dashboard-products')
        
    
@active_distributor_required
def distributor_product_creation(request):
    """Creates or edits products for a distributor."""
    try:
        product_category_choices = DistProductMaster._meta.get_field('product_category').choices
        product_type_choices = DistProductMaster._meta.get_field('product_type').choices
        distributor = Distributor.objects.filter(user=request.user).first()
        if request.method == 'POST':
            with transaction.atomic():
                obj={
                "name":request.POST.get('name'),
                "distributor_sku":request.POST.get('distributor_sku'),
                "description":request.POST.get('description',""),
                "hsn":request.POST.get('hsn'),
                "ptr":request.POST.get('ptr'),
                "mrp":request.POST.get('mrp'),
                "packing":request.POST.get('packing'),
                "product_category":request.POST.get('product_category'),
                "product_class":request.POST.get('product_class'),
                "product_salt":request.POST.get('product_salt'),
                "product_type":request.POST.get('product_type'),
                "product_composition":request.POST.get('product_composition'),
                "distributor":distributor
                }
                dist_product, created = DistProductMaster.objects.update_or_create(
                distributor_sku=obj['distributor_sku'],distributor=distributor,
                defaults=obj)
                obj_2 = {
                "distributor":distributor,
                "product": dist_product,
                "expiry_date":request.POST.get('expiry_date'),
                "gst":request.POST.get('gst'),
                "ptr":request.POST.get('ptr'),
                "mrp":request.POST.get('mrp'),
                "discount":request.POST.get('discount') if request.POST.get('discount') else 0,
                "batch_number":request.POST.get('batch_number'),
                "manufacturer":request.POST.get('manufacturer'),
                "quantity": request.POST.get('quantity', 0)
                }
                dist_stock, created = DistributorStock.objects.update_or_create(
                    product=dist_product,distributor=distributor,
                    defaults=obj_2
                )
                messages.success(request,'Product created successfully')
                logger.info('Product created successfully by user: %s', request.user.username)
                url = reverse('distributor-products')
                return redirect(url)
        ctx = {
            "product_category_choices":product_category_choices,
            "product_type_choices":product_type_choices,
            'distributors':distributor,
            'template_to_extend' :'distributor_base.html'
        }
        return TemplateResponse(request,'product_creation.html',ctx)
    except Exception as e:
        logger.warning('Error during product update/creation by user %s: %s', request.user, str(e))
        url = reverse('distributor-products')
        messages.error(request,'Exception Occered :',str(e))
        return redirect(url)


@active_admin_or_sub_admin_required
def product_edit(request,prod_id):
    product_instance = DistProductMaster.objects.filter(id=prod_id).first()
    redirect_url = 'dashboard-products'
    template_to_extend ='dashboard.html'
    return get_product_edit_context(request,product_instance,template_to_extend,redirect_url)
    
@active_distributor_required
def distributor_product_edit(request,prod_id):
    distributor = Distributor.objects.filter(user=request.user).first()
    product_instance = DistProductMaster.objects.filter(id=prod_id,distributor=distributor).first()
    redirect_url = 'distributor-products'
    template_to_extend = 'distributor_base.html'
    return get_product_edit_context(request,product_instance,template_to_extend,redirect_url)

@active_admin_or_sub_admin_required
def product_list(request):
    distributor_products = DistProductMaster.objects.annotate(total_quantity=Sum('distributorstock__quantity')).order_by('name')
    template_to_extend = 'dashboard.html'
    redirect_url = 'dashboard-products'
    prod_create_url = "product-creation"
    return get_product_list_context(request, distributor_products,template_to_extend,redirect_url,prod_create_url)

@active_distributor_required
def distributor_product_list(request):
    distributor = Distributor.objects.filter(user=request.user).first()
    distributor_products = DistProductMaster.objects.filter(distributor=distributor).annotate(total_quantity=Sum('distributorstock__quantity')).order_by('name')
    template_to_extend = 'distributor_base.html'
    redirect_url = 'distributor-products'
    prod_create_url = "dist-product-creation"
    return get_product_list_context(request, distributor_products,template_to_extend,redirect_url,prod_create_url)


@active_admin_or_sub_admin_required
def distributor_add_stock(request,pk=None):
    """Adds stock for a distributor's product."""

    distributor = Distributor.objects.get(user=pk)
    if request.method == 'POST':
        dist_prod_master = DistProductMaster.objects.filter(pk=request.POST.get('product_id')).first()
        if dist_prod_master:
            total_quantity = DistributorStock.objects.filter(product=dist_prod_master).aggregate(Sum('quantity'))['quantity__sum']
            total_quantity = total_quantity if total_quantity is not None else 0
            new_quantity = int(request.POST.get('quantity', 0)) + total_quantity
        form_data = {
            "distributor":distributor,
            "product": dist_prod_master,
            "expiry_date":request.POST.get('expiry_date'),
            "quantity": new_quantity,
            "cost_price": request.POST.get('cost_price'),
            "selling_price": request.POST.get('selling_price'),
            "discount": request.POST.get('discount'),
            "manufacturer":request.POST.get('manufacturer'),
            "gst": request.POST.get('gst'),
        }
        try:
            dist_add_stock, created = DistributorStock.objects.update_or_create(
            product=dist_prod_master,
            defaults=form_data)
            logger.info('Stock added successfully for product ID %s ', dist_prod_master.pk)
        except Exception as e:
            logger.warning('Error during stock addition for product ID %s error is %s', dist_prod_master.pk, str(e))
        url = reverse('customer-details', kwargs={'pk': pk})
        return redirect(url)
    distributor_products = DistProductMaster.objects.select_related('distributor').filter(distributor=distributor)
    ctx={
        "distributor_products":distributor_products,
        "dist_id":pk
    }
    return TemplateResponse(request,'distributor_add_stock.html',ctx)




@csrf_exempt
def distributorSKUBatch_existance(request):
    if request.method == 'POST':
        model_name = request.POST.get('model_name')
        value = request.POST.get('value')
        product_id = request.POST.get('prod_id',"")
        dist_id = request.POST.get('dist_id',"")
        if not model_name or not value:
            return JsonResponse({'error': 'Invalid request parameters'}, status=400)
        try:
            model = None
            if model_name == 'DistProductMaster':
                model = DistProductMaster
                field_name = 'distributor_sku'
            elif model_name == 'DistributorStock':
                model = DistributorStock
                field_name = 'batch_number'
            else:
                return JsonResponse({'error': 'Invalid model name'}, status=400)
            if product_id:
                distributor_obj = Distributor.objects.filter(user=dist_id).first()
                sku_exist = DistProductMaster.objects.exclude(id=product_id).filter(distributor_sku=value,distributor=distributor_obj)
                is_exist = True if sku_exist else False
            else:
                is_exist = is_exists(model, {field_name: value})
            logger.info('%s check for %s. Existence: %s', model_name, value, is_exist)
            return JsonResponse({f'is_exist': is_exist}, status=200)  # Successful response
        except Exception as e:
            # Handle any errors gracefully
            logger.error('Error fetching data: %s', str(e))
            error_message = f"Error fetching data: {str(e)}"
            return JsonResponse({'error': error_message}, status=400)  # Error response
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@active_admin_or_sub_admin__distributor_required
def distrubutor_uploadstock(request):
    """
        As per Distributor id the Stock upload will update here
        Matching Distributor product name with master 
        product name(id) > match in distributor product(id) > distributor stock
    """
    def valid(n):
        return type(n)==int or type(n)==float
    try:
        if request.method == "POST":
            with transaction.atomic():
                if request.FILES.get('file'):
                    file = request.FILES.get('file')
                    if request.user.is_superuser or request.user.is_admin:
                        distributor_id = request.POST.get('distributor_id')
                        distributor = Distributor.objects.get(id=distributor_id)
                    else:
                        distributor = Distributor.objects.get(user=request.user)  
                    field = UploadProductDetailsFields.objects.get(user=distributor.user)
                    expected_columns = [
                        field.product_name, field.product_sku, field.hsncode, field.ptr, 
                        field.mrp, field.packing, field.product_category, field.product_composition, field.batch_number, 
                        field.quantity, field.expiry_date, field.discount, field.scheme_billed, field.scheme_free, field.manufacturer, field.gst]
                    filter_expected_columns = [field_name for field_name in expected_columns if field_name]
                    required_columns = [field.product_sku, field.product_name, field.mrp, field.ptr, field.quantity]
                    columns_to_convert = {field.hsncode: 'object', field.product_sku: str}
                    file_data = process_uploaded_file(field,file,required_columns, columns_to_convert,filter_expected_columns)
                    if field.expiry_date in file_data.columns:
                        file_data[field.expiry_date] = file_data[field.expiry_date].astype(str)
                    products_exist = False
                    exist_sku_list = []
                    for i, row in file_data.iterrows():
                        if (type(row.loc[field.product_sku])=="") and not valid(row.loc[field.quantity]):
                            continue
                        else:
                            product_sku = row.loc[field.product_sku]
                        distributor_prod_master, created = DistProductMaster.objects.update_or_create(
                            defaults={ "name":row.loc[field.product_name],
                            "distributor_sku":row.loc[field.product_sku],
                            "ptr":row.loc[field.ptr],
                            "mrp":row.loc[field.mrp],
                            "hsn":row.loc[field.hsncode],
                            "packing":row.loc[field.packing],
                            "product_category":row.loc[field.product_category],
                            "scheme_billed":row.loc[field.scheme_billed],
                            "scheme_free":row.loc[field.scheme_free],
                            "product_composition":row.loc[field.product_composition],
                            "distributor":distributor
                                      }, distributor_sku=product_sku,distributor=distributor)
                        
                        new_quantity = abs(row.loc[field.quantity])
                        dist_stock, created = DistributorStock.objects.update_or_create(
                            product=distributor_prod_master,
                            distributor=distributor,
                            batch_number=row.loc[field.batch_number],
                            defaults={
                                'batch_number': row.loc[field.batch_number],
                                'expiry_date': row.loc[field.expiry_date],
                                'ptr': row.loc[field.mrp],
                                'mrp': row.loc[field.ptr],
                                'discount': row.loc[field.discount],
                                'manufacturer': row.loc[field.manufacturer],
                                'gst': row.loc[field.gst],
                                'quantity':new_quantity
                            }
                        )
                        if dist_stock:
                            products_exist=True
                            exist_sku_list.append(row.loc[field.product_sku])
                        # if not created:
                        #     dist_stock_existing_qty = abs(dist_stock.quantity)
                        #     dist_stock.quantity = new_quantity
                        #     dist_stock.save()
                        # else:
                        #     dist_stock.quantity = new_quantity
                        #     dist_stock.save()
                    if products_exist:
                        DistributorStock.objects.select_related('product').filter(distributor=distributor).exclude(product__distributor_sku__in=exist_sku_list).update(quantity=0)
                        messages.success(request, 'Products File upload successfully.')
                        logger.info('Products File upload successfully')
                    else:
                        messages.error(request, 'Products Not Found.')
                        logger.info('Products File upload successfully')
                    return JsonResponse({'status':200})
    except Distributor.DoesNotExist:
        logger.error('Distributor Not Found!')
        return JsonResponse({'status':404,'message':"Distributor Not Found!"})
    except UploadProductDetailsFields.DoesNotExist:
        logger.error('Upload configuration not found for this distributor')
        return JsonResponse({'status':404,'message':"Upload configuration not found for this Partner"})
    except KeyError as e:
        logger.error(f"Column Name {str(e)} Not Found In File")
        return JsonResponse({'status':404,'message':f"Column Name {str(e)} Not Found In File"})
    except Exception as e:
        import sys, os
        logger.error("Issue upload file: ",str(e))
        return JsonResponse({'status':404,'message':str(e)})

@active_admin_or_sub_admin_required
def deals_list(request):
    today = date.today()
    products = Deal.objects.filter(
                                # Q(start_date__lte=today) &
                                (Q(end_date__gte=today) | Q(end_date__isnull=True))
                            ).order_by('-created_at')

    search_query = request.GET.get('search_query')
    if search_query:
        products = products.filter(
            Q(product__name__icontains=search_query) |
            Q(distributor__name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if request.method == "POST":
        if 'bulk_delete' in request.POST:
            selected_products = request.POST.getlist('selected_products[]')
            if selected_products:
                try:
                    # Delete selected Deal from the database
                    Deal.objects.filter(id__in=selected_products).delete()
                    messages.success(request, 'Selected Deals have been deleted successfully.')
                    return redirect('deals-list')
                except Exception as e:
                    messages.error(request, f'An error occurred while deleting Deal: {e}')
                    return redirect('deals-list')
            else:
                messages.warning(request, 'No Deals were selected for deletion.')
            return redirect('deals-list')  # Redirect to the Deal list page
        
        # if 'delete_deal' in request.POST:
        #     delete_id = request.POST.get('delete_deal')
        #     delete_org = Deal.objects.get(id=delete_id)
        #     if delete_org:
        #         delete_org.delete()
        #         messages.success(request,'Deleted  Successfully.')
        #         return redirect('deals-list')
            
        if 'deactive_deal' in request.POST:
            deactive_deal_id = request.POST.get('deactive_deal')
            deal_obj = Deal.objects.get(id=deactive_deal_id)
            if deal_obj:
                deal_obj.end_date = datetime.now().date()
                deal_obj.is_expired = True
                deal_obj.save()
                messages.success(request,'Deal Deactive Successfully.')
                return redirect('deals-list')
            
        if request.POST.get('selectedPartnerId') == 'All':
            distributor_id = request.POST.get('selectedPartnerId')
            if distributor_id == 'All':
                dist_products = Deal.objects.values_list(
                    'distributor__name','distributor__id', 'product__distributor_sku', 'product__name',
                    'discount_percentage', 'quantity', 'description'
                )
                if not dist_products:
                    messages.error(request, 'No Deals available for any Partner.')
                else:
                    response = HttpResponse(content_type='text/csv')
                    response['Content-Disposition'] = 'attachment; filename="All_Partner_Deals.csv"'
                    writer = csv.writer(response)
                    writer.writerow(['Distributor Name','Distributor Id', 'Distributor Product Id', 'Product Name',
                                    'Extra Discount', 'Qty', 'Description'])
                    writer.writerows(dist_products)
                    logger.info(f'All Partner Deals Downloaded By: {request.user.username}')
                    return response  
            else:
                messages.warning(request, 'Something went wrong.')
                return redirect('deals-list')
                
            
        if 'dashboard-deals' in request.POST: 
            distributor_id = request.POST.get('selectedPartnerId')
            if distributor_id:
                distributor = Distributor.objects.filter(id=distributor_id).first()
                if not distributor:
                    return HttpResponse("Partner not found.", status=404)
                # Filter products and related stock items
                dist_products = products.filter(distributor=distributor).values_list(
                    'distributor__name', 'distributor__id','product__distributor_sku','product__name','discount_percentage','quantity','description'
                )
                if not dist_products.exists():
                    messages.error(request, "No Deals available for the selected Partner.")
                    return redirect('deals-list')
                # Create a CSV response
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{ distributor.name }_Deals.csv"'

                # Write CSV data
                writer = csv.writer(response)
                writer.writerow(['Distributor Name','Distributor Id', 'Distributor Product Id','Product Name','Extra Discount','Qty','Description'])
                writer.writerows(dist_products)
                # ActivityLog.log_activity(user=request.user, action="Downloaded", details=f" '{distributor.name}' Deals has been downloaded by {request.user.username}.", to_user=distributor.user)
                logger.info(f'{distributor.name} Distributor Deals Downloaded By: {request.user.username}')
                return response
            
            else:
                messages.error(request, "Please select a valid Partner.")
                return redirect('deals-list')
            
        uploaded_file = request.FILES['file']
        if uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.csv') or uploaded_file.name.endswith('.xls'):
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['Distributor Product Id', 'Qty', 'Discount Percentage','Description']
            missing_columns = [col for col in cols if col not in df.columns]
            if not missing_columns:
                partnerId = request.POST.get('partner_id')
                end_date = request.POST.get('end_date')                
                distributor = Distributor.objects.filter(id=partnerId).first()
                msg = False
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="Wrong_Deals_Data.csv"'
                writer = csv.writer(response)
                writer.writerow(['Distributor Product Id', 'Qty', 'Discount Percentage','Description'])
                row_count = 0
                
                for index, row in df.iterrows():
                    product = DistProductMaster.objects.filter(distributor_sku=row['Distributor Product Id'], distributor=distributor ).first()
                    if product:
                        deal = Deal.objects.filter(
                            Q(is_expired=False) | Q(is_expired__isnull=True),distributor=distributor,
                            product=product,).first()
                                                
                        try:                            
                            if pd.isna(row['Description']) or row['Description'] == '':
                                writer.writerow([row.get('Distributor Product Id', ''), 
                                            row.get('Qty', ''), row.get('Discount Percentage', ''), 
                                            row.get('Description', ''), "Invalid data "])
                                row_count += 1
                                     
                            if deal:
                                if deal.start_date == datetime.now().date()+timedelta(days=1):                                
                                    writer.writerow([row.get('Distributor Product Id', ''), 
                                            row.get('Qty', ''), row.get('Discount Percentage', ''), 
                                            row.get('Description', ''), 'This deal already exists for the same date.'])
                                    row_count += 1
                                    continue
                                
                                if deal.start_date is None and deal.end_date is None:
                                    deal.start_date = deal.created_at.date()
                                    deal.end_date = datetime.now().date()
                                    deal.is_expired = True
                                    deal.save()
                                    
                                elif deal.start_date is not None:
                                    deal.end_date = datetime.now().date() if deal.end_date is None else deal.end_date
                                    deal.is_expired = True
                                    deal.save()
                                    
                                discription = row['Description']
                                Deal.objects.create(distributor=distributor, product=product, quantity=int(row['Qty']),
                                                description=discription,discount_percentage = row['Discount Percentage'],
                                                end_date = end_date if end_date else None)
                            else:
                                discription = row['Description']
                                Deal.objects.create(distributor=distributor, product=product, quantity=int(row['Qty']),
                                                description=discription,discount_percentage = row['Discount Percentage'],
                                                end_date = end_date if end_date else None)
                        except Exception as e:
                            logger.error(f"Error processing row {index}: {e}")
                            writer.writerow([row.get('Distributor Product Id', ''), 
                                            row.get('Qty', ''), row.get('Discount Percentage', ''), 
                                            row.get('Description', ''), "Invalid data "])
                            row_count += 1
                        # else:     
                        #     discription = f"Buy {row['Qty']} of {product.name} and get additional discount of {row['Extra Discount']}%"
                        #     deal = Deal.objects.filter(distributor=distributor, product=product).first()
                        #     if deal:
                        #         deal.quantity, deal.discount_percentage, deal.description = row['Qty'], row['Extra Discount'],discription
                        #         deal.save()
                        #     else:
                        #         Deal.objects.create(distributor=distributor, product=product, quantity=row['Qty'], discount_percentage=row['Extra Discount'],
                        #                             description=discription)
                        msg = True
                if row_count>=1:
                    return response
                messages.success(request, "File Uploaded Successfully." if msg else "No SKU Matched For This Partner." )
                return redirect('deals-list')
            else:
                if missing_columns:
                    missing_columns_are = ', '.join(missing_columns) if missing_columns else None
                    messages.error(request, f"The following columns are missing in the uploaded file: {missing_columns_are}.")
                else:
                    messages.error(request, "Please upload a Valid file.")
        else:
            messages.error(request, "Please upload Excel or CSV file only.")
    products = paginate_items(request, products, 20)
    partners = Distributor.objects.all()
    ctx = {'products': products, 'partners':partners}
    return TemplateResponse(request, 'deals_list.html', ctx)
    
@active_admin_required    
def distributor_deals(request, dist_id=None):
    product_id = request.GET.get('prod_id', "")
    if product_id:
        product = DistProductMaster.objects.get(id=product_id)
        distributor = Distributor.objects.get(user_id=dist_id)
        if request.method == "POST":
            try:
                discount_percentage = float(request.POST.get("discount_percentage", 0))
                description = request.POST.get("description", "")
                quantity = request.POST.get("quantity", 0)
                Deal.objects.update_or_create(
                    distributor=distributor,
                    product=product,
                    defaults={
                        "discount_percentage": discount_percentage,
                        "description": description,'quantity':quantity})
                logger.info("Deal created/updated successfully")
                return redirect('deals-list')
            except (ValueError, ObjectDoesNotExist) as e:
                logger.error(str(e))
                return render(request, 'deals.html', {"error": "Invalid data"})
            except Exception as e:
                logger.error(str(e))
                return render(request, 'deals.html', {"error": "An error occurred"})
        else:
            try:
                deal = Deal.objects.filter(distributor=distributor, product=product).first()
                ctx = {"dist_id": dist_id, "deal": deal}
                logger.info("Deal object successfully retrieved for GET request.")
                return render(request, 'deals.html', ctx) 
            except ObjectDoesNotExist:
                logger.error("Deal, product, or distributor not found")
                ctx = {"dist_id": dist_id, "error": "Deal, product, or distributor not found"}
            except Exception as e:
                logger.error(str(e))
    else:
        logger.error("Product ID not found")
        ctx = {"dist_id": dist_id, "error": "Product ID not found"}
        return redirect('deals-list', pk=dist_id)
    
@active_admin_or_sub_admin_required
def upload_configuration_partners(request,form_type):
    try:
        customers = Distributor.objects.all()
        customers = customers.order_by('organisation')
        partner_name = request.GET.get("partner_name")
        partner_id = request.GET.get("selectedPartnerId")
        customer_filter = customers
        if partner_name:
            customer_filter = customer_filter.filter(name__icontains=partner_name)
        if partner_id:
            customer_filter = customer_filter.filter(id=partner_id)
        customers = get_paginator_items(customer_filter, 30, request.GET.get('page'))
        ctx = {
            'customers': customers,
            'form_type':form_type
        }
        logger.info('Customer list retrieved successfully by user: %s', request.user.username)
        return TemplateResponse(request, 'upload_configuration_partners.html', ctx)
    except Exception as e:
        logger.error('Error fetching customer list: %s', str(e))


@active_admin_or_sub_admin_required
def dashboard_upload_configurations(request, form_type, dist_id):
    user = get_object_or_404(User, id=dist_id)
    template_to_extend = "dashboard.html"
    return process_upload_configurations(request, form_type, user, template_to_extend)


@active_distributor_required
def distributor_upload_configurations(request, form_type):
    user = get_object_or_404(User, id=request.user.pk)
    template_to_extend = "distributor_base.html"
    return process_upload_configurations(request, form_type, user, template_to_extend)



def get_medica_products(*args, **kwargs):
    print ("Medica api calling...")
    try:
        response = requests.get(REMOTE_API_URL)
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data:
                    data = data.get('data', [])
                    upload_medica_products(data)

                response_data = {
                    'status': 'success',
                    'message': 'Stock data retrieved successfully',
                    # 'data': data
                }

                return HttpResponse(json.dumps(response_data), content_type='application/json', status=200)

            except ValueError as ve:
                response_data = {
                    'status': 'error',
                    'message': 'Failed to parse response from the server as JSON',
                    'error': str(ve)
                }

                return HttpResponse(json.dumps(response_data), content_type='application/json', status=500)

        else:
            error_message = 'Remote server responded with status code 500'
            response_data = {
                'status': 'error',
                'message': 'Failed to retrieve stock data',
                'error': error_message
            }

            return HttpResponse(json.dumps(response_data), content_type='application/json', status=500)

    except Exception as e:
        error_message = str(e)
        response_data = {
            'status': 'error',
            'message': 'Failed to retrieve stock data',
            'error': error_message
        }

        return HttpResponse(json.dumps(response_data), content_type='application/json', status=500)