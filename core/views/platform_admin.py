from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from core.models import Tenant, TenantUser
import stripe
import json
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
def delete_tenant(request, tenant_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        name = tenant.name
        tenant.delete()
        return JsonResponse({'success': True})
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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


@superuser_required
@require_http_methods(["POST"])
def save_tenant_config(request, tenant_id):
    """Save email/twilio/subscription config for a tenant (platform admin only)"""
    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Email settings
    if 'inbound_email_address' in data:
        tenant.inbound_email_address = data['inbound_email_address']
    if 'inbound_email_imap_server' in data:
        tenant.inbound_email_imap_server = data['inbound_email_imap_server']
    if data.get('inbound_email_password'):
        tenant.inbound_email_password = data['inbound_email_password']

    # Twilio settings
    if 'twilio_account_sid' in data:
        tenant.twilio_account_sid = data['twilio_account_sid']
    if data.get('twilio_auth_token'):
        tenant.twilio_auth_token = data['twilio_auth_token']
    if 'twilio_phone_number' in data:
        tenant.twilio_phone_number = data['twilio_phone_number']

    # Subscription settings
    if 'subscription_status' in data:
        tenant.subscription_status = data['subscription_status']

    tenant.save()
    return JsonResponse({'success': True})
