import os
import re
import zipfile
import io
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from django.core.mail import EmailMessage
from core.models import Customer, Vendor, DocumentFile


# =============================================================================
# CUSTOMER DOCUMENT APIs
# =============================================================================

@login_required
def get_customer_documents(request):
    """Get customers with document counts"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    customer_id = request.GET.get('customer_id', '').strip()
    name = request.GET.get('name', '').strip()
    load_all = request.GET.get('all', '').strip()
    
    qs = Customer.objects.all()
    
    if customer_id:
        qs = qs.filter(customer_id__icontains=customer_id)
    if name:
        qs = qs.filter(name__icontains=name)
    
    if not customer_id and not name and not load_all:
        return JsonResponse([], safe=False)
    
    qs = qs.order_by('name')[:100]
    
    results = []
    for c in qs:
        file_count = DocumentFile.objects.filter(document_type='customer', document_id=str(c.id)).count()
        results.append({
            'id': c.id, 'customer_id': c.customer_id, 'name': c.name,
            'contact_name': c.contact_name, 'email': c.email, 'phone': c.phone,
            'city': c.city, 'state': c.state, 'file_count': file_count,
        })
    
    return JsonResponse(results, safe=False)


@login_required
def get_customer_files(request, customer_id):
    """Get all files for a customer"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    files = DocumentFile.objects.filter(document_type='customer', document_id=str(customer_id)).order_by('filename')
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/customer/{customer_id}/files/{f.filename}/view/'
        })
    
    customer_name = None
    try:
        customer = Customer.objects.get(id=customer_id)
        customer_name = customer.name
    except Customer.DoesNotExist:
        pass
    
    return JsonResponse({'files': file_list, 'customer_name': customer_name})


@login_required
def view_customer_file(request, customer_id, filename):
    """View/download a specific file for a customer"""
    if not request.tenant:
        raise Http404("Not authenticated")
    
    doc_file = get_object_or_404(DocumentFile, document_type='customer', document_id=str(customer_id), filename=filename)
    file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif'}
    content_type = content_types.get(file_ext, 'application/octet-stream')
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{filename}"' if file_ext in content_types else f'attachment; filename="{filename}"'
        return response


@csrf_exempt
@login_required
def upload_customer_file(request):
    """Upload a file for a Customer"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    customer_id = request.POST.get('customer_id')
    file_upload = request.FILES.get('file')
    
    if not customer_id or not file_upload:
        return JsonResponse({'success': False, 'error': 'Customer ID and file required'})
    
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip() or 'file' + os.path.splitext(original_filename)[1]
    
    folder_path = os.path.join('documents', 'customer', str(customer_id))
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_path)
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = clean_filename
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    file_path = os.path.join(folder_path, filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'wb') as f:
        for chunk in file_upload.chunks():
            f.write(chunk)
    
    file_ext = os.path.splitext(filename)[1].lower()
    DocumentFile.objects.create(
        tenant=request.tenant, document_type='customer', document_id=str(customer_id),
        filename=filename, file_path=file_path,
        file_type='pdf' if file_ext == '.pdf' else 'image', file_size=file_upload.size
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@csrf_exempt
@login_required
def delete_customer_file(request, customer_id, filename):
    """Delete a file for a customer"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        doc_file = DocumentFile.objects.get(document_type='customer', document_id=str(customer_id), filename=filename)
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        doc_file.delete()
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})


@csrf_exempt
@login_required
def email_customer_files(request):
    """Email selected files for a customer"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    customer_id = request.POST.get('customer_id')
    emails = request.POST.getlist('emails')
    filenames = request.POST.getlist('filenames')
    
    if not customer_id or not emails or not filenames:
        return JsonResponse({'success': False, 'error': 'Customer ID, emails, and filenames required'})
    
    customer_name = "Customer"
    try:
        customer = Customer.objects.get(id=customer_id)
        customer_name = customer.name
    except Customer.DoesNotExist:
        pass
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in filenames:
            doc_file = DocumentFile.objects.filter(document_type='customer', document_id=str(customer_id), filename=filename).first()
            if doc_file:
                file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
    
    zip_buffer.seek(0)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    
    reply_to = []
    if request.tenant and request.tenant.reply_to_email:
        reply_to = [f'{request.tenant.reply_to_name} <{request.tenant.reply_to_email}>'] if request.tenant.reply_to_name else [request.tenant.reply_to_email]
    
    email_msg = EmailMessage(
        subject=f'Documents for {customer_name}',
        body=f'Attached are {len(filenames)} file(s) for {customer_name}.',
        from_email=settings.DEFAULT_FROM_EMAIL, to=emails, reply_to=reply_to
    )
    email_msg.attach(f'Customer_{customer_id}_{timestamp}.zip', zip_buffer.getvalue(), 'application/zip')
    email_msg.send()
    
    return JsonResponse({'success': True})


# =============================================================================
# VENDOR DOCUMENT APIs
# =============================================================================

@login_required
def get_vendor_documents(request):
    """Get vendors with document counts"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    vendor_id = request.GET.get('vendor_id', '').strip()
    name = request.GET.get('name', '').strip()
    load_all = request.GET.get('all', '').strip()
    
    qs = Vendor.objects.all()
    
    if vendor_id:
        qs = qs.filter(vendor_id__icontains=vendor_id)
    if name:
        qs = qs.filter(name__icontains=name)
    
    if not vendor_id and not name and not load_all:
        return JsonResponse([], safe=False)
    
    qs = qs.order_by('name')[:100]
    
    results = []
    for v in qs:
        file_count = DocumentFile.objects.filter(document_type='vendor', document_id=str(v.id)).count()
        results.append({
            'id': v.id, 'vendor_id': v.vendor_id, 'name': v.name,
            'contact_name': v.contact_name, 'email': v.email, 'phone': v.phone,
            'city': v.city, 'state': v.state, 'file_count': file_count,
        })
    
    return JsonResponse(results, safe=False)


@login_required
def get_vendor_files(request, vendor_id):
    """Get all files for a vendor"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    files = DocumentFile.objects.filter(document_type='vendor', document_id=str(vendor_id)).order_by('filename')
    
    file_list = []
    for f in files:
        file_ext = os.path.splitext(f.filename)[1].lower()
        file_type = 'pdf' if file_ext == '.pdf' else 'image'
        file_list.append({
            'filename': f.filename,
            'type': file_type,
            'url': f'/api/documents/vendor/{vendor_id}/files/{f.filename}/view/'
        })
    
    vendor_name = None
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        vendor_name = vendor.name
    except Vendor.DoesNotExist:
        pass
    
    return JsonResponse({'files': file_list, 'vendor_name': vendor_name})


@login_required
def view_vendor_file(request, vendor_id, filename):
    """View/download a specific file for a vendor"""
    if not request.tenant:
        raise Http404("Not authenticated")
    
    doc_file = get_object_or_404(DocumentFile, document_type='vendor', document_id=str(vendor_id), filename=filename)
    file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
    
    if not os.path.exists(file_path):
        raise Http404("File not found")
    
    file_ext = os.path.splitext(filename)[1].lower()
    content_types = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif'}
    content_type = content_types.get(file_ext, 'application/octet-stream')
    
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{filename}"' if file_ext in content_types else f'attachment; filename="{filename}"'
        return response


@csrf_exempt
@login_required
def upload_vendor_file(request):
    """Upload a file for a Vendor"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    vendor_id = request.POST.get('vendor_id')
    file_upload = request.FILES.get('file')
    
    if not vendor_id or not file_upload:
        return JsonResponse({'success': False, 'error': 'Vendor ID and file required'})
    
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip() or 'file' + os.path.splitext(original_filename)[1]
    
    folder_path = os.path.join('documents', 'vendor', str(vendor_id))
    upload_dir = os.path.join(settings.MEDIA_ROOT, folder_path)
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = clean_filename
    base_name, extension = os.path.splitext(filename)
    counter = 1
    while os.path.exists(os.path.join(upload_dir, filename)):
        filename = f"{base_name}_{counter}{extension}"
        counter += 1
    
    file_path = os.path.join(folder_path, filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    
    with open(full_path, 'wb') as f:
        for chunk in file_upload.chunks():
            f.write(chunk)
    
    file_ext = os.path.splitext(filename)[1].lower()
    DocumentFile.objects.create(
        tenant=request.tenant, document_type='vendor', document_id=str(vendor_id),
        filename=filename, file_path=file_path,
        file_type='pdf' if file_ext == '.pdf' else 'image', file_size=file_upload.size
    )
    
    return JsonResponse({'success': True, 'filename': filename})


@csrf_exempt
@login_required
def delete_vendor_file(request, vendor_id, filename):
    """Delete a file for a vendor"""
    if request.method != 'DELETE':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    try:
        doc_file = DocumentFile.objects.get(document_type='vendor', document_id=str(vendor_id), filename=filename)
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        doc_file.delete()
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})


@csrf_exempt
@login_required
def email_vendor_files(request):
    """Email selected files for a vendor"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
    if not request.tenant:
        return JsonResponse({'success': False, 'error': 'Not authenticated'}, status=401)
    
    vendor_id = request.POST.get('vendor_id')
    emails = request.POST.getlist('emails')
    filenames = request.POST.getlist('filenames')
    
    if not vendor_id or not emails or not filenames:
        return JsonResponse({'success': False, 'error': 'Vendor ID, emails, and filenames required'})
    
    vendor_name = "Vendor"
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        vendor_name = vendor.name
    except Vendor.DoesNotExist:
        pass
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename in filenames:
            doc_file = DocumentFile.objects.filter(document_type='vendor', document_id=str(vendor_id), filename=filename).first()
            if doc_file:
                file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
                if os.path.exists(file_path):
                    zip_file.write(file_path, filename)
    
    zip_buffer.seek(0)
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    
    reply_to = []
    if request.tenant and request.tenant.reply_to_email:
        reply_to = [f'{request.tenant.reply_to_name} <{request.tenant.reply_to_email}>'] if request.tenant.reply_to_name else [request.tenant.reply_to_email]
    
    email_msg = EmailMessage(
        subject=f'Documents for {vendor_name}',
        body=f'Attached are {len(filenames)} file(s) for {vendor_name}.',
        from_email=settings.DEFAULT_FROM_EMAIL, to=emails, reply_to=reply_to
    )
    email_msg.attach(f'Vendor_{vendor_id}_{timestamp}.zip', zip_buffer.getvalue(), 'application/zip')
    email_msg.send()
    
    return JsonResponse({'success': True})