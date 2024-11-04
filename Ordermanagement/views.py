from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from Activitylog.models import ActivityLog
from Paymentmanagement.utils import log_activity
import csv
from django.http import HttpResponse
import pandas as pd
from django.db.models import Q
from Usermanagement import paginate_items
from Usermanagement.models import KYC, Distributor, PartyCode, Retailer, User
from Productmanagement.forms import ProductDealsForm
from Productmanagement.models import Deal, DistProductMaster
from b2b2.settings import CURRENCY, S3_LINK
from .models import Order,OrderedItem
from Paymentmanagement.models import Invoice, UploadedBillDetails
from Usermanagement.utils import active_admin_or_sub_admin_required, active_admin_required, active_distributor_required, generate_presigned_url, login_required
from django.contrib import messages
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) 
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Create your views here.
@active_admin_required
def order_details(request,pk=None):
    orders = Order.objects.all().order_by('-created_at')
    orders = paginate_items(request,orders,10)
    ctx={'orders':orders,'currency':CURRENCY}
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_admin):
        return TemplateResponse(request,'orders_list.html',ctx)
    return TemplateResponse(request,'distributor_list.html',ctx)


@active_distributor_required
def order_list(request):
    distributor = get_object_or_404(Distributor,user_id=request.user.pk)
    orders = Order.objects.filter(distributor_id=distributor.id).order_by('-created_at')
    order_search_for = request.GET.get('search_order_details')
    date_range = request.GET.get('daterange')   
    if order_search_for:
        orders = orders.filter(
            Q(id__icontains = order_search_for)|
            Q(order_status__icontains = order_search_for)|
            Q(user__retailer__store_name__icontains = order_search_for)
            )
    if date_range:
        start_date, end_date = date_range.split(' - ')
        start_date = datetime.strptime(start_date, '%m/%d/%Y').date()
        end_date = datetime.strptime(end_date, '%m/%d/%Y').date()
        orders = orders.filter(created_at__date__range=[start_date, end_date])
    orders = paginate_items(request,orders,10)
    ctx={'orders':orders,"currency":CURRENCY}
    return TemplateResponse(request,'distributor_orders_list.html',ctx)

@active_distributor_required
def dist_order_details(request,order_id):
    try:
        order_instance = get_object_or_404(Order, id=order_id)
        if request.method == 'POST':
            status = request.POST.get('status', "")
            if status:
                order_instance.order_status = status
                order_instance.save()
                log_activity(request,status,order_instance)
                messages.success(request, f"Order {status}")
                return redirect('dist-order-details', order_id)
        ordered_items = order_instance.ordereditem_set.all().order_by('product__name')
        # order_items = paginate_items(request, ordered_items, 10)
        user_kyc = get_object_or_404(KYC, user_id=order_instance.user_id)
        drug_license_number = user_kyc.drug_license_number
        drug_license_images = order_instance.user.documents
        customer = get_object_or_404(Retailer, user=order_instance.user)
        invoice_details = Invoice.objects.filter(order=order_instance).first()
        invoice_history = ActivityLog.objects.filter(order=order_instance)
        party_code = PartyCode.objects.filter(retailer=customer,distributor=order_instance.distributor).first()
        

        ctx = {
            "order_instance": order_instance,
            "order_items": ordered_items,
            "drug_license_number": drug_license_number,
            "customer": customer,
            "invoice":invoice_details,
            "invoice_image": generate_presigned_url(str(invoice_details.invoice_file)) if invoice_details and invoice_details.invoice_file else "",
            # "s3_link":S3_LINK,generate_presigned_url(str()),
            "drug_license_form20":generate_presigned_url(str(drug_license_images.drug_license_form20)),
            "drug_license_form21":generate_presigned_url(str(drug_license_images.drug_license_form21)),
            "invoice_history":invoice_history,
            "currency":CURRENCY,
            "party_code":party_code,
        }
        return TemplateResponse(request, 'distributor_order_details.html', ctx)
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        logger.error("Order not found")
        return redirect('dist-order-details', order_id)
    except KYC.DoesNotExist:
        messages.error(request, "KYC details not found")
        logger.error("KYC details not found")
        return redirect('dist-order-details', order_id)
    except Retailer.DoesNotExist:
        messages.error(request, "Retailer details not found")
        logger.error("Retailer details not found")
        return redirect('dist-order-details', order_id)
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        logger.error(f"An unexpected error occurred: {str(e)}")
        return redirect('dist-order-details', order_id)


@active_admin_or_sub_admin_required
def dashboard_order_details(request,order_id):
    try:
        order_instance = get_object_or_404(Order, id=order_id)
        if request.method == 'POST':
            status = request.POST.get('status', "")
            if status:
                order_instance.order_status = status
                order_instance.save() 
                log_activity(request,status,order_instance)
                messages.success(request, f"Order {status}")
                return redirect('dashboard-order-details', order_id)
        ordered_items = order_instance.ordereditem_set.all().order_by('product__name')
        distributor_name = ordered_items.first().distributor_id.name
        customer = get_object_or_404(Retailer, user=order_instance.user)
        invoice_history = ActivityLog.objects.filter(order=order_instance)
        party_code = PartyCode.objects.filter(retailer=customer,distributor=order_instance.distributor).first()
        ctx = {
            "order_instance": order_instance,
            "order_items": ordered_items,
            "customer": customer,
            "invoice_history":invoice_history,
            "currency":CURRENCY,
            'distributor_name':distributor_name,
            "party_code":party_code
        }
        return TemplateResponse(request, 'dashboard_order_details.html', ctx)
    except Order.DoesNotExist:
        messages.error(request, "Order not found")
        logger.error("Order not found")
        return redirect('dashboard-orders', order_id)
    except Retailer.DoesNotExist:
        messages.error(request, "Retailer details not found")
        logger.error("Retailer details not found")
        return redirect('dashboard-orders', order_id)
    except Exception as e:
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        logger.error(f"An unexpected error occurred: {str(e)}")
        return redirect('dashboard-orders', order_id)
      
@active_distributor_required
def upload_deals(request):
    from datetime import date
    distributor = get_object_or_404(Distributor,user_id=request.user.pk)
    form = ProductDealsForm(request.GET)
    today = date.today()
    products = Deal.objects.filter((Q(end_date__gte=today) | Q(end_date__isnull=True)), distributor=distributor)
    if form.is_valid():
        search_query = form.cleaned_data.get('search_query')
        if search_query:
            products = products.filter(
                Q(product__name__icontains=search_query) |
                Q(distributor__name__icontains=search_query) |
                Q(description__icontains=search_query)
            )
    if request.method == "POST":
        uploaded_file = request.FILES['file']
        if uploaded_file.name.endswith('.xlsx') or uploaded_file.name.endswith('.csv') or uploaded_file.name.endswith('.xls'):
            df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
            cols_stripped = [col.strip() for col in df.columns]
            df.columns = cols_stripped
            cols = ['Distributor Product Id', 'Qty', 'Extra Discount', 'Description']
            missing_columns = [col for col in cols if col not in df.columns]
            if not missing_columns:
                for index, row in df.iterrows():
                    # distributor_in_df = Distributor.objects.filter(id=row['Distributor Id']).first()
                    # if distributor_in_df == distributor:
                    product = DistProductMaster.objects.filter(distributor_sku=row['Distributor Product Id']).first()
                    deal = Deal.objects.filter(distributor=distributor, product=product).first()
                    if deal:
                        deal.quantity, deal.discount_percentage, deal.description = row['Qty'], row['Extra Discount'], row['Description']
                        deal.save()
                    else:
                        Deal.objects.create(distributor=distributor, product=product, quantity=row['Qty'], discount_percentage=row['Extra Discount'],
                                            description=row['Description'])
                messages.success(request, "File Uploaded Successfully.")
            else:
                messages.error(request, "Please upload a Valid file.")
        else:
            messages.error(request, "Please upload Excel or CSV file only.")
    products = paginate_items(request, products, 10)
    ctx = {'products': products}
    return TemplateResponse(request,'distributor_upload_deals.html', ctx)


@active_distributor_required
def raised_issues(request):
    distributor = get_object_or_404(Distributor, user_id=request.user.pk)
    if request.method == "POST" and "issueId" in request.POST:
        order_id = request.POST.get('issueId')
        order = get_object_or_404(Order, id=order_id, distributor=distributor)
        order.issue_status = 'Close'
        order.save()
    open_issues = Order.objects.filter(distributor=distributor, issue_status="Open").order_by('-created_at')
    search_query = request.GET.get('search_query')
    if search_query:
        open_issues = open_issues.filter(
            Q(issue_type__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    ctx = {'issues': open_issues}
    return TemplateResponse(request, 'distributor_open_issues.html', ctx)

@active_distributor_required
def download_order_details(request, order_id):
    headers = [
        'OrderID',
        'Retailer Name',
        'Retailer address',
        'Retailer Drug License No.',
        'Retailer GST No.',
        'Contact number',
        'Owner Name',
        'Product Name',
        'Packing',
        'Quantity'
    ]
    try:
        order = Order.objects.get(id=order_id)
        retailer = Retailer.objects.get(user=order.user)
        kyc = order.user.kyc_details
    except Order.DoesNotExist:
        return redirect('dist-order-details',order_id)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename=Order Details {order_id}.csv'
    writer = csv.writer(response)
    writer.writerow(headers)
    for item in order.ordereditem_set.all():
        data_row = [
            order_id,
            order.retailer_store_name,
            order.get_address,
            kyc.drug_license_number,
            kyc.gst_number,
            order.user.phone_number,
            retailer.owner_name,
            item.product.name,
            item.product.packing,
            item.quantity
        ]
        writer.writerow(data_row)
    return response

