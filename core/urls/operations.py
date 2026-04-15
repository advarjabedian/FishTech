from django.urls import path
from ..views.auth import operations_hub
from ..views.operations_reports import (
    generate_operational_report,
    generate_deviations_report,
    generate_bulk_report,
)

urlpatterns = [
    path('', operations_hub, name='operations_hub'),
    path('report/operational/<int:parent_id>/', generate_operational_report, name='generate_operational_report'),
    path('report/deviations/<int:parent_id>/', generate_deviations_report, name='generate_deviations_report'),
    path('bulk-report/', generate_bulk_report, name='generate_bulk_report'),
]
