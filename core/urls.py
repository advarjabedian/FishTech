from django.urls import path
from . import views

urlpatterns = [
    path('haccp/', views.haccp, name='haccp'),
    path('haccp/<int:company_id>/', views.haccp_company, name='haccp_company'),
    path('haccp/<int:company_id>/<slug:product_type>/', views.haccp_documents, name='haccp_documents'),
    path('haccp/<int:company_id>/<slug:product_type>/<str:document_type>/', views.haccp_document_view, name='haccp_document_view'),
    
    # API endpoints for saving/managing documents
    path('api/haccp/<int:company_id>/<slug:product_type>/<str:document_type>/save/', views.haccp_save_document, name='haccp_save_document'),
    path('api/company-product-types/<int:company_id>/', views.get_company_product_types, name='get_company_product_types'),
    path('api/company-product-types/<int:company_id>/toggle/', views.toggle_company_product_type, name='toggle_company_product_type'),
    path('api/haccp-generate-version/<int:company_id>/<slug:product_type>/<str:document_type>/', views.generate_new_version, name='generate_new_version'),
    
    # Version history and document syncing
    path('api/haccp-version-history/<int:company_id>/<slug:product_type>/<str:document_type>/', views.get_version_history, name='get_version_history'),
    path('api/haccp-flow-chart-data/<int:company_id>/<slug:product_type>/', views.get_flow_chart_data, name='get_flow_chart_data'),
    path('api/haccp-hazard-analysis-data/<int:company_id>/<slug:product_type>/', views.get_hazard_analysis_data, name='get_hazard_analysis_data'),
    path('api/haccp-delete-version/<int:company_id>/<slug:product_type>/<str:document_type>/', views.delete_haccp_version, name='delete_haccp_version'),
    path('api/haccp-get-version/<int:company_id>/<slug:product_type>/<str:document_type>/', views.get_haccp_version, name='get_haccp_version'),
    
    # Product type management
    path('api/haccp-master-product-types/', views.get_master_product_types, name='get_master_product_types'),
    path('api/haccp-all-product-types/', views.get_all_product_types, name='api_haccp_all_product_types'),
    path('api/haccp-add-product-type/', views.add_product_type, name='api_haccp_add_product_type'),
    path('api/haccp-delete-product-type/', views.delete_product_type, name='api_haccp_delete_product_type'),
    path('api/haccp-inactive-product-types/', views.get_inactive_product_types, name='api_haccp_inactive_product_types'),
    path('api/haccp-restore-product-type/', views.restore_product_type, name='api_haccp_restore_product_type'),
    
    # Owner and certificates
    path('api/haccp-set-owner/<int:company_id>/', views.set_haccp_owner, name='haccp_set_owner'),
    path('api/company-certificates/<int:company_id>/', views.get_company_certificates, name='get_company_certificates'),
    path('api/company-certificates/<int:company_id>/save/', views.save_company_certificate, name='save_company_certificate'),
    path('haccp/certificate/<int:company_id>/<str:certificate_type>/', views.view_company_certificate, name='view_company_certificate'),
]