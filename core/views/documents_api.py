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
    Customer, Vendor, SO, SOD, PO, POD, DocumentFile
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
        return JsonResponse([], safe=False)
    
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
            'customer_po': so.customer_po,
            'dispatchdate': so.dispatchdate.isoformat() if so.dispatchdate else None,
            'paid': so.paid,
            'total_amount': float(so.total_amount) if so.total_amount else None,
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