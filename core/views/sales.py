from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import SalesOrder, SalesOrderItem, Customer, Product, set_current_tenant
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
def sales_orders_page(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/sales_orders.html')


@login_required
@ensure_tenant
def sales_order_detail_page(request, so_id):
    if not request.tenant:
        return redirect('login')
    so = get_object_or_404(SalesOrder, tenant=request.tenant, id=so_id)
    return render(request, 'core/sales_order_detail.html', {'so': so})


# ── API views ────────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def sales_orders_list_api(request):
    qs = SalesOrder.objects.filter(tenant=request.tenant)

    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(qb_invoice_number__icontains=search) |
            Q(sales_rep__icontains=search)
        )

    for param, field in [
        ('order_status', 'order_status'), ('packed_status', 'packed_status'),
        ('customer', 'customer_name__icontains'), ('sales_rep', 'sales_rep__icontains'),
        ('shipper', 'shipper__icontains'), ('shipping_route', 'shipping_route__icontains'),
    ]:
        val = request.GET.get(param, '').strip()
        if val:
            qs = qs.filter(**{field: val})

    date_from = request.GET.get('date_from', '').strip()
    if date_from:
        qs = qs.filter(order_date__gte=date_from)
    date_to = request.GET.get('date_to', '').strip()
    if date_to:
        qs = qs.filter(order_date__lte=date_to)

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 100))
    total = qs.count()
    offset = (page - 1) * page_size

    orders = []
    for so in qs.select_related('customer').prefetch_related('items')[offset:offset + page_size]:
        total_amount = sum(float(item.amount or 0) for item in so.items.all())
        orders.append({
            'id': so.id,
            'order_number': so.order_number,
            'order_status': so.order_status,
            'order_status_display': so.get_order_status_display(),
            'packed_status': so.packed_status,
            'packed_status_display': so.get_packed_status_display(),
            'qb_invoice_number': so.qb_invoice_number,
            'customer_name': so.customer_name,
            'total': total_amount,
            'order_date': so.order_date.strftime('%d %b %Y') if so.order_date else '',
            'sales_rep': so.sales_rep,
            'shipping_route': so.shipping_route,
        })

    return JsonResponse({'orders': orders, 'total': total, 'page': page, 'page_size': page_size})


@login_required
@ensure_tenant
@require_POST
def sales_order_create_api(request):
    data = json.loads(request.body)
    customer_name = data.get('customer_name', '').strip()
    if not customer_name:
        return JsonResponse({'error': 'Customer is required.'}, status=400)

    last = SalesOrder.objects.filter(tenant=request.tenant).order_by('-id').first()
    next_num = 10001
    if last:
        try:
            next_num = int(last.order_number) + 1
        except (ValueError, TypeError):
            next_num = last.id + 10001

    customer = Customer.objects.filter(tenant=request.tenant, name__iexact=customer_name).first()

    so = SalesOrder.objects.create(
        tenant=request.tenant,
        order_number=str(next_num),
        customer=customer,
        customer_name=customer_name,
        order_status='draft',
        order_date=date.today(),
        created_by=request.user,
    )
    return JsonResponse({'id': so.id, 'order_number': so.order_number})


@login_required
@ensure_tenant
@require_POST
def sales_order_update_api(request, so_id):
    so = get_object_or_404(SalesOrder, tenant=request.tenant, id=so_id)
    data = json.loads(request.body)

    for field in ['sales_rep', 'po_number', 'air_bill_number', 'qb_invoice_number',
                  'notes', 'order_status', 'packed_status', 'shipper', 'shipping_route']:
        if field in data:
            setattr(so, field, (data[field] or '').strip() if isinstance(data[field], str) else data[field])

    for df in ['order_date', 'pack_date', 'delivery_date', 'ship_date']:
        if df in data:
            setattr(so, df, data[df] or None)

    if 'order_weight' in data:
        so.order_weight = Decimal(str(data['order_weight'])) if data['order_weight'] else None

    so.save()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
@require_POST
def sales_order_delete_api(request, so_id):
    so = get_object_or_404(SalesOrder, tenant=request.tenant, id=so_id)
    so.delete()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
def sales_order_detail_api(request, so_id):
    so = get_object_or_404(SalesOrder, tenant=request.tenant, id=so_id)

    items = []
    item_subtotal = 0
    fee_subtotal = 0
    for item in so.items.all():
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
            'margin': item.margin,
            'amount': amt,
        })

    contact_info = {}
    delivery_address = {}
    mailing_address = {}
    if so.customer:
        c = so.customer
        contact_info = {'name': c.contact_name or c.name, 'phone': c.phone, 'email': c.email}
        delivery_address = {
            'address': c.ship_address or c.address,
            'city': c.ship_city or c.city,
            'state': c.ship_state or c.state,
            'zip': c.ship_zipcode or c.zipcode,
        }
        mailing_address = {
            'address': c.address, 'city': c.city,
            'state': c.state, 'zip': c.zipcode,
        }

    return JsonResponse({
        'id': so.id,
        'order_number': so.order_number,
        'customer_name': so.customer_name,
        'order_status': so.order_status,
        'packed_status': so.packed_status,
        'qb_invoice_number': so.qb_invoice_number,
        'sales_rep': so.sales_rep,
        'po_number': so.po_number,
        'air_bill_number': so.air_bill_number,
        'order_date': so.order_date.isoformat() if so.order_date else '',
        'pack_date': so.pack_date.isoformat() if so.pack_date else '',
        'delivery_date': so.delivery_date.isoformat() if so.delivery_date else '',
        'ship_date': so.ship_date.isoformat() if so.ship_date else '',
        'shipper': so.shipper,
        'shipping_route': so.shipping_route,
        'order_weight': float(so.order_weight) if so.order_weight else None,
        'notes': so.notes,
        'items': items,
        'item_subtotal': item_subtotal,
        'fee_subtotal': fee_subtotal,
        'total': item_subtotal + fee_subtotal,
        'contact_info': contact_info,
        'delivery_address': delivery_address,
        'mailing_address': mailing_address,
    })


@login_required
@ensure_tenant
@require_POST
def sales_order_item_add_api(request, so_id):
    so = get_object_or_404(SalesOrder, tenant=request.tenant, id=so_id)
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

    item = SalesOrderItem.objects.create(
        tenant=request.tenant,
        sales_order=so,
        item_type=data.get('item_type', 'item'),
        product=product,
        description=data.get('description', product.item_name if product else '').strip(),
        notes=data.get('notes', '').strip(),
        quantity=qty,
        unit_type=data.get('unit_type', '').strip(),
        unit_price=price,
        margin=data.get('margin', '').strip() if isinstance(data.get('margin'), str) else '',
        amount=amount,
    )
    return JsonResponse({'id': item.id})


@login_required
@ensure_tenant
@require_POST
def sales_order_item_delete_api(request, so_id, item_id):
    item = get_object_or_404(SalesOrderItem, tenant=request.tenant, sales_order_id=so_id, id=item_id)
    item.delete()
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
def sales_customers_api(request):
    """Return customer list for dropdowns."""
    customers = Customer.objects.filter(tenant=request.tenant).values(
        'id', 'name', 'contact_name', 'phone', 'email'
    ).order_by('name')
    return JsonResponse({'customers': list(customers)})
