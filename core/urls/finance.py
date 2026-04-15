from django.urls import path
from ..views.finance import *

urlpatterns = [
    # AR
    path('accounts-receivable/', ar_invoices, name='ar_invoices'),
    # AP
    path('accounts-payable/', ap_expenses, name='ap_expenses'),
    # Ledger
    path('ledger/', ledger, name='ledger'),
    # Reports
    path('accounting/reports/', accounting_reports, name='accounting_reports'),
]

ar_api_urlpatterns = [
    path('', ar_list, name='ar_list'),
    path('create/', ar_create, name='ar_create'),
    path('<int:invoice_id>/update/', ar_update, name='ar_update'),
    path('<int:invoice_id>/delete/', ar_delete, name='ar_delete'),
    path('<int:invoice_id>/mark-paid/', ar_mark_paid, name='ar_mark_paid'),
    path('customer-balances/', ar_customer_balances, name='ar_customer_balances'),
]

ap_api_urlpatterns = [
    path('', ap_list, name='ap_list'),
    path('create/', ap_create, name='ap_create'),
    path('<int:expense_id>/update/', ap_update, name='ap_update'),
    path('<int:expense_id>/delete/', ap_delete, name='ap_delete'),
]

ledger_api_urlpatterns = [
    path('', ledger_data, name='ledger_data'),
]

reports_api_urlpatterns = [
    path('', accounting_reports_api, name='accounting_reports_api'),
]
