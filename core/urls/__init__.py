from django.urls import path, include
from ..views.auth import (
    login_view,
    logout_view,
    register_view,
)
from .operations import urlpatterns as operations_urls
from .api import urlpatterns as api_urls
from ..views.operations_pages import sales_order_detail

urlpatterns = [
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),

    path('operations/', include(operations_urls)),
    path('api/', include(api_urls)),

    path('sales/<int:order_id>/', sales_order_detail, name='sales_order_detail'),
]
