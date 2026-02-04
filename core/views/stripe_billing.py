"""
Stripe billing views for FishTech multi-tenant SaaS
"""
import stripe
import json
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import logging

from core.models import Tenant, TenantUser

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Your Stripe Price ID for $10/month subscription
# Create this in Stripe Dashboard: Products > Add Product > $10/month recurring
STRIPE_PRICE_ID = settings.STRIPE_PRICE_ID  # e.g., 'price_1234567890'


@login_required
def get_billing_status(request):
    """Get current billing status for the tenant - checks Stripe directly"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    tenant = request.tenant
    
    # If we have a Stripe customer, check their subscription status directly
    if tenant.stripe_customer_id:
        try:
            subscriptions = stripe.Subscription.list(
                customer=tenant.stripe_customer_id,
                status='active',
                limit=1
            )
            
            if subscriptions.data:
                sub = subscriptions.data[0]
                # Update local record
                tenant.stripe_subscription_id = sub.id
                tenant.subscription_status = sub.status
                if sub.current_period_end:
                    tenant.subscription_ends_at = timezone.datetime.fromtimestamp(
                        sub.current_period_end, tz=timezone.utc
                    )
                tenant.save()
        except stripe.error.StripeError as e:
            logger.error(f"Error checking Stripe subscription: {e}")
    
    return JsonResponse({
        'success': True,
        'subscription_status': tenant.subscription_status,
        'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        'subscription_ends_at': tenant.subscription_ends_at.isoformat() if tenant.subscription_ends_at else None,
        'days_remaining': tenant.days_remaining_in_trial() if tenant.subscription_status == 'trialing' else None,
        'is_valid': tenant.is_subscription_valid(),
        'stripe_customer_id': tenant.stripe_customer_id,
        'has_subscription': bool(tenant.stripe_subscription_id),
    })


@login_required
def create_checkout_session(request):
    """Create a Stripe Checkout session for subscription"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Admin access required'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    tenant = request.tenant
    
    try:
        # Create or get Stripe customer
        if not tenant.stripe_customer_id:
            customer = stripe.Customer.create(
                name=tenant.name,
                email=request.user.email if request.user.email else None,
                metadata={
                    'tenant_id': tenant.id,
                    'subdomain': tenant.subdomain,
                }
            )
            tenant.stripe_customer_id = customer.id
            tenant.save()
        
        # Build success and cancel URLs
        success_url = request.build_absolute_uri('/manage-users/') + '?payment=success'
        cancel_url = request.build_absolute_uri('/manage-users/') + '?payment=cancelled'
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=tenant.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'tenant_id': tenant.id,
            },
            subscription_data={
                'metadata': {
                    'tenant_id': tenant.id,
                }
            }
        )
        
        return JsonResponse({
            'success': True,
            'checkout_url': checkout_session.url,
            'session_id': checkout_session.id,
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def create_portal_session(request):
    """Create a Stripe Customer Portal session to manage subscription"""
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'No tenant'})
    
    # Check admin permission
    try:
        tenant_user = TenantUser.objects.get(user=request.user, tenant=request.tenant)
        if not tenant_user.is_admin:
            return JsonResponse({'success': False, 'error': 'Admin access required'})
    except TenantUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not authenticated'})
    
    tenant = request.tenant
    
    if not tenant.stripe_customer_id:
        return JsonResponse({'success': False, 'error': 'No billing account found'})
    
    try:
        return_url = request.build_absolute_uri('/manage-users/')
        
        portal_session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=return_url,
        )
        
        return JsonResponse({
            'success': True,
            'portal_url': portal_session.url,
        })
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        logger.error(f"Error creating portal session: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events for subscription management"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            event = json.loads(payload)
            logger.warning("Webhook signature verification skipped - set STRIPE_WEBHOOK_SECRET!")
            
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification failed: {e}")
        return HttpResponse(status=400)
    
    event_type = event['type']
    data = event['data']['object']
    
    logger.info(f"Received Stripe webhook: {event_type}")
    
    try:
        if event_type == 'checkout.session.completed':
            handle_checkout_completed(data)
            
        elif event_type == 'customer.subscription.created':
            handle_subscription_created(data)
            
        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(data)
            
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data)
            
        elif event_type == 'invoice.paid':
            handle_invoice_paid(data)
            
        elif event_type == 'invoice.payment_failed':
            handle_invoice_payment_failed(data)
            
    except Exception as e:
        logger.error(f"Error handling webhook {event_type}: {e}")
        return HttpResponse(status=500)
    
    return HttpResponse(status=200)


def get_tenant_from_customer(customer_id):
    """Get tenant from Stripe customer ID"""
    try:
        return Tenant.objects.get(stripe_customer_id=customer_id)
    except Tenant.DoesNotExist:
        logger.error(f"No tenant found for Stripe customer {customer_id}")
        return None


def get_tenant_from_metadata(metadata):
    """Get tenant from metadata"""
    tenant_id = metadata.get('tenant_id')
    if tenant_id:
        try:
            return Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            pass
    return None


def handle_checkout_completed(session):
    """Handle successful checkout"""
    tenant = get_tenant_from_metadata(session.get('metadata', {}))
    if not tenant and session.get('customer'):
        tenant = get_tenant_from_customer(session['customer'])
    
    if not tenant:
        logger.error(f"Could not find tenant for checkout session {session['id']}")
        return
    
    # Subscription ID will be set by subscription.created event
    logger.info(f"Checkout completed for tenant {tenant.name}")


def handle_subscription_created(subscription):
    """Handle new subscription"""
    tenant = get_tenant_from_metadata(subscription.get('metadata', {}))
    if not tenant:
        tenant = get_tenant_from_customer(subscription['customer'])
    
    if not tenant:
        logger.error(f"Could not find tenant for subscription {subscription['id']}")
        return
    
    tenant.stripe_subscription_id = subscription['id']
    tenant.subscription_status = subscription['status']
    
    if subscription.get('current_period_end'):
        tenant.subscription_ends_at = timezone.datetime.fromtimestamp(
            subscription['current_period_end'], tz=timezone.utc
        )
    
    tenant.save()
    logger.info(f"Subscription created for tenant {tenant.name}: {subscription['status']}")


def handle_subscription_updated(subscription):
    """Handle subscription update"""
    tenant = get_tenant_from_customer(subscription['customer'])
    if not tenant:
        tenant = get_tenant_from_metadata(subscription.get('metadata', {}))
    
    if not tenant:
        logger.error(f"Could not find tenant for subscription {subscription['id']}")
        return
    
    tenant.subscription_status = subscription['status']
    
    if subscription.get('current_period_end'):
        tenant.subscription_ends_at = timezone.datetime.fromtimestamp(
            subscription['current_period_end'], tz=timezone.utc
        )
    
    # Update active status based on subscription
    tenant.is_active = subscription['status'] in ['active', 'trialing']
    
    tenant.save()
    logger.info(f"Subscription updated for tenant {tenant.name}: {subscription['status']}")


def handle_subscription_deleted(subscription):
    """Handle subscription cancellation"""
    tenant = get_tenant_from_customer(subscription['customer'])
    if not tenant:
        return
    
    tenant.subscription_status = 'canceled'
    tenant.stripe_subscription_id = ''
    tenant.save()
    logger.info(f"Subscription canceled for tenant {tenant.name}")


def handle_invoice_paid(invoice):
    """Handle successful payment"""
    tenant = get_tenant_from_customer(invoice['customer'])
    if not tenant:
        return
    
    # Ensure subscription is marked active
    if tenant.subscription_status == 'past_due':
        tenant.subscription_status = 'active'
        tenant.save()
    
    logger.info(f"Invoice paid for tenant {tenant.name}")


def handle_invoice_payment_failed(invoice):
    """Handle failed payment"""
    tenant = get_tenant_from_customer(invoice['customer'])
    if not tenant:
        return
    
    tenant.subscription_status = 'past_due'
    tenant.save()
    logger.info(f"Invoice payment failed for tenant {tenant.name}")