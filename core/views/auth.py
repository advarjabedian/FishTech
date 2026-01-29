from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.models import TenantUser, Tenant

def login_view(request):
    """Login page for all tenants"""
    if request.user.is_authenticated:
        return redirect('haccp')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Check if user belongs to a tenant
            try:
                tenant_user = TenantUser.objects.select_related('tenant').get(user=user)
                if not tenant_user.tenant.is_active:
                    messages.error(request, 'Your account is inactive.')
                    return render(request, 'core/login.html')
                
                login(request, user)
                
                # Redirect to next or operations hub
                next_url = request.GET.get('next', 'operations_hub')
                return redirect(next_url)
            except TenantUser.DoesNotExist:
                messages.error(request, 'User not associated with any tenant.')
                return render(request, 'core/login.html')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'core/login.html')


def logout_view(request):
    """Logout user"""
    logout(request)
    return redirect('login')


@login_required
def operations_hub(request):
    """Operations landing page"""
    if not request.tenant:
        return redirect('admin:index')
    
    # Check if user is admin
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        is_admin = tenant_user.is_admin
    except TenantUser.DoesNotExist:
        is_admin = False
    
    return render(request, 'core/operations_hub.html', {
        'is_admin': is_admin
    })


def register_view(request):
    """Public registration page for new tenants"""
    if request.user.is_authenticated:
        return redirect('operations_hub')
    
    if request.method == 'POST':
        # Tenant info
        company_name = request.POST.get('company_name', '').strip()
        subdomain = request.POST.get('subdomain', '').strip()
        
        # Admin user info
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        
        # Validation
        if not all([company_name, subdomain, username, password]):
            messages.error(request, 'All required fields must be filled out.')
            return render(request, 'core/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/register.html')
        
        # Check if subdomain already exists
        if Tenant.objects.filter(subdomain=subdomain).exists():
            messages.error(request, 'This subdomain is already taken.')
            return render(request, 'core/register.html')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'This username is already taken.')
            return render(request, 'core/register.html')
        
        try:
            # Create tenant
            tenant = Tenant.objects.create(
                name=company_name,
                subdomain=subdomain,
                is_active=True
            )
            
            # Create admin user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password
            )
            
            # Link user to tenant as admin
            TenantUser.objects.create(user=user, tenant=tenant, is_admin=True)
            
            # Log them in
            login(request, user)
            
            messages.success(request, f'Welcome to FishTech! Your account has been created.')
            return redirect('operations_hub')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'core/register.html')
    
    return render(request, 'core/register.html')