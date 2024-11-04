import logging
from django.shortcuts import redirect, render
import pandas as pd
from Activitylog.models import ActivityLog
from Paymentmanagement.utils import extract_form_data
from Productmanagement.forms import ProductDealsForm
from Productmanagement.models import DistProductMaster, DistributorStock, UploadProductDetailsFields, UploadedBillDetailsFields
from django.contrib import messages
from django.template.response import TemplateResponse

from Usermanagement import paginate_items
from Usermanagement.models import Distributor
from django.http import HttpResponse 
import csv
from b2b2.settings import CURRENCY



logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def process_upload_configurations(request, form_type, user, template_to_extend):
    if form_type == 'billdetails':
        model_name = UploadedBillDetailsFields
    elif form_type == 'products':
        model_name = UploadProductDetailsFields
    if request.method == 'POST':
        if request.FILES.get('file'):
            try:
                file = request.FILES.get('file')
                file_header = int(request.POST.get('header'))
                file_header-=1
                if str(file).lower().endswith('.csv'):
                    file_data = pd.read_csv(file,header=file_header,nrows=1)
                elif str(file).lower().endswith('.xlsx',):
                    file_data = pd.read_excel(file,header=file_header,nrows=1)
                elif str(file).lower().endswith('.xls',):
                    file_data = pd.read_excel(file,header=file_header,nrows=1)
                else:
                    messages.error(request, "Invalid file format. Only XLSX, CSV, and XLS formats are accepted.")
                    if request.user.is_superuser or request.user.is_admin:
                        return redirect('dashboard-upload-configuration', form_type=form_type, dist_id=user.id)
                    elif request.user.is_distributor:
                        return redirect('distributor-upload-configuration', form_type=form_type)
                invalid_columns = [col for col in file_data.columns if not isinstance(col, str) or isinstance(col, int) or str(col).startswith('Unnamed: ')]
                if invalid_columns:
                    ctx = {
                        "form_type": form_type, "template_to_extend": template_to_extend
                        }
                    messages.error(request,f"The upload file columns are not valid type please check configuration demo")
                    if request.user.is_superuser or request.user.is_admin:
                        return redirect('dashboard-upload-configuration', form_type=form_type, dist_id=user.id)
                    elif request.user.is_distributor:
                        return redirect('distributor-upload-configuration', form_type=form_type)
                column_headers = sorted(file_data.columns.tolist())
                ctx = {
                    'column_headers': column_headers,
                    'form_type': form_type,
                    'dist_id': user.id,
                    "template_to_extend": template_to_extend
                }
                form_type = request.POST.get('form_type')
                if form_type == 'billdetails':
                    return render(request, 'bill_details_column_mapping.html', ctx)
                elif form_type == 'products':
                    return render(request, 'products_column_mapping.html', ctx)
            except pd.errors.EmptyDataError:
                logger.error("Empty CSV file")
            except Exception as e:
                logger.error(f"Error: {e}")
        else:
            if request.POST.get('upload_flag'):
                ctx = {
                    "form_type": form_type, "template_to_extend": template_to_extend
                }
                return render(request, 'upload_configuration.html', ctx)
            fields_to_remove = ['user', 'id']
            all_fields_list = [field.name for field in model_name._meta.get_fields()]
            all_fields_list = [field for field in all_fields_list if field not in fields_to_remove]
            form_data = extract_form_data(request, *all_fields_list)
            obj, created = model_name.objects.update_or_create(
                user=user,
                defaults=form_data,
            )
            if created:
                messages.success(request, 'Form submitted successfully!')
            else:
                messages.success(request, 'Form updated successfully!')
            if request.user.is_superuser or request.user.is_admin:
                return redirect('dashboard-upload-configuration', form_type=form_type, dist_id=user.id)
            elif request.user.is_distributor:
                return redirect('distributor-upload-configuration', form_type=form_type)
    if form_type == 'billdetails':
        if model_name.objects.filter(user=user).exists():
            details = model_name.objects.filter(user=user).first()
            ctx = {
                'bill_details': details, "template_to_extend": template_to_extend
            }
            return TemplateResponse(request, 'upload_billdetails_configuration_edit.html', ctx)
    elif form_type == 'products':
        if model_name.objects.filter(user=user).exists():
            details = model_name.objects.filter(user=user).first()
            ctx = {
                'bill_details': details, "template_to_extend": template_to_extend
            }
            return TemplateResponse(request, 'upload_products_configuration_edit.html', ctx)

    ctx = {
        "form_type": form_type, "template_to_extend": template_to_extend
    }
    return TemplateResponse(request, 'upload_configuration.html', ctx)


def get_product_list_context(request, query_set,template_to_extend,redirect_url,prod_create_url):
    try:
        form = ProductDealsForm(request.GET)
        if form.is_valid():
            search_query = form.cleaned_data.get('search_query')
            partner_id = request.GET.get('selectedPartnerId')
            partner_name = request.GET.get('partner_name')
            product_sku = request.GET.get('product_sku')
            if search_query:
                query_set = query_set.filter(name__icontains=search_query)

            # Modify the queryset based on other form fields if needed
            if partner_id and partner_name:
                query_set = query_set.filter(distributor__id=partner_id,distributor__name__icontains=partner_name)
            if product_sku:
                query_set = query_set.filter(distributor_sku=product_sku)
                
     
        if 'dashboard-products' in request.POST:
            distributor_id = request.POST.get('selectedPartnerId1')
            if distributor_id:
                distributor = Distributor.objects.filter(id=distributor_id).first()
            
                if not distributor:
                    return HttpResponse("Distributor not found.", status=404)

                # Filter products and related stock items
                dist_products = query_set.filter(distributor=distributor).values_list(
                    'name', 'distributor__name', 'distributor_sku', 'description','product_category', 'hsn', 
                    'ptr', 'mrp',  'distributorstock__quantity','scheme_billed','scheme_free', 'distributorstock__batch_number',
                    'distributorstock__expiry_date', 'distributorstock__discount', 
                    'distributorstock__manufacturer', 'distributorstock__gst'
                )
                if not dist_products.exists():
                    messages.error(request, "No products available for the selected Partner.")
                    return redirect('dashboard-products')

                # Create a CSV response
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="{ distributor.name }_Products.csv"'

                # Write CSV data
                writer = csv.writer(response)
                writer.writerow(['Product Name', 'Distributor Name', 'Distributor SKU', 'Description','Category', 'HSN', 'PTR', 'MRP', 'Quantity','Scheme Billed','Scheme Free', 'Batch Number', 'Expiry Date', 'Discount', 'Manufacturer', 'GST'])
                writer.writerows(dist_products)
                # ActivityLog.log_activity(user=request.user, action="Downloaded", details=f" '{distributor.name}' Products has been downloaded by {request.user.username}.", to_user=distributor.user)
                logger.info(f'{distributor.name} Distributor Products Downloaded By: {request.user.username}')

                return response
            else:
                messages.error(request,"Please select a valid Partner")
                return redirect('dashboard-products')


        # Paginate and render the filtered queryset
        products = paginate_items(request, query_set, 10)          
        ctx = {
            "distributor_products": products,
            "form": form,
            "currency": CURRENCY,
            "template_to_extend": template_to_extend,
            "redirect_url":redirect_url,
            "prod_create_url":prod_create_url,
            "request":request
        }
    except Exception as e:
        logger.error("Exception occurred in products list", str(e))
        ctx = {}
    return TemplateResponse(request, "product_list.html", ctx)

def get_product_edit_context(request,product_instance,template_to_extend,redirect_url):
    try:
        if request.method == "POST":
            product_instance.name=request.POST.get('name')
            product_instance.distributor_sku=request.POST.get('distributor_sku')
            product_instance.ptr=request.POST.get('ptr')
            product_instance.mrp=request.POST.get('mrp')
            product_instance.hsn=request.POST.get('hsn')
            product_instance.packing=request.POST.get('packing')
            product_instance.product_category=request.POST.get('product_category')
            product_instance.scheme_billed=request.POST.get('scheme_billed')
            product_instance.scheme_free=request.POST.get('scheme_free')
            product_instance.product_class=request.POST.get('product_class')
            product_instance.product_salt=request.POST.get('product_salt')
            product_instance.product_composition=request.POST.get('product_composition')
            product_instance.save()
            messages.success(request,f"Product Name :{product_instance.name} updated Successfully")
            logger.info('Product updated Successfully')
            return redirect(redirect_url)
        distributor_stock_instances = product_instance.distributorstock_set.all()
        ctx = {'product':product_instance,'distributor_stock_instances':distributor_stock_instances,
               "currency":CURRENCY,"template_to_extend":template_to_extend
               }
        return TemplateResponse(request,"product_edit.html",ctx)
    except Exception as e:
        messages.error(request,f"Exception Occured!{str(e)}")
        logger.error(f"exception occcured in product edit : {str(e)}")
        return redirect(redirect_url)

def upload_medica_products(data):
    print("Stock updating")
    try:
        products_data = data
        dist_id = "1"
        # product_ids = [product['product_id'].lower() for product in products_data]

        dist_data = DistProductMaster.objects.filter(distributor_id=dist_id)
        dist_data_dict = {each_obj.distributor_sku.lower(): each_obj for each_obj in dist_data}

        data = DistributorStock.objects.select_related('product') \
            .filter(product__distributor_id=dist_id, product__is_deleted=0)
        data_dict = {each_obj.product.distributor_sku.lower(): each_obj for each_obj in data}

        for product in products_data:
            product_id = product['product_id'].lower()
            distributor_stock_obj = data_dict.get(product_id)
            distributor_obj = dist_data_dict.get(product_id)
            if distributor_obj:
                if distributor_stock_obj:
                    distributor_stock_obj.quantity = abs(product['quantity']) if product['quantity'] else 0
                    distributor_stock_obj.save()
    except Exception as e:
        logger.exception("An error occurred in upload_medica_products: %s", e)