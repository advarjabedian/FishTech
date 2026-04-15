from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from ..models import Customer, CustomerProfile, ProductImage, Product, SalesOrder, SalesOrderItem, get_current_tenant
from ..models import Tenant, InboundMessage
from ..decorators import tenant_api
import json
import io
import csv
import logging

logger = logging.getLogger(__name__)


@login_required
def customer_list(request):
    customers = Customer.objects.order_by('name')
    return render(request, 'core/Orders/customer_list.html', {'customers': customers})


@login_required
def products_page(request):
    """View tenant product catalog and customer assignments"""
    from django.db.models import Prefetch
    tenant = get_current_tenant()
    products = Product.objects.filter(is_active=True).prefetch_related('images').order_by('sort_order', 'description')
    customers = Customer.objects.prefetch_related(
        Prefetch('profiles', queryset=CustomerProfile.objects.select_related('product').prefetch_related('product__images'))
    ).order_by('name')
    return render(request, 'core/Orders/products.html', {
        'customers': customers,
        'products': products,
    })


def profile_order_form(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    profiles = CustomerProfile.objects.filter(customer=customer, is_active=True).order_by('description')
    return render(request, 'core/Orders/profile_order_form.html', {
        'customer': customer,
        'profiles': profiles,
    })


@require_POST
def submit_profile_order(request):
    try:
        data = json.loads(request.body)
        order_data = data.get('orderData', {})
        order_items = data.get('orderItems', [])

        if not order_items:
            return JsonResponse({'error': 'No items in order'}, status=400)

        customer = get_object_or_404(Customer, id=order_data.get('customerId'))
        tenant = customer.tenant

        # Generate next order number
        last_so = SalesOrder.all_objects.filter(tenant=tenant).order_by('-id').first()
        next_num = 10001
        if last_so:
            try:
                next_num = int(last_so.order_number) + 1
            except (ValueError, TypeError):
                next_num = last_so.id + 10001

        import datetime
        from django.utils.dateparse import parse_date
        dispatch_date_str = order_data.get('dispatchDate', '')
        try:
            dispatch_date = datetime.datetime.strptime(dispatch_date_str, '%m/%d/%Y').date()
        except ValueError:
            dispatch_date = parse_date(dispatch_date_str)

        so = SalesOrder.objects.create(
            tenant=tenant,
            order_number=str(next_num),
            customer=customer,
            customer_name=customer.name,
            order_date=dispatch_date,
            delivery_date=dispatch_date,
            notes=order_data.get('comments', ''),
            po_number=order_data.get('customerPO', ''),
            order_status='open',
        )

        for item in order_items:
            qty = item.get('quantity', 0)
            price = item.get('price', 0)
            pack = item.get('packSize', 1)
            SalesOrderItem.objects.create(
                tenant=tenant,
                sales_order=so,
                description=item.get('name', ''),
                quantity=qty,
                unit_price=price,
                amount=float(qty or 0) * float(pack or 1) * float(price or 0),
                notes=item.get('instructions', ''),
            )

        return JsonResponse({'success': True, 'order_id': so.order_number,
                             'message': f'Order SO-{so.order_number} submitted successfully'})

    except Exception as e:
        logger.error(f"Error submitting profile order: {e}")
        return JsonResponse({'error': str(e)}, status=500)

# =============================================================================
# IMPORT VIEWS
# =============================================================================

from ..services import import_service


@login_required
def import_customers_page(request):
    return render(request, 'core/Orders/import_customers.html')


@login_required
def download_import_template(request):
    """Return a blank Excel template for customer/profile import"""
    try:
        wb = import_service.generate_template_workbook()
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="fishteck_import_template.xlsx"'
        return response

    except ImportError:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="fishteck_import_template.csv"'
        writer = csv.writer(response)
        writer.writerow(import_service.IMPORT_HEADERS)
        writer.writerow(import_service.IMPORT_SAMPLE_ROW)
        return response


@login_required
@require_POST
def import_preview(request):
    """Parse uploaded file and return preview data without saving"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    try:
        raw_headers, raw_rows = import_service.parse_file(file)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    existing_ids = set(
        Customer.all_objects.filter(tenant=tenant)
        .values_list('customer_id', flat=True)
    )

    try:
        result = import_service.validate_and_preview(raw_headers, raw_rows, existing_ids)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse(result)


@login_required
@require_POST
def import_confirm(request):
    """Save previewed import data"""
    tenant = get_current_tenant()
    if not tenant:
        return JsonResponse({'error': 'No tenant context'}, status=400)

    try:
        data = json.loads(request.body)
        rows = data.get('rows', [])

        if not rows:
            return JsonResponse({'error': 'No rows to import'}, status=400)

        result = import_service.execute_import(tenant, rows)
        return JsonResponse({'success': True, **result})

    except Exception as e:
        logger.error(f"Import confirm error: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def add_customer_api(request, tenant, data):
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)

    from django.db.models import Max
    max_id = Customer.all_objects.filter(tenant=tenant).aggregate(Max('customer_id'))['customer_id__max']
    next_id = (max_id + 1) if max_id else 1

    customer = Customer.objects.create(
        tenant=tenant,
        customer_id=next_id,
        name=name,
        contact_name=data.get('contact_name', ''),
        phone=data.get('phone', ''),
        email=data.get('email', ''),
        address=data.get('address', ''),
        city=data.get('city', ''),
        state=data.get('state', ''),
        zipcode=data.get('zipcode', ''),
    )
    return JsonResponse({'success': True, 'id': customer.id, 'name': customer.name})


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def update_customer_api(request, tenant, data, customer_id):
    customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    customer.name = name
    for field in ('contact_name', 'phone', 'email', 'address', 'city', 'state', 'zipcode'):
        if field in data:
            setattr(customer, field, data[field].strip() if isinstance(data[field], str) else data[field])
    customer.save()
    return JsonResponse({'success': True})


@login_required
@tenant_api(methods=['POST'])
def delete_customer_api(request, tenant, customer_id):
    customer = get_object_or_404(Customer, id=customer_id, tenant=tenant)
    customer.delete()
    return JsonResponse({'success': True})


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def add_profile_item_api(request, tenant, data, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required'}, status=400)

    profile = CustomerProfile.objects.create(
        tenant=tenant,
        customer=customer,
        description=description,
        unit_type=data.get('unit_type', ''),
        pack_size=float(data.get('pack_size') or 1),
        sales_price=float(data.get('sales_price') or 0),
        is_active=True,
    )
    return JsonResponse({
        'success': True,
        'id': profile.id,
        'description': profile.description,
        'unit_type': profile.unit_type,
        'pack_size': str(profile.pack_size),
        'sales_price': str(profile.sales_price),
    })


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def update_profile_item_api(request, tenant, data, profile_id):
    profile = get_object_or_404(CustomerProfile, id=profile_id)
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required'}, status=400)
    profile.description = description
    profile.unit_type = data.get('unit_type', '')
    profile.pack_size = float(data.get('pack_size') or 1)
    profile.sales_price = float(data.get('sales_price') or 0)
    profile.save()
    return JsonResponse({
        'success': True,
        'id': profile.id,
        'description': profile.description,
        'unit_type': profile.unit_type,
        'pack_size': str(profile.pack_size),
        'sales_price': str(profile.sales_price),
    })


@login_required
@tenant_api(methods=['POST'])
def delete_profile_item_api(request, tenant, profile_id):
    profile = get_object_or_404(CustomerProfile, id=profile_id)
    profile.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
@tenant_api(methods=['POST'])
def upload_product_image(request, tenant, product_id):
    """Upload an image (slot 1, 2, or 3) for a product"""
    product = get_object_or_404(Product, id=product_id)
    slot = int(request.POST.get('slot', 1))
    if slot not in (1, 2, 3):
        return JsonResponse({'error': 'Slot must be 1, 2, or 3'}, status=400)

    image_file = request.FILES.get('image')
    if not image_file:
        return JsonResponse({'error': 'No image provided'}, status=400)

    ProductImage.objects.filter(product=product, slot=slot).delete()

    img = ProductImage.objects.create(
        product=product,
        slot=slot,
        image=image_file,
    )
    return JsonResponse({'success': True, 'url': img.image.url, 'slot': slot})


@login_required
@tenant_api(methods=['POST'])
def delete_product_image(request, tenant, product_id, slot):
    """Delete a product image by slot"""
    product = get_object_or_404(Product, id=product_id)
    img = ProductImage.objects.filter(product=product, slot=slot).first()
    if img:
        img.image.delete(save=False)
        img.delete()
    return JsonResponse({'success': True})


@login_required
@tenant_api()
def get_product_images(request, tenant, product_id):
    """Get all images for a tenant product"""
    product = get_object_or_404(Product, id=product_id)
    images = [{'slot': img.slot, 'url': img.image.url}
              for img in ProductImage.objects.filter(product=product).order_by('slot')]
    return JsonResponse({'success': True, 'images': images})


# =============================================================================
# TENANT PRODUCT CATALOG
# =============================================================================

@login_required
@tenant_api()
def get_tenant_products_api(request, tenant):
    """List all products in the catalog"""
    products = Product.objects.order_by('sort_order', 'description')
    data = [{
        'id': p.id,
        'description': p.description,
        'unit_type': p.unit_type,
        'pack_size': str(p.pack_size) if p.pack_size else '',
        'default_price': str(p.default_price) if p.default_price else '',
        'is_active': p.is_active,
    } for p in products]
    return JsonResponse({'success': True, 'products': data})


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def add_tenant_product_api(request, tenant, data):
    """Add a product to the catalog"""
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required'}, status=400)
    if Product.objects.filter(description=description).exists():
        return JsonResponse({'error': 'A product with this description already exists'}, status=400)
    product = Product.objects.create(
        tenant=tenant,
        description=description,
        unit_type=data.get('unit_type', ''),
        pack_size=float(data.get('pack_size') or 0) or None,
        default_price=float(data.get('default_price') or 0) or None,
        is_active=True,
    )
    return JsonResponse({
        'success': True,
        'id': product.id,
        'description': product.description,
        'unit_type': product.unit_type,
        'pack_size': str(product.pack_size) if product.pack_size else '',
        'default_price': str(product.default_price) if product.default_price else '',
    })


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def update_tenant_product_api(request, tenant, data, product_id):
    """Update a product"""
    product = get_object_or_404(Product, id=product_id)
    description = data.get('description', '').strip()
    if not description:
        return JsonResponse({'error': 'Description is required'}, status=400)
    dup = Product.objects.filter(description=description).exclude(id=product_id).exists()
    if dup:
        return JsonResponse({'error': 'A product with this description already exists'}, status=400)
    product.description = description
    product.unit_type = data.get('unit_type', '')
    product.pack_size = float(data.get('pack_size') or 0) or None
    product.default_price = float(data.get('default_price') or 0) or None
    product.save()
    return JsonResponse({
        'success': True,
        'id': product.id,
        'description': product.description,
        'unit_type': product.unit_type,
        'pack_size': str(product.pack_size) if product.pack_size else '',
        'default_price': str(product.default_price) if product.default_price else '',
    })


@login_required
@tenant_api(methods=['POST'])
def delete_tenant_product_api(request, tenant, product_id):
    """Delete a product (and unlink from customer assignments)"""
    product = get_object_or_404(Product, id=product_id)
    product.delete()
    return JsonResponse({'success': True})


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def assign_product_to_customer_api(request, tenant, data):
    """Assign a tenant product to a customer (drag-and-drop)"""
    product_id = data.get('product_id')
    customer_id = data.get('customer_id')
    if not product_id or not customer_id:
        return JsonResponse({'error': 'product_id and customer_id are required'}, status=400)

    product = get_object_or_404(Product, id=product_id)
    customer = get_object_or_404(Customer, id=customer_id)

    existing = CustomerProfile.objects.filter(customer=customer, product=product).first()
    if existing:
        return JsonResponse({'error': f'"{product.description}" is already assigned to this customer'}, status=400)

    profile = CustomerProfile.objects.create(
        tenant=tenant,
        customer=customer,
        product=product,
        description=product.description,
        unit_type=product.unit_type,
        pack_size=product.pack_size,
        sales_price=product.default_price,
        is_active=True,
    )
    images = [{'slot': img.slot, 'url': img.image.url}
              for img in product.images.all().order_by('slot')]

    return JsonResponse({
        'success': True,
        'id': profile.id,
        'product_id': product.id,
        'description': profile.description,
        'unit_type': profile.unit_type,
        'pack_size': str(profile.pack_size) if profile.pack_size else '',
        'sales_price': str(profile.sales_price) if profile.sales_price else '0.00',
        'images': images,
    })


@login_required
@tenant_api(methods=['POST'])
def unassign_product_from_customer_api(request, tenant, profile_id):
    """Remove a product assignment from a customer"""
    profile = get_object_or_404(CustomerProfile, id=profile_id)
    profile.delete()
    return JsonResponse({'success': True})


# =============================================================================
# VIEW ORDERS
# =============================================================================

@login_required
def profile_orders_list(request):
    from ..models import TenantUser
    tenant = get_current_tenant()
    tenant_users = TenantUser.objects.filter(tenant=tenant).select_related('user').order_by('user__username')
    users = [{'id': tu.user.id, 'name': tu.user.username} for tu in tenant_users]
    return render(request, 'core/Orders/profile_orders_list.html', {'users': users})


@login_required
@tenant_api()
def get_profile_orders_api(request, tenant):
    completed = request.GET.get('completed', 'false') == 'true'
    from django.db.models import Sum, Value
    from django.db.models.functions import Coalesce
    orders = SalesOrder.objects.filter(is_completed=completed).select_related(
        'customer', 'assigned_to', 'completed_by'
    ).annotate(
        total_amount=Coalesce(Sum('items__amount'), Value(0.0))
    ).order_by('-id')

    data = []
    for o in orders:
        data.append({
            'soid': o.id,
            'order_number': o.order_number,
            'customer': o.customer_name or '',
            'dispatch_date': o.order_date.strftime('%m/%d/%Y') if o.order_date else '',
            'total': float(o.total_amount),
            'customerpo': o.po_number or '',
            'comments': o.notes or '',
            'assigned_to_id': o.assigned_to_id,
            'assigned_to_name': o.assigned_to.username if o.assigned_to else '',
            'completed_at': o.completed_at.strftime('%m/%d/%Y %I:%M %p') if o.completed_at else '',
            'completed_by': o.completed_by.username if o.completed_by else '',
        })

    return JsonResponse({'orders': data})


@login_required
@tenant_api()
def get_profile_order_items_api(request, tenant, soid):
    so = get_object_or_404(SalesOrder, id=soid)
    items = SalesOrderItem.objects.filter(sales_order=so).order_by('sort_order', 'id')
    data = [{
        'description': i.description or '',
        'qty': float(i.quantity or 0),
        'pack': 1,
        'price': float(i.unit_price or 0),
        'total': float(i.amount or 0),
        'instructions': i.notes or '',
    } for i in items]

    return JsonResponse({'items': data})


@login_required
@tenant_api(methods=['POST'], parse_json=True)
def assign_profile_order_api(request, tenant, data, soid):
    so = get_object_or_404(SalesOrder, id=soid)
    user_id = data.get('user_id')

    if user_id:
        from django.contrib.auth.models import User as DjangoUser
        so.assigned_to = get_object_or_404(DjangoUser, id=user_id)
    else:
        so.assigned_to = None
    so.save()
    return JsonResponse({'success': True})


@login_required
@tenant_api(methods=['POST'])
def complete_profile_order_api(request, tenant, soid):
    from django.utils import timezone
    so = get_object_or_404(SalesOrder, id=soid)
    so.is_completed = True
    so.completed_at = timezone.now()
    so.completed_by = request.user
    so.save()
    return JsonResponse({'success': True})


@login_required
@tenant_api(methods=['POST'])
def uncomplete_profile_order_api(request, tenant, soid):
    so = get_object_or_404(SalesOrder, id=soid)
    so.is_completed = False
    so.completed_at = None
    so.completed_by = None
    so.save()
    return JsonResponse({'success': True})
    
def public_profile_order_form(request, token):
    customer = get_object_or_404(Customer, public_token=token)
    profiles = CustomerProfile.objects.filter(customer=customer, is_active=True).order_by('description')
    return render(request, 'core/Orders/profile_order_form.html', {
        'customer': customer,
        'profiles': profiles,
    })
