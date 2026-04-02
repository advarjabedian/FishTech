from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from ..models import APExpense, FishOrder, get_current_tenant
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def unused_tiles(request):
    return render(request, 'core/unused_tiles.html')


@login_required
def ap_expenses(request):
    return render(request, 'core/ap_expenses.html')


@login_required
def ledger(request):
    return render(request, 'core/ledger.html')


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

    # Income: fish market orders (Confirmed or Delivered)
    orders = FishOrder.objects.filter(status__in=['Confirmed', 'Delivered', 'Pending'])
    income_rows = []
    total_income = 0
    for o in orders.order_by('-created_at'):
        total_income += float(o.subtotal)
        income_rows.append({
            'id': o.id,
            'date': o.created_at.strftime('%m/%d/%Y'),
            'description': f'Fish Market Order #{o.id} — {o.customer_name}',
            'amount': float(o.subtotal),
            'status': o.status,
            'type': 'income',
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
