from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from core.models import TenantUser
from django.contrib.auth.decorators import login_required


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
    
    return render(request, 'core/operations_hub.html')