from django.urls import path
from ..views.operations import *
from ..views.operations_api import *
from ..views.operations_reports import *

urlpatterns = [
    # Pages
    path('daily/', operations_dashboard, name='operations_dashboard'),
    path('inspection/<int:parent_id>/', inspection_form, name='inspection_form'),
    path('admin/', operations_admin, name='operations_admin'),
    path('print-sop-schedule/', print_sop_schedule, name='print_sop_schedule'),

    # Reports
    path('report/operational/<int:parent_id>/', generate_operational_report, name='generate_operational_report'),
    path('report/deviations/<int:parent_id>/', generate_deviations_report, name='generate_deviations_report'),
    path('bulk-report/', generate_bulk_report, name='generate_bulk_report'),
]

api_urlpatterns = [
    path('start-inspection/', start_inspection, name='start_inspection'),
    path('save-inspection/<int:parent_id>/', save_inspection, name='save_inspection'),
    path('update-time/<int:parent_id>/', update_inspection_time, name='update_inspection_time'),
    path('update-inspector/<int:parent_id>/', update_inspection_inspector, name='update_inspection_inspector'),
    path('update-config/', update_company_config, name='update_company_config'),
    path('toggle-holiday/', toggle_holiday, name='toggle_holiday'),
    path('get-deviations/<int:parent_id>/', get_deviations, name='get_deviations'),
    path('save-corrective-actions/', save_corrective_actions, name='save_corrective_actions'),
    path('submit-verification/', submit_verification, name='submit_verification'),
    path('save-verifier-signature/', save_verifier_signature, name='save_verifier_signature'),
    path('get-verifier-signature/', get_verifier_signature, name='get_verifier_signature'),
    path('save-monitor-signature/', save_monitor_signature, name='save_monitor_signature'),
    path('get-monitor-signature/', get_monitor_signature, name='get_monitor_signature'),
    path('save-user-signature/', save_user_signature, name='save_user_signature'),
    path('get-user-signature/', get_user_signature, name='get_user_signature'),
    path('get-config/', get_operations_config, name='get_operations_config'),
    path('sop-list/', get_sop_list, name='get_sop_list'),
    path('sop-create/', create_sop, name='create_sop'),
    path('sop-update/', update_sop, name='update_sop'),
    path('sop-delete/', delete_sop, name='delete_sop'),
    path('zones/', get_zones, name='get_zones'),
    path('zone-create/', create_zone, name='create_zone'),
    path('zone-update/', update_zone, name='update_zone'),
    path('zone-delete/', delete_zone, name='delete_zone'),
    path('get-calendar-data/', get_calendar_data, name='get_calendar_data'),
    path('get-inspection-images/<int:parent_id>/', get_inspection_images, name='get_inspection_images'),
    path('upload-inspection-image/', upload_inspection_image, name='upload_inspection_image'),
    path('inspection-image/<int:parent_id>/<str:filename>/', view_inspection_image, name='view_inspection_image'),
    path('get-companies/', get_companies, name='get_companies'),
]
