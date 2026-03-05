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
    
    # Check if current user is admin
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('operations_hub')
    except TenantUser.DoesNotExist:
        return redirect('login')
    
    # Get all companies for this tenant
    from core.models import Company, UserCompany, User
    companies = Company.objects.all().order_by('companyname')
    
    # Get all users for this tenant
    users = User.objects.all().order_by('name')
    
    # Build user-company associations and admin status
    user_companies = {}
    user_admins = {}
    
    for uc in UserCompany.objects.select_related('user', 'company'):
        if uc.user_id not in user_companies:
            user_companies[uc.user_id] = []
        user_companies[uc.user_id].append(uc.company_id)
    
    # Get admin status for each user (using Django User model, not core.User)
    from django.contrib.auth.models import User as DjangoUser
    for user in users:
        try:
            django_user = DjangoUser.objects.get(username=user.name)
            tenant_user = TenantUser.objects.get(user=django_user, tenant=request.tenant)
            user_admins[user.id] = tenant_user.is_admin
        except (DjangoUser.DoesNotExist, TenantUser.DoesNotExist):
            user_admins[user.id] = False
    
    return render(request, 'core/manage_users.html', {
        'users': users,
        'companies': companies,
        'user_companies': user_companies,
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
        from core.models import User
        
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
        
        # Check if Django username already exists
        if DjangoUser.objects.filter(username=name).exists():
            return JsonResponse({'success': False, 'error': f'A user with the name "{name}" already exists'})
        
        # Create Django auth user (enables login)
        django_user = DjangoUser.objects.create_user(
            username=name,
            email=email,
            password=password
        )
        
        # Link to tenant
        TenantUser.objects.create(
            user=django_user,
            tenant=request.tenant,
            is_admin=False
        )
        
        # Create core.User for business logic
        User.objects.create(
            tenant=request.tenant,
            name=name,
            email=email
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
        from core.models import Company
        company = get_object_or_404(Company, companyid=company_id)
        
        data = json.loads(request.body)
        company.logo = data.get('logo', '')
        company.save()
        
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
        from core.models import User
        
        user = get_object_or_404(User, id=user_id, tenant=request.tenant)
        data = json.loads(request.body)
        
        user.name = data.get('name', user.name)
        user.email = data.get('email', user.email)
        user.save()
        
        # Update Django auth user if it exists
        django_user = DjangoUser.objects.filter(username=user.name).first()
        if django_user:
            django_user.email = user.email
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
        from core.models import User
        
        # User.objects already filters by tenant through TenantManager
        user = get_object_or_404(User, id=user_id, tenant=request.tenant)
        user.delete()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@require_http_methods(["POST"])
def toggle_user_company(request):
    """Toggle user-company association"""
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
        from core.models import Company, UserCompany, User
        
        data = json.loads(request.body)
        user_id = data.get('user_id')
        company_id = data.get('company_id')
        
        user = get_object_or_404(User, id=user_id)
        company = get_object_or_404(Company, companyid=company_id)
        
        uc, created = UserCompany.objects.get_or_create(
            tenant=request.tenant,
            user=user,
            company=company
        )
        
        if not created:
            uc.delete()
            return JsonResponse({'success': True, 'associated': False})
        
        return JsonResponse({'success': True, 'associated': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

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
        from core.models import User
        from django.contrib.auth.models import User as DjangoUser
        
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        core_user = get_object_or_404(User, id=user_id)
        
        # Find corresponding Django user by username (assuming username = name)
        django_user = DjangoUser.objects.filter(username=core_user.name).first()
        if not django_user:
            return JsonResponse({'success': False, 'error': 'Django user not found'})
        
        tenant_user = TenantUser.objects.get(user=django_user, tenant=request.tenant)
        tenant_user.is_admin = not tenant_user.is_admin
        tenant_user.save()
        
        return JsonResponse({'success': True, 'is_admin': tenant_user.is_admin})
        
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not associated with tenant'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})