from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
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
    
    # Get all users for this tenant
    tenant_users = TenantUser.objects.filter(tenant=request.tenant).select_related('user')
    users = [tu.user for tu in tenant_users]
    
    return render(request, 'core/manage_users.html', {
        'users': users
    })


@require_http_methods(["POST"])
def add_user(request):
    """Add a new user to the tenant"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required'})
        
        # Check if username exists
        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists'})
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        
        # Link to tenant
        TenantUser.objects.create(user=user, tenant=request.tenant)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def edit_user(request, user_id):
    """Edit an existing user"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Verify user belongs to this tenant
        if not TenantUser.objects.filter(user=user, tenant=request.tenant).exists():
            return JsonResponse({'success': False, 'error': 'User not found'})
        
        data = json.loads(request.body)
        
        user.email = data.get('email', user.email)
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        
        # Update password if provided
        password = data.get('password', '').strip()
        if password:
            user.set_password(password)
        
        user.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def delete_user(request, user_id):
    """Delete a user"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    try:
        user = get_object_or_404(User, id=user_id)
        
        # Verify user belongs to this tenant
        if not TenantUser.objects.filter(user=user, tenant=request.tenant).exists():
            return JsonResponse({'success': False, 'error': 'User not found'})
        
        # Don't allow deleting yourself
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'Cannot delete yourself'})
        
        user.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})