from django.urls import path
from .views import (
    # Auth views
    login_view, logout_view,
    # HACCP views
    haccp, haccp_company, haccp_documents, haccp_document_view,
    haccp_save_document, get_company_product_types, toggle_company_product_type,
    generate_new_version, get_version_history, get_flow_chart_data,
    get_hazard_analysis_data, delete_haccp_version, get_haccp_version,
    get_master_product_types, get_all_product_types, add_product_type,
    delete_product_type, get_inactive_product_types, restore_product_type,
    set_haccp_owner, get_company_certificates, save_company_certificate,
    view_company_certificate, login_view, logout_view, operations_hub,
    manage_users, add_user, edit_user, delete_user,
)

urlpatterns = [
    # Auth routes
    path('', login_view, name='login'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    
    # HACCP main routes
    path('haccp/', haccp, name='haccp'),
    path('haccp/<int:company_id>/', haccp_company, name='haccp_company'),
    path('haccp/<int:company_id>/<slug:product_type>/', haccp_documents, name='haccp_documents'),
    path('haccp/<int:company_id>/<slug:product_type>/<str:document_type>/', haccp_document_view, name='haccp_document_view'),
    
    # API endpoints for saving/managing documents
    path('api/haccp/<int:company_id>/<slug:product_type>/<str:document_type>/save/', haccp_save_document, name='haccp_save_document'),
    path('api/company-product-types/<int:company_id>/', get_company_product_types, name='get_company_product_types'),
    path('api/company-product-types/<int:company_id>/toggle/', toggle_company_product_type, name='toggle_company_product_type'),
    path('api/haccp-generate-version/<int:company_id>/<slug:product_type>/<str:document_type>/', generate_new_version, name='generate_new_version'),
    
    # Version history and document syncing
    path('api/haccp-version-history/<int:company_id>/<slug:product_type>/<str:document_type>/', get_version_history, name='get_version_history'),
    path('api/haccp-flow-chart-data/<int:company_id>/<slug:product_type>/', get_flow_chart_data, name='get_flow_chart_data'),
    path('api/haccp-hazard-analysis-data/<int:company_id>/<slug:product_type>/', get_hazard_analysis_data, name='get_hazard_analysis_data'),
    path('api/haccp-delete-version/<int:company_id>/<slug:product_type>/<str:document_type>/', delete_haccp_version, name='delete_haccp_version'),
    path('api/haccp-get-version/<int:company_id>/<slug:product_type>/<str:document_type>/', get_haccp_version, name='get_haccp_version'),
    
    # Product type management
    path('api/haccp-master-product-types/', get_master_product_types, name='get_master_product_types'),
    path('api/haccp-all-product-types/', get_all_product_types, name='api_haccp_all_product_types'),
    path('api/haccp-add-product-type/', add_product_type, name='api_haccp_add_product_type'),
    path('api/haccp-delete-product-type/', delete_product_type, name='api_haccp_delete_product_type'),
    path('api/haccp-inactive-product-types/', get_inactive_product_types, name='api_haccp_inactive_product_types'),
    path('api/haccp-restore-product-type/', restore_product_type, name='api_haccp_restore_product_type'),
    
    # Owner and certificates
    path('api/haccp-set-owner/<int:company_id>/', set_haccp_owner, name='haccp_set_owner'),
    path('api/company-certificates/<int:company_id>/', get_company_certificates, name='get_company_certificates'),
    path('api/company-certificates/<int:company_id>/save/', save_company_certificate, name='save_company_certificate'),
    path('haccp/certificate/<int:company_id>/<str:certificate_type>/', view_company_certificate, name='view_company_certificate'),

    path('logout/', logout_view, name='logout'),
    
    # Operations Hub
    path('operations/', operations_hub, name='operations_hub'),
    
    # HACCP main routes
    path('haccp/', haccp, name='haccp'),

    # Operations Hub
    path('operations/', operations_hub, name='operations_hub'),
    
    # User management
    path('manage-users/', manage_users, name='manage_users'),
    path('api/add-user/', add_user, name='add_user'),
    path('api/edit-user/<int:user_id>/', edit_user, name='edit_user'),
    path('api/delete-user/<int:user_id>/', delete_user, name='delete_user'),
    
    # HACCP main routes
]