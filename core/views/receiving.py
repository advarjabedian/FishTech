from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import Inventory, Product, Vendor, set_current_tenant
import json
import uuid
from datetime import datetime
from decimal import Decimal

import logging
logger = logging.getLogger(__name__)


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
def receiving_page(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/receiving.html')


# ── API views ────────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def receiving_list_api(request):
    """List received lots with filtering."""
    search = request.GET.get('search', '').strip()
    vendor_filter = request.GET.get('vendor', '').strip()
    vendor_type_filter = request.GET.get('vendor_type', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    qs = Inventory.objects.filter(tenant=request.tenant)

    # Only show received lots (have a receive date)
    qs = qs.exclude(receivedate='').exclude(receivedate__isnull=True)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(vendorlot__icontains=search) |
            Q(desc__icontains=search) |
            Q(productid__icontains=search) |
            Q(vendorid__icontains=search) |
            Q(poid__icontains=search) |
            Q(location__icontains=search)
        )

    if vendor_filter:
        qs = qs.filter(vendorid__icontains=vendor_filter)

    if vendor_type_filter:
        qs = qs.filter(vendor_type=vendor_type_filter)

    if date_from:
        qs = qs.filter(receivedate__gte=date_from)
    if date_to:
        qs = qs.filter(receivedate__lte=date_to)

    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    total = qs.count()
    offset = (page - 1) * page_size

    lots = []
    for inv in qs.order_by('-receivedate', '-id')[offset:offset + page_size]:
        # Generate trace lot code
        trace_lot = inv.vendorlot or inv.poid or f"BT-{inv.id}"

        # Look up product for item name
        product = None
        if inv.productid:
            product = Product.objects.filter(tenant=request.tenant, product_id=inv.productid).first()
        item_name = product.item_name if product else inv.desc or inv.productid or ''

        on_hand = float(inv.unitsonhand or 0)
        initial_qty = float(inv.unitsin or inv.unitsonhand or 0)
        unit_type = inv.unittype or (product.inventory_unit_of_measure if product else '') or ''

        # Calculate lot age
        lot_age = ''
        if inv.receivedate:
            try:
                rd = datetime.strptime(inv.receivedate, '%Y-%m-%d').date() if '-' in (inv.receivedate or '') else None
                if not rd and '/' in (inv.receivedate or ''):
                    rd = datetime.strptime(inv.receivedate, '%m/%d/%Y').date()
                if rd:
                    days = (datetime.now().date() - rd).days
                    lot_age = f"{days} Days" if days != 1 else "1 Day"
            except (ValueError, TypeError):
                pass

        lots.append({
            'id': inv.id,
            'trace_lot': trace_lot,
            'item_name': item_name,
            'product_id': inv.productid or '',
            'location': inv.location or '',
            'receive_date': inv.receivedate or '',
            'receive_time': inv.receive_time or '',
            'purchase_order': inv.poid or '',
            'vendor': inv.vendorid or '',
            'vendor_type': inv.vendor_type or '',
            'cost': float(inv.actualcost) if inv.actualcost else None,
            'on_hand': on_hand,
            'initial_qty': initial_qty,
            'unit_type': unit_type,
            'lot_age': lot_age,
            'origin': inv.origin or '',
            'vendor_lot': inv.vendorlot or '',
        })

    return JsonResponse({
        'lots': lots,
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@login_required
@ensure_tenant
def receiving_lot_detail_api(request, lot_id):
    """Get full detail for a single received lot."""
    inv = get_object_or_404(Inventory, tenant=request.tenant, id=lot_id)

    product = None
    if inv.productid:
        product = Product.objects.filter(tenant=request.tenant, product_id=inv.productid).first()
    item_name = product.item_name if product else inv.desc or inv.productid or ''
    unit_type = inv.unittype or (product.inventory_unit_of_measure if product else '') or ''

    # Lot age
    lot_age = ''
    if inv.receivedate:
        try:
            rd = datetime.strptime(inv.receivedate, '%Y-%m-%d').date() if '-' in (inv.receivedate or '') else None
            if rd:
                days = (datetime.now().date() - rd).days
                lot_age = f"{days}"
        except (ValueError, TypeError):
            pass

    # Activity: look for processing batches that used this lot
    from core.models import ProcessBatchSource
    activities = []

    # Receive activity
    activities.append({
        'type': 'Receive',
        'order': inv.poid or '',
        'customer_vendor': inv.vendorid or '',
        'date': inv.receivedate or '',
        'quantity': f"{float(inv.unitsin or inv.unitsonhand or 0)} {unit_type}",
    })

    # Process activities
    for src in ProcessBatchSource.objects.filter(inventory=inv).select_related('batch'):
        activities.append({
            'type': src.batch.get_process_type_display(),
            'order': src.batch.batch_number,
            'customer_vendor': '',
            'date': src.batch.started_at.strftime('%d %b %Y') if src.batch.started_at else '',
            'quantity': f"{float(src.quantity)} {src.unit_type}",
        })

    # Vendor info
    vendor_info = {}
    if inv.vendorid:
        vendor = Vendor.objects.filter(tenant=request.tenant, name__icontains=inv.vendorid).first()
        if vendor:
            vendor_info = {
                'name': vendor.name,
                'type': vendor.vendor_type,
                'cert': vendor.cert,
                'address': vendor.full_mailing_address,
            }

    return JsonResponse({
        'id': inv.id,
        'trace_lot': inv.vendorlot or inv.poid or f"BT-{inv.id}",
        'item_name': item_name,
        'product_id': inv.productid or '',
        'initial_qty': float(inv.unitsin or inv.unitsonhand or 0),
        'on_hand': float(inv.unitsonhand or 0),
        'unit_type': unit_type,
        'lot_age': lot_age,
        'location': inv.location or '',
        'receive_date': inv.receivedate or '',
        'receive_time': inv.receive_time or '',
        'vendor': inv.vendorid or '',
        'vendor_type': inv.vendor_type or '',
        'vendor_info': vendor_info,
        'vendor_lot': inv.vendorlot or '',
        'cost': float(inv.actualcost) if inv.actualcost else None,
        'origin': inv.origin or '',
        'activities': activities,
    })


@login_required
@ensure_tenant
@require_POST
def receiving_create_api(request):
    """Create a new received lot."""
    data = json.loads(request.body)

    product_id = data.get('product_id', '').strip()
    if not product_id:
        return JsonResponse({'error': 'Product is required.'}, status=400)

    qty = data.get('quantity')
    if not qty or float(qty) <= 0:
        return JsonResponse({'error': 'Quantity must be greater than 0.'}, status=400)

    qty = Decimal(str(qty))

    # Look up product
    product = Product.objects.filter(tenant=request.tenant, product_id=product_id).first()

    # Generate trace lot code
    now = datetime.now()
    trace_lot = f"BT-{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:4].upper()}"

    unit_type = data.get('unit_type', '').strip()
    if not unit_type and product:
        unit_type = product.inventory_unit_of_measure or product.quantity_description or ''

    inv = Inventory.objects.create(
        tenant=request.tenant,
        productid=product_id,
        desc=product.item_name if product else data.get('description', '').strip(),
        vendorid=data.get('vendor', '').strip(),
        vendorlot=trace_lot,
        receivedate=data.get('receive_date', now.strftime('%Y-%m-%d')),
        receive_time=data.get('receive_time', now.strftime('%I:%M %p').lstrip('0').lower()),
        location=data.get('location', '').strip(),
        vendor_type=data.get('vendor_type', '').strip(),
        actualcost=Decimal(str(data['cost'])) if data.get('cost') else None,
        unittype=unit_type,
        unitsonhand=qty,
        unitsavailable=qty,
        unitsin=qty,
        origin=data.get('origin', '').strip(),
        poid=data.get('purchase_order', '').strip(),
    )

    return JsonResponse({
        'id': inv.id,
        'trace_lot': trace_lot,
    })


@login_required
@ensure_tenant
@require_POST
def receiving_update_api(request, lot_id):
    """Update a received lot."""
    inv = get_object_or_404(Inventory, tenant=request.tenant, id=lot_id)
    data = json.loads(request.body)

    if 'location' in data:
        inv.location = data['location'].strip()
    if 'vendor' in data:
        inv.vendorid = data['vendor'].strip()
    if 'vendor_type' in data:
        inv.vendor_type = data['vendor_type'].strip()
    if 'cost' in data:
        inv.actualcost = Decimal(str(data['cost'])) if data['cost'] else None
    if 'receive_date' in data:
        inv.receivedate = data['receive_date'].strip()
    if 'receive_time' in data:
        inv.receive_time = data['receive_time'].strip()
    if 'origin' in data:
        inv.origin = data['origin'].strip()
    if 'purchase_order' in data:
        inv.poid = data['purchase_order'].strip()

    # Allow adjusting quantity
    if 'quantity' in data:
        new_qty = Decimal(str(data['quantity']))
        inv.unitsonhand = new_qty
        inv.unitsavailable = new_qty

    inv.save()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
def receiving_vendors_api(request):
    """Return vendor list for dropdowns."""
    vendors = Vendor.objects.filter(tenant=request.tenant, is_active=True).values(
        'id', 'name', 'vendor_type'
    ).order_by('name')
    return JsonResponse({'vendors': list(vendors)})
