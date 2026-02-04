import os
import re
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from core.models import Customer, SO, SOD, DocumentFile


@login_required
def search_customers(request):
    """Search customers for autocomplete"""
    if not request.tenant:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    search = request.GET.get('search', '')
    
    if len(search) < 2:
        return JsonResponse([], safe=False)
    
    customers = Customer.objects.filter(name__icontains=search).order_by('name')[:20]
    
    return JsonResponse([
        {'id': c.id, 'customer_id': c.customer_id, 'name': c.name}
        for c in customers
    ], safe=False)


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
        qs = qs.order_by('-soid')[:100]
    else:
        qs = qs.order_by('-soid')[:500]
    
    results = []
    for so in qs:
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
    
    original_filename = file_upload.name
    clean_filename = re.sub(r'[^a-zA-Z0-9\s._-]', '', original_filename)
    clean_filename = re.sub(r'\s+', ' ', clean_filename).strip()
    if not clean_filename:
        clean_filename = 'file' + os.path.splitext(original_filename)[1]
    
    folder_path = os.path.join('documents', 'so', str(soid))
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
        
        file_path = os.path.join(settings.MEDIA_ROOT, doc_file.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        doc_file.delete()
        return JsonResponse({'success': True})
    except DocumentFile.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'File not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


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
            files = DocumentFile.objects.filter(document_type='so', document_id=str(soid))
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