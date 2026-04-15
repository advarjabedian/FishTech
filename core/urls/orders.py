from django.urls import path
from ..views.profile_orders import *
from ..views.order_requests import *
from ..views.sales import *
from ..views.purchasing import *

# Profile orders / customer management pages
urlpatterns = [
    path('', orders_hub, name='orders_hub'),
    path('view/', profile_orders_list, name='profile_orders_list'),
    path('customers/', customer_list, name='customer_list'),
    path('products/', products_page, name='products_page'),
    path('customers/import/', import_customers_page, name='import_customers_page'),
    path('customers/<int:customer_id>/', profile_order_form, name='profile_order_form'),
]

# Profile orders API
profile_api_urlpatterns = [
    path('list/', get_profile_orders_api, name='get_profile_orders_api'),
    path('submit/', submit_profile_order, name='submit_profile_order'),
    path('import/preview/', import_preview, name='import_preview'),
    path('import/confirm/', import_confirm, name='import_confirm'),
    path('import/template/', download_import_template, name='download_import_template'),
    path('<int:soid>/assign/', assign_profile_order_api, name='assign_profile_order_api'),
    path('<int:soid>/complete/', complete_profile_order_api, name='complete_profile_order_api'),
    path('<int:soid>/uncomplete/', uncomplete_profile_order_api, name='uncomplete_profile_order_api'),
    path('<int:soid>/items/', get_profile_order_items_api, name='get_profile_order_items_api'),
]

# Customer CRUD API
customer_api_urlpatterns = [
    path('add/', add_customer_api, name='add_customer_api'),
    path('<int:customer_id>/update/', update_customer_api, name='update_customer_api'),
    path('<int:customer_id>/delete/', delete_customer_api, name='delete_customer_api'),
    path('<int:customer_id>/add-profile-item/', add_profile_item_api, name='add_profile_item_api'),
]

# Profile item API
profile_item_api_urlpatterns = [
    path('<int:profile_id>/update/', update_profile_item_api, name='update_profile_item_api'),
    path('<int:profile_id>/delete/', delete_profile_item_api, name='delete_profile_item_api'),
]

# Tenant product catalog API
product_api_urlpatterns = [
    path('', get_tenant_products_api, name='get_tenant_products_api'),
    path('add/', add_tenant_product_api, name='add_tenant_product_api'),
    path('<int:product_id>/update/', update_tenant_product_api, name='update_tenant_product_api'),
    path('<int:product_id>/delete/', delete_tenant_product_api, name='delete_tenant_product_api'),
    path('assign/', assign_product_to_customer_api, name='assign_product_to_customer_api'),
    path('unassign/<int:profile_id>/', unassign_product_from_customer_api, name='unassign_product_from_customer_api'),
]

# Product images API
product_image_api_urlpatterns = [
    path('<int:product_id>/upload/', upload_product_image, name='upload_product_image'),
    path('<int:product_id>/delete/<int:slot>/', delete_product_image, name='delete_product_image'),
    path('<int:product_id>/', get_product_images, name='get_product_images'),
]

# Order requests API
order_request_api_urlpatterns = [
    path('', get_order_requests_api, name='get_order_requests_api'),
    path('users/', get_order_request_users_api, name='get_order_request_users_api'),
    path('complete/', get_order_requests_complete_api, name='get_order_requests_complete_api'),
]

order_request_detail_api_urlpatterns = [
    path('<int:order_request_id>/view/', view_order_request_api, name='view_order_request_api'),
    path('<int:order_request_id>/assign-user/', assign_order_request_user_api, name='assign_order_request_user_api'),
    path('<int:order_request_id>/complete/', complete_order_request_api, name='complete_order_request_api'),
    path('<int:order_request_id>/uncomplete/', uncomplete_order_request_api, name='uncomplete_order_request_api'),
    path('<int:order_request_id>/update-notes/', update_order_request_notes_api, name='update_order_request_notes_api'),
    path('<int:order_request_id>/update-customer/', update_order_request_customer_api, name='update_order_request_customer_api'),
]

# Sales orders
sales_urlpatterns = [
    path('', sales_orders_page, name='sales_orders_page'),
    path('<int:so_id>/', sales_order_detail_page, name='sales_order_detail_page'),
]

sales_api_urlpatterns = [
    path('orders/', sales_orders_list_api, name='sales_orders_list_api'),
    path('orders/create/', sales_order_create_api, name='sales_order_create_api'),
    path('orders/<int:so_id>/update/', sales_order_update_api, name='sales_order_update_api'),
    path('orders/<int:so_id>/delete/', sales_order_delete_api, name='sales_order_delete_api'),
    path('orders/<int:so_id>/detail/', sales_order_detail_api, name='sales_order_detail_api'),
    path('orders/<int:so_id>/items/add/', sales_order_item_add_api, name='sales_order_item_add_api'),
    path('orders/<int:so_id>/items/<int:item_id>/delete/', sales_order_item_delete_api, name='sales_order_item_delete_api'),
    path('customers/', sales_customers_api, name='sales_customers_api'),
]

# Purchasing
purchasing_urlpatterns = [
    path('', purchases_page, name='purchases_page'),
    path('<int:po_id>/', purchase_detail_page, name='purchase_detail_page'),
]

purchasing_api_urlpatterns = [
    path('orders/', purchases_list_api, name='purchases_list_api'),
    path('orders/create/', purchase_create_api, name='purchase_create_api'),
    path('orders/<int:po_id>/update/', purchase_update_api, name='purchase_update_api'),
    path('orders/<int:po_id>/delete/', purchase_delete_api, name='purchase_delete_api'),
    path('orders/<int:po_id>/detail/', purchase_detail_api, name='purchase_detail_api'),
    path('orders/<int:po_id>/items/add/', purchase_item_add_api, name='purchase_item_add_api'),
    path('orders/<int:po_id>/items/<int:item_id>/delete/', purchase_item_delete_api, name='purchase_item_delete_api'),
]
