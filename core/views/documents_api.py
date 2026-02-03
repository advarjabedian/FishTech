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