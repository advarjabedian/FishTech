from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from core.models import Product, Inventory, ItemGroup, set_current_tenant
import json
import logging

logger = logging.getLogger(__name__)

SIZE_CULL_CHOICES = [
    'Small', 'Medium', 'Large', 'Jumbo', 'Mixed', 'Choice', 'Select',
    'Petite', '1x', '1+ Per Lb', '2-3 Per Lb', '10 Dozen',
    '50 CT Bag', '100 Ct Bag', '10 # Bag', '1 x 10#',
]
HABITAT_CHOICES = [
    'Wild', 'Farm Raised', 'Aquaculture', 'Line Caught',
    'Net Caught', 'Dredged', 'Dive Harvested',
]
COUNTRY_CHOICES = [
    'USA', 'Canada', 'Mexico', 'Chile', 'Ecuador', 'Japan', 'China',
    'Vietnam', 'Thailand', 'Indonesia', 'India', 'Norway', 'Iceland',
    'Spain', 'Portugal', 'UK', 'Australia', 'New Zealand',
]


def ensure_tenant(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.tenant:
            set_current_tenant(request.tenant)
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Page views ───────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def inventory_item_library(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/inventory_item_library.html')


@login_required
@ensure_tenant
def inventory_item_detail(request, product_id):
    if not request.tenant:
        return redirect('login')
    product = get_object_or_404(Product, tenant=request.tenant, id=product_id)
    # Generate initials for avatar
    name = product.item_name or product.description or ''
    words = name.replace('·', ' ').replace(':', ' ').split()
    initials = ''.join(w[0].upper() for w in words[:2] if w) or '?'

    return render(request, 'core/inventory_item_detail.html', {
        'product': product,
        'initials': initials,
        'size_cull_choices': SIZE_CULL_CHOICES,
        'habitat_choices': HABITAT_CHOICES,
        'country_choices': COUNTRY_CHOICES,
    })


# ── Item Group API ───────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def item_groups_api(request):
    groups = ItemGroup.objects.filter(tenant=request.tenant, is_active=True).values(
        'id', 'name', 'sort_order'
    )
    return JsonResponse({'groups': list(groups)})


@login_required
@ensure_tenant
@require_POST
def item_group_create_api(request):
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required.'}, status=400)
    if ItemGroup.objects.filter(tenant=request.tenant, name__iexact=name).exists():
        return JsonResponse({'error': 'Item group already exists.'}, status=400)
    group = ItemGroup.objects.create(tenant=request.tenant, name=name)
    return JsonResponse({'id': group.id, 'name': group.name})


# ── Product (Item) API ───────────────────────────────────────────────────────

@login_required
@ensure_tenant
def inventory_items_api(request):
    """List all inventory products with aggregated inventory data."""
    show = request.GET.get('show', 'active')
    search = request.GET.get('search', '').strip()
    group_id = request.GET.get('group', '')

    qs = Product.objects.filter(tenant=request.tenant)

    if show == 'active':
        qs = qs.filter(is_active=True)
    elif show == 'inactive':
        qs = qs.filter(is_active=False)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(description__icontains=search) |
            Q(item_name__icontains=search) |
            Q(sku__icontains=search) |
            Q(qb_item_name__icontains=search) |
            Q(brand__icontains=search)
        )

    if group_id:
        qs = qs.filter(item_group_id=group_id)

    products = []
    for p in qs.select_related('item_group').order_by('description'):
        # Aggregate inventory for this product
        inv_qs = Inventory.objects.filter(tenant=request.tenant, productid=p.product_id)
        on_hand = sum(float(i.unitsonhand or 0) for i in inv_qs)
        allocated = sum(float(i.unitsallocated or 0) for i in inv_qs)
        expected = sum(float(i.pendingunits or 0) for i in inv_qs)

        products.append({
            'id': p.id,
            'product_id': p.product_id,
            'item_name': p.item_name or p.description,
            'description': p.description,
            'sku': p.sku or p.item_number,
            'item_group': p.item_group.name if p.item_group else '',
            'item_group_id': p.item_group_id,
            'qb_item_name': p.qb_item_name,
            'friendly_name': p.friendly_name,
            'size_cull': p.size_cull,
            'tasting_notes': p.tasting_notes,
            'quantity_description': p.quantity_description,
            'country_of_origin': p.country_of_origin,
            'brand': p.brand,
            'inventory_unit_of_measure': p.inventory_unit_of_measure,
            'origin': p.origin,
            'notes': p.notes,
            'list_price': float(p.list_price) if p.list_price else None,
            'wholesale_price': float(p.wholesale_price) if p.wholesale_price else None,
            'is_active': p.is_active,
            'on_hand': on_hand,
            'allocated': allocated,
            'expected': expected,
            'unit_type': p.inventory_unit_of_measure or p.quantity_description or '',
            'habitat_production_method': p.habitat_production_method,
            'species': p.species,
            'department': p.department,
            'upc': p.upc,
        })

    return JsonResponse({'items': products, 'count': len(products)})


@login_required
@ensure_tenant
@require_POST
def inventory_item_create_api(request):
    data = json.loads(request.body)

    # Generate product_id from SKU or auto-increment
    sku = data.get('sku', '').strip()
    if sku:
        pid = sku
    else:
        last = Product.objects.filter(tenant=request.tenant).order_by('-id').first()
        pid = f"ITEM{(last.id + 1) if last else 1:04d}"

    if Product.objects.filter(tenant=request.tenant, product_id=pid).exists():
        return JsonResponse({'error': f'Product ID "{pid}" already exists.'}, status=400)

    group = None
    group_id = data.get('item_group_id')
    if group_id:
        group = ItemGroup.objects.filter(tenant=request.tenant, id=group_id).first()

    product = Product.objects.create(
        tenant=request.tenant,
        product_id=pid,
        item_number=sku,
        description=data.get('description', '').strip(),
        item_group=group,
        qb_item_name=data.get('qb_item_name', '').strip(),
        friendly_name=data.get('friendly_name', '').strip(),
        size_cull=data.get('size_cull', '').strip(),
        sku=sku,
        tasting_notes=data.get('tasting_notes', '').strip(),
        quantity_description=data.get('quantity_description', '').strip(),
        country_of_origin=data.get('country_of_origin', '').strip(),
        brand=data.get('brand', '').strip(),
        inventory_unit_of_measure=data.get('inventory_unit_of_measure', '').strip(),
        origin=data.get('country_of_origin', '').strip(),
        list_price=data.get('list_price') or None,
        wholesale_price=data.get('wholesale_price') or None,
        habitat_production_method=data.get('habitat_production_method', '').strip(),
        species=data.get('species', '').strip(),
        department=data.get('department', '').strip(),
        upc=data.get('upc', '').strip(),
        is_active=True,
    )
    # Auto-generate item name
    product.item_name = product.generate_item_name()
    product.save(update_fields=['item_name'])

    return JsonResponse({'id': product.id, 'product_id': product.product_id, 'item_name': product.item_name})


@login_required
@ensure_tenant
@require_POST
def inventory_item_update_api(request, product_id):
    product = Product.objects.filter(tenant=request.tenant, id=product_id).first()
    if not product:
        return JsonResponse({'error': 'Item not found.'}, status=404)

    data = json.loads(request.body)

    group_id = data.get('item_group_id')
    if group_id:
        product.item_group = ItemGroup.objects.filter(tenant=request.tenant, id=group_id).first()
    elif group_id == '' or group_id is None:
        product.item_group = None

    product.description = data.get('description', product.description).strip()
    product.qb_item_name = data.get('qb_item_name', product.qb_item_name).strip()
    product.friendly_name = data.get('friendly_name', product.friendly_name).strip()
    product.size_cull = data.get('size_cull', product.size_cull).strip()
    product.tasting_notes = data.get('tasting_notes', product.tasting_notes).strip()
    product.quantity_description = data.get('quantity_description', product.quantity_description).strip()
    product.country_of_origin = data.get('country_of_origin', product.country_of_origin).strip()
    product.brand = data.get('brand', product.brand).strip()
    product.inventory_unit_of_measure = data.get('inventory_unit_of_measure', product.inventory_unit_of_measure).strip()
    product.origin = data.get('country_of_origin', product.origin).strip()
    if 'list_price' in data:
        product.list_price = data['list_price'] or None
    if 'wholesale_price' in data:
        product.wholesale_price = data['wholesale_price'] or None

    # New detail fields
    for field in ['habitat_production_method', 'species', 'department', 'upc',
                  'selling_unit_of_measure', 'selling_weight', 'selling_volume',
                  'selling_piece_count', 'inventory_conversion',
                  'buying_unit_of_measure', 'buying_weight', 'buying_volume',
                  'buying_piece_count']:
        if field in data:
            setattr(product, field, (data[field] or '').strip() if isinstance(data[field], str) else data[field] or '')

    if 'profit_margin_target' in data:
        product.profit_margin_target = data['profit_margin_target'] or None

    new_sku = data.get('sku', '').strip()
    if new_sku:
        product.sku = new_sku
        product.item_number = new_sku

    product.item_name = product.generate_item_name()
    product.save()

    return JsonResponse({'ok': True, 'item_name': product.item_name})


@login_required
@ensure_tenant
@require_POST
def inventory_item_delete_api(request, product_id):
    product = Product.objects.filter(tenant=request.tenant, id=product_id).first()
    if not product:
        return JsonResponse({'error': 'Item not found.'}, status=404)
    product.delete()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
@require_POST
def inventory_item_toggle_active_api(request, product_id):
    product = Product.objects.filter(tenant=request.tenant, id=product_id).first()
    if not product:
        return JsonResponse({'error': 'Item not found.'}, status=404)
    product.is_active = not product.is_active
    product.save(update_fields=['is_active'])
    return JsonResponse({'ok': True, 'is_active': product.is_active})


@login_required
@ensure_tenant
def inventory_export_api(request):
    """Export inventory items as CSV."""
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="item_library.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Item Name', 'SKU', 'Item Group', 'Description', 'Brand',
        'Country of Origin', 'Size/Cull', 'Quantity Description',
        'Unit of Measure', 'List Price', 'Wholesale Price', 'Active'
    ])

    products = Product.objects.filter(tenant=request.tenant).select_related('item_group').order_by('description')
    for p in products:
        writer.writerow([
            p.item_name or p.description,
            p.sku or p.item_number,
            p.item_group.name if p.item_group else '',
            p.description,
            p.brand,
            p.country_of_origin or p.origin,
            p.size_cull,
            p.quantity_description,
            p.inventory_unit_of_measure,
            p.list_price or '',
            p.wholesale_price or '',
            'Yes' if p.is_active else 'No',
        ])

    return response


@login_required
@ensure_tenant
def inventory_item_lots_api(request, product_id):
    """Return lot-level inventory data for a product (like BlueTrace lot tracking)."""
    product = Product.objects.filter(tenant=request.tenant, id=product_id).first()
    if not product:
        return JsonResponse({'error': 'Item not found.'}, status=404)

    inv_records = Inventory.objects.filter(
        tenant=request.tenant, productid=product.product_id
    ).order_by('-receivedate')

    lots = []
    total_on_hand = 0
    total_allocated = 0
    total_expected = 0

    for inv in inv_records:
        on_hand = float(inv.unitsonhand or 0)
        total_on_hand += on_hand
        total_allocated += float(inv.unitsallocated or 0)
        total_expected += float(inv.pendingunits or 0)

        # Determine status
        if on_hand <= 0 and float(inv.unitsout or 0) > 0:
            status = 'Sold Out'
        elif float(inv.unitsstored or 0) > 0:
            status = 'Processed'
        else:
            status = 'Received'

        lot_id = inv.vendorlot or inv.poid or f"LOT-{inv.id}"

        lots.append({
            'id': inv.id,
            'lot_id': lot_id,
            'status': status,
            'date': inv.receivedate or '',
            'on_hand': on_hand,
            'unit_type': inv.unittype or product.inventory_unit_of_measure or product.quantity_description or '',
            'vendor': inv.vendorid,
            'cost': float(inv.actualcost) if inv.actualcost else None,
        })

    return JsonResponse({
        'lots': lots,
        'on_hand': total_on_hand,
        'allocated': total_allocated,
        'expected': total_expected,
    })


# =============================================================================
# SHELF LIFE & EXPIRY MANAGEMENT
# =============================================================================

@login_required
def inventory_expiry_alerts_api(request):
    """Return inventory lots approaching expiry or already expired.

    Uses receivedate + shelflife (days) to calculate expiry date.
    Returns lots in 3 buckets: expired, expiring_soon (<=3 days), expiring (<=7 days).
    """
    if not request.tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    set_current_tenant(request.tenant)

    from datetime import datetime, timedelta

    today = datetime.now().date()

    # Only lots with both a receive date and shelf life set, and stock on hand
    lots = Inventory.objects.filter(
        tenant=request.tenant,
        shelflife__isnull=False,
        unitsonhand__gt=0,
    ).exclude(receivedate='').exclude(receivedate__isnull=True)

    expired = []
    expiring_soon = []  # <=3 days
    expiring = []       # 4-7 days

    for inv in lots:
        try:
            if '-' in (inv.receivedate or ''):
                rd = datetime.strptime(inv.receivedate, '%Y-%m-%d').date()
            elif '/' in (inv.receivedate or ''):
                rd = datetime.strptime(inv.receivedate, '%m/%d/%Y').date()
            else:
                continue
        except (ValueError, TypeError):
            continue

        shelf_days = int(inv.shelflife or 0)
        if shelf_days <= 0:
            continue

        expiry_date = rd + timedelta(days=shelf_days)
        days_remaining = (expiry_date - today).days

        product = None
        if inv.productid:
            product = Product.objects.filter(tenant=request.tenant, product_id=inv.productid).first()

        lot_data = {
            'id': inv.id,
            'trace_lot': inv.vendorlot or f"BT-{inv.id}",
            'item_name': product.item_name if product else inv.desc or inv.productid or '',
            'on_hand': float(inv.unitsonhand or 0),
            'unit_type': inv.unittype or '',
            'receive_date': inv.receivedate,
            'shelf_life_days': shelf_days,
            'expiry_date': expiry_date.strftime('%Y-%m-%d'),
            'days_remaining': days_remaining,
            'location': inv.location or '',
            'vendor': inv.vendorid or '',
        }

        if days_remaining < 0:
            lot_data['status'] = 'expired'
            expired.append(lot_data)
        elif days_remaining <= 3:
            lot_data['status'] = 'critical'
            expiring_soon.append(lot_data)
        elif days_remaining <= 7:
            lot_data['status'] = 'warning'
            expiring.append(lot_data)

    # Sort by urgency
    expired.sort(key=lambda x: x['days_remaining'])
    expiring_soon.sort(key=lambda x: x['days_remaining'])
    expiring.sort(key=lambda x: x['days_remaining'])

    return JsonResponse({
        'expired': expired,
        'expiring_soon': expiring_soon,
        'expiring': expiring,
        'summary': {
            'expired_count': len(expired),
            'expired_value': sum(lot.get('on_hand', 0) for lot in expired),
            'critical_count': len(expiring_soon),
            'warning_count': len(expiring),
            'total_at_risk': len(expired) + len(expiring_soon) + len(expiring),
        }
    })
