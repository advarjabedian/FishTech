from collections import defaultdict
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Count
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.models import TenantUser, Tenant

def login_view(request):
    """Login page for all tenants"""
    if request.user.is_authenticated:
        return redirect('operations_hub')
    
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
                
                # Redirect to next or Operations dashboard
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


@login_required
def platform_admin_redirect(request):
    """Platform admin dashboard for tenant billing oversight."""
    if not request.user.is_superuser:
        return redirect('home')

    tenants = list(
        Tenant.objects.annotate(user_count=Count('tenantuser'))
        .order_by('name')
    )

    billing_by_customer = defaultdict(lambda: {
        'last_paid_at': None,
        'total_paid': 0.0,
        'paid_invoice_count': 0,
        'this_month_paid': 0.0,
    })
    stripe_connected = bool(settings.STRIPE_SECRET_KEY)
    stripe_error = ""
    stripe_balance = None

    if stripe_connected:
        try:
            import stripe

            stripe.api_key = settings.STRIPE_SECRET_KEY

            invoices = stripe.Invoice.list(limit=100, status='paid')
            for invoice in invoices.auto_paging_iter():
                customer_id = getattr(invoice, 'customer', None)
                if not customer_id:
                    continue

                amount_paid = (getattr(invoice, 'amount_paid', 0) or 0) / 100
                paid_at_ts = getattr(getattr(invoice, 'status_transitions', None), 'paid_at', None)
                paid_at = None
                if paid_at_ts:
                    from django.utils import timezone
                    paid_at = timezone.datetime.fromtimestamp(paid_at_ts, tz=dt_timezone.utc)

                summary = billing_by_customer[customer_id]
                summary['total_paid'] += amount_paid
                summary['paid_invoice_count'] += 1

                if paid_at and (summary['last_paid_at'] is None or paid_at > summary['last_paid_at']):
                    summary['last_paid_at'] = paid_at

                if paid_at and paid_at.year == timezone.now().year and paid_at.month == timezone.now().month:
                    summary['this_month_paid'] += amount_paid

            try:
                balance = stripe.Balance.retrieve()
                available = sum(item.amount for item in getattr(balance, 'available', [])) / 100
                pending = sum(item.amount for item in getattr(balance, 'pending', [])) / 100
                stripe_balance = {
                    'available': available,
                    'pending': pending,
                }
            except Exception:
                stripe_balance = None
        except Exception as exc:
            stripe_error = str(exc)

    active_subscriptions = 0
    trialing = 0
    past_due = 0
    canceled = 0
    total_revenue = 0.0
    monthly_revenue = 0.0

    for tenant in tenants:
        billing = billing_by_customer.get(tenant.stripe_customer_id, {})
        tenant.last_paid_at = billing.get('last_paid_at')
        tenant.total_paid = billing.get('total_paid', 0.0)
        tenant.this_month_paid = billing.get('this_month_paid', 0.0)
        tenant.paid_invoice_count = billing.get('paid_invoice_count', 0)

        total_revenue += tenant.total_paid
        monthly_revenue += tenant.this_month_paid

        if tenant.subscription_status == 'active':
            active_subscriptions += 1
        elif tenant.subscription_status == 'trialing':
            trialing += 1
        elif tenant.subscription_status == 'past_due':
            past_due += 1
        elif tenant.subscription_status == 'canceled':
            canceled += 1

    return render(request, 'core/platform_admin_billing.html', {
        'tenants': tenants,
        'total_tenants': len(tenants),
        'active_subscriptions': active_subscriptions,
        'trialing': trialing,
        'past_due': past_due,
        'canceled': canceled,
        'total_revenue': round(total_revenue, 2),
        'monthly_revenue': round(monthly_revenue, 2),
        'stripe_connected': stripe_connected,
        'stripe_error': stripe_error,
        'stripe_balance': stripe_balance,
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
        import re
        subdomain = re.sub(r'[^a-z0-9-]', '', company_name.lower().replace(' ', '-'))

        if not all([company_name, username, password]):
            messages.error(request, 'All required fields must be filled out.')
            return render(request, 'core/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'core/register.html')
        
        # Check if subdomain already exists
        if Tenant.objects.filter(subdomain=subdomain).exists():
            messages.error(request, 'A company with that name already exists.')
            return render(request, 'core/register.html')
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'This username is already taken.')
            return render(request, 'core/register.html')
        
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            # Create tenant with 30-day trial
            tenant = Tenant.objects.create(
                name=company_name,
                subdomain=subdomain,
                is_active=True,
                subscription_status='trialing',
                trial_ends_at=timezone.now() + timedelta(days=30)
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

            # Set default logo on tenant
            from core.utils import get_default_company_logo
            tenant.logo = get_default_company_logo(1)
            tenant.save()

            # Auto-create default Retail customer
            from core.models import Customer
            Customer.all_objects.create(
                tenant=tenant,
                customer_id=0,
                name='Retail',
                is_retail=True,
            )
            
            # Log them in
            login(request, user)
            
            messages.success(request, f'Welcome to FishTech! Your account has been created.')
            return redirect('operations_hub')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'core/register.html')
    
    return render(request, 'core/register.html')
