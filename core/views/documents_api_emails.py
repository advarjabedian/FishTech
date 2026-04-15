import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core.models import ContactEmail, get_current_tenant


# =============================================================================
# GENERIC EMAIL HELPERS
# =============================================================================

def _list_emails(request, contact_type, entity_id=None):
    tenant = request.tenant or get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    qs = ContactEmail.objects.filter(tenant=tenant, contact_type=contact_type)
    if entity_id is not None:
        qs = qs.filter(entity_id=entity_id)
    else:
        qs = qs.filter(entity_id__isnull=True)
    return JsonResponse([{'id': e.id, 'email': e.email, 'label': e.label} for e in qs.order_by('-created_at')], safe=False)


def _add_email(request, contact_type, entity_id=None):
    tenant = request.tenant or get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    label = data.get('label', '').strip()
    if not email:
        return JsonResponse({'success': False, 'error': 'Email required'})
    if ContactEmail.objects.filter(tenant=tenant, contact_type=contact_type, entity_id=entity_id, email=email).exists():
        return JsonResponse({'success': False, 'error': 'Email already exists'})
    ContactEmail.objects.create(tenant=tenant, contact_type=contact_type, entity_id=entity_id, email=email, label=label)
    return JsonResponse({'success': True})


def _delete_email(request, email_id):
    tenant = request.tenant or get_current_tenant()
    if not tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    ContactEmail.objects.filter(id=email_id, tenant=tenant).delete()
    return JsonResponse({'success': True})


# =============================================================================
# CUSTOMER EMAIL APIs
# =============================================================================

@login_required
def get_customer_emails(request, customer_id):
    return _list_emails(request, 'customer', entity_id=customer_id)


@csrf_exempt
@login_required
def add_customer_email(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    data = json.loads(request.body)
    entity_id = data.get('customer_id')
    if not entity_id:
        return JsonResponse({'success': False, 'error': 'Customer ID required'})
    return _add_email(request, 'customer', entity_id=entity_id)


@csrf_exempt
@login_required
def delete_customer_email(request, email_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    return _delete_email(request, email_id)


# =============================================================================
# VENDOR EMAIL APIs
# =============================================================================

@login_required
def get_vendor_emails(request, vendor_id):
    return _list_emails(request, 'vendor', entity_id=vendor_id)


@login_required
@require_http_methods(["POST"])
def add_vendor_email(request):
    data = json.loads(request.body)
    entity_id = data.get('vendor_id')
    if not entity_id:
        return JsonResponse({'success': False, 'error': 'Vendor ID required'})
    return _add_email(request, 'vendor', entity_id=entity_id)


@login_required
@require_http_methods(["DELETE"])
def delete_vendor_email(request, email_id):
    return _delete_email(request, email_id)


# =============================================================================
# TENANT EMAIL APIs (Tenant-wide Address Book)
# =============================================================================

@login_required
def get_tenant_emails(request):
    return _list_emails(request, 'tenant', entity_id=None)


@csrf_exempt
@login_required
def add_tenant_email(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    return _add_email(request, 'tenant', entity_id=None)


@csrf_exempt
@login_required
def delete_tenant_email(request, email_id):
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    return _delete_email(request, email_id)
