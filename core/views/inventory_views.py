from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
import json
import logging

logger = logging.getLogger(__name__)
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from ..models import Inventory, Product, Vendor, Company, get_current_tenant


@login_required
def inventory_list(request):
    return render(request, 'core/Inventory/inventory_list.html')


@login_required
@require_GET
def inventory_api(request):
    """Paginated inventory grouped by productid"""
    try:
        tenant = get_current_tenant()
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        search = request.GET.get('search', '').strip()
        exclude = request.GET.get('exclude', '').strip()
        sort_field = request.GET.get('sort', '')
        sort_direction = request.GET.get('direction', 'asc')
        company_filter = request.GET.get('company', '').strip()

        base_qs = Inventory.objects.all()  # TenantManager handles tenant filter

        if company_filter:
            base_qs = base_qs.filter(company_id=company_filter)

        # Sample updatetime
        sample = base_qs.values('updatetime').first()
        sample_updatetime = sample['updatetime'] if sample else ''

        inv_qs = base_qs.values('productid').annotate(
            total_units_available=Sum('unitsavailable'),
            total_available_weight=Sum('availableweight'),
            total_units_on_hand=Sum('unitsonhand'),
            record_count=Count('id'),
        ).filter(productid__isnull=False)

        if search:
            terms = search.split()
            ids = None
            for term in terms:
                matched = set(Product.objects.filter(
                    Q(description__icontains=term) |
                    Q(item_number__icontains=term) |
                    Q(product_id__icontains=term)
                ).values_list('product_id', flat=True))
                ids = matched if ids is None else ids & matched
            inv_qs = inv_qs.filter(productid__in=ids) if ids else inv_qs.none()

        if exclude:
            terms = exclude.split()
            ex_ids = set()
            for term in terms:
                ex_ids.update(Product.objects.filter(
                    Q(description__icontains=term) |
                    Q(item_number__icontains=term) |
                    Q(product_id__icontains=term)
                ).values_list('product_id', flat=True))
            if ex_ids:
                inv_qs = inv_qs.exclude(productid__in=ex_ids)

        inv_qs = inv_qs.exclude(
            Q(total_units_available=0, total_available_weight=0) |
            Q(total_units_available__isnull=True, total_available_weight__isnull=True)
        )

        sort_map = {
            'item_number': 'productid',
            'desc': 'productid',
            'unitsavailable': 'total_units_available',
            'availableweight': 'total_available_weight',
        }
        if sort_field and sort_field in sort_map and sort_field != 'desc':
            db_field = sort_map[sort_field]
            inv_qs = inv_qs.order_by(f"-{db_field}" if sort_direction == 'desc' else db_field)
        else:
            inv_qs = inv_qs.order_by('productid')

        product_lookup = {str(p.product_id): p for p in Product.objects.all()}

        inv_list = list(inv_qs)
        if sort_field == 'desc':
            inv_list.sort(
                key=lambda x: (product_lookup.get(str(x['productid'])) or Product()).description or '',
                reverse=(sort_direction == 'desc')
            )

        paginator = Paginator(inv_list, page_size)
        page_obj = paginator.get_page(page)

        results = []
        for item in page_obj:
            pid = str(item['productid'])
            p = product_lookup.get(pid)
            results.append({
                'id': item['productid'],
                'productid': pid,
                'item_number': p.item_number if p else pid,
                'desc': p.description if p else f"Product {pid}",
                'unitsavailable': float(item['total_units_available'] or 0),
                'availableweight': float(item['total_available_weight'] or 0),
                'unitsonhand': float(item['total_units_on_hand'] or 0),
                'record_count': item['record_count'],
                'updatetime': sample_updatetime,
                'origin': p.origin if p else '',
                'notes': p.notes if p else '',
            })

        return JsonResponse({
            'results': results,
            'page': page,
            'page_size': page_size,
            'total': paginator.count,
            'num_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        })

    except Exception as e:
        return JsonResponse({'error': str(e), 'results': [], 'total': 0,
                             'has_next': False, 'has_previous': False}, status=500)


@login_required
@require_GET
def inventory_detail_api(request, product_id):
    """All inventory records for a specific productid"""
    try:
        records_qs = Inventory.objects.filter(productid=product_id).order_by('-receivedate', 'vendorlot')

        company_filter = request.GET.get('company', '').strip()
        if company_filter:
            records_qs = records_qs.filter(company_id=company_filter)

        vendor_lookup = {str(v.vendor_id): v.name for v in Vendor.objects.all()}
        company_lookup = {str(c.companyid): c.companyname for c in Company.objects.all()}
        product_lookup = {str(p.product_id): p.item_number for p in Product.objects.all()}

        data = []
        for item in records_qs:
            status = 'hidden' if item.hidden == 1 else ('flagged' if item.flagged == 1 else ('fixed' if item.fixed == 1 else 'active'))
            vendor_id_str = str(item.vendorid).strip() if item.vendorid else None
            data.append({
                'id': item.id,
                'productid': item.productid or '',
                'item_number': product_lookup.get(str(item.productid), item.productid or ''),
                'desc': item.desc or '',
                'company_name': company_lookup.get(str(item.company_id), '') if item.company_id else '',
                'vendor_name': vendor_lookup.get(vendor_id_str, item.vendorid or 'N/A') if vendor_id_str else 'N/A',
                'vendorid': item.vendorid or '',
                'receivedate': item.receivedate or '',
                'vendorlot': item.vendorlot or '',
                'actualcost': float(item.actualcost) if item.actualcost else 0,
                'unittype': item.unittype or '',
                'unitsonhand': float(item.unitsonhand or 0),
                'unitsavailable': float(item.unitsavailable or 0),
                'unitsallocated': float(item.unitsallocated or 0),
                'unitsin': float(item.unitsin or 0),
                'unitsout': float(item.unitsout or 0),
                'weightin': float(item.weightin or 0),
                'weightout': float(item.weightout or 0),
                'billedweight': float(item.billedweight or 0),
                'availableweight': float(item.availableweight or 0),
                'casesavailable': float(item.casesavailable or 0),
                'casesonhand': float(item.casesonhand or 0),
                'pendingunits': float(item.pendingunits or 0),
                'age': float(item.age or 0),
                'origin': item.origin or '',
                'shelflife': float(item.shelflife or 0),
                'critical': item.critical or '',
                'packdate': item.packdate or '',
                'poid': item.poid or '',
                'podid': item.podid or '',
                'category': item.category or '',
                'storageid': item.storageid or '',
                'status': status,
                'flagged': item.flagged == 1,
                'fixed': item.fixed == 1,
                'hidden': item.hidden == 1,
            })

        return JsonResponse({'success': True, 'records': data, 'total_records': len(data)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e), 'records': []}, status=500)


# =============================================================================
# INVENTORY IMPORT + CRUD
# =============================================================================

@login_required
def inventory_import_template(request):
    """Download a blank CSV import template"""
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="inventory_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'ProductID', 'Description', 'ItemNumber', 'VendorID', 'ReceiveDate',
        'VendorLot', 'UnitType', 'UnitsIn', 'UnitsAvailable', 'UnitsOnHand',
        'WeightIn', 'AvailableWeight', 'ActualCost', 'PackDate', 'Origin',
        'ShelfLife', 'POID', 'PODID', 'Category', 'Age'
    ])
    writer.writerow([
        'SALMON01', 'Atlantic Salmon 10lb', 'ATL-SAL-10', 'V001', '2025-01-15',
        'LOT-001', 'CS', '100', '80', '80',
        '1000', '800', '45.00', '2025-01-10', 'Canada',
        '30', 'PO-001', 'POD-001', '1', '5'
    ])
    return response


@login_required
@require_POST
def inventory_import_preview(request):
    """Parse uploaded CSV and return preview without saving"""
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

        # Normalize headers
        def norm(k):
            return k.strip().lower().replace(' ', '').replace('_', '')

        normalized_rows = [{norm(k): v.strip() for k, v in row.items()} for row in rows]

        COL_MAP = {
            'productid': 'productid', 'product_id': 'productid',
            'description': 'desc', 'desc': 'desc',
            'itemnumber': 'item_number', 'item_number': 'item_number',
            'vendorid': 'vendorid',
            'receivedate': 'receivedate',
            'vendorlot': 'vendorlot',
            'unittype': 'unittype',
            'unitsin': 'unitsin',
            'unitsavailable': 'unitsavailable',
            'unitsonhand': 'unitsonhand',
            'weightin': 'weightin',
            'availableweight': 'availableweight',
            'actualcost': 'actualcost',
            'packdate': 'packdate',
            'origin': 'origin',
            'shelflife': 'shelflife',
            'poid': 'poid',
            'podid': 'podid',
            'category': 'category',
            'age': 'age',
        }

        preview = []
        errors = []
        for i, row in enumerate(normalized_rows, start=2):
            mapped = {COL_MAP[k]: v for k, v in row.items() if k in COL_MAP}
            if not mapped.get('productid'):
                errors.append(f'Row {i}: Missing ProductID')
                continue
            preview.append(mapped)

        return JsonResponse({
            'success': True,
            'total_rows': len(preview),
            'error_count': len(errors),
            'errors': errors[:20],
            'rows': preview[:200],
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def inventory_product_delete(request, product_id):
    """Delete ALL inventory records for a given productid"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        deleted, _ = Inventory.objects.filter(productid=product_id).delete()
        return JsonResponse({'success': True, 'deleted': deleted})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def inventory_import_confirm(request):
    """Save previewed inventory rows"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)

    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])
        if not rows:
            return JsonResponse({'error': 'No rows to import'}, status=400)

        def to_dec(v):
            try:
                return float(str(v).replace(',', '')) if v else None
            except (ValueError, TypeError):
                return None

        created = 0
        for row in rows:
            # Upsert the Product catalog entry
            product_id = str(row.get('productid', '')).strip()
            if not product_id:
                continue

            Product.all_objects.update_or_create(
                tenant=tenant,
                product_id=product_id,
                defaults={
                    'description': row.get('desc', ''),
                    'item_number': row.get('item_number', ''),
                    'origin': row.get('origin', ''),
                }
            )

            Inventory.objects.create(
                tenant=tenant,
                productid=product_id,
                desc=row.get('desc', ''),
                vendorid=row.get('vendorid', ''),
                receivedate=row.get('receivedate', ''),
                vendorlot=row.get('vendorlot', ''),
                unittype=row.get('unittype', ''),
                unitsin=to_dec(row.get('unitsin')),
                unitsavailable=to_dec(row.get('unitsavailable')),
                unitsonhand=to_dec(row.get('unitsonhand')),
                weightin=to_dec(row.get('weightin')),
                availableweight=to_dec(row.get('availableweight')),
                actualcost=to_dec(row.get('actualcost')),
                packdate=row.get('packdate', ''),
                origin=row.get('origin', ''),
                shelflife=to_dec(row.get('shelflife')),
                poid=row.get('poid', ''),
                podid=row.get('podid', ''),
                category=int(row['category']) if row.get('category') else None,
                age=to_dec(row.get('age')),
            )
            created += 1

        return JsonResponse({'success': True, 'created': created})

    except Exception as e:
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def inventory_record_create(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        data = json.loads(request.body)
        product_id = str(data.get('productid', '')).strip()
        if not product_id:
            return JsonResponse({'error': 'ProductID is required'}, status=400)

        def to_dec(v):
            try:
                return float(v) if v not in (None, '') else None
            except (ValueError, TypeError):
                return None

        # Keep product catalog in sync
        Product.all_objects.update_or_create(
            tenant=tenant,
            product_id=product_id,
            defaults={
                'description': data.get('desc', ''),
                'item_number': data.get('item_number', ''),
                'origin': data.get('origin', ''),
            }
        )

        record = Inventory.objects.create(
            tenant=tenant,
            productid=product_id,
            desc=data.get('desc', ''),
            vendorid=data.get('vendorid', ''),
            receivedate=data.get('receivedate', ''),
            vendorlot=data.get('vendorlot', ''),
            unittype=data.get('unittype', ''),
            unitsin=to_dec(data.get('unitsin')),
            unitsavailable=to_dec(data.get('unitsavailable')),
            unitsonhand=to_dec(data.get('unitsonhand')),
            weightin=to_dec(data.get('weightin')),
            availableweight=to_dec(data.get('availableweight')),
            actualcost=to_dec(data.get('actualcost')),
            packdate=data.get('packdate', ''),
            origin=data.get('origin', ''),
            poid=data.get('poid', ''),
            podid=data.get('podid', ''),
        )
        return JsonResponse({'success': True, 'id': record.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def inventory_record_update(request, record_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        record = get_object_or_404(Inventory, id=record_id)
        data = json.loads(request.body)

        def to_dec(v):
            try:
                return float(v) if v not in (None, '') else None
            except (ValueError, TypeError):
                return None

        for field in ['desc', 'vendorid', 'receivedate', 'vendorlot', 'unittype', 'packdate', 'origin', 'poid', 'podid']:
            if field in data:
                setattr(record, field, data[field])
        for field in ['unitsavailable', 'unitsonhand', 'unitsin', 'weightin', 'availableweight', 'actualcost']:
            if field in data:
                setattr(record, field, to_dec(data[field]))
        record.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def inventory_record_delete(request, record_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)
    try:
        record = get_object_or_404(Inventory, id=record_id)
        record.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)