from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from ..models import APExpense, ARInvoice, FishOrder, Vendor, get_current_tenant
import json
import logging

logger = logging.getLogger(__name__)


# ── Hub Pages ─────────────────────────────────────────────────────────────────

@login_required
def unused_tiles(request):
    return render(request, 'core/unused_tiles.html')


@login_required
def accounting_hub(request):
    return render(request, 'core/accounting_hub.html')


@login_required
def compliance_hub(request):
    return render(request, 'core/compliance_hub.html')


@login_required
def orders_landing(request):
    return render(request, 'core/orders_landing.html')


# ── Page Views ────────────────────────────────────────────────────────────────

@login_required
def ar_invoices(request):
    return render(request, 'core/ar_invoices.html')


@login_required
def ap_expenses(request):
    return render(request, 'core/ap_expenses.html')


@login_required
def ledger(request):
    return render(request, 'core/ledger.html')


# ── AR Invoices API ───────────────────────────────────────────────────────────

@login_required
def ar_list(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)

    invoices = ARInvoice.objects.all().order_by('-invoice_date', '-created_at')
    data = []
    for inv in invoices:
        data.append({
            'id': inv.id,
            'customer': inv.customer,
            'description': inv.description,
            'amount': float(inv.amount),
            'invoice_date': inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '',
            'due_date': inv.due_date.strftime('%Y-%m-%d') if inv.due_date else '',
            'paid_date': inv.paid_date.strftime('%Y-%m-%d') if inv.paid_date else '',
            'status': inv.status,
            'payment_type': inv.payment_type,
            'payment_notes': inv.payment_notes,
            'notes': inv.notes,
            'created_at': inv.created_at.strftime('%m/%d/%Y'),
        })
    return JsonResponse({'invoices': data})


@login_required
@require_POST
def ar_create(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        data = json.loads(request.body)
        inv = ARInvoice.objects.create(
            tenant=tenant,
            customer=data.get('customer', '').strip(),
            description=data.get('description', '').strip(),
            amount=data.get('amount', 0),
            invoice_date=data.get('invoice_date') or None,
            due_date=data.get('due_date') or None,
            paid_date=data.get('paid_date') or None,
            status=data.get('status', 'Unpaid'),
            payment_type=data.get('payment_type', '').strip(),
            payment_notes=data.get('payment_notes', '').strip(),
            notes=data.get('notes', '').strip(),
        )
        return JsonResponse({'success': True, 'id': inv.id})
    except Exception as e:
        logger.error(f"ar_create error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def ar_update(request, invoice_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        inv = ARInvoice.objects.get(id=invoice_id, tenant=tenant)
        data = json.loads(request.body)
        for field in ('customer', 'description', 'notes', 'status', 'payment_type', 'payment_notes'):
            if field in data:
                setattr(inv, field, data[field].strip() if isinstance(data[field], str) else data[field])
        if 'amount' in data:
            inv.amount = data['amount']
        if 'invoice_date' in data:
            inv.invoice_date = data['invoice_date'] or None
        if 'due_date' in data:
            inv.due_date = data['due_date'] or None
        if 'paid_date' in data:
            inv.paid_date = data['paid_date'] or None
        inv.save()
        return JsonResponse({'success': True})
    except ARInvoice.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def ar_delete(request, invoice_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        ARInvoice.objects.get(id=invoice_id, tenant=tenant).delete()
        return JsonResponse({'success': True})
    except ARInvoice.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
@require_POST
def ar_mark_paid(request, invoice_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        inv = ARInvoice.objects.get(id=invoice_id, tenant=tenant)
        data = json.loads(request.body) if request.body else {}
        if inv.status == 'Paid':
            inv.status = 'Unpaid'
            inv.paid_date = None
            inv.payment_type = ''
            inv.payment_notes = ''
        else:
            inv.status = 'Paid'
            inv.paid_date = data.get('paid_date') or None
            inv.payment_type = data.get('payment_type', '').strip()
            inv.payment_notes = data.get('payment_notes', '').strip()
        inv.save()
        return JsonResponse({'success': True, 'status': inv.status})
    except ARInvoice.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@login_required
def ar_customer_balances(request):
    """Aggregate customer balances from AR invoices"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)

    invoices = ARInvoice.objects.all()
    customer_map = {}
    for inv in invoices:
        name = inv.customer
        if name not in customer_map:
            customer_map[name] = {'customer': name, 'total_billed': 0, 'total_paid': 0, 'outstanding': 0, 'unpaid_count': 0}
        customer_map[name]['total_billed'] += float(inv.amount)
        if inv.status == 'Paid':
            customer_map[name]['total_paid'] += float(inv.amount)
        else:
            customer_map[name]['outstanding'] += float(inv.amount)
            customer_map[name]['unpaid_count'] += 1

    balances = sorted(customer_map.values(), key=lambda x: x['outstanding'], reverse=True)
    return JsonResponse({'balances': balances})


# ── AP Expenses API ───────────────────────────────────────────────────────────

@login_required
def ap_list(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)

    expenses = APExpense.objects.all().order_by('-created_at')
    data = []
    for e in expenses:
        data.append({
            'id': e.id,
            'vendor': e.vendor,
            'description': e.description,
            'amount': float(e.amount),
            'category': e.category,
            'due_date': e.due_date.strftime('%Y-%m-%d') if e.due_date else '',
            'paid_date': e.paid_date.strftime('%Y-%m-%d') if e.paid_date else '',
            'status': e.status,
            'notes': e.notes,
            'created_at': e.created_at.strftime('%m/%d/%Y'),
        })
    return JsonResponse({'expenses': data})


@login_required
@require_POST
def ap_create(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        data = json.loads(request.body)
        expense = APExpense.objects.create(
            tenant=tenant,
            vendor=data.get('vendor', '').strip(),
            description=data.get('description', '').strip(),
            amount=data.get('amount', 0),
            category=data.get('category', '').strip(),
            due_date=data.get('due_date') or None,
            paid_date=data.get('paid_date') or None,
            status=data.get('status', 'Unpaid'),
            notes=data.get('notes', '').strip(),
        )
        return JsonResponse({'success': True, 'id': expense.id})
    except Exception as e:
        logger.error(f"ap_create error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def ap_update(request, expense_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        expense = APExpense.objects.get(id=expense_id, tenant=tenant)
        data = json.loads(request.body)
        for field in ('vendor', 'description', 'category', 'notes', 'status'):
            if field in data:
                setattr(expense, field, data[field].strip() if isinstance(data[field], str) else data[field])
        if 'amount' in data:
            expense.amount = data['amount']
        if 'due_date' in data:
            expense.due_date = data['due_date'] or None
        if 'paid_date' in data:
            expense.paid_date = data['paid_date'] or None
        expense.save()
        return JsonResponse({'success': True})
    except APExpense.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def ap_delete(request, expense_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        APExpense.objects.get(id=expense_id, tenant=tenant).delete()
        return JsonResponse({'success': True})
    except APExpense.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ── Ledger API ────────────────────────────────────────────────────────────────

@login_required
def ledger_data(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)

    # Income: AR invoices marked Paid + fish market orders
    ar_paid = ARInvoice.objects.filter(status='Paid')
    income_rows = []
    total_income = 0

    for inv in ar_paid.order_by('-paid_date', '-created_at'):
        total_income += float(inv.amount)
        income_rows.append({
            'id': inv.id,
            'date': inv.paid_date.strftime('%m/%d/%Y') if inv.paid_date else inv.created_at.strftime('%m/%d/%Y'),
            'description': f'{inv.customer} — {inv.description}',
            'amount': float(inv.amount),
            'status': 'Paid',
            'type': 'income',
            'source': 'AR Invoice',
        })

    orders = FishOrder.objects.filter(status__in=['Confirmed', 'Delivered', 'Pending'])
    for o in orders.order_by('-created_at'):
        total_income += float(o.subtotal)
        income_rows.append({
            'id': o.id,
            'date': o.created_at.strftime('%m/%d/%Y'),
            'description': f'Fish Market Order #{o.id} — {o.customer_name}',
            'amount': float(o.subtotal),
            'status': o.status,
            'type': 'income',
            'source': 'Fish Market',
        })

    # Expenses: all AP entries
    expenses = APExpense.objects.all().order_by('-created_at')
    expense_rows = []
    total_expenses = 0
    total_paid = 0
    total_unpaid = 0
    for e in expenses:
        total_expenses += float(e.amount)
        if e.status == 'Paid':
            total_paid += float(e.amount)
        else:
            total_unpaid += float(e.amount)
        expense_rows.append({
            'id': e.id,
            'date': e.created_at.strftime('%m/%d/%Y'),
            'due_date': e.due_date.strftime('%m/%d/%Y') if e.due_date else '',
            'paid_date': e.paid_date.strftime('%m/%d/%Y') if e.paid_date else '',
            'description': f'{e.vendor} — {e.description}',
            'category': e.category,
            'amount': float(e.amount),
            'status': e.status,
            'type': 'expense',
        })

    return JsonResponse({
        'summary': {
            'total_income': round(total_income, 2),
            'total_expenses': round(total_expenses, 2),
            'total_paid_expenses': round(total_paid, 2),
            'total_unpaid_expenses': round(total_unpaid, 2),
            'net': round(total_income - total_paid, 2),
        },
        'income': income_rows,
        'expenses': expense_rows,
    })


# ── Vendor Management ─────────────────────────────────────────────────────────

@login_required
def vendor_list_page(request):
    return render(request, 'core/vendor_list.html')


@login_required
def vendor_list_api(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    vendors = Vendor.objects.all().order_by('name')
    return JsonResponse({'vendors': [{
        'id': v.id,
        'vendor_id': v.vendor_id,
        'name': v.name,
        'contact_name': v.contact_name,
        'phone': v.phone,
        'email': v.email,
        'address': v.address,
        'city': v.city,
        'state': v.state,
        'zipcode': v.zipcode,
    } for v in vendors]})


@login_required
@require_POST
def vendor_create_api(request):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Name is required'}, status=400)
        from django.db.models import Max
        max_id = Vendor.all_objects.filter(tenant=tenant).aggregate(Max('vendor_id'))['vendor_id__max']
        next_id = (max_id + 1) if max_id else 1
        v = Vendor.objects.create(
            tenant=tenant, vendor_id=next_id, name=name,
            contact_name=data.get('contact_name', ''),
            phone=data.get('phone', ''),
            email=data.get('email', ''),
            address=data.get('address', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            zipcode=data.get('zipcode', ''),
        )
        return JsonResponse({'success': True, 'id': v.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def vendor_update_api(request, vendor_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        v = Vendor.objects.get(id=vendor_id, tenant=tenant)
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'error': 'Name is required'}, status=400)
        v.name = name
        for field in ('contact_name', 'phone', 'email', 'address', 'city', 'state', 'zipcode'):
            if field in data:
                setattr(v, field, data[field].strip() if isinstance(data[field], str) else data[field])
        v.save()
        return JsonResponse({'success': True})
    except Vendor.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def vendor_delete_api(request, vendor_id):
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant'}, status=400)
    try:
        Vendor.objects.get(id=vendor_id, tenant=tenant).delete()
        return JsonResponse({'success': True})
    except Vendor.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
