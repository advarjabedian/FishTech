from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as DjangoUser
from django.conf import settings
from ..models import FishMenuItem, FishOrder, Tenant, TenantUser, get_current_tenant
import stripe
import json
import logging

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


def fish_market_redirect(request):
    """Redirect logged-in users to their tenant's fish market page."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return redirect('login')
    return redirect('fish_market_page', slug=tenant.subdomain)


def fish_market_page(request, slug):
    """Public fish market page for a specific tenant."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
    except Tenant.DoesNotExist:
        raise Http404

    menu_items = FishMenuItem.all_objects.filter(
        tenant=tenant, is_available=True
    ).order_by('sort_order', 'name')

    all_items = FishMenuItem.all_objects.filter(
        tenant=tenant
    ).order_by('sort_order', 'name')

    is_manager = False
    if request.user.is_authenticated:
        try:
            TenantUser.objects.get(user=request.user, tenant=tenant)
            is_manager = True
        except TenantUser.DoesNotExist:
            pass

    return render(request, 'core/fish_market.html', {
        'tenant': tenant,
        'menu_items': menu_items if not is_manager else all_items,
        'is_manager': is_manager,
        'slug': slug,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY or '',
    })


# ── Menu Management (login required) ─────────────────────────────────────────

@login_required
@require_POST
def fish_market_add_item(request, slug):
    """Add a new menu item (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        data = json.loads(request.body)
        item = FishMenuItem.all_objects.create(
            tenant=tenant,
            name=data.get('name', '').strip(),
            description=data.get('description', '').strip(),
            price=data.get('price', 0),
            category=data.get('category', '').strip(),
            sort_order=data.get('sort_order', 0),
            is_available=data.get('is_available', True),
        )
        return JsonResponse({'success': True, 'id': item.id})
    except Exception as e:
        logger.error(f"fish_market_add_item error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def fish_market_update_item(request, slug, item_id):
    """Update an existing menu item (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        item = FishMenuItem.all_objects.get(id=item_id, tenant=tenant)
        data = json.loads(request.body)

        if 'name' in data:
            item.name = data['name'].strip()
        if 'description' in data:
            item.description = data['description'].strip()
        if 'price' in data:
            item.price = data['price']
        if 'category' in data:
            item.category = data['category'].strip()
        if 'sort_order' in data:
            item.sort_order = data['sort_order']
        if 'is_available' in data:
            item.is_available = data['is_available']

        item.save()
        return JsonResponse({'success': True})
    except FishMenuItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)
    except Exception as e:
        logger.error(f"fish_market_update_item error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def fish_market_delete_item(request, slug, item_id):
    """Delete a menu item (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        item = FishMenuItem.all_objects.get(id=item_id, tenant=tenant)
        item.delete()
        return JsonResponse({'success': True})
    except FishMenuItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)


@login_required
@require_POST
def fish_market_update_image(request, slug, item_id):
    """Update the image for a menu item (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        item = FishMenuItem.all_objects.get(id=item_id, tenant=tenant)
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'error': 'No image provided'}, status=400)

        import base64
        content_type = image_file.content_type
        image_data = base64.b64encode(image_file.read()).decode('utf-8')
        item.image = f"data:{content_type};base64,{image_data}"
        item.save()

        return JsonResponse({'success': True, 'image': item.image})
    except FishMenuItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found'}, status=404)
    except Exception as e:
        logger.error(f"fish_market_update_image error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ── Stripe Payment Intent ─────────────────────────────────────────────────────

@require_POST
def fish_market_create_payment_intent(request, slug):
    """Create a Stripe PaymentIntent for the cart total (public)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body)
        items = data.get('items', [])

        if not items:
            return JsonResponse({'error': 'No items in cart'}, status=400)

        # Calculate total server-side from saved prices
        item_ids = [i.get('id') for i in items if i.get('id')]
        db_items = {
            m.id: m for m in FishMenuItem.all_objects.filter(
                tenant=tenant, id__in=item_ids, is_available=True
            )
        }

        total_cents = 0
        for cart_item in items:
            db_item = db_items.get(cart_item.get('id'))
            if db_item:
                qty = max(1, int(cart_item.get('quantity', 1)))
                total_cents += int(float(db_item.price) * qty * 100)

        if total_cents == 0:
            return JsonResponse({'error': 'No valid items found'}, status=400)

        intent = stripe.PaymentIntent.create(
            amount=total_cents,
            currency='usd',
            metadata={'tenant_slug': slug, 'tenant_id': tenant.id},
        )

        return JsonResponse({'client_secret': intent.client_secret})

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating PaymentIntent: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    except Exception as e:
        logger.error(f"fish_market_create_payment_intent error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ── Public Order Submission ───────────────────────────────────────────────────

@require_POST
def fish_market_submit_order(request, slug):
    """Submit a fish market order (public)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
    except Tenant.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    try:
        data = json.loads(request.body)

        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        customer_address = data.get('customer_address', '').strip()
        customer_email = data.get('customer_email', '').strip()
        payment_type = data.get('payment_type', 'card')
        card_holder_name = data.get('card_holder_name', '').strip()
        card_last_four = data.get('card_last_four', '').strip()
        card_brand = data.get('card_brand', '').strip()
        card_expiry = data.get('card_expiry', '').strip()
        payment_intent_id = data.get('payment_intent_id', '').strip()
        notes = data.get('notes', '').strip()
        items = data.get('items', [])

        if not customer_name:
            return JsonResponse({'error': 'Name is required'}, status=400)
        if not customer_phone:
            return JsonResponse({'error': 'Phone is required'}, status=400)
        if not customer_address:
            return JsonResponse({'error': 'Address is required'}, status=400)
        if not items:
            return JsonResponse({'error': 'No items in order'}, status=400)

        # Calculate subtotal from saved prices (don't trust client prices)
        item_ids = [i.get('id') for i in items if i.get('id')]
        db_items = {
            m.id: m for m in FishMenuItem.all_objects.filter(
                tenant=tenant, id__in=item_ids, is_available=True
            )
        }

        order_items = []
        subtotal = 0
        for cart_item in items:
            db_item = db_items.get(cart_item.get('id'))
            if not db_item:
                continue
            qty = max(1, int(cart_item.get('quantity', 1)))
            line_total = float(db_item.price) * qty
            subtotal += line_total
            order_items.append({
                'id': db_item.id,
                'name': db_item.name,
                'price': float(db_item.price),
                'quantity': qty,
                'subtotal': line_total,
            })

        if not order_items:
            return JsonResponse({'error': 'No valid items found'}, status=400)

        order = FishOrder.all_objects.create(
            tenant=tenant,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            customer_address=customer_address,
            payment_type=payment_type,
            card_holder_name=card_holder_name,
            card_last_four=card_last_four,
            card_brand=card_brand,
            card_expiry=card_expiry,
            stripe_payment_intent_id=payment_intent_id,
            items_json=order_items,
            subtotal=round(subtotal, 2),
            notes=notes,
            status='Confirmed' if payment_intent_id else 'Pending',
        )

        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'subtotal': float(order.subtotal),
        })
    except Exception as e:
        logger.error(f"fish_market_submit_order error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# ── Orders Management (login required) ───────────────────────────────────────

@login_required
def fish_market_orders_list(request, slug):
    """View submitted orders for a tenant (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    orders = FishOrder.all_objects.filter(tenant=tenant).order_by('-created_at')[:200]
    import pytz
    pacific = pytz.timezone('America/Los_Angeles')

    data = []
    for o in orders:
        local_dt = o.created_at.astimezone(pacific)
        data.append({
            'id': o.id,
            'customer_name': o.customer_name,
            'customer_phone': o.customer_phone,
            'customer_address': o.customer_address,
            'customer_email': o.customer_email,
            'payment_type': o.payment_type,
            'card_last_four': o.card_last_four,
            'card_brand': o.card_brand,
            'items': o.items_json,
            'subtotal': float(o.subtotal),
            'notes': o.notes,
            'status': o.status,
            'created_at': local_dt.strftime('%m/%d/%Y %I:%M %p'),
        })

    return JsonResponse({'orders': data})


@login_required
@require_POST
def fish_market_update_order_status(request, slug, order_id):
    """Update order status (managers only)."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        TenantUser.objects.get(user=request.user, tenant=tenant)
    except (Tenant.DoesNotExist, TenantUser.DoesNotExist):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    try:
        order = FishOrder.all_objects.get(id=order_id, tenant=tenant)
        data = json.loads(request.body)
        order.status = data.get('status', order.status)
        order.save()
        return JsonResponse({'success': True})
    except FishOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
