import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from core.models import CustomerEmail, VendorEmail, TenantEmail, get_current_tenant


# =============================================================================
# CUSTOMER EMAIL APIs
# =============================================================================

@login_required
def get_customer_emails(request, customer_id):
    """Get saved emails for a customer"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    emails = CustomerEmail.objects.filter(customer_id=customer_id).order_by('-created_at')
    return JsonResponse([{'id': e.id, 'email': e.email, 'label': e.label} for e in emails], safe=False)


@csrf_exempt
@login_required
def add_customer_email(request):
    """Add email for a customer"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    data = json.loads(request.body)
    customer_id = data.get('customer_id')
    email = data.get('email', '').strip()
    label = data.get('label', '').strip()
    
    if not customer_id or not email:
        return JsonResponse({'success': False, 'error': 'Customer ID and email required'})
    
    if CustomerEmail.objects.filter(customer_id=customer_id, email=email).exists():
        return JsonResponse({'success': False, 'error': 'Email already exists'})
    
    CustomerEmail.objects.create(tenant=request.tenant, customer_id=customer_id, email=email, label=label)
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def delete_customer_email(request, email_id):
    """Delete a customer email"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        CustomerEmail.objects.filter(id=email_id).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# VENDOR EMAIL APIs
# =============================================================================

@login_required
def get_vendor_emails(request, vendor_id):
    """Get saved emails for a vendor"""
    tenant = get_current_tenant()
    emails = VendorEmail.objects.filter(tenant=tenant, vendor_id=vendor_id)
    return JsonResponse([{'id': e.id, 'email': e.email, 'label': e.label} for e in emails], safe=False)


@login_required
@require_http_methods(["POST"])
def add_vendor_email(request):
    """Add an email to a vendor"""
    tenant = get_current_tenant()
    
    try:
        data = json.loads(request.body)
        vendor_id = data.get('vendor_id')
        email = data.get('email')
        label = data.get('label', '')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    
    if not vendor_id or not email:
        return JsonResponse({'success': False, 'error': 'Missing vendor_id or email'})
    
    from core.models import Vendor
    try:
        vendor = Vendor.objects.get(tenant=tenant, id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor not found'})
    
    VendorEmail.objects.get_or_create(tenant=tenant, vendor=vendor, email=email, defaults={'label': label})
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["DELETE"])
def delete_vendor_email(request, email_id):
    """Delete a vendor email"""
    tenant = get_current_tenant()
    
    try:
        email = VendorEmail.objects.get(tenant=tenant, id=email_id)
        email.delete()
        return JsonResponse({'success': True})
    except VendorEmail.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Email not found'})


# =============================================================================
# TENANT EMAIL APIs (Tenant-wide Address Book)
# =============================================================================

@login_required
def get_tenant_emails(request):
    """Get all tenant-wide emails"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    emails = TenantEmail.objects.filter(tenant=request.tenant).order_by('-created_at')
    return JsonResponse([{'id': e.id, 'email': e.email, 'label': e.label} for e in emails], safe=False)


@csrf_exempt
@login_required
def add_tenant_email(request):
    """Add tenant-wide email"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    label = data.get('label', '').strip()
    
    if not email:
        return JsonResponse({'success': False, 'error': 'Email required'})
    
    if TenantEmail.objects.filter(tenant=request.tenant, email=email).exists():
        return JsonResponse({'success': False, 'error': 'Email already exists'})
    
    TenantEmail.objects.create(tenant=request.tenant, email=email, label=label)
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def delete_tenant_email(request, email_id):
    """Delete a tenant-wide email"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        TenantEmail.objects.filter(id=email_id, tenant=request.tenant).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})