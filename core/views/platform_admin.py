from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from core.models import Tenant, TenantUser, Lead, TenantDocument
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
def edit_tenant(request, tenant_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        tenant = Tenant.objects.get(id=tenant_id)
        data = json.loads(request.body)
        tenant.name = data.get('name', tenant.name)
        tenant.subdomain = data.get('subdomain', tenant.subdomain)
        tenant.address = data.get('address', tenant.address)
        tenant.city = data.get('city', tenant.city)
        tenant.state = data.get('state', tenant.state)
        tenant.zipcode = data.get('zipcode', tenant.zipcode)
        if data.get('subscription_status'):
            tenant.subscription_status = data['subscription_status']
        tenant.save()
        return JsonResponse({'success': True})
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Tenant not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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

    # Ensure all tenants have document records
    for tenant in tenants:
        for doc_type, _ in TenantDocument.DOCUMENT_TYPES:
            TenantDocument.objects.get_or_create(
                tenant=tenant, document_type=doc_type
            )
        tenant.docs = {
            d.document_type: d for d in TenantDocument.objects.filter(tenant=tenant)
        }

    # Lead tracking
    leads = Lead.objects.all().order_by('next_followup', '-updated_at')
    leads_by_stage = {}
    for stage_key, stage_label in Lead.STAGE_CHOICES:
        leads_by_stage[stage_key] = {
            'label': stage_label,
            'count': leads.filter(stage=stage_key).count()
        }

    return render(request, 'core/platform_admin.html', {
        'tenants': tenants,
        'total_tenants': total_tenants,
        'active_subscriptions': active_subscriptions,
        'trialing': trialing,
        'past_due': past_due,
        'canceled': canceled,
        'monthly_revenue': monthly_revenue,
        'stripe_balance': stripe_balance,
        'leads': leads,
        'leads_by_stage': leads_by_stage,
        'stage_choices': Lead.STAGE_CHOICES,
        'today': timezone.now().date(),
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

    # Outbound SMTP settings
    if 'smtp_host' in data:
        tenant.smtp_host = data['smtp_host']
    if 'smtp_port' in data:
        tenant.smtp_port = data['smtp_port'] or 587
    if 'smtp_use_tls' in data:
        tenant.smtp_use_tls = data['smtp_use_tls']
    if 'smtp_user' in data:
        tenant.smtp_user = data['smtp_user']
    if data.get('smtp_password'):
        tenant.smtp_password = data['smtp_password']
    if 'smtp_from_email' in data:
        tenant.smtp_from_email = data['smtp_from_email']

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


@superuser_required
@require_http_methods(["POST"])
def save_lead(request):
    """Create or update a lead"""
    try:
        data = json.loads(request.body)
        lead_id = data.get('id')

        if lead_id:
            lead = Lead.objects.get(id=lead_id)
        else:
            lead = Lead()

        lead.company_name = data.get('company_name', '').strip()
        lead.contact_name = data.get('contact_name', '').strip()
        lead.contact_email = data.get('contact_email', '').strip()
        lead.contact_phone = data.get('contact_phone', '').strip()
        lead.stage = data.get('stage', 'prospect')
        lead.contract_value = data.get('contract_value') or None
        lead.notes = data.get('notes', '').strip()
        lead.last_contacted = data.get('last_contacted') or None
        lead.next_followup = data.get('next_followup') or None
        lead.save()

        return JsonResponse({'success': True, 'id': lead.id})
    except Lead.DoesNotExist:
        return JsonResponse({'error': 'Lead not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@superuser_required
@require_http_methods(["POST"])
def delete_lead(request, lead_id):
    """Delete a lead"""
    try:
        lead = Lead.objects.get(id=lead_id)
        lead.delete()
        return JsonResponse({'success': True})
    except Lead.DoesNotExist:
        return JsonResponse({'error': 'Lead not found'}, status=404)


def sign_document(request, token):
    """Public page for customer to view and sign a document"""
    from django.shortcuts import get_object_or_404
    import uuid as uuid_mod
    try:
        token_uuid = uuid_mod.UUID(str(token))
    except ValueError:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound("Invalid link")

    doc = get_object_or_404(TenantDocument, signing_token=token_uuid)
    return render(request, 'core/sign_document.html', {
        'doc': doc,
        'tenant': doc.tenant,
    })


@csrf_exempt
@require_http_methods(["POST"])
def submit_signature(request, token):
    """Submit a signature for a document"""
    import uuid as uuid_mod
    try:
        token_uuid = uuid_mod.UUID(str(token))
        doc = TenantDocument.objects.get(signing_token=token_uuid)
    except (ValueError, TenantDocument.DoesNotExist):
        return JsonResponse({'error': 'Document not found'}, status=404)

    try:
        data = json.loads(request.body)
        doc.signer_name = data.get('signer_name', '').strip()
        doc.signer_title = data.get('signer_title', '').strip()
        doc.signature = data.get('signature', '')
        doc.is_signed = True
        doc.signed_at = timezone.now()
        doc.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@superuser_required
@require_http_methods(["POST"])
def reset_document(request, doc_id):
    """Reset a signed document so it can be re-signed"""
    try:
        doc = TenantDocument.objects.get(id=doc_id)
        doc.is_signed = False
        doc.signer_name = ''
        doc.signer_title = ''
        doc.signature = ''
        doc.signed_at = None
        import uuid as uuid_mod
        doc.signing_token = uuid_mod.uuid4()
        doc.save()
        return JsonResponse({'success': True})
    except TenantDocument.DoesNotExist:
        return JsonResponse({'error': 'Document not found'}, status=404)
