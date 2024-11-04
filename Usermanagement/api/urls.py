from django.urls import path
from .views import *

urlpatterns = [
    path("generate-otp/", SendLoginOTP, name="generate-otp"),
    path("verify-otp/", VerifyOTP, name="verify-otp"),
    path("retailer-kyc/", retailer_kyc, name="retailer-kyc"),  # for creating new retailer KYC
    path("edit-retailer-kyc/", edit_retailer_kyc, name="edit-retailer-kyc"),  # for editing retailer KYC
    path('distributors/', distributor_list, name='distributor-list'),
    path('feedback/', feedback, name='feedback'),
    path("dashboard_api/", dashboard_api, name="dashboard_api"),
    path("get-kyc/", get_retailer_kyc_data, name="get-kyc"),
    path("register-retailer/", register_retailer, name="register_retailer"),
    path("myaccount_api/", MyAccount, name="my-profile-api"),
    path('daily-sales-report/', daily_sales_report, name='daily-sales-report'),
    path('monthly-sales-report/', monthly_sales_report, name='monthly-sales-report'),
    path('configuration/', Configuration, name='configuration'),
    path('retailer_delete/', retailer_delete, name='retailer_delete'),
    path('callex_dashboard/', callex_dashboard, name='callex_dashboard'),
    path('callex_search_retailer/', callex_search_retailer, name='callex_search_retailer'),

    # Add more API endpoints as needed
]
