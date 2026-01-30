from django.urls import path
from .views import (
    # Auth views
    login_view, logout_view, operations_hub, register_view,
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
    generate_operational_report, generate_deviations_report, generate_bulk_report,
    # Operations API
    start_inspection, save_inspection, update_inspection_time, update_inspection_inspector,
    update_company_config, toggle_holiday, get_deviations, save_corrective_actions,
    submit_verification, save_verifier_signature, get_verifier_signature,
    save_monitor_signature, get_monitor_signature, get_operations_config,
    get_sop_list, create_sop, update_sop, delete_sop, get_zones, create_zone,
    delete_zone, get_calendar_data, get_inspection_images, get_companies
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
]