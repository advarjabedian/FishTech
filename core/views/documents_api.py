import os
import re
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from core.models import (
    Customer, Vendor, SO, SOD, PO, POD, DocumentFile, CustomerEmail
)
from django.views.decorators.csrf import csrf_exempt
import json


# =============================================================================
# CUSTOMER APIs
# =============================================================================

@login_required
def search_customers(request):
    """Search customers for autocomplete"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    search = request.GET.get('search', '')
    
    if len(search) < 2:
        return JsonResponse([], safe=False)
    
    customers = Customer.objects.filter(
        name__icontains=search
    ).order_by('name')[:20]
    
    return JsonResponse([
        {'id': c.id, 'customer_id': c.customer_id, 'name': c.name}
        for c in customers
    ], safe=False)


# =============================================================================
# VENDOR APIs
# =============================================================================

@login_required
def search_vendors(request):
    """Search vendors for autocomplete"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    search = request.GET.get('search', '')
    
    if len(search) < 2:
        return JsonResponse([], safe=False)
    
    vendors = Vendor.objects.filter(
        name__icontains=search
    ).order_by('name')[:20]
    
    return JsonResponse([
        {'id': v.id, 'vendor_id': v.vendor_id, 'name': v.name}
        for v in vendors
    ], safe=False)


# =============================================================================
# SALES ORDER APIs
# =============================================================================

@login_required
def get_sales_orders(request):
    """Get sales orders with filters"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    soid = request.GET.get('soid', '').strip()
    customer = request.GET.get('customer', '').strip()
    
    qs = SO.objects.select_related('company', 'customer')
    
    if soid:
        qs = qs.filter(soid__icontains=soid)
    
    if customer:
        qs = qs.filter(customer__name__icontains=customer)
    
    if not soid and not customer:
        # Return most recent 100 records when no filter
        qs = qs.order_by('-soid')[:100]
    else:
        qs = qs.order_by('-soid')[:500]
    
    results = []
    for so in qs:
        # Count files for this SO
        file_count = DocumentFile.objects.filter(
            document_type='so',
            document_id=str(so.soid)
        ).count()
        
        results.append({
            'id': so.id,
            'soid': so.soid,
            'company_name': so.company.companyname if so.company else '',
            'customer_name': so.customer.name if so.customer else '',
            'customer_po': so.customerpo,
            'dispatchdate': so.dispatchdate.isoformat() if so.dispatchdate else None,
            'paid': so.paid,
            'total_amount': float(so.totalamount) if so.totalamount else None,
            'file_count': file_count,
        })
    
    return JsonResponse(results, safe=False)


@login_required
def get_so_files(request, soid):
    """Get all files for a sales order"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    files = DocumentFile.objects.filter(
        document_type='so',
        document_id=str(soid)
    ).order_by('filename')
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/so/{soid}/files/{f.filename}/view/'
        })
    
    # Get customer info from SO
    customer_id = None
    customer_name = None
    try:
        so = SO.objects.select_related('customer').get(soid=soid)
        if so.customer:
            customer_id = so.customer.id
            customer_name = so.customer.name
    except SO.DoesNotExist:
        pass
    
    return JsonResponse({
        'files': file_list,
        'customer_id': customer_id,
        'customer_name': customer_name
    })
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/so/{soid}/files/{f.filename}/view/'
        })
    
    return JsonResponse({'files': file_list})


@login_required
def view_so_file(request, soid, filename):
    """View/download a specific file for a sales order"""
    if not request.tenant:
        raise Http404("Not authenticated")
    
    doc_file = get_object_or_404(
        DocumentFile,
        document_type='so',
        document_id=str(soid),
        filename=filename
    )
    
    file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
    }
    content_type = content_types.get(file_ext, 'application/octet-stream')
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        if file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif']:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@csrf_exempt
@csrf_exempt
@login_required
def upload_so_file(request):
    """Upload a file for a Sales Order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    soid = request.POST.get('soid')
    file_upload = request.FILES.get('file')
    
    if not soid or not file_upload:
        return JsonResponse({'success': False, 'error': 'SOID and file required'})
    
    # Clean filename
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip()
    if not clean_filename:
        clean_filename = 'file' + os.path.splitext(original_filename)[1]
    
    # Create directory structure
    folder_path = os.path.join('documents', 'so', str(soid))
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_path)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Handle filename conflicts
    filename = clean_filename
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    # Save file
    file_path = os.path.join(folder_path, filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'wb') as f:
        for chunk in file_upload.chunks():
            f.write(chunk)
    
    # Create database record
    file_ext = os.path.splitext(filename)[1].lower()
    DocumentFile.objects.create(
        tenant=request.tenant,
        document_type='so',
        document_id=str(soid),
        filename=filename,
        file_path=file_path,
        file_type='pdf' if file_ext == '.pdf' else 'image',
        file_size=file_upload.size
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@csrf_exempt
@login_required
def delete_so_file(request, soid, filename):
    """Delete a file for a sales order"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        doc_file = DocumentFile.objects.get(
            document_type='so',
            document_id=str(soid),
            filename=filename
        )
        
        # Delete physical file
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete database record
        doc_file.delete()
        
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# PURCHASE ORDER APIs
# =============================================================================

@login_required
def get_purchase_orders(request):
    """Get purchase orders with filters"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    poid = request.GET.get('poid', '').strip()
    vendor = request.GET.get('vendor', '').strip()
    
    qs = PO.objects.select_related('company', 'vendor', 'buyer')
    
    if poid:
        qs = qs.filter(poid__icontains=poid)
    
    if vendor:
        qs = qs.filter(vendor__name__icontains=vendor)
    
    if not poid and not vendor:
        return JsonResponse([], safe=False)
    
    qs = qs.order_by('-poid')[:500]
    
    results = []
    for po in qs:
        # Count files for this PO
        file_count = DocumentFile.objects.filter(
            document_type='po',
            document_id=str(po.poid)
        ).count()
        
        results.append({
            'id': po.id,
            'poid': po.poid,
            'company_name': po.company.companyname if po.company else '',
            'vendor_name': po.vendor.name if po.vendor else '',
            'buyer_name': po.buyer.name if po.buyer else '',
            'orderdate': po.orderdate.isoformat() if po.orderdate else None,
            'receivedate': po.receivedate.isoformat() if po.receivedate else None,
            'paid': po.paid,
            'totalcost': float(po.totalcost) if po.totalcost else None,
            'file_count': file_count,
            'verified': po.verified,
            'has_receiving_data': bool(po.receivetime),
        })
    
    return JsonResponse(results, safe=False)


@login_required
def get_po_files(request, poid):
    """Get all files for a purchase order"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    files = DocumentFile.objects.filter(
        document_type='po',
        document_id=str(poid)
    ).order_by('filename')
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/po/{poid}/files/{f.filename}/view/'
        })
    
    return JsonResponse({'files': file_list})


@login_required
def view_po_file(request, poid, filename):
    """View/download a specific file for a purchase order"""
    if not request.tenant:
        raise Http404("Not authenticated")
    
    doc_file = get_object_or_404(
        DocumentFile,
        document_type='po',
        document_id=str(poid),
        filename=filename
    )
    
    file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
    }
    content_type = content_types.get(file_ext, 'application/octet-stream')
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        if file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif']:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@csrf_exempt
@login_required
def upload_po_file(request):
    """Upload a file for a purchase order"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    poid = request.POST.get('poid')
    file_upload = request.FILES.get('file')
    
    if not poid or not file_upload:
        return JsonResponse({'success': False, 'error': 'POID and file required'})
    
    # Clean filename
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip()
    if not clean_filename:
        clean_filename = 'file' + os.path.splitext(original_filename)[1]
    
    # Create directory structure
    folder_path = os.path.join('documents', 'po', str(poid))
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_path)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Handle filename conflicts
    filename = clean_filename
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    # Save file
    file_path = os.path.join(folder_path, filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'wb') as f:
        for chunk in file_upload.chunks():
            f.write(chunk)
    
    # Create database record
    file_ext = os.path.splitext(filename)[1].lower()
    DocumentFile.objects.create(
        tenant=request.tenant,
        document_type='po',
        document_id=str(poid),
        filename=filename,
        file_path=file_path,
        file_type='pdf' if file_ext == '.pdf' else 'image',
        file_size=file_upload.size
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@csrf_exempt
@login_required
def delete_po_file(request, poid, filename):
    """Delete a file for a purchase order"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        doc_file = DocumentFile.objects.get(
            document_type='po',
            document_id=str(poid),
            filename=filename
        )
        
        # Delete physical file
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete database record
        doc_file.delete()
        
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_pod_items(request, poid):
    """Get POD items for a purchase order"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        po = PO.objects.get(poid=poid)
    except PO.DoesNotExist:
        return JsonResponse([], safe=False)
    
    items = POD.objects.filter(po=po).order_by('podid')
    
    return JsonResponse([
        {
            'podid': item.podid,
            'productid': item.productid,
            'description': item.descriptionmemo,
            'unitsin': float(item.unitsin) if item.unitsin else None,
            'weightin': float(item.weightin) if item.weightin else None,
            'vendorlot': item.vendorlot,
            'packdate': item.packdate.isoformat() if item.packdate else None,
        }
        for item in items
    ], safe=False)


# =============================================================================
# POD DOCUMENT APIs
# =============================================================================

@login_required
def get_pod_documents(request):
    """Get POD records with filters"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    podid = request.GET.get('podid', '').strip()
    product = request.GET.get('product', '').strip()
    vendorlot = request.GET.get('vendorlot', '').strip()
    poid = request.GET.get('poid', '').strip()
    
    qs = POD.objects.select_related('po')
    
    if podid:
        qs = qs.filter(podid__icontains=podid)
    
    if product:
        qs = qs.filter(descriptionmemo__icontains=product)
    
    if vendorlot:
        qs = qs.filter(vendorlot__icontains=vendorlot)
    
    if poid:
        qs = qs.filter(po__poid=poid)
    
    if not podid and not product and not vendorlot and not poid:
        return JsonResponse([], safe=False)
    
    qs = qs.order_by('-podid')[:500]
    
    results = []
    for pod in qs:
        file_count = DocumentFile.objects.filter(
            document_type='pod',
            document_id=str(pod.podid)
        ).count()
        
        results.append({
            'id': pod.id,
            'podid': pod.podid,
            'poid': pod.po.poid if pod.po else None,
            'productid': pod.productid,
            'description': pod.descriptionmemo,
            'vendorlot': pod.vendorlot,
            'packdate': pod.packdate.isoformat() if pod.packdate else None,
            'unitsin': float(pod.unitsin) if pod.unitsin else None,
            'weightin': float(pod.weightin) if pod.weightin else None,
            'file_count': file_count,
        })
    
    return JsonResponse(results, safe=False)


@login_required
def get_pod_files(request, podid):
    """Get all files for a POD"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    files = DocumentFile.objects.filter(
        document_type='pod',
        document_id=str(podid)
    ).order_by('filename')
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/pod/{podid}/files/{f.filename}/view/'
        })
    
    return JsonResponse({'files': file_list})


@login_required
def view_pod_file(request, podid, filename):
    """View/download a specific file for a POD"""
    if not request.tenant:
        raise Http404("Not authenticated")
    
    doc_file = get_object_or_404(
        DocumentFile,
        document_type='pod',
        document_id=str(podid),
        filename=filename
    )
    
    file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
    }
    content_type = content_types.get(file_ext, 'application/octet-stream')
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        if file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif']:
            response['Content-Disposition'] = f'inline; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@csrf_exempt
@login_required
def upload_pod_file(request):
    """Upload a file for a POD"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    podid = request.POST.get('podid')
    file_upload = request.FILES.get('file')
    
    if not podid or not file_upload:
        return JsonResponse({'success': False, 'error': 'PODID and file required'})
    
    # Clean filename
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip()
    if not clean_filename:
        clean_filename = 'file' + os.path.splitext(original_filename)[1]
    
    # Create directory structure
    folder_path = os.path.join('documents', 'pod', str(podid))
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_path)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Handle filename conflicts
    filename = clean_filename
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    # Save file
    file_path = os.path.join(folder_path, filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'wb') as f:
        for chunk in file_upload.chunks():
            f.write(chunk)
    
    # Create database record
    file_ext = os.path.splitext(filename)[1].lower()
    DocumentFile.objects.create(
        tenant=request.tenant,
        document_type='pod',
        document_id=str(podid),
        filename=filename,
        file_path=file_path,
        file_type='pdf' if file_ext == '.pdf' else 'image',
        file_size=file_upload.size
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@csrf_exempt
@login_required
def delete_pod_file(request, podid, filename):
    """Delete a file for a POD"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        doc_file = DocumentFile.objects.get(
            document_type='pod',
            document_id=str(podid),
            filename=filename
        )
        
        # Delete physical file
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Delete database record
        doc_file.delete()
        
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def search_pod_products(request):
    """Search products for POD autocomplete"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    search = request.GET.get('search', '')
    
    if len(search) < 2:
        return JsonResponse([], safe=False)
    
    # Get distinct product descriptions from POD
    products = POD.objects.filter(
        descriptionmemo__icontains=search
    ).values('descriptionmemo').distinct()[:20]
    
    return JsonResponse([
        {'description': p['descriptionmemo']}
        for p in products if p['descriptionmemo']
    ], safe=False)


# =============================================================================
# CUSTOMER EMAIL APIs
# =============================================================================

@login_required
def get_customer_emails(request, customer_id):
    """Get saved emails for a customer"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    emails = CustomerEmail.objects.filter(
        customer_id=customer_id
    ).order_by('-created_at')
    
    return JsonResponse([
        {'id': e.id, 'email': e.email, 'label': e.label}
        for e in emails
    ], safe=False)


@csrf_exempt
@login_required
def add_customer_email(request):
    """Add email for a customer"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    import json
    data = json.loads(request.body)
    customer_id = data.get('customer_id')
    email = data.get('email', '').strip()
    label = data.get('label', '').strip()
    
    if not customer_id or not email:
        return JsonResponse({'success': False, 'error': 'Customer ID and email required'})
    
    # Check for duplicate
    if CustomerEmail.objects.filter(customer_id=customer_id, email=email).exists():
        return JsonResponse({'success': False, 'error': 'Email already exists'})
    
    CustomerEmail.objects.create(
        tenant=request.tenant,
        customer_id=customer_id,
        email=email,
        label=label
    )
    
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
# BULK DOWNLOAD/EMAIL APIs
# =============================================================================

@csrf_exempt
@login_required
def download_bulk_so_files(request):
    """Download files for multiple SOIDs as ZIP"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    import zipfile
    import io
    from django.utils import timezone
    
    soids = request.POST.getlist('soids')
    if not soids:
        return JsonResponse({'error': 'No SOIDs provided'}, status=400)
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for soid in soids:
            files = DocumentFile.objects.filter(
                document_type='so',
                document_id=str(soid)
            )
            for doc_file in files:
                file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
                if os.path.exists(file_path):
                    arcname = f"SOID_{soid}/{doc_file.filename}"
                    zip_file.write(file_path, arcname)
    
    zip_buffer.seek(0)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="SO_Documents_{timestamp}.zip"'
    return response


@csrf_exempt
@login_required
def email_so_files(request):
    """Email selected files for a SOID"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    import zipfile
    import io
    from django.utils import timezone
    from django.core.mail import EmailMessage
    
    soid = request.POST.get('soid')
    emails = request.POST.getlist('emails')
    filenames = request.POST.getlist('filenames')
    
    if not soid or not emails or not filenames:
        return JsonResponse({'success': False, 'error': 'SOID, emails, and filenames required'})
    
    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in filenames:
            doc_file = DocumentFile.objects.filter(
                document_type='so',
                document_id=str(soid),
                filename=filename
            ).first()
            if doc_file:
                file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
    
    zip_buffer.seek(0)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    
    email_msg = EmailMessage(
        subject=f'Invoice {soid} Documents',
        body=f'Attached are {len(filenames)} file(s) for Invoice {soid}.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emails
    )
    email_msg.attach(f'Invoice_{soid}_{timestamp}.zip', zip_buffer.getvalue(), 'application/zip')
    email_msg.send()
    
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def email_bulk_so_files(request):
    """Email files for multiple SOIDs as ZIP"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    import zipfile
    import io
    from django.utils import timezone
    from django.core.mail import EmailMessage
    
    soids = request.POST.getlist('soids')
    emails = request.POST.getlist('emails')
    
    if not soids or not emails:
        return JsonResponse({'success': False, 'error': 'SOIDs and emails required'})
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for soid in soids:
            files = DocumentFile.objects.filter(document_type='so', document_id=str(soid))
            for doc_file in files:
                file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
                if os.path.exists(file_path):
                    zip_file.write(file_path, f"SOID_{soid}/{doc_file.filename}")
    
    zip_buffer.seek(0)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    
    # Build reply-to from tenant settings
    reply_to = []
    if request.tenant and request.tenant.reply_to_email:
        if request.tenant.reply_to_name:
            reply_to = [f'{request.tenant.reply_to_name} <{request.tenant.reply_to_email}>']
        else:
            reply_to = [request.tenant.reply_to_email]
    
    email_msg = EmailMessage(
        subject=f'Invoice Documents - {len(soids)} Orders',
        body=f'Attached are documents for {len(soids)} invoice(s).',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emails,
        reply_to=reply_to
    )
    email_msg.attach(f'SO_Documents_{timestamp}.zip', zip_buffer.getvalue(), 'application/zip')
    email_msg.send()
    
    return JsonResponse({'success': True})


# =============================================================================
# TENANT EMAIL APIs (Tenant-wide Address Book)
# =============================================================================

@login_required
def get_tenant_emails(request):
    """Get all tenant-wide emails"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    from core.models import TenantEmail
    emails = TenantEmail.objects.filter(tenant=request.tenant).order_by('-created_at')
    
    return JsonResponse([
        {'id': e.id, 'email': e.email, 'label': e.label}
        for e in emails
    ], safe=False)


@csrf_exempt
@login_required
def add_tenant_email(request):
    """Add tenant-wide email"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    from core.models import TenantEmail
    data = json.loads(request.body)
    email = data.get('email', '').strip()
    label = data.get('label', '').strip()
    
    if not email:
        return JsonResponse({'success': False, 'error': 'Email required'})
    
    if TenantEmail.objects.filter(tenant=request.tenant, email=email).exists():
        return JsonResponse({'success': False, 'error': 'Email already exists'})
    
    TenantEmail.objects.create(
        tenant=request.tenant,
        email=email,
        label=label
    )
    
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def delete_tenant_email(request, email_id):
    """Delete a tenant-wide email"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    from core.models import TenantEmail
    try:
        TenantEmail.objects.filter(id=email_id, tenant=request.tenant).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# PO DOCUMENTS API - Add these functions to your documents views file
# ============================================================================

from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import models
from ..models import PO, POD, Vendor, VendorEmail, DocumentFile, Company, get_current_tenant
import os
import json
import zipfile
from io import BytesIO


@login_required
def get_purchase_orders(request):
    """Get purchase orders with optional filters"""
    tenant = get_current_tenant()
    
    poid = request.GET.get('poid')
    vendor = request.GET.get('vendor')
    startdate = request.GET.get('startdate')
    enddate = request.GET.get('enddate')
    paid = request.GET.get('paid')
    
    pos = PO.objects.filter(tenant=tenant).select_related('company', 'vendor')
    
    if poid:
        pos = pos.filter(poid__icontains=poid)
    if vendor:
        pos = pos.filter(vendor__name__icontains=vendor)
    if startdate:
        pos = pos.filter(orderdate__gte=startdate)
    if enddate:
        pos = pos.filter(orderdate__lte=enddate)
    if paid == 'yes':
        pos = pos.filter(paid__in=['1', 'Yes', 'yes', 'Y', 'y'])
    elif paid == 'no':
        pos = pos.exclude(paid__in=['1', 'Yes', 'yes', 'Y', 'y'])
    
    pos = pos.order_by('-orderdate', '-poid')[:500]
    
    # Get file counts
    file_counts = {}
    doc_files = DocumentFile.objects.filter(
        tenant=tenant,
        document_type='po',
        document_id__in=[str(po.poid) for po in pos]
    ).values('document_id').annotate(count=models.Count('id'))
    for df in doc_files:
        file_counts[df['document_id']] = df['count']
    
    data = []
    for po in pos:
        data.append({
            'poid': po.poid,
            'company_name': po.company.companyname if po.company else '',
            'vendor_name': po.vendor.name if po.vendor else '',
            'orderdate': po.orderdate.isoformat() if po.orderdate else '',
            'receivedate': po.receivedate.isoformat() if po.receivedate else '',
            'paid': po.paid,
            'verified': po.verified,
            'file_count': file_counts.get(str(po.poid), 0),
        })
    
    return JsonResponse(data, safe=False)


@login_required
def get_po_files(request, poid):
    """Get files for a specific PO"""
    tenant = get_current_tenant()
    
    try:
        po = PO.objects.get(tenant=tenant, poid=poid)
    except PO.DoesNotExist:
        return JsonResponse({'files': [], 'vendor_id': None, 'vendor_name': None})
    
    files = DocumentFile.objects.filter(
        tenant=tenant,
        document_type='po',
        document_id=str(poid)
    )
    
    file_list = []
    for f in files:
        file_type = 'pdf' if f.filename.lower().endswith('.pdf') else 'image'
        file_list.append({
            'filename': f.filename,
            'url': f'/api/documents/po/{poid}/files/{f.filename}/view/',
            'type': file_type,
            'uploaded_at': f.uploaded_at.isoformat() if f.uploaded_at else '',
        })
    
    return JsonResponse({
        'files': file_list,
        'vendor_id': po.vendor.id if po.vendor else None,
        'vendor_name': po.vendor.name if po.vendor else None,
    })


@login_required
def view_po_file(request, poid, filename):
    """View/download a PO file"""
    tenant = get_current_tenant()
    
    try:
        doc_file = DocumentFile.objects.get(
            tenant=tenant,
            document_type='po',
            document_id=str(poid),
            filename=filename
        )
    except DocumentFile.DoesNotExist:
        return HttpResponse('File not found', status=404)
    
    file_path = doc_file.file_path
    if not os.path.exists(file_path):
        return HttpResponse('File not found on disk', status=404)
    
    # Determine content type
    if filename.lower().endswith('.pdf'):
        content_type = 'application/pdf'
    elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        ext = filename.lower().split('.')[-1]
        content_type = f'image/{ext}' if ext != 'jpg' else 'image/jpeg'
    else:
        content_type = 'application/octet-stream'
    
    return FileResponse(open(file_path, 'rb'), content_type=content_type)


@login_required
@require_http_methods(["POST"])
def upload_po_file(request):
    """Upload a file to a PO"""
    tenant = get_current_tenant()
    
    poid = request.POST.get('poid')
    uploaded_file = request.FILES.get('file')
    
    if not poid or not uploaded_file:
        return JsonResponse({'success': False, 'error': 'Missing poid or file'})
    
    # Check PO exists
    if not PO.objects.filter(tenant=tenant, poid=poid).exists():
        return JsonResponse({'success': False, 'error': f'PO {poid} not found'})
    
    # Create upload directory
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(tenant.id), 'po', str(poid))
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save file
    filename = uploaded_file.name
    file_path = os.path.join(upload_dir, filename)
    
    # Handle duplicate filenames
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(file_path):
        filename = f"{base_name}_{counter}{ext}"
        file_path = os.path.join(upload_dir, filename)
        counter += 1
    
    with open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
    # Create database record
    DocumentFile.objects.create(
        tenant=tenant,
        document_type='po',
        document_id=str(poid),
        filename=filename,
        file_path=file_path,
        file_type='pdf' if filename.lower().endswith('.pdf') else 'image',
        file_size=uploaded_file.size,
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@login_required
@require_http_methods(["DELETE"])
def delete_po_file(request, poid, filename):
    """Delete a PO file"""
    tenant = get_current_tenant()
    
    try:
        doc_file = DocumentFile.objects.get(
            tenant=tenant,
            document_type='po',
            document_id=str(poid),
            filename=filename
        )
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})
    
    # Delete from disk
    if os.path.exists(doc_file.file_path):
        os.remove(doc_file.file_path)
    
    # Delete from database
    doc_file.delete()
    
    return JsonResponse({'success': True})


@login_required
def get_pod_items(request, poid):
    """Get POD line items for a PO"""
    tenant = get_current_tenant()
    
    items = POD.objects.filter(tenant=tenant, poid=poid)
    
    data = []
    for item in items:
        data.append({
            'podid': item.podid,
            'productid': item.productid,
            'description': item.descriptionmemo,
            'unitsin': float(item.unitsin) if item.unitsin else None,
            'weightin': float(item.weightin) if item.weightin else None,
            'vendorlot': item.vendorlot,
        })
    
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["POST"])
def download_bulk_po_files(request):
    """Download files from multiple POs as a ZIP"""
    tenant = get_current_tenant()
    
    poids = request.POST.getlist('poids')
    if not poids:
        return HttpResponse('No POs selected', status=400)
    
    # Create ZIP in memory
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for poid in poids:
            files = DocumentFile.objects.filter(
                tenant=tenant,
                document_type='po',
                document_id=str(poid)
            )
            for f in files:
                if os.path.exists(f.file_path):
                    arcname = f'PO_{poid}/{f.filename}'
                    zip_file.write(f.file_path, arcname)
    
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="po_documents.zip"'
    return response


@login_required
@require_http_methods(["POST"])
def email_bulk_po_files(request):
    """Email files from multiple POs"""
    tenant = get_current_tenant()
    
    emails = request.POST.getlist('emails')
    poids = request.POST.getlist('poids')
    
    if not emails or not poids:
        return JsonResponse({'success': False, 'error': 'Missing emails or poids'})
    
    # Collect all files
    attachments = []
    for poid in poids:
        files = DocumentFile.objects.filter(
            tenant=tenant,
            document_type='po',
            document_id=str(poid)
        )
        for f in files:
            if os.path.exists(f.file_path):
                attachments.append({
                    'path': f.file_path,
                    'name': f'PO_{poid}_{f.filename}',
                })
    
    if not attachments:
        return JsonResponse({'success': False, 'error': 'No files found'})
    
    try:
        # Build email
        subject = f'Purchase Order Documents - {", ".join(poids)}'
        body = f'Please find attached the documents for PO(s): {", ".join(poids)}'
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )
        
        # Set reply-to if configured
        if tenant.reply_to_email:
            email.reply_to = [tenant.reply_to_email]
        
        # Attach files
        for att in attachments:
            with open(att['path'], 'rb') as f:
                email.attach(att['name'], f.read())
        
        email.send()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def email_po_files(request):
    """Email specific files from a PO"""
    tenant = get_current_tenant()
    
    poid = request.POST.get('poid')
    emails = request.POST.getlist('emails')
    filenames = request.POST.getlist('filenames')
    
    if not poid or not emails or not filenames:
        return JsonResponse({'success': False, 'error': 'Missing required fields'})
    
    # Get files
    attachments = []
    for filename in filenames:
        try:
            doc_file = DocumentFile.objects.get(
                tenant=tenant,
                document_type='po',
                document_id=str(poid),
                filename=filename
            )
            if os.path.exists(doc_file.file_path):
                attachments.append({
                    'path': doc_file.file_path,
                    'name': filename,
                })
        except DocumentFile.DoesNotExist:
            continue
    
    if not attachments:
        return JsonResponse({'success': False, 'error': 'No files found'})
    
    try:
        subject = f'Purchase Order Documents - PO #{poid}'
        body = f'Please find attached the documents for PO #{poid}'
        
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=emails,
        )
        
        if tenant.reply_to_email:
            email.reply_to = [tenant.reply_to_email]
        
        for att in attachments:
            with open(att['path'], 'rb') as f:
                email.attach(att['name'], f.read())
        
        email.send()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def search_vendors(request):
    """Search vendors by name"""
    tenant = get_current_tenant()
    search = request.GET.get('search', '')
    
    vendors = Vendor.objects.filter(tenant=tenant)
    if search:
        vendors = vendors.filter(name__icontains=search)
    
    vendors = vendors.order_by('name')[:20]
    
    data = [{'id': v.id, 'name': v.name} for v in vendors]
    return JsonResponse(data, safe=False)


@login_required
def get_vendor_emails(request, vendor_id):
    """Get saved emails for a vendor"""
    tenant = get_current_tenant()
    
    emails = VendorEmail.objects.filter(tenant=tenant, vendor_id=vendor_id)
    data = [{'id': e.id, 'email': e.email, 'label': e.label} for e in emails]
    return JsonResponse(data, safe=False)


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
    
    try:
        vendor = Vendor.objects.get(tenant=tenant, id=vendor_id)
    except Vendor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor not found'})
    
    VendorEmail.objects.get_or_create(
        tenant=tenant,
        vendor=vendor,
        email=email,
        defaults={'label': label}
    )
    
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