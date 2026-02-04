import os
import re
import json
import zipfile
from io import BytesIO
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.conf import settings
from django.db import models
from core.models import PO, POD, Vendor, DocumentFile, get_current_tenant


@login_required
def search_vendors(request):
    """Search vendors for autocomplete"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    search = request.GET.get('search', '')
    
    if len(search) < 2:
        return JsonResponse([], safe=False)
    
    vendors = Vendor.objects.filter(name__icontains=search).order_by('name')[:20]
    
    return JsonResponse([
        {'id': v.id, 'vendor_id': v.vendor_id, 'name': v.name}
        for v in vendors
    ], safe=False)


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
    
    files = DocumentFile.objects.filter(tenant=tenant, document_type='po', document_id=str(poid))
    
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
    
    if not PO.objects.filter(tenant=tenant, poid=poid).exists():
        return JsonResponse({'success': False, 'error': f'PO {poid} not found'})
    
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents', str(tenant.id), 'po', str(poid))
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = uploaded_file.name
    file_path = os.path.join(upload_dir, filename)
    
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(file_path):
        filename = f"{base_name}_{counter}{ext}"
        file_path = os.path.join(upload_dir, filename)
        counter += 1
    
    with open(file_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    
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
    
    if os.path.exists(doc_file.file_path):
        os.remove(doc_file.file_path)
    
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
    
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for poid in poids:
            files = DocumentFile.objects.filter(tenant=tenant, document_type='po', document_id=str(poid))
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
    
    attachments = []
    for poid in poids:
        files = DocumentFile.objects.filter(tenant=tenant, document_type='po', document_id=str(poid))
        for f in files:
            if os.path.exists(f.file_path):
                attachments.append({'path': f.file_path, 'name': f'PO_{poid}_{f.filename}'})
    
    if not attachments:
        return JsonResponse({'success': False, 'error': 'No files found'})
    
    try:
        subject = f'Purchase Order Documents - {", ".join(poids)}'
        body = f'Please find attached the documents for PO(s): {", ".join(poids)}'
        
        email = EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=emails)
        
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
@require_http_methods(["POST"])
def email_po_files(request):
    """Email specific files from a PO"""
    tenant = get_current_tenant()
    
    poid = request.POST.get('poid')
    emails = request.POST.getlist('emails')
    filenames = request.POST.getlist('filenames')
    
    if not poid or not emails or not filenames:
        return JsonResponse({'success': False, 'error': 'Missing required fields'})
    
    attachments = []
    for filename in filenames:
        try:
            doc_file = DocumentFile.objects.get(tenant=tenant, document_type='po', document_id=str(poid), filename=filename)
            if os.path.exists(doc_file.file_path):
                attachments.append({'path': doc_file.file_path, 'name': filename})
        except DocumentFile.DoesNotExist:
            continue
    
    if not attachments:
        return JsonResponse({'success': False, 'error': 'No files found'})
    
    try:
        subject = f'Purchase Order Documents - PO #{poid}'
        body = f'Please find attached the documents for PO #{poid}'
        
        email = EmailMessage(subject=subject, body=body, from_email=settings.DEFAULT_FROM_EMAIL, to=emails)
        
        if tenant.reply_to_email:
            email.reply_to = [tenant.reply_to_email]
        
        for att in attachments:
            with open(att['path'], 'rb') as f:
                email.attach(att['name'], f.read())
        
        email.send()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})