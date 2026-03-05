from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from ..models import Product, get_current_tenant
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def product_list(request):
    return render(request, 'core/Inventory/product_list.html')


@login_required
@require_GET
def product_api(request):
    """Paginated + searchable product catalog"""
    try:
        search = request.GET.get('search', '').strip()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        sort_field = request.GET.get('sort', 'item_number')
        sort_direction = request.GET.get('direction', 'asc')

        qs = Product.objects.all()

        if search:
            qs = qs.filter(
                Q(product_id__icontains=search) |
                Q(item_number__icontains=search) |
                Q(description__icontains=search) |
                Q(origin__icontains=search)
            )

        sort_map = {
            'product_id': 'product_id',
            'item_number': 'item_number',
            'description': 'description',
            'origin': 'origin',
        }
        db_field = sort_map.get(sort_field, 'item_number')
        qs = qs.order_by(f"-{db_field}" if sort_direction == 'desc' else db_field)

        total = qs.count()
        offset = (page - 1) * page_size
        products = qs[offset:offset + page_size]

        results = [{
            'id': p.id,
            'product_id': p.product_id,
            'item_number': p.item_number,
            'description': p.description,
            'origin': p.origin,
            'notes': p.notes,
        } for p in products]

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'has_next': (offset + page_size) < total,
        })

    except Exception as e:
        return JsonResponse({'error': str(e), 'results': [], 'total': 0}, status=500)


@login_required
@require_POST
def product_create(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        data = json.loads(request.body)
        product_id = str(data.get('product_id', '')).strip()
        description = str(data.get('description', '')).strip()
        if not product_id or not description:
            return JsonResponse({'error': 'Product ID and Description are required'}, status=400)

        if Product.all_objects.filter(tenant=tenant, product_id=product_id).exists():
            return JsonResponse({'error': f'Product ID "{product_id}" already exists'}, status=400)

        p = Product.objects.create(
            tenant=tenant,
            product_id=product_id,
            item_number=data.get('item_number', ''),
            description=description,
            origin=data.get('origin', ''),
            notes=data.get('notes', ''),
        )
        return JsonResponse({'success': True, 'id': p.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def product_update(request, product_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        p = get_object_or_404(Product, id=product_id)
        data = json.loads(request.body)
        description = str(data.get('description', '')).strip()
        if not description:
            return JsonResponse({'error': 'Description is required'}, status=400)
        p.item_number = data.get('item_number', p.item_number)
        p.description = description
        p.origin = data.get('origin', p.origin)
        p.notes = data.get('notes', p.notes)
        p.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def product_delete(request, product_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        p = get_object_or_404(Product, id=product_id)
        p.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def product_import_template(request):
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['ProductID', 'ItemNumber', 'Description', 'Origin', 'Notes'])
    writer.writerow(['SALMON01', 'ATL-SAL-10', 'Atlantic Salmon 10lb', 'Canada', ''])
    return response


@login_required
@require_POST
def product_import_preview(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    try:
        import csv, io
        content = file.read().decode('utf-8-sig', errors='ignore')
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return JsonResponse({'error': 'File is empty'}, status=400)

        def norm(k):
            return k.strip().lower().replace(' ', '').replace('_', '')

        COL_MAP = {
            'productid': 'product_id', 'product_id': 'product_id',
            'itemnumber': 'item_number', 'item_number': 'item_number',
            'description': 'description', 'desc': 'description',
            'origin': 'origin',
            'notes': 'notes',
        }

        preview = []
        errors = []
        for i, row in enumerate(rows, start=2):
            mapped = {COL_MAP[norm(k)]: v.strip() for k, v in row.items() if norm(k) in COL_MAP}
            if not mapped.get('product_id'):
                errors.append(f'Row {i}: Missing ProductID')
                continue
            if not mapped.get('description'):
                errors.append(f'Row {i}: Missing Description')
                continue
            preview.append(mapped)

        return JsonResponse({
            'success': True,
            'total_rows': len(preview),
            'error_count': len(errors),
            'errors': errors[:20],
            'rows': preview[:500],
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def product_import_confirm(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        if not rows:
            return JsonResponse({'error': 'No rows to import'}, status=400)

        created = updated = 0
        for row in rows:
            _, was_created = Product.all_objects.update_or_create(
                tenant=tenant,
                product_id=row['product_id'],
                defaults={
                    'item_number': row.get('item_number', ''),
                    'description': row.get('description', ''),
                    'origin': row.get('origin', ''),
                    'notes': row.get('notes', ''),
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return JsonResponse({'success': True, 'created': created, 'updated': updated})

    except Exception as e:
        logger.error(str(e))
        return JsonResponse({'error': str(e)}, status=500)