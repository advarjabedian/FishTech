from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as DjangoUser
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from core.models import TenantUser
import json


@login_required
def manage_users(request):
    """Manage users for the current tenant"""
    if not request.tenant:
        return redirect('admin:index')
    
    # Verify user belongs to this tenant
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
    except TenantUser.DoesNotExist:
        return redirect('login')
    
    # Get all users for this tenant via TenantUser (single source of truth)
    tenant_users = TenantUser.objects.filter(
        tenant=request.tenant
    ).select_related('user').order_by('user__username')

    users = []
    user_admins = {}
    for tu in tenant_users:
        users.append({
            'id': tu.user.id,
            'name': tu.user.username,
            'email': tu.user.email,
        })
        user_admins[tu.user.id] = tu.is_admin

    return render(request, 'core/manage_users.html', {
        'users': users,
        'user_admins': user_admins
    })


@require_http_methods(["POST"])
def add_user(request):
    """Add a new user to the tenant"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()

        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'})
        if not password:
            return JsonResponse({'success': False, 'error': 'Password is required'})
        if len(password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters'})

        if DjangoUser.objects.filter(username=name).exists():
            return JsonResponse({'success': False, 'error': f'A user with the name "{name}" already exists'})

        django_user = DjangoUser.objects.create_user(
            username=name,
            email=email,
            password=password
        )

        TenantUser.objects.create(
            user=django_user,
            tenant=request.tenant,
            is_admin=False
        )

        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def update_company_logo(request, company_id):
    """Update company logo"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        request.tenant.logo = data.get('logo', '')
        request.tenant.save()

        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def edit_user(request, user_id):
    """Edit an existing user"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        django_user = get_object_or_404(DjangoUser, id=user_id)
        # Verify this user belongs to the tenant
        if not TenantUser.objects.filter(user=django_user, tenant=request.tenant).exists():
            return JsonResponse({'success': False, 'error': 'User not found'})

        data = json.loads(request.body)
        new_name = data.get('name', django_user.username).strip()
        new_email = data.get('email', django_user.email).strip()

        # Check for username conflicts
        if new_name != django_user.username and DjangoUser.objects.filter(username=new_name).exists():
            return JsonResponse({'success': False, 'error': f'Username "{new_name}" is already taken'})

        django_user.username = new_name
        django_user.email = new_email
        password = data.get('password')
        if password:
            django_user.set_password(password)
        django_user.save()

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def delete_user(request, user_id):
    """Delete a user"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        django_user = get_object_or_404(DjangoUser, id=user_id)
        # Verify this user belongs to the tenant
        if not TenantUser.objects.filter(user=django_user, tenant=request.tenant).exists():
            return JsonResponse({'success': False, 'error': 'User not found'})
        # Deleting DjangoUser cascades to TenantUser
        django_user.delete()
        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@require_http_methods(["POST"])
def toggle_user_company(request):
    """No-op: Company associations removed. Kept for URL compatibility."""
    return JsonResponse({'success': True})
    

@require_http_methods(["POST"])
def toggle_user_admin(request):
    """Toggle user admin status"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    # Check admin permission
    try:
        current_tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not current_tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Permission denied'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')

        tenant_user = TenantUser.objects.get(user_id=user_id, tenant=request.tenant)
        tenant_user.is_admin = not tenant_user.is_admin
        tenant_user.save()

        return JsonResponse({'success': True, 'is_admin': tenant_user.is_admin})

    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not associated with tenant'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})