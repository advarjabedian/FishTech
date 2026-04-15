from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import set_current_tenant, ItemGroup
import json

import logging
logger = logging.getLogger(__name__)


def ensure_tenant(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.tenant:
            set_current_tenant(request.tenant)
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@ensure_tenant
def settings_page(request):
    if not request.tenant:
        return redirect('login')
    section = request.GET.get('section', 'profile')
    return render(request, 'core/settings.html', {'section': section})


@login_required
@ensure_tenant
def settings_profile_api(request):
    """Get/update current user profile."""
    user = request.user
    if request.method == 'POST':
        data = json.loads(request.body)
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.save()
        return JsonResponse({'ok': True})

    return JsonResponse({
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username,
        'email': user.email,
    })


@login_required
@ensure_tenant
def settings_account_api(request):
    """Get tenant/account info."""
    tenant = request.tenant
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)

    if request.method == 'POST':
        data = json.loads(request.body)
        tenant.name = data.get('name', tenant.name)
        tenant.address = data.get('address', tenant.address)
        tenant.city = data.get('city', tenant.city)
        tenant.state = data.get('state', tenant.state)
        tenant.zipcode = data.get('zipcode', tenant.zipcode)
        tenant.phone = data.get('phone', tenant.phone)
        tenant.save()
        return JsonResponse({'ok': True})

    return JsonResponse({
        'name': tenant.name,
        'address': tenant.address,
        'city': tenant.city,
        'state': getattr(tenant, 'state', ''),
        'zipcode': getattr(tenant, 'zipcode', ''),
        'phone': getattr(tenant, 'phone', ''),
    })


@login_required
@ensure_tenant
def settings_users_api(request):
    """List users for this tenant."""
    from core.models import User
    users = User.objects.filter(tenant=request.tenant).select_related('user')
    result = []
    for u in users:
        result.append({
            'id': u.id,
            'name': u.user.get_full_name() or u.user.username,
            'username': u.user.username,
            'email': u.user.email,
            'is_active': u.user.is_active,
            'is_admin': u.is_admin,
        })
    return JsonResponse({'users': result})


@login_required
@ensure_tenant
def settings_item_groups_api(request):
    """List item groups for settings."""
    groups = ItemGroup.objects.filter(tenant=request.tenant).values('id', 'name', 'is_active', 'sort_order')
    return JsonResponse({'groups': list(groups)})
