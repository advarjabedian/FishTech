from django.urls import path
from .views.public_pages import *
from .views.platform_admin import *
from .views.profile_orders import *
from .views import *
from .views.operations_reports import *
from .views.stripe_billing import *

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
    path('haccp/<int:company_id>/<slug:product_type>/print/', haccp_print_set, name='haccp_print_set'),
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
    path('api/haccp-delete-version-set/<int:company_id>/<slug:product_type>/', delete_haccp_version_set, name='delete_haccp_version_set'),
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
    path('api/operations/zone-update/', update_zone, name='update_zone'),
    path('api/operations/zone-delete/', delete_zone, name='delete_zone'),
    path('api/operations/get-calendar-data/', get_calendar_data, name='get_calendar_data'),
    path('api/operations/get-inspection-images/<int:parent_id>/', get_inspection_images, name='get_inspection_images'),
    path('api/operations/upload-inspection-image/', upload_inspection_image, name='upload_inspection_image'),
    path('api/operations/inspection-image/<int:parent_id>/<str:filename>/', view_inspection_image, name='view_inspection_image'),
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
    # Platform Admin (superuser only)
    # Platform Admin (superuser only)
    path('platform-admin/', platform_admin, name='platform_admin'),
    
    # Order Requests
    path('orders/', orders_hub, name='orders_hub'),
    path('orders/view/', profile_orders_list, name='profile_orders_list'),
    path('orders/customers/', customer_list, name='customer_list'),
    path('api/profile-orders/list/', get_profile_orders_api, name='get_profile_orders_api'),
    path('api/profile-orders/<int:soid>/assign/', assign_profile_order_api, name='assign_profile_order_api'),
    path('api/profile-orders/<int:soid>/complete/', complete_profile_order_api, name='complete_profile_order_api'),
    path('api/profile-orders/<int:soid>/uncomplete/', uncomplete_profile_order_api, name='uncomplete_profile_order_api'),
    path('api/profile-orders/<int:soid>/items/', get_profile_order_items_api, name='get_profile_order_items_api'),
path('orders/customers/import/', import_customers_page, name='import_customers_page'),
path('orders/customers/<int:customer_id>/', profile_order_form, name='profile_order_form'),
path('order/<uuid:token>/', public_profile_order_form, name='public_profile_order_form'),
path('api/profile-orders/submit/', submit_profile_order, name='submit_profile_order'),
path('api/profile-orders/import/preview/', import_preview, name='import_preview'),
path('api/profile-orders/import/confirm/', import_confirm, name='import_confirm'),
    path('api/customers/add/', add_customer_api, name='add_customer_api'),
    path('api/customers/<int:customer_id>/add-profile-item/', add_profile_item_api, name='add_profile_item_api'),
    path('api/profile-item/<int:profile_id>/update/', update_profile_item_api, name='update_profile_item_api'),
    path('api/profile-item/<int:profile_id>/delete/', delete_profile_item_api, name='delete_profile_item_api'),
path('api/profile-orders/import/template/', download_import_template, name='download_import_template'),
    path('order-requests/', order_requests, name='order_requests'),
    path('api/order-requests/', get_order_requests_api, name='get_order_requests_api'),
    path('api/order-requests/users/', get_order_request_users_api, name='get_order_request_users_api'),
    path('api/order-requests/complete/', get_order_requests_complete_api, name='get_order_requests_complete_api'),
    path('api/order-request/<int:order_request_id>/view/', view_order_request_api, name='view_order_request_api'),
    path('api/order-request/<int:order_request_id>/assign-user/', assign_order_request_user_api, name='assign_order_request_user_api'),
    path('api/order-request/<int:order_request_id>/complete/', complete_order_request_api, name='complete_order_request_api'),
    path('api/order-request/<int:order_request_id>/uncomplete/', uncomplete_order_request_api, name='uncomplete_order_request_api'),
    path('api/order-request/<int:order_request_id>/update-notes/', update_order_request_notes_api, name='update_order_request_notes_api'),
    path('api/order-request/<int:order_request_id>/update-customer/', update_order_request_customer_api, name='update_order_request_customer_api'),
    path('api/check-order-emails/', check_order_emails_api, name='check_order_emails_api'),
    path('api/email-settings/', get_email_settings_api, name='get_email_settings_api'),
    path('api/email-settings/save/', save_email_settings_api, name='save_email_settings_api'),
    path('api/email-settings/test/', test_email_connection_api, name='test_email_connection_api'),
    path('api/twilio-sms-webhook/', twilio_sms_webhook, name='twilio_sms_webhook'),
    path('api/twilio-settings/', get_twilio_settings_api, name='get_twilio_settings_api'),
    path('api/twilio-settings/save/', save_twilio_settings_api, name='save_twilio_settings_api'),
    path('api/twilio-settings/test/', test_twilio_connection_api, name='test_twilio_connection_api'),
    # Public pages (no login required)
    path('sms-opt-in/', sms_opt_in, name='sms_opt_in'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-of-service/', terms_of_service, name='terms_of_service'),
]