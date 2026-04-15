from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from core.models import SalesOrder, SalesOrderItem, Product, set_current_tenant
from datetime import date, timedelta

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
def shipping_hub(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/shipping/shipping_log.html')


@login_required
@ensure_tenant
def shipping_picking(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/shipping/picking.html')


@login_required
@ensure_tenant
def shipping_packing(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/shipping/packing.html')


@login_required
@ensure_tenant
def shipping_loading(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/shipping/loading.html')


# ── API views ────────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def shipping_picking_api(request):
    """Picking list: items grouped by department, filtered by pack date."""
    date_from = request.GET.get('date_from', date.today().isoformat())
    date_to = request.GET.get('date_to', date_from)
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'department')

    from django.db.models import Q
    qs = SalesOrderItem.objects.filter(
        tenant=request.tenant,
        item_type='item',
        sales_order__pack_date__gte=date_from,
        sales_order__pack_date__lte=date_to,
    ).select_related('sales_order', 'product')

    if search:
        qs = qs.filter(Q(description__icontains=search) | Q(sales_order__order_number__icontains=search))

    # Group by department
    departments = {}
    for item in qs:
        dept = ''
        if item.product:
            dept = item.product.department or item.product.item_group.name if item.product.item_group else ''
        if not dept:
            dept = 'Other'
        departments.setdefault(dept, []).append({
            'id': item.id,
            'so_id': item.sales_order.id,
            'item_name': item.description,
            'order_number': item.sales_order.order_number,
            'customer': item.sales_order.customer_name,
            'quantity': float(item.quantity or 0),
            'unit_type': item.unit_type,
        })

    result = []
    for dept in sorted(departments.keys()):
        result.append({'department': dept, 'items': departments[dept]})

    total_items = sum(len(d['items']) for d in result)
    return JsonResponse({'departments': result, 'total_departments': len(result), 'total_items': total_items})


@login_required
@ensure_tenant
def shipping_packing_api(request):
    """Packing list: items grouped by order, filtered by pack date."""
    date_from = request.GET.get('date_from', date.today().isoformat())
    date_to = request.GET.get('date_to', date_from)
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'old_to_new')

    from django.db.models import Q
    qs = SalesOrder.objects.filter(
        tenant=request.tenant,
        pack_date__gte=date_from,
        pack_date__lte=date_to,
    ).prefetch_related('items')

    if search:
        qs = qs.filter(Q(customer_name__icontains=search) | Q(order_number__icontains=search))

    if sort == 'new_to_old':
        qs = qs.order_by('-order_number')
    else:
        qs = qs.order_by('order_number')

    orders = []
    for so in qs:
        items = []
        for item in so.items.filter(item_type='item'):
            items.append({
                'id': item.id,
                'item_name': item.description,
                'notes': item.notes,
                'quantity': float(item.quantity or 0),
                'unit_type': item.unit_type,
                'packed_status': so.packed_status,
                'packed_status_display': so.get_packed_status_display(),
            })
        if items:
            orders.append({
                'id': so.id,
                'order_number': so.order_number,
                'customer': so.customer_name,
                'ship_date': so.ship_date.strftime('%d %b %Y') if so.ship_date else '',
                'items': items,
            })

    total_items = sum(len(o['items']) for o in orders)
    return JsonResponse({'orders': orders, 'total_orders': len(orders), 'total_items': total_items})


@login_required
@ensure_tenant
def shipping_loading_api(request):
    """Loading list: items grouped by order and ship date."""
    date_from = request.GET.get('date_from', date.today().isoformat())
    date_to = request.GET.get('date_to', date_from)
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'old_to_new')

    from django.db.models import Q
    qs = SalesOrder.objects.filter(
        tenant=request.tenant,
        ship_date__gte=date_from,
        ship_date__lte=date_to,
    ).prefetch_related('items')

    if search:
        qs = qs.filter(Q(customer_name__icontains=search) | Q(order_number__icontains=search) | Q(shipper__icontains=search))

    if sort == 'new_to_old':
        qs = qs.order_by('-ship_date', '-order_number')
    else:
        qs = qs.order_by('ship_date', 'order_number')

    # Group by ship date
    date_groups = {}
    for so in qs:
        ship_key = so.ship_date.strftime('%d %b %Y') if so.ship_date else 'No Date'
        date_groups.setdefault(ship_key, [])
        items = []
        for item in so.items.filter(item_type='item'):
            items.append({
                'id': item.id,
                'item_name': item.description,
                'notes': item.notes,
                'quantity': float(item.quantity or 0),
                'unit_type': item.unit_type,
                'packed_status': so.packed_status,
                'packed_status_display': so.get_packed_status_display(),
            })
        if items:
            date_groups[ship_key].append({
                'id': so.id,
                'order_number': so.order_number,
                'customer': so.customer_name,
                'ship_date': ship_key,
                'shipper': so.shipper,
                'items': items,
            })

    result = []
    for dt, orders in date_groups.items():
        result.append({'ship_date': dt, 'orders': orders})

    total_items = sum(len(i) for g in result for o in g['orders'] for i in [o['items']])
    return JsonResponse({'groups': result, 'total_sequences': total_items})


@login_required
@ensure_tenant
def shipping_log_api(request):
    """Shipping log: list of shipped orders."""
    search = request.GET.get('search', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    from django.db.models import Q
    qs = SalesOrder.objects.filter(tenant=request.tenant).exclude(ship_date__isnull=True)

    if search:
        qs = qs.filter(Q(order_number__icontains=search) | Q(customer_name__icontains=search) | Q(shipper__icontains=search))
    if date_from:
        qs = qs.filter(ship_date__gte=date_from)
    if date_to:
        qs = qs.filter(ship_date__lte=date_to)

    page = int(request.GET.get('page', 1))
    page_size = 100
    total = qs.count()
    offset = (page - 1) * page_size

    orders = []
    for so in qs.order_by('-ship_date')[offset:offset + page_size]:
        total_amount = sum(float(i.amount or 0) for i in so.items.all())
        orders.append({
            'id': so.id,
            'order_number': so.order_number,
            'customer': so.customer_name,
            'ship_date': so.ship_date.strftime('%d %b %Y') if so.ship_date else '',
            'shipper': so.shipper,
            'shipping_route': so.shipping_route,
            'packed_status': so.packed_status,
            'packed_status_display': so.get_packed_status_display(),
            'total': total_amount,
        })

    return JsonResponse({'orders': orders, 'total': total, 'page': page})
