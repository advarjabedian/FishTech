from django.urls import path
from ..views.documents import *
from ..views.documents_api_entities import *
from ..views.documents_api_emails import *
from ..views.licenses_vehicles import *

urlpatterns = [
    path('', documents_home, name='documents_home'),
    path('customer/', customer_documents, name='customer_documents'),
    path('vendor/', vendor_documents, name='vendor_documents'),
    path('licenses/', licenses, name='licenses'),
    path('vehicles/', vehicles, name='vehicles'),
]

api_urlpatterns = [
    # Search
    path('customers/search/', search_customers, name='search_customers'),
    path('vendors/search/', search_vendors, name='search_vendors'),

    # Tenant address book
    path('tenant-emails/', get_tenant_emails, name='get_tenant_emails'),
    path('add-tenant-email/', add_tenant_email, name='add_tenant_email'),
    path('delete-tenant-email/<int:email_id>/', delete_tenant_email, name='delete_tenant_email'),

    # Customer emails
    path('customer-emails/<int:customer_id>/', get_customer_emails, name='get_customer_emails'),
    path('add-customer-email/', add_customer_email, name='add_customer_email'),
    path('delete-customer-email/<int:email_id>/', delete_customer_email, name='delete_customer_email'),

    # Vendor emails
    path('vendor-emails/<int:vendor_id>/', get_vendor_emails, name='get_vendor_emails'),
    path('add-vendor-email/', add_vendor_email, name='add_vendor_email'),
    path('delete-vendor-email/<int:email_id>/', delete_vendor_email, name='delete_vendor_email'),

    # Customer files
    path('customer/', get_customer_documents, name='get_customer_documents'),
    path('customer/<int:customer_id>/files/', get_customer_files, name='get_customer_files'),
    path('customer/<int:customer_id>/files/<str:filename>/view/', view_customer_file, name='view_customer_file'),
    path('customer/upload/', upload_customer_file, name='upload_customer_file'),
    path('customer/<int:customer_id>/files/<str:filename>/', delete_customer_file, name='delete_customer_file'),
    path('customer/email-files/', email_customer_files, name='email_customer_files'),

    # Vendor files
    path('vendor/', get_vendor_documents, name='get_vendor_documents'),
    path('vendor/<int:vendor_id>/files/', get_vendor_files, name='get_vendor_files'),
    path('vendor/<int:vendor_id>/files/<str:filename>/view/', view_vendor_file, name='view_vendor_file'),
    path('vendor/upload/', upload_vendor_file, name='upload_vendor_file'),
    path('vendor/<int:vendor_id>/files/<str:filename>/', delete_vendor_file, name='delete_vendor_file'),
    path('vendor/email-files/', email_vendor_files, name='email_vendor_files'),

    # Licenses
    path('licenses/', get_licenses_api, name='get_licenses_api'),
    path('licenses/upload/', upload_license_api, name='upload_license_api'),
    path('licenses/<int:license_id>/update/', update_license_api, name='update_license_api'),
    path('licenses/<str:filename>/view/', view_license_file_api, name='view_license_file_api'),
    path('licenses/delete/<str:filename>/', delete_license_api, name='delete_license_api'),

    # Vehicles
    path('vehicles/', get_vehicles_api, name='get_vehicles_api'),
    path('vehicles/add/', add_vehicle_api, name='add_vehicle_api'),
    path('vehicles/<int:vehicle_id>/update/', update_vehicle_api, name='update_vehicle_api'),
    path('vehicles/<int:vehicle_id>/delete/', delete_vehicle_api, name='delete_vehicle_api'),
]
