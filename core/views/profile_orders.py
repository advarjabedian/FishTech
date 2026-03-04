from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ..models import Customer, CustomerProfile, SO, SOD, get_current_tenant
import json
import logging

logger = logging.getLogger(__name__)


@login_required
def customer_list(request):
    """Display list of customers for profile orders"""
    customers = Customer.objects.order_by('name')
    return render(request, 'core/customer_list.html', {'customers': customers})


@login_required
def profile_order_form(request, customer_id):
    """Display profile order form for a specific customer"""
    customer = get_object_or_404(Customer, id=customer_id)
    profiles = CustomerProfile.objects.filter(customer=customer, is_active=True).order_by('description')

    return render(request, 'core/profile_order_form.html', {
        'customer': customer,
        'profiles': profiles,
    })


@login_required
@require_POST
def submit_profile_order(request):
    """Submit a profile order — creates SO + SOD records"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)

    try:
        data = json.loads(request.body)
        order_data = data.get('orderData', {})
        order_items = data.get('orderItems', [])

        if not order_items:
            return JsonResponse({'error': 'No items in order'}, status=400)

        customer_id = order_data.get('customerId')
        customer = get_object_or_404(Customer, id=customer_id)

        # Get next SO ID for this tenant
        last_so = SO.all_objects.filter(tenant=tenant).order_by('-soid').first()
        next_soid = (last_so.soid + 1) if last_so else 1

        # Parse dispatch date
        import datetime
        from django.utils.dateparse import parse_date
        dispatch_date_str = order_data.get('dispatchDate', '')
        try:
            dispatch_date = datetime.datetime.strptime(dispatch_date_str, '%m/%d/%Y').date()
        except ValueError:
            dispatch_date = parse_date(dispatch_date_str)

        # Create SO header
        so = SO.objects.create(
            tenant=tenant,
            soid=next_soid,
            customer=customer,
            customerid=customer.customer_id,
            dispatchdate=dispatch_date,
            comments=order_data.get('comments', ''),
            customerpo=order_data.get('customerPO', ''),
            billto1=customer.name,
            billto2=customer.address,
            billto3=f"{customer.city}, {customer.state} {customer.zipcode}",
            shipto1=customer.name,
            shipto2=customer.ship_address or customer.address,
            shipto3=f"{customer.ship_city or customer.city}, {customer.ship_state or customer.state} {customer.ship_zipcode or customer.zipcode}",
            totalamount=order_data.get('total', 0),
        )

        # Get next SOD ID
        last_sod = SOD.all_objects.filter(tenant=tenant).order_by('-sodid').first()
        next_sodid = (last_sod.sodid + 1) if last_sod else 1

        # Create SOD line items
        for item in order_items:
            SOD.objects.create(
                tenant=tenant,
                sodid=next_sodid,
                so=so,
                soid=so.soid,
                productid=item.get('id'),
                descriptionmemo=item.get('name', ''),
                orderedunits=item.get('quantity', 0),
                unitsize=item.get('packSize', 1),
                salesprice=item.get('price', 0),
                specialinstructions=item.get('instructions', ''),
            )
            next_sodid += 1

        logger.info(f"Tenant {tenant.name}: Created SO-{so.soid} for customer {customer.name} with {len(order_items)} items")

        return JsonResponse({
            'success': True,
            'order_id': so.soid,
            'message': f'Order SO-{so.soid} submitted successfully'
        })

    except Exception as e:
        logger.error(f"Error submitting profile order: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)