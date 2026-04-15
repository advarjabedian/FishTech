from django.urls import path, include
from ..views.public_pages import *
from ..views.platform_admin import *
from ..views.profile_orders import public_profile_order_form
from ..views import *
from ..views.stripe_billing import *
from ..views.settings_page import (
    settings_page, settings_profile_api, settings_account_api,
    settings_users_api, settings_item_groups_api,
)
from ..views.shipping import (
    shipping_hub, shipping_picking, shipping_packing, shipping_loading,
    shipping_log_api, shipping_picking_api, shipping_packing_api, shipping_loading_api,
    delivery_confirm_api, delivery_update_status_api, delivery_list_api,
)
from ..views.receiving import (
    receiving_page, receiving_list_api, receiving_lot_detail_api,
    receiving_create_api, receiving_update_api, receiving_vendors_api,
    receiving_open_pos_api,
)
from ..views.processing import (
    processing_hub, processing_new, processing_detail,
    processing_batches_api, processing_source_lots_api,
    processing_create_batch_api, processing_batch_sources_api,
    processing_batch_complete_api, processing_batch_cancel_api,
    processing_batch_outputs_api, processing_products_api,
)
from ..views.fish_market import (
    fish_market_redirect, fish_market_page, fish_market_checkout,
    fish_market_order_status,
    fish_market_add_item, fish_market_update_item, fish_market_delete_item,
    fish_market_update_image, fish_market_create_payment_intent,
    fish_market_submit_order, fish_market_orders_list,
    fish_market_update_order_status,
    retail_orders_api, retail_order_update_status,
)
from ..views.order_requests import (
    check_order_emails_api, get_email_settings_api, save_email_settings_api,
    test_email_connection_api, twilio_sms_webhook, twilio_voice_webhook,
    twilio_recording_webhook, get_twilio_settings_api, save_twilio_settings_api,
    test_twilio_connection_api,
)

# Import modular URL configs
from .operations import urlpatterns as operations_urls, api_urlpatterns as operations_api_urls
from .haccp import (
    urlpatterns as haccp_urls, api_urlpatterns as haccp_api_urls,
    company_api_urlpatterns as company_product_api_urls,
    certificate_api_urlpatterns as certificate_api_urls,
)
from .documents import urlpatterns as documents_urls, api_urlpatterns as documents_api_urls
from .orders import (
    urlpatterns as orders_urls, profile_api_urlpatterns as profile_orders_api_urls,
    customer_api_urlpatterns as customer_api_urls,
    profile_item_api_urlpatterns as profile_item_api_urls,
    product_api_urlpatterns as product_api_urls,
    product_image_api_urlpatterns as product_image_api_urls,
    order_request_api_urlpatterns as order_request_api_urls,
    order_request_detail_api_urlpatterns as order_request_detail_api_urls,
    sales_urlpatterns as sales_urls, sales_api_urlpatterns as sales_api_urls,
    purchasing_urlpatterns as purchasing_urls, purchasing_api_urlpatterns as purchasing_api_urls,
)
from .finance import (
    urlpatterns as finance_urls,
    ar_api_urlpatterns as ar_api_urls, ap_api_urlpatterns as ap_api_urls,
    ledger_api_urlpatterns as ledger_api_urls,
    reports_api_urlpatterns as reports_api_urls,
)

urlpatterns = [
    # ── Auth & Public ──
    path('', public_home, name='public_home'),
    path('api/contact/', submit_contact_form, name='submit_contact_form'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('sms-opt-in/', sms_opt_in, name='sms_opt_in'),
    path('privacy-policy/', privacy_policy, name='privacy_policy'),
    path('terms-of-service/', terms_of_service, name='terms_of_service'),
    path('order/<uuid:token>/', public_profile_order_form, name='public_profile_order_form'),
    path('sign/<uuid:token>/', sign_document, name='sign_document'),
    path('sign/<uuid:token>/submit/', submit_signature, name='submit_signature'),

    # ── Operations ──
    path('operations/', operations_hub, name='operations_hub'),
    path('operations/', include(operations_urls)),
    path('api/operations/', include(operations_api_urls)),

    # ── HACCP ──
    path('haccp/', include(haccp_urls)),
    path('api/haccp/', include(haccp_api_urls)),
    path('api/company-product-types/', include(company_product_api_urls)),
    path('api/company-certificates/', include(certificate_api_urls)),

    # ── Documents ──
    path('documents/', include(documents_urls)),
    path('api/documents/', include(documents_api_urls)),

    # ── Orders & Customers ──
    path('orders/', include(orders_urls)),
    path('api/profile-orders/', include(profile_orders_api_urls)),
    path('api/customers/', include(customer_api_urls)),
    path('api/profile-item/', include(profile_item_api_urls)),
    path('api/tenant-products/', include(product_api_urls)),
    path('api/product-images/', include(product_image_api_urls)),
    path('api/order-requests/', include(order_request_api_urls)),
    path('api/order-request/', include(order_request_detail_api_urls)),

    # ── Sales ──
    path('sales/', include(sales_urls)),
    path('api/sales/', include(sales_api_urls)),

    # ── Purchasing ──
    path('purchasing/', include(purchasing_urls)),
    path('api/purchasing/', include(purchasing_api_urls)),

    # ── Finance ──
    path('', include(finance_urls)),
    path('api/ar/', include(ar_api_urls)),
    path('api/ap/', include(ap_api_urls)),
    path('api/ledger/', include(ledger_api_urls)),
    path('api/accounting/reports/', include(reports_api_urls)),

    # ── Shipping ──
    path('shipping/', shipping_hub, name='shipping_hub'),
    path('shipping/picking/', shipping_picking, name='shipping_picking'),
    path('shipping/packing/', shipping_packing, name='shipping_packing'),
    path('shipping/loading/', shipping_loading, name='shipping_loading'),
    path('api/shipping/log/', shipping_log_api, name='shipping_log_api'),
    path('api/shipping/picking/', shipping_picking_api, name='shipping_picking_api'),
    path('api/shipping/packing/', shipping_packing_api, name='shipping_packing_api'),
    path('api/shipping/loading/', shipping_loading_api, name='shipping_loading_api'),
    path('api/shipping/deliveries/', delivery_list_api, name='delivery_list_api'),
    path('api/shipping/delivery/<int:so_id>/confirm/', delivery_confirm_api, name='delivery_confirm_api'),
    path('api/shipping/delivery/<int:so_id>/status/', delivery_update_status_api, name='delivery_update_status_api'),

    # ── Receiving ──
    path('receiving/', receiving_page, name='receiving_page'),
    path('api/receiving/lots/', receiving_list_api, name='receiving_list_api'),
    path('api/receiving/lots/<int:lot_id>/', receiving_lot_detail_api, name='receiving_lot_detail_api'),
    path('api/receiving/lots/create/', receiving_create_api, name='receiving_create_api'),
    path('api/receiving/lots/<int:lot_id>/update/', receiving_update_api, name='receiving_update_api'),
    path('api/receiving/vendors/', receiving_vendors_api, name='receiving_vendors_api'),
    path('api/receiving/open-pos/', receiving_open_pos_api, name='receiving_open_pos_api'),

    # ── Processing ──
    path('processing/', processing_hub, name='processing_hub'),
    path('processing/new/', processing_new, name='processing_new'),
    path('processing/<int:batch_id>/', processing_detail, name='processing_detail'),
    path('api/processing/batches/', processing_batches_api, name='processing_batches_api'),
    path('api/processing/source-lots/', processing_source_lots_api, name='processing_source_lots_api'),
    path('api/processing/batches/create/', processing_create_batch_api, name='processing_create_batch_api'),
    path('api/processing/batches/<int:batch_id>/sources/', processing_batch_sources_api, name='processing_batch_sources_api'),
    path('api/processing/batches/<int:batch_id>/complete/', processing_batch_complete_api, name='processing_batch_complete_api'),
    path('api/processing/batches/<int:batch_id>/cancel/', processing_batch_cancel_api, name='processing_batch_cancel_api'),
    path('api/processing/batches/<int:batch_id>/outputs/', processing_batch_outputs_api, name='processing_batch_outputs_api'),
    path('api/processing/products/', processing_products_api, name='processing_products_api'),

    # ── Inventory ──
    path('inventory/', inventory_item_library, name='inventory_item_library'),
    path('inventory/<int:product_id>/', inventory_item_detail, name='inventory_item_detail'),
    path('api/inventory/groups/', item_groups_api, name='item_groups_api'),
    path('api/inventory/groups/create/', item_group_create_api, name='item_group_create_api'),
    path('api/inventory/items/', inventory_items_api, name='inventory_items_api'),
    path('api/inventory/items/create/', inventory_item_create_api, name='inventory_item_create_api'),
    path('api/inventory/items/<int:product_id>/update/', inventory_item_update_api, name='inventory_item_update_api'),
    path('api/inventory/items/<int:product_id>/delete/', inventory_item_delete_api, name='inventory_item_delete_api'),
    path('api/inventory/items/<int:product_id>/toggle-active/', inventory_item_toggle_active_api, name='inventory_item_toggle_active_api'),
    path('api/inventory/items/<int:product_id>/lots/', inventory_item_lots_api, name='inventory_item_lots_api'),
    path('api/inventory/export/', inventory_export_api, name='inventory_export_api'),
    path('api/inventory/expiry-alerts/', inventory_expiry_alerts_api, name='inventory_expiry_alerts_api'),

    # ── Vendors ──
    path('vendors/', vendor_list_page, name='vendor_list_page'),
    path('api/vendors/list/', vendor_list_api, name='vendor_list_api'),
    path('api/vendors/create/', vendor_create_api, name='vendor_create_api'),
    path('api/vendors/<int:vendor_id>/update/', vendor_update_api, name='vendor_update_api'),
    path('api/vendors/<int:vendor_id>/delete/', vendor_delete_api, name='vendor_delete_api'),

    # ── Fish Market ──
    path('fish-market/', fish_market_redirect, name='fish_market_redirect'),
    path('fish-market/<str:slug>/', fish_market_page, name='fish_market_page'),
    path('fish-market/<str:slug>/checkout/', fish_market_checkout, name='fish_market_checkout'),
    path('fish-market/<str:slug>/order/<int:order_id>/status/', fish_market_order_status, name='fish_market_order_status'),
    path('api/fish-market/<str:slug>/item/add/', fish_market_add_item, name='fish_market_add_item'),
    path('api/fish-market/<str:slug>/item/<int:item_id>/update/', fish_market_update_item, name='fish_market_update_item'),
    path('api/fish-market/<str:slug>/item/<int:item_id>/delete/', fish_market_delete_item, name='fish_market_delete_item'),
    path('api/fish-market/<str:slug>/item/<int:item_id>/image/', fish_market_update_image, name='fish_market_update_image'),
    path('api/fish-market/<str:slug>/create-payment-intent/', fish_market_create_payment_intent, name='fish_market_create_payment_intent'),
    path('api/fish-market/<str:slug>/order/', fish_market_submit_order, name='fish_market_submit_order'),
    path('api/fish-market/<str:slug>/orders/', fish_market_orders_list, name='fish_market_orders_list'),
    path('api/fish-market/<str:slug>/order/<int:order_id>/status/', fish_market_update_order_status, name='fish_market_update_order_status'),
    path('api/retail-orders/', retail_orders_api, name='retail_orders_api'),
    path('api/retail-orders/<int:order_id>/status/', retail_order_update_status, name='retail_order_update_status'),

    # ── Stripe Billing ──
    path('api/billing/status/', get_billing_status, name='billing_status'),
    path('api/billing/checkout/', create_checkout_session, name='create_checkout'),
    path('api/billing/portal/', create_portal_session, name='create_portal'),
    path('webhook/stripe/', stripe_webhook, name='stripe_webhook'),

    # ── Email & Twilio ──
    path('api/check-order-emails/', check_order_emails_api, name='check_order_emails_api'),
    path('api/email-settings/', get_email_settings_api, name='get_email_settings_api'),
    path('api/email-settings/save/', save_email_settings_api, name='save_email_settings_api'),
    path('api/email-settings/test/', test_email_connection_api, name='test_email_connection_api'),
    path('api/twilio-sms-webhook/', twilio_sms_webhook, name='twilio_sms_webhook'),
    path('order-requests/sms-webhook/', twilio_sms_webhook),  # legacy webhook URL
    path('api/twilio-voice-webhook/', twilio_voice_webhook, name='twilio_voice_webhook'),
    path('api/twilio-recording-webhook/', twilio_recording_webhook, name='twilio_recording_webhook'),
    path('api/twilio-settings/', get_twilio_settings_api, name='get_twilio_settings_api'),
    path('api/twilio-settings/save/', save_twilio_settings_api, name='save_twilio_settings_api'),
    path('api/twilio-settings/test/', test_twilio_connection_api, name='test_twilio_connection_api'),

    # ── Settings ──
    path('settings/', settings_page, name='settings_page'),
    path('api/settings/profile/', settings_profile_api, name='settings_profile_api'),
    path('api/settings/account/', settings_account_api, name='settings_account_api'),
    path('api/settings/users/', settings_users_api, name='settings_users_api'),
    path('api/settings/item-groups/', settings_item_groups_api, name='settings_item_groups_api'),

    # ── User & Company Management ──
    path('manage-users/', manage_users, name='manage_users'),
    path('api/add-user/', add_user, name='add_user'),
    path('api/edit-user/<int:user_id>/', edit_user, name='edit_user'),
    path('api/delete-user/<int:user_id>/', delete_user, name='delete_user'),
    path('api/toggle-user-company/', toggle_user_company, name='toggle_user_company'),
    path('api/toggle-user-admin/', toggle_user_admin, name='toggle_user_admin'),
    path('api/add-company/', add_company, name='add_company'),
    path('api/edit-company/<int:company_id>/', edit_company, name='edit_company'),
    path('api/delete-company/<int:company_id>/', delete_company, name='delete_company'),
    path('api/update-company-logo/<int:company_id>/', update_company_logo, name='update_company_logo'),
    path('api/expiration-counts/', get_expiration_counts_api, name='get_expiration_counts_api'),

    # ── Hub Pages ──
    path('more-tools/', unused_tiles, name='unused_tiles'),
    path('accounting/', accounting_hub, name='accounting_hub'),
    path('compliance/', compliance_hub, name='compliance_hub'),
    path('orders-landing/', orders_landing, name='orders_landing'),

    # ── Platform Admin ──
    path('platform-admin/', platform_admin, name='platform_admin'),
    path('platform-admin/tenant/<int:tenant_id>/edit/', edit_tenant, name='edit_tenant'),
    path('platform-admin/tenant/<int:tenant_id>/delete/', delete_tenant, name='delete_tenant'),
    path('platform-admin/tenant/<int:tenant_id>/config/', save_tenant_config, name='save_tenant_config'),
    path('platform-admin/leads/save/', save_lead, name='save_lead'),
    path('platform-admin/leads/<int:lead_id>/delete/', delete_lead, name='delete_lead'),
    path('platform-admin/document/<int:doc_id>/reset/', reset_document, name='reset_document'),
]
