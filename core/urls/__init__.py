from django.urls import path, include
from ..views.auth import (
    login_view,
    logout_view,
    register_view,
    licenses_view,
    vehicles_view,
    platform_admin_redirect,
)
from .haccp import (
    urlpatterns as haccp_urls,
    api_urlpatterns as haccp_api_urls,
    company_api_urlpatterns as company_product_api_urls,
    certificate_api_urlpatterns as certificate_api_urls,
)
from .operations import urlpatterns as operations_urls

urlpatterns = [
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('licenses/', licenses_view, name='licenses'),
    path('vehicles/', vehicles_view, name='vehicles'),
    path('platform-admin/', platform_admin_redirect, name='platform_admin'),

    path('haccp/', include(haccp_urls)),
    path('api/haccp/', include(haccp_api_urls)),
    path('api/company-product-types/', include(company_product_api_urls)),
    path('api/company-certificates/', include(certificate_api_urls)),

    path('operations/', include(operations_urls)),
]
