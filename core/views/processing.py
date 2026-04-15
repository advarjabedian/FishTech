from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core.models import ProcessBatch, ProcessBatchSource, ProcessBatchOutput, Inventory, Product, set_current_tenant
import json
import uuid
from datetime import datetime

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
def processing_hub(request):
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/processing_hub.html')


@login_required
@ensure_tenant
def processing_new(request):
    """Start a new processing batch — shows lot selection."""
    if not request.tenant:
        return redirect('login')
    process_type = request.GET.get('type', 'fish_cutting')
    valid_types = dict(ProcessBatch.PROCESS_TYPES)
    if process_type not in valid_types:
        process_type = 'fish_cutting'
    return render(request, 'core/processing_new.html', {
        'process_type': process_type,
        'process_type_label': valid_types[process_type],
    })


@login_required
@ensure_tenant
def processing_detail(request, batch_id):
    """View/edit a processing batch."""
    if not request.tenant:
        return redirect('login')
    batch = get_object_or_404(ProcessBatch, tenant=request.tenant, id=batch_id)
    return render(request, 'core/processing_detail.html', {'batch': batch})


# ── API views ────────────────────────────────────────────────────────────────

@login_required
@ensure_tenant
def processing_batches_api(request):
    """List processing batches for the tenant."""
    qs = ProcessBatch.objects.filter(tenant=request.tenant)

    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)

    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(batch_number__icontains=search) |
            Q(notes__icontains=search)
        )

    batches = []
    for b in qs.select_related('created_by').order_by('-started_at')[:100]:
        batches.append({
            'id': b.id,
            'batch_number': b.batch_number,
            'process_type': b.process_type,
            'status': b.status,
            'status_display': b.get_status_display(),
            'started_at': b.started_at.strftime('%d %b %Y %H:%M') if b.started_at else '',
            'completed_at': b.completed_at.strftime('%d %b %Y %H:%M') if b.completed_at else '',
            'created_by': b.created_by.get_full_name() or b.created_by.username if b.created_by else '',
            'notes': b.notes,
            'actual_yield_pct': float(b.actual_yield_pct) if b.actual_yield_pct else None,
            'expected_yield_pct': float(b.expected_yield_pct) if b.expected_yield_pct else None,
            'yield_flagged': b.yield_flagged,
        })

    return JsonResponse({'batches': batches})


@login_required
@ensure_tenant
def processing_source_lots_api(request):
    """Return available inventory lots for source selection."""
    search = request.GET.get('search', '').strip()
    product_id = request.GET.get('product_id', '').strip()

    qs = Inventory.objects.filter(tenant=request.tenant)

    # Only lots with remaining units
    from django.db.models import Q
    qs = qs.filter(Q(unitsonhand__gt=0) | Q(unitsavailable__gt=0))

    if search:
        qs = qs.filter(
            Q(desc__icontains=search) |
            Q(productid__icontains=search) |
            Q(vendorlot__icontains=search) |
            Q(vendorid__icontains=search)
        )

    if product_id:
        qs = qs.filter(productid=product_id)

    lots = []
    for inv in qs.order_by('-receivedate')[:200]:
        # Look up product info
        product = Product.objects.filter(tenant=request.tenant, product_id=inv.productid).first()
        item_name = product.item_name if product else inv.desc or inv.productid

        lot_id = inv.vendorlot or inv.poid or f"LOT-{inv.id}"
        on_hand = float(inv.unitsonhand or 0)
        unit_type = inv.unittype or (product.inventory_unit_of_measure if product else '') or ''

        lots.append({
            'id': inv.id,
            'lot_id': lot_id,
            'item_name': item_name,
            'product_id': inv.productid,
            'description': inv.desc,
            'vendor': inv.vendorid,
            'receive_date': inv.receivedate or '',
            'on_hand': on_hand,
            'unit_type': unit_type,
            'origin': inv.origin,
            'vendor_lot': inv.vendorlot,
        })

    return JsonResponse({'lots': lots})


@login_required
@ensure_tenant
@require_POST
def processing_create_batch_api(request):
    """Create a new processing batch with source lots and outputs."""
    data = json.loads(request.body)

    process_type = data.get('process_type', '')
    valid_types = dict(ProcessBatch.PROCESS_TYPES)
    if process_type not in valid_types:
        return JsonResponse({'error': 'Invalid process type.'}, status=400)

    sources = data.get('sources', [])
    if not sources:
        return JsonResponse({'error': 'At least one source lot is required.'}, status=400)

    outputs = data.get('outputs', [])

    # Generate batch number
    now = datetime.now()
    batch_number = f"PB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    batch = ProcessBatch.objects.create(
        tenant=request.tenant,
        batch_number=batch_number,
        process_type=process_type,
        status='in_progress',
        created_by=request.user,
        notes=data.get('notes', ''),
    )

    # Create source records and deduct from inventory
    from decimal import Decimal
    for src in sources:
        inv = Inventory.objects.filter(tenant=request.tenant, id=src['inventory_id']).first()
        if not inv:
            continue
        qty = Decimal(str(src.get('quantity', 0)))
        ProcessBatchSource.objects.create(
            tenant=request.tenant,
            batch=batch,
            inventory=inv,
            quantity=qty,
            unit_type=src.get('unit_type', inv.unittype or ''),
        )
        # Deduct from source inventory
        inv.unitsonhand = (inv.unitsonhand or Decimal('0')) - qty
        inv.unitsstored = (inv.unitsstored or Decimal('0')) + qty
        inv.save(update_fields=['unitsonhand', 'unitsstored'])

    # Create output records and new inventory lots
    for out in outputs:
        product = None
        product_id_val = out.get('product_id', '')
        if product_id_val:
            product = Product.objects.filter(tenant=request.tenant, product_id=product_id_val).first()

        out_qty = Decimal(str(out.get('quantity', 0)))
        out_unit = out.get('unit_type', '')
        yield_pct = out.get('yield_percent')
        out_lot_id = out.get('lot_id', f"{batch_number}-OUT")

        # Create a new inventory record for the output
        new_inv = Inventory.objects.create(
            tenant=request.tenant,
            productid=product_id_val or (sources[0].get('product_id', '') if sources else ''),
            desc=out.get('description', product.item_name if product else ''),
            vendorlot=out_lot_id,
            unittype=out_unit,
            unitsonhand=out_qty,
            unitsavailable=out_qty,
            unitsin=out_qty,
            receivedate=now.strftime('%Y-%m-%d'),
            packdate=now.strftime('%Y-%m-%d'),
            origin=out.get('origin', ''),
            poid=batch_number,
        )

        ProcessBatchOutput.objects.create(
            tenant=request.tenant,
            batch=batch,
            inventory=new_inv,
            product=product,
            quantity=out_qty,
            unit_type=out_unit,
            lot_id=out_lot_id,
            yield_percent=yield_pct,
        )

    return JsonResponse({
        'id': batch.id,
        'batch_number': batch.batch_number,
    })


@login_required
@ensure_tenant
def processing_batch_sources_api(request, batch_id):
    """Return source lots for a batch."""
    batch = get_object_or_404(ProcessBatch, tenant=request.tenant, id=batch_id)
    sources = []
    for src in batch.sources.select_related('inventory'):
        inv = src.inventory
        product = Product.objects.filter(tenant=request.tenant, product_id=inv.productid).first()
        item_name = product.item_name if product else inv.desc or inv.productid
        lot_id = inv.vendorlot or inv.poid or f"LOT-{inv.id}"
        sources.append({
            'id': src.id,
            'lot_id': lot_id,
            'item_name': item_name,
            'vendor': inv.vendorid,
            'quantity': float(src.quantity),
            'unit_type': src.unit_type,
        })
    return JsonResponse({'sources': sources})


@login_required
@ensure_tenant
@require_POST
def processing_batch_complete_api(request, batch_id):
    batch = get_object_or_404(ProcessBatch, tenant=request.tenant, id=batch_id)
    if batch.status != 'in_progress':
        return JsonResponse({'error': 'Batch is not in progress.'}, status=400)
    batch.status = 'completed'
    batch.completed_at = datetime.now()

    # Calculate yield on completion
    batch.calculate_yield()
    batch.save()

    response = {'ok': True}
    if batch.actual_yield_pct is not None:
        response['yield'] = {
            'actual': float(batch.actual_yield_pct),
            'expected': float(batch.expected_yield_pct) if batch.expected_yield_pct else None,
            'variance': float(batch.yield_variance_pct) if batch.yield_variance_pct else None,
            'flagged': batch.yield_flagged,
            'input_weight': float(batch.total_input_weight),
            'output_weight': float(batch.total_output_weight),
        }
    return JsonResponse(response)


@login_required
@ensure_tenant
@require_POST
def processing_batch_cancel_api(request, batch_id):
    """Cancel a batch and reverse inventory deductions."""
    from decimal import Decimal
    batch = get_object_or_404(ProcessBatch, tenant=request.tenant, id=batch_id)
    if batch.status not in ('draft', 'in_progress'):
        return JsonResponse({'error': 'Cannot cancel a completed batch.'}, status=400)

    # Reverse source deductions
    for src in batch.sources.select_related('inventory'):
        inv = src.inventory
        inv.unitsonhand = (inv.unitsonhand or Decimal('0')) + src.quantity
        inv.unitsstored = max((inv.unitsstored or Decimal('0')) - src.quantity, Decimal('0'))
        inv.save(update_fields=['unitsonhand', 'unitsstored'])

    # Remove output inventory records
    for out in batch.outputs.select_related('inventory'):
        if out.inventory:
            out.inventory.delete()

    batch.status = 'cancelled'
    batch.save(update_fields=['status'])
    return JsonResponse({'ok': True})


@login_required
@ensure_tenant
def processing_batch_outputs_api(request, batch_id):
    """Return output lots for a batch."""
    batch = get_object_or_404(ProcessBatch, tenant=request.tenant, id=batch_id)
    outputs = []
    for out in batch.outputs.select_related('inventory', 'product'):
        product_name = ''
        if out.product:
            product_name = out.product.item_name or out.product.description
        elif out.inventory:
            product_name = out.inventory.desc
        outputs.append({
            'id': out.id,
            'lot_id': out.lot_id,
            'product_name': product_name,
            'quantity': float(out.quantity),
            'unit_type': out.unit_type,
            'yield_percent': float(out.yield_percent) if out.yield_percent else None,
        })
    return JsonResponse({'outputs': outputs})


@login_required
@ensure_tenant
def processing_products_api(request):
    """Return products for output product selection."""
    search = request.GET.get('search', '').strip()
    qs = Product.objects.filter(tenant=request.tenant, is_active=True)
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(item_name__icontains=search) |
            Q(description__icontains=search) |
            Q(product_id__icontains=search)
        )
    products = [{
        'id': p.id,
        'product_id': p.product_id,
        'item_name': p.item_name or p.description,
        'unit_type': p.inventory_unit_of_measure or p.quantity_description or '',
    } for p in qs.order_by('description')[:50]]
    return JsonResponse({'products': products})
