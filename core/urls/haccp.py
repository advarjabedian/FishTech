from django.urls import path
from ..views.haccp import *

urlpatterns = [
    path('', haccp, name='haccp'),
    path('<int:company_id>/', haccp_company, name='haccp_company'),
    path('<int:company_id>/<slug:product_type>/', haccp_documents, name='haccp_documents'),
    path('<int:company_id>/<slug:product_type>/print/', haccp_print_set, name='haccp_print_set'),
    path('<int:company_id>/<slug:product_type>/<str:document_type>/', haccp_document_view, name='haccp_document_view'),
    path('certificate/<int:company_id>/<str:certificate_type>/', view_company_certificate, name='view_company_certificate'),
]

api_urlpatterns = [
    path('<int:company_id>/<slug:product_type>/<str:document_type>/save/', haccp_save_document, name='haccp_save_document'),
    path('generate-version/<int:company_id>/<slug:product_type>/<str:document_type>/', generate_new_version, name='generate_new_version'),
    path('version-history/<int:company_id>/<slug:product_type>/<str:document_type>/', get_version_history, name='get_version_history'),
    path('flow-chart-data/<int:company_id>/<slug:product_type>/', get_flow_chart_data, name='get_flow_chart_data'),
    path('hazard-analysis-data/<int:company_id>/<slug:product_type>/', get_hazard_analysis_data, name='get_hazard_analysis_data'),
    path('delete-version/<int:company_id>/<slug:product_type>/<str:document_type>/', delete_haccp_version, name='delete_haccp_version'),
    path('delete-version-set/<int:company_id>/<slug:product_type>/', delete_haccp_version_set, name='delete_haccp_version_set'),
    path('get-version/<int:company_id>/<slug:product_type>/<str:document_type>/', get_haccp_version, name='get_haccp_version'),
    path('master-product-types/', get_master_product_types, name='get_master_product_types'),
    path('all-product-types/', get_all_product_types, name='api_haccp_all_product_types'),
    path('add-product-type/', add_product_type, name='api_haccp_add_product_type'),
    path('delete-product-type/', delete_product_type, name='api_haccp_delete_product_type'),
    path('inactive-product-types/', get_inactive_product_types, name='api_haccp_inactive_product_types'),
    path('restore-product-type/', restore_product_type, name='api_haccp_restore_product_type'),
    path('update-product-type/', update_product_type, name='api_haccp_update_product_type'),
    path('set-owner/<int:company_id>/', set_haccp_owner, name='haccp_set_owner'),
    path('copy-previous-year/<int:company_id>/<slug:product_type>/<str:document_type>/', copy_from_previous_year, name='copy_from_previous_year'),
]

company_api_urlpatterns = [
    path('<int:company_id>/', get_company_product_types, name='get_company_product_types'),
    path('<int:company_id>/toggle/', toggle_company_product_type, name='toggle_company_product_type'),
]

certificate_api_urlpatterns = [
    path('<int:company_id>/', get_company_certificates, name='get_company_certificates'),
    path('<int:company_id>/save/', save_company_certificate, name='save_company_certificate'),
]
