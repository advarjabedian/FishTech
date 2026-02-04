from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from core.models import Tenant, TenantUser
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def superuser_required(view_func):
    """Decorator to require superuser access"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Access denied")
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


@superuser_required
def platform_admin(request):
    """Platform admin dashboard - superusers only"""
    
    # Get all tenants with user counts
    tenants = Tenant.objects.annotate(
        user_count=Count('tenantuser')
    ).order_by('-created_at')
    
    # Calculate metrics
    total_tenants = tenants.count()
    active_subscriptions = tenants.filter(subscription_status='active').count()
    trialing = tenants.filter(subscription_status='trialing').count()
    past_due = tenants.filter(subscription_status='past_due').count()
    canceled = tenants.filter(subscription_status='canceled').count()
    
    # Monthly revenue (active subs * $10)
    monthly_revenue = active_subscriptions * 10
    
    # Try to get more detailed Stripe data
    stripe_balance = None
    try:
        balance = stripe.Balance.retrieve()
        stripe_balance = balance.available[0].amount / 100 if balance.available else 0
    except:
        pass
    
    return render(request, 'core/platform_admin.html', {
        'tenants': tenants,
        'total_tenants': total_tenants,
        'active_subscriptions': active_subscriptions,
        'trialing': trialing,
        'past_due': past_due,
        'canceled': canceled,
        'monthly_revenue': monthly_revenue,
        'stripe_balance': stripe_balance,
    })