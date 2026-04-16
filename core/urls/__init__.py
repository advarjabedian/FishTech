from django.urls import path, include
from ..views.auth import (
    login_view,
    logout_view,
    register_view,
    platform_admin_redirect,
)
from ..views.billing import billing_checkout, billing_page, billing_portal, stripe_webhook
from .haccp import (
    urlpatterns as haccp_urls,
    api_urlpatterns as haccp_api_urls,
    company_api_urlpatterns as company_product_api_urls,
    certificate_api_urlpatterns as certificate_api_urls,
)
from .operations import urlpatterns as operations_urls
from .api import urlpatterns as api_urls
from ..views.operations_pages import sales_order_detail

urlpatterns = [
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('platform-admin/', platform_admin_redirect, name='platform_admin'),
    path('billing/', billing_page, name='billing_page'),
    path('billing/checkout/', billing_checkout, name='billing_checkout'),
    path('billing/portal/', billing_portal, name='billing_portal'),
    path('api/billing/webhook/', stripe_webhook, name='stripe_webhook'),

    path('haccp/', include(haccp_urls)),
    path('api/haccp/', include(haccp_api_urls)),
    path('api/company-product-types/', include(company_product_api_urls)),
    path('api/company-certificates/', include(certificate_api_urls)),

    path('operations/', include(operations_urls)),
    path('api/', include(api_urls)),

    path('sales/<int:order_id>/', sales_order_detail, name='sales_order_detail'),
]
