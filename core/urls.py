from django.urls import path
from .views import (
    # Auth views
    login_view, logout_view, operations_hub, register_view,
    # Document views
    documents_home, so_documents, po_documents, customer_documents, vendor_documents,
    licenses, vehicles,
    get_licenses_api, upload_license_api, update_license_api, view_license_file_api, delete_license_api,
    get_vehicles_api, add_vehicle_api, update_vehicle_api, delete_vehicle_api,
    get_expiration_counts_api,
    # Document APIs
    search_customers, search_vendors,
    get_sales_orders, get_so_files, view_so_file, upload_so_file, delete_so_file,
    get_purchase_orders, get_po_files, view_po_file, upload_po_file, delete_po_file,
    get_pod_items, download_bulk_po_files, email_bulk_po_files, email_po_files,
    get_vendor_emails, add_vendor_email, delete_vendor_email,
    get_customer_emails, add_customer_email, delete_customer_email,
    get_tenant_emails, add_tenant_email, delete_tenant_email,
    get_customer_documents, get_customer_files, view_customer_file,
    upload_customer_file, delete_customer_file, email_customer_files,
    get_vendor_documents, get_vendor_files, view_vendor_file,
    upload_vendor_file, delete_vendor_file, email_vendor_files,
    download_bulk_so_files, email_bulk_so_files, email_so_files,
    # HACCP views
    haccp, haccp_company, haccp_documents, haccp_document_view,
    haccp_save_document, get_company_product_types, toggle_company_product_type,
    generate_new_version, get_version_history, get_flow_chart_data,
    get_hazard_analysis_data, delete_haccp_version, get_haccp_version,
    get_master_product_types, get_all_product_types, add_product_type,
    delete_product_type, get_inactive_product_types, restore_product_type,
    update_product_type,
    set_haccp_owner, get_company_certificates, save_company_certificate,
    view_company_certificate, add_company, edit_company, delete_company,
    # User management
    manage_users, add_user, edit_user, delete_user, update_company_logo,
    toggle_user_company, toggle_user_admin,
    # Operations views
    operations_dashboard, inspection_form, operations_admin, print_sop_schedule,
    # Operations API
    start_inspection, save_inspection, update_inspection_time, update_inspection_inspector,
    update_company_config, toggle_holiday, get_deviations, save_corrective_actions,
    submit_verification, save_verifier_signature, get_verifier_signature,
    save_monitor_signature, get_monitor_signature, get_operations_config,
    get_sop_list, create_sop, update_sop, delete_sop, get_zones, create_zone,
    delete_zone, get_calendar_data, get_inspection_images, get_companies
)
from .views.operations_reports import generate_operational_report, generate_deviations_report, generate_bulk_report
from .views.stripe_billing import (
    get_billing_status, create_checkout_session, create_portal_session, stripe_webhook
)

urlpatterns = [
    # Auth routes
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    
    # Operations Hub
    path('operations/', operations_hub, name='operations_hub'),
    
    # HACCP routes
    path('haccp/', haccp, name='haccp'),
    path('haccp/<int:company_id>/', haccp_company, name='haccp_company'),
    path('haccp/<int:company_id>/<slug:product_type>/', haccp_documents, name='haccp_documents'),
    path('haccp/<int:company_id>/<slug:product_type>/<str:document_type>/', haccp_document_view, name='haccp_document_view'),
    path('haccp/certificate/<int:company_id>/<str:certificate_type>/', view_company_certificate, name='view_company_certificate'),
    
    # HACCP API
    path('api/haccp/<int:company_id>/<slug:product_type>/<str:document_type>/save/', haccp_save_document, name='haccp_save_document'),
    path('api/company-product-types/<int:company_id>/', get_company_product_types, name='get_company_product_types'),
    path('api/company-product-types/<int:company_id>/toggle/', toggle_company_product_type, name='toggle_company_product_type'),
    path('api/haccp-generate-version/<int:company_id>/<slug:product_type>/<str:document_type>/', generate_new_version, name='generate_new_version'),
    path('api/haccp-version-history/<int:company_id>/<slug:product_type>/<str:document_type>/', get_version_history, name='get_version_history'),
    path('api/haccp-flow-chart-data/<int:company_id>/<slug:product_type>/', get_flow_chart_data, name='get_flow_chart_data'),
    path('api/haccp-hazard-analysis-data/<int:company_id>/<slug:product_type>/', get_hazard_analysis_data, name='get_hazard_analysis_data'),
    path('api/haccp-delete-version/<int:company_id>/<slug:product_type>/<str:document_type>/', delete_haccp_version, name='delete_haccp_version'),
    path('api/haccp-get-version/<int:company_id>/<slug:product_type>/<str:document_type>/', get_haccp_version, name='get_haccp_version'),
    path('api/haccp-master-product-types/', get_master_product_types, name='get_master_product_types'),
    path('api/haccp-all-product-types/', get_all_product_types, name='api_haccp_all_product_types'),
    path('api/haccp-add-product-type/', add_product_type, name='api_haccp_add_product_type'),
    path('api/haccp-delete-product-type/', delete_product_type, name='api_haccp_delete_product_type'),
    path('api/haccp-inactive-product-types/', get_inactive_product_types, name='api_haccp_inactive_product_types'),
    path('api/haccp-restore-product-type/', restore_product_type, name='api_haccp_restore_product_type'),
    path('api/haccp-update-product-type/', update_product_type, name='api_haccp_update_product_type'),  
    path('api/haccp-set-owner/<int:company_id>/', set_haccp_owner, name='haccp_set_owner'),
    path('api/company-certificates/<int:company_id>/', get_company_certificates, name='get_company_certificates'),
    path('api/company-certificates/<int:company_id>/save/', save_company_certificate, name='save_company_certificate'),
    
    # User management
    path('manage-users/', manage_users, name='manage_users'),
    path('api/add-user/', add_user, name='add_user'),
    path('api/edit-user/<int:user_id>/', edit_user, name='edit_user'),
    path('api/delete-user/<int:user_id>/', delete_user, name='delete_user'),
    path('api/toggle-user-company/', toggle_user_company, name='toggle_user_company'),
    path('api/toggle-user-admin/', toggle_user_admin, name='toggle_user_admin'),
    
    # Company management
    path('api/add-company/', add_company, name='add_company'),
    path('api/edit-company/<int:company_id>/', edit_company, name='edit_company'),
    path('api/delete-company/<int:company_id>/', delete_company, name='delete_company'),
    
    # Daily Inspections / Operations
    path('operations/daily/', operations_dashboard, name='operations_dashboard'),
    path('operations/inspection/<int:parent_id>/', inspection_form, name='inspection_form'),
    path('operations/admin/', operations_admin, name='operations_admin'),
    path('operations/print-sop-schedule/', print_sop_schedule, name='print_sop_schedule'),
    
    # Operations Reports
    path('operations/report/operational/<int:parent_id>/', generate_operational_report, name='generate_operational_report'),
    path('operations/report/deviations/<int:parent_id>/', generate_deviations_report, name='generate_deviations_report'),
    path('operations/bulk-report/', generate_bulk_report, name='generate_bulk_report'),
    
    # Operations API
    path('api/operations/start-inspection/', start_inspection, name='start_inspection'),
    path('api/operations/save-inspection/<int:parent_id>/', save_inspection, name='save_inspection'),
    path('api/operations/update-time/<int:parent_id>/', update_inspection_time, name='update_inspection_time'),
    path('api/operations/update-inspector/<int:parent_id>/', update_inspection_inspector, name='update_inspection_inspector'),
    path('api/operations/update-config/', update_company_config, name='update_company_config'),
    path('api/operations/toggle-holiday/', toggle_holiday, name='toggle_holiday'),
    path('api/operations/get-deviations/<int:parent_id>/', get_deviations, name='get_deviations'),
    path('api/operations/save-corrective-actions/', save_corrective_actions, name='save_corrective_actions'),
    path('api/operations/submit-verification/', submit_verification, name='submit_verification'),
    path('api/operations/save-verifier-signature/', save_verifier_signature, name='save_verifier_signature'),
    path('api/operations/get-verifier-signature/', get_verifier_signature, name='get_verifier_signature'),
    path('api/operations/save-monitor-signature/', save_monitor_signature, name='save_monitor_signature'),
    path('api/operations/get-monitor-signature/', get_monitor_signature, name='get_monitor_signature'),
    path('api/operations/get-config/', get_operations_config, name='get_operations_config'),
    path('api/operations/sop-list/', get_sop_list, name='get_sop_list'),
    path('api/operations/sop-create/', create_sop, name='create_sop'),
    path('api/operations/sop-update/', update_sop, name='update_sop'),
    path('api/operations/sop-delete/', delete_sop, name='delete_sop'),
    path('api/operations/zones/', get_zones, name='get_zones'),
    path('api/operations/zone-create/', create_zone, name='create_zone'),
    path('api/operations/zone-delete/', delete_zone, name='delete_zone'),
    path('api/operations/get-calendar-data/', get_calendar_data, name='get_calendar_data'),
    path('api/operations/get-inspection-images/<int:parent_id>/', get_inspection_images, name='get_inspection_images'),
    path('api/operations/get-companies/', get_companies, name='get_companies'),

    path('api/update-company-logo/<int:company_id>/', update_company_logo, name='update_company_logo'),
    
    # Documents
    path('documents/', documents_home, name='documents_home'),
    path('documents/so/', so_documents, name='so_documents'),
    path('documents/po/', po_documents, name='po_documents'),
    path('documents/customer/', customer_documents, name='customer_documents'),
    
    # Documents API - Customers
    path('api/documents/customers/search/', search_customers, name='search_customers'),
    
    # Documents API - Vendors
    path('api/documents/vendors/search/', search_vendors, name='search_vendors'),
    
    # Documents API - Sales Orders
    path('api/documents/so/', get_sales_orders, name='get_sales_orders'),
    path('api/documents/so/upload/', upload_so_file, name='upload_so_file'),
    path('api/documents/so/<str:soid>/files/', get_so_files, name='get_so_files'),
    path('api/documents/so/<str:soid>/files/<str:filename>/view/', view_so_file, name='view_so_file'),
    path('api/documents/so/<str:soid>/files/<str:filename>/', delete_so_file, name='delete_so_file'),
    path('api/documents/so/email-files/', email_so_files, name='email_so_files'),
    
    # Tenant-wide Address Book
    path('api/documents/tenant-emails/', get_tenant_emails, name='get_tenant_emails'),
    path('api/documents/add-tenant-email/', add_tenant_email, name='add_tenant_email'),
    path('api/documents/delete-tenant-email/<int:email_id>/', delete_tenant_email, name='delete_tenant_email'),
    
    # Documents API - Purchase Orders
    path('api/documents/po/', get_purchase_orders, name='get_purchase_orders'),
    path('api/documents/po/upload/', upload_po_file, name='upload_po_file'),
    path('api/documents/po/<str:poid>/files/', get_po_files, name='get_po_files'),
    path('api/documents/po/<str:poid>/files/<str:filename>/view/', view_po_file, name='view_po_file'),
    path('api/documents/po/<str:poid>/files/<str:filename>/', delete_po_file, name='delete_po_file'),
    path('api/documents/po/<str:poid>/pod-items/', get_pod_items, name='get_pod_items'),
    path('api/documents/po/download-bulk/', download_bulk_po_files, name='download_bulk_po_files'),
    path('api/documents/po/email-bulk/', email_bulk_po_files, name='email_bulk_po_files'),
    path('api/documents/po/email-files/', email_po_files, name='email_po_files'),
    
    # Vendor Emails API
    path('api/documents/vendor-emails/<int:vendor_id>/', get_vendor_emails, name='get_vendor_emails'),
    path('api/documents/add-vendor-email/', add_vendor_email, name='add_vendor_email'),
    path('api/documents/delete-vendor-email/<int:email_id>/', delete_vendor_email, name='delete_vendor_email'),
    
    # Stripe billing
    path('api/billing/status/', get_billing_status, name='billing_status'), 
    path('api/billing/checkout/', create_checkout_session, name='create_checkout'),
    path('api/billing/portal/', create_portal_session, name='create_portal'),
    path('webhook/stripe/', stripe_webhook, name='stripe_webhook'),
    # Customer Emails API
    path('api/documents/customer-emails/<int:customer_id>/', get_customer_emails, name='get_customer_emails'),
    path('api/documents/add-customer-email/', add_customer_email, name='add_customer_email'),
    path('api/documents/delete-customer-email/<int:email_id>/', delete_customer_email, name='delete_customer_email'),
    
    # Customer Documents API
    path('api/documents/customer/', get_customer_documents, name='get_customer_documents'),
    path('api/documents/customer/<int:customer_id>/files/', get_customer_files, name='get_customer_files'),
    path('api/documents/customer/<int:customer_id>/files/<str:filename>/view/', view_customer_file, name='view_customer_file'),
    path('api/documents/customer/upload/', upload_customer_file, name='upload_customer_file'),
    path('api/documents/customer/<int:customer_id>/files/<str:filename>/', delete_customer_file, name='delete_customer_file'),
    path('api/documents/customer/email-files/', email_customer_files, name='email_customer_files'),
    
    # Documents API - Bulk operations
    path('api/documents/so/download-bulk/', download_bulk_so_files, name='download_bulk_so_files'),
    path('api/documents/so/email-bulk/', email_bulk_so_files, name='email_bulk_so_files'),
    path('api/documents/customer-emails/<int:customer_id>/', get_customer_emails, name='get_customer_emails'),

    # Documents - Vendor
    path('documents/vendor/', vendor_documents, name='vendor_documents'),
    
    # Vendor Documents API
    path('api/documents/vendor/', get_vendor_documents, name='get_vendor_documents'),
    path('api/documents/vendor/<int:vendor_id>/files/', get_vendor_files, name='get_vendor_files'),
    path('api/documents/vendor/<int:vendor_id>/files/<str:filename>/view/', view_vendor_file, name='view_vendor_file'),
    path('api/documents/vendor/upload/', upload_vendor_file, name='upload_vendor_file'),
    path('api/documents/vendor/<int:vendor_id>/files/<str:filename>/', delete_vendor_file, name='delete_vendor_file'),
    path('api/documents/vendor/email-files/', email_vendor_files, name='email_vendor_files'),
    
    # Licenses
    path('documents/licenses/', licenses, name='licenses'),
    path('api/documents/licenses/', get_licenses_api, name='get_licenses_api'),
    path('api/documents/licenses/upload/', upload_license_api, name='upload_license_api'),
    path('api/documents/licenses/<int:license_id>/update/', update_license_api, name='update_license_api'),
    path('api/documents/licenses/<str:filename>/view/', view_license_file_api, name='view_license_file_api'),
    path('api/documents/licenses/delete/<str:filename>/', delete_license_api, name='delete_license_api'),
    
    # Vehicles
    path('documents/vehicles/', vehicles, name='vehicles'),
    path('api/documents/vehicles/', get_vehicles_api, name='get_vehicles_api'),
    path('api/documents/vehicles/add/', add_vehicle_api, name='add_vehicle_api'),
    path('api/documents/vehicles/<int:vehicle_id>/update/', update_vehicle_api, name='update_vehicle_api'),
    path('api/documents/vehicles/<int:vehicle_id>/delete/', delete_vehicle_api, name='delete_vehicle_api'),

        # Vehicles
    path('documents/vehicles/', vehicles, name='vehicles'),
    path('api/vehicles/', get_vehicles_api, name='get_vehicles_api'),
    path('api/vehicles/add/', add_vehicle_api, name='add_vehicle_api'),
    path('api/vehicles/<int:vehicle_id>/update/', update_vehicle_api, name='update_vehicle_api'),
    path('api/vehicles/<int:vehicle_id>/delete/', delete_vehicle_api, name='delete_vehicle_api'),
    
    # Expiration counts for navbar badges
    path('api/expiration-counts/', get_expiration_counts_api, name='get_expiration_counts_api'),
]