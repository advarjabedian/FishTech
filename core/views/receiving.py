from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import Inventory, Product, Vendor, PurchaseOrder, PurchaseOrderItem, set_current_tenant
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
            'variance_flagged': inv.variance_flagged,
            'quantity_variance': float(inv.quantity_variance) if inv.quantity_variance else None,
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
        # Variance data
        'purchase_order_id': inv.purchase_order_id,
        'po_item_id': inv.po_item_id,
        'expected_weight': float(inv.expected_weight) if inv.expected_weight else None,
        'weight_variance': float(inv.weight_variance) if inv.weight_variance else None,
        'quantity_variance': float(inv.quantity_variance) if inv.quantity_variance else None,
        'variance_flagged': inv.variance_flagged,
        'weightin': float(inv.weightin) if inv.weightin else None,
        'billedweight': float(inv.billedweight) if inv.billedweight else None,
    })


VARIANCE_THRESHOLD_PCT = Decimal('5')  # Flag if variance exceeds 5%


@login_required
@ensure_tenant
@require_POST
def receiving_create_api(request):
    """Create a new received lot, optionally linked to a PO line item."""
    data = json.loads(request.body)

    product_id = data.get('product_id', '').strip()
    if not product_id:
        return JsonResponse({'error': 'Product is required.'}, status=400)

    qty = data.get('quantity')
    if not qty or float(qty) <= 0:
        return JsonResponse({'error': 'Quantity must be greater than 0.'}, status=400)

    qty = Decimal(str(qty))
    weight = Decimal(str(data['weight'])) if data.get('weight') else None

    # Look up product
    product = Product.objects.filter(tenant=request.tenant, product_id=product_id).first()

    # Generate trace lot code
    now = datetime.now()
    trace_lot = f"BT-{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:4].upper()}"

    unit_type = data.get('unit_type', '').strip()
    if not unit_type and product:
        unit_type = product.inventory_unit_of_measure or product.quantity_description or ''

    # PO linking
    po = None
    po_item = None
    po_item_id = data.get('po_item_id')
    po_number = data.get('purchase_order', '').strip()

    if po_item_id:
        po_item = PurchaseOrderItem.objects.filter(
            id=po_item_id, purchase_order__tenant=request.tenant
        ).select_related('purchase_order').first()
        if po_item:
            po = po_item.purchase_order
            po_number = po.po_number
            # Auto-fill from PO item if not provided
            if not product_id and po_item.product:
                product_id = po_item.product.product_id
            if not unit_type:
                unit_type = po_item.unit_type
    elif po_number:
        po = PurchaseOrder.objects.filter(tenant=request.tenant, po_number=po_number).first()

    # Calculate variance if receiving against a PO item
    expected_qty = Decimal(str(po_item.quantity)) if po_item and po_item.quantity else None
    expected_wt = None  # PO items track quantity, weight comes from billed weight
    qty_variance = None
    wt_variance = None
    flagged = False

    if expected_qty is not None:
        qty_variance = qty - expected_qty
        variance_pct = abs(qty_variance) / expected_qty * 100 if expected_qty else 0
        flagged = variance_pct > VARIANCE_THRESHOLD_PCT

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
        weightin=weight,
        availableweight=weight,
        origin=data.get('origin', '').strip(),
        poid=po_number,
        purchase_order=po,
        po_item=po_item,
        expected_weight=expected_wt,
        weight_variance=wt_variance,
        quantity_variance=qty_variance,
        variance_flagged=flagged,
    )

    # Update PO item received quantity
    if po_item:
        po_item.received_quantity = (po_item.received_quantity or 0) + qty
        if weight:
            po_item.received_weight = (po_item.received_weight or 0) + weight
        po_item.save()

    # Auto-update PO receive_status
    if po:
        _update_po_receive_status(po)

    response = {
        'id': inv.id,
        'trace_lot': trace_lot,
    }
    if flagged:
        response['variance_warning'] = (
            f"Quantity variance of {float(qty_variance):+.2f} {unit_type} "
            f"(expected {float(expected_qty)}, received {float(qty)})"
        )

    return JsonResponse(response)


def _update_po_receive_status(po):
    """Update PO receive_status based on how much has been received across all items."""
    items = po.items.filter(item_type='item')
    if not items.exists():
        return

    all_received = all(item.is_fully_received for item in items)
    any_received = any((item.received_quantity or 0) > 0 for item in items)

    if all_received:
        po.receive_status = 'received'
    elif any_received:
        po.receive_status = 'partial'
    else:
        po.receive_status = 'not_received'
    po.save(update_fields=['receive_status'])


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


@login_required
@ensure_tenant
def receiving_open_pos_api(request):
    """Return open POs with their unreceived line items for the receive-against-PO workflow."""
    vendor = request.GET.get('vendor', '').strip()

    qs = PurchaseOrder.objects.filter(
        tenant=request.tenant,
        receive_status__in=['not_received', 'partial'],
        order_status__in=['open', 'draft'],
    ).select_related('vendor').prefetch_related('items').order_by('-order_date')

    if vendor:
        qs = qs.filter(vendor_name__icontains=vendor)

    pos = []
    for po in qs[:50]:
        items = []
        for item in po.items.filter(item_type='item'):
            remaining = float(item.remaining_quantity)
            if remaining <= 0:
                continue
            items.append({
                'id': item.id,
                'description': item.description,
                'product_id': item.product.product_id if item.product else '',
                'ordered_qty': float(item.quantity or 0),
                'received_qty': float(item.received_quantity or 0),
                'remaining_qty': remaining,
                'unit_type': item.unit_type,
                'unit_price': float(item.unit_price or 0),
            })
        if items:
            pos.append({
                'id': po.id,
                'po_number': po.po_number,
                'vendor_name': po.vendor_name,
                'expected_date': po.expected_date.strftime('%Y-%m-%d') if po.expected_date else '',
                'receive_status': po.receive_status,
                'items': items,
            })

    return JsonResponse({'purchase_orders': pos})
