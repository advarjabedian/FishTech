from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import PurchaseOrder, PurchaseOrderItem, Vendor, Product, set_current_tenant
import json
from datetime import date
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
def purchases_page(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/purchases.html')


@login_required
@ensure_tenant
def purchase_detail_page(request, po_id):
    if not request.tenant:
        return redirect('login')
    po = get_object_or_404(PurchaseOrder, tenant=request.tenant, id=po_id)
    return render(request, 'core/purchase_detail.html', {'po': po})


# ── API views ────────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def purchases_list_api(request):
    """List purchase orders with filtering."""
    qs = PurchaseOrder.objects.filter(tenant=request.tenant)

    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(po_number__icontains=search) |
            Q(vendor_name__icontains=search) |
            Q(qb_po_number__icontains=search) |
            Q(buyer__icontains=search)
        )

    # Filters
    vendor = request.GET.get('vendor', '').strip()
    if vendor:
        qs = qs.filter(vendor_name__icontains=vendor)

    vendor_type = request.GET.get('vendor_type', '').strip()
    if vendor_type:
        qs = qs.filter(vendor__vendor_type=vendor_type)

    buyer = request.GET.get('buyer', '').strip()
    if buyer:
        qs = qs.filter(buyer__icontains=buyer)

    order_status = request.GET.get('order_status', '').strip()
    if order_status:
        qs = qs.filter(order_status=order_status)

    receive_status = request.GET.get('receive_status', '').strip()
    if receive_status:
        qs = qs.filter(receive_status=receive_status)

    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        qs = qs.filter(order_date__gte=date_from)

    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        qs = qs.filter(order_date__lte=date_to)

    expected_from = request.GET.get('expected_from', '').strip()
    if expected_from:
        qs = qs.filter(expected_date__gte=expected_from)

    expected_to = request.GET.get('expected_to', '').strip()
    if expected_to:
        qs = qs.filter(expected_date__lte=expected_to)

    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    total = qs.count()
    offset = (page - 1) * page_size

    orders = []
    for po in qs.select_related('vendor').prefetch_related('items')[offset:offset + page_size]:
        total_amount = sum(float(item.amount or 0) for item in po.items.all())
        expected = sum(float(item.quantity or 0) for item in po.items.filter(item_type='item'))
        vendor_type = po.vendor.vendor_type if po.vendor else ''

        orders.append({
            'id': po.id,
            'po_number': po.po_number,
            'order_status': po.order_status,
            'order_status_display': po.get_order_status_display(),
            'receive_status': po.receive_status,
            'receive_status_display': po.get_receive_status_display(),
            'qb_po_number': po.qb_po_number,
            'vendor_name': po.vendor_name,
            'vendor_type': vendor_type,
            'total': total_amount,
            'expected': expected,
            'order_date': po.order_date.strftime('%d %b %Y') if po.order_date else '',
            'expected_date': po.expected_date.strftime('%d %b %Y') if po.expected_date else '',
            'buyer': po.buyer,
        })

    return JsonResponse({
        'orders': orders,
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@login_required
@ensure_tenant
@require_POST
def purchase_create_api(request):
    """Create a new purchase order."""
    data = json.loads(request.body)

    vendor_name = data.get('vendor_name', '').strip()
    if not vendor_name:
        return JsonResponse({'error': 'Vendor is required.'}, status=400)

    # Auto-generate PO number
    last = PurchaseOrder.objects.filter(tenant=request.tenant).order_by('-id').first()
    next_num = 10001
    if last:
        try:
            next_num = int(last.po_number) + 1
        except (ValueError, TypeError):
            next_num = last.id + 10001

    vendor = Vendor.objects.filter(tenant=request.tenant, name__iexact=vendor_name).first()

    po = PurchaseOrder.objects.create(
        tenant=request.tenant,
        po_number=str(next_num),
        vendor=vendor,
        vendor_name=vendor_name,
        order_status='draft',
        buyer=data.get('buyer', '').strip(),
        vendor_invoice_number=data.get('vendor_invoice_number', '').strip(),
        order_date=data.get('order_date') or date.today(),
        expected_date=data.get('expected_date') or None,
        notes=data.get('notes', '').strip(),
        created_by=request.user,
    )

    return JsonResponse({'id': po.id, 'po_number': po.po_number})


@login_required
@ensure_tenant
@require_POST
def purchase_update_api(request, po_id):
    """Update purchase order header fields."""
    po = get_object_or_404(PurchaseOrder, tenant=request.tenant, id=po_id)
    data = json.loads(request.body)

    for field in ['buyer', 'vendor_invoice_number', 'qb_po_number', 'notes', 'order_status', 'receive_status']:
        if field in data:
            setattr(po, field, (data[field] or '').strip() if isinstance(data[field], str) else data[field])

    if 'order_date' in data:
        po.order_date = data['order_date'] or None
    if 'expected_date' in data:
        po.expected_date = data['expected_date'] or None

    po.save()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
@require_POST
def purchase_delete_api(request, po_id):
    po = get_object_or_404(PurchaseOrder, tenant=request.tenant, id=po_id)
    po.delete()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
def purchase_detail_api(request, po_id):
    """Get full PO detail with line items."""
    po = get_object_or_404(PurchaseOrder, tenant=request.tenant, id=po_id)

    items = []
    item_subtotal = 0
    fee_subtotal = 0
    for item in po.items.all():
        amt = float(item.amount or 0)
        if item.item_type == 'fee':
            fee_subtotal += amt
        else:
            item_subtotal += amt
        items.append({
            'id': item.id,
            'item_type': item.item_type,
            'product_id': item.product.product_id if item.product else '',
            'description': item.description,
            'notes': item.notes,
            'quantity': float(item.quantity) if item.quantity else None,
            'unit_type': item.unit_type,
            'unit_price': float(item.unit_price) if item.unit_price else None,
            'amount': amt,
        })

    vendor_info = {}
    if po.vendor:
        v = po.vendor
        vendor_info = {
            'name': v.contact_name or v.name,
            'phone': v.phone,
            'email': v.email,
        }

    return JsonResponse({
        'id': po.id,
        'po_number': po.po_number,
        'vendor_name': po.vendor_name,
        'order_status': po.order_status,
        'receive_status': po.receive_status,
        'qb_po_number': po.qb_po_number,
        'buyer': po.buyer,
        'vendor_invoice_number': po.vendor_invoice_number,
        'order_date': po.order_date.isoformat() if po.order_date else '',
        'expected_date': po.expected_date.isoformat() if po.expected_date else '',
        'notes': po.notes,
        'items': items,
        'item_subtotal': item_subtotal,
        'fee_subtotal': fee_subtotal,
        'total': item_subtotal + fee_subtotal,
        'vendor_info': vendor_info,
    })


@login_required
@ensure_tenant
@require_POST
def purchase_item_add_api(request, po_id):
    """Add a line item to a PO."""
    po = get_object_or_404(PurchaseOrder, tenant=request.tenant, id=po_id)
    data = json.loads(request.body)

    product = None
    product_id = data.get('product_id', '').strip()
    if product_id:
        product = Product.objects.filter(tenant=request.tenant, product_id=product_id).first()

    qty = Decimal(str(data.get('quantity', 0))) if data.get('quantity') else None
    price = Decimal(str(data.get('unit_price', 0))) if data.get('unit_price') else None
    amount = None
    if data.get('amount'):
        amount = Decimal(str(data['amount']))
    elif qty and price:
        amount = qty * price

    item = PurchaseOrderItem.objects.create(
        tenant=request.tenant,
        purchase_order=po,
        item_type=data.get('item_type', 'item'),
        product=product,
        description=data.get('description', product.item_name if product else '').strip(),
        notes=data.get('notes', '').strip(),
        quantity=qty,
        unit_type=data.get('unit_type', '').strip(),
        unit_price=price,
        amount=amount,
    )

    return JsonResponse({'id': item.id})


@login_required
@ensure_tenant
@require_POST
def purchase_item_delete_api(request, po_id, item_id):
    item = get_object_or_404(PurchaseOrderItem, tenant=request.tenant, purchase_order_id=po_id, id=item_id)
    item.delete()
    return JsonResponse({'ok': True})
