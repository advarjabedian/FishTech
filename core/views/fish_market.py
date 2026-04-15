from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as DjangoUser
from django.conf import settings
from ..models import FishOrder, Tenant, TenantUser, Customer, CustomerProfile, ProductImage, ProductSize, Product, get_current_tenant
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
    if not tenant.subdomain:
        # Subdomain is blank — auto-populate from tenant name
        from django.utils.text import slugify
        tenant.subdomain = slugify(tenant.name) or str(tenant.id)
        tenant.save(update_fields=['subdomain'])
    return redirect('fish_market_page', slug=tenant.subdomain)


def fish_market_page(request, slug):
    """Public fish market page for a specific tenant."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
    except Tenant.DoesNotExist:
        raise Http404

    # Get the Retail customer's profile items as menu items
    retail_customer = Customer.all_objects.filter(tenant=tenant, is_retail=True).first()

    if retail_customer:
        menu_items = CustomerProfile.all_objects.filter(
            tenant=tenant, customer=retail_customer, is_active=True
        ).select_related('product').prefetch_related('product__images', 'sizes').order_by('sort_order', 'description')

        all_items = CustomerProfile.all_objects.filter(
            tenant=tenant, customer=retail_customer
        ).select_related('product').prefetch_related('product__images', 'sizes').order_by('sort_order', 'description')
    else:
        menu_items = CustomerProfile.objects.none()
        all_items = CustomerProfile.objects.none()

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


def fish_market_checkout(request, slug):
    """Checkout page — customer info + payment."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
    except Tenant.DoesNotExist:
        raise Http404

    return render(request, 'core/fish_market_checkout.html', {
        'tenant': tenant,
        'slug': slug,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY or '',
    })


def fish_market_order_status(request, slug, order_id):
    """Public order status page for customers."""
    try:
        tenant = Tenant.objects.get(subdomain=slug)
        order = FishOrder.all_objects.get(id=order_id, tenant=tenant)
    except (Tenant.DoesNotExist, FishOrder.DoesNotExist):
        raise Http404

    return render(request, 'core/fish_market_order_status.html', {
        'tenant': tenant,
        'order': order,
        'slug': slug,
    })


# ── Menu Management (login required) ─────────────────────────────────────────

def _get_retail_customer(tenant):
    """Helper to get the Retail customer for a tenant."""
    return Customer.all_objects.filter(tenant=tenant, is_retail=True).first()


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
        retail = _get_retail_customer(tenant)
        if not retail:
            return JsonResponse({'error': 'Retail customer not found'}, status=500)

        data = json.loads(request.body)
        item = CustomerProfile.all_objects.create(
            tenant=tenant,
            customer=retail,
            description=data.get('name', '').strip(),
            instruction=data.get('description', '').strip(),
            sales_price=data.get('price', 0),
            category=data.get('category', '').strip(),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_available', True),
        )
        # Create sizes if provided
        for i, sz in enumerate(data.get('sizes', [])):
            if sz.get('name', '').strip():
                ProductSize.objects.create(
                    profile=item,
                    name=sz['name'].strip(),
                    price=sz.get('price', 0),
                    sort_order=i,
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
        item = CustomerProfile.all_objects.get(id=item_id, tenant=tenant)
        data = json.loads(request.body)

        if 'name' in data:
            item.description = data['name'].strip()
        if 'description' in data:
            item.instruction = data['description'].strip()
        if 'price' in data:
            item.sales_price = data['price']
        if 'category' in data:
            item.category = data['category'].strip()
        if 'sort_order' in data:
            item.sort_order = data['sort_order']
        if 'is_available' in data:
            item.is_active = data['is_available']

        item.save()

        # Sync sizes if provided
        if 'sizes' in data:
            item.sizes.all().delete()
            for i, sz in enumerate(data['sizes']):
                if sz.get('name', '').strip():
                    ProductSize.objects.create(
                        profile=item,
                        name=sz['name'].strip(),
                        price=sz.get('price', 0),
                        sort_order=i,
                    )

        return JsonResponse({'success': True})
    except CustomerProfile.DoesNotExist:
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
        item = CustomerProfile.all_objects.get(id=item_id, tenant=tenant)
        item.delete()
        return JsonResponse({'success': True})
    except CustomerProfile.DoesNotExist:
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
        item = CustomerProfile.all_objects.get(id=item_id, tenant=tenant)
        image_file = request.FILES.get('image')
        if not image_file:
            return JsonResponse({'error': 'No image provided'}, status=400)

        # Auto-create a Product if the profile doesn't have one
        if not item.product:
            p = Product.all_objects.create(
                tenant=tenant,
                description=item.description,
                default_price=item.sales_price or 0,
            )
            item.product = p
            item.save(update_fields=['product'])

        # Upload to R2 as slot 1 (primary image)
        ProductImage.objects.filter(product=item.product, slot=1).delete()
        img = ProductImage.objects.create(product=item.product, slot=1, image=image_file)

        return JsonResponse({'success': True, 'image': img.image.url})
    except CustomerProfile.DoesNotExist:
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
            m.id: m for m in CustomerProfile.all_objects.filter(
                tenant=tenant, id__in=item_ids, is_active=True
            )
        }

        # Pre-load sizes for items that have size_id
        size_ids = [i.get('size_id') for i in items if i.get('size_id')]
        db_sizes = {}
        if size_ids:
            db_sizes = {s.id: s for s in ProductSize.objects.filter(id__in=size_ids, is_active=True)}

        total_cents = 0
        for cart_item in items:
            db_item = db_items.get(cart_item.get('id'))
            if db_item:
                qty = max(1, int(cart_item.get('quantity', 1)))
                # Use size price if a size was selected
                size = db_sizes.get(cart_item.get('size_id'))
                price = float(size.price) if size else float(db_item.sales_price or 0)
                total_cents += int(price * qty * 100)

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
            m.id: m for m in CustomerProfile.all_objects.filter(
                tenant=tenant, id__in=item_ids, is_active=True
            )
        }

        # Pre-load sizes for items that have size_id
        size_ids = [i.get('size_id') for i in items if i.get('size_id')]
        db_sizes = {}
        if size_ids:
            db_sizes = {s.id: s for s in ProductSize.objects.filter(id__in=size_ids, is_active=True)}

        order_items = []
        subtotal = 0
        for cart_item in items:
            db_item = db_items.get(cart_item.get('id'))
            if not db_item:
                continue
            qty = max(1, int(cart_item.get('quantity', 1)))
            # Use size price if a size was selected
            size = db_sizes.get(cart_item.get('size_id'))
            price = float(size.price) if size else float(db_item.sales_price or 0)
            size_name = size.name if size else ''
            line_total = price * qty
            subtotal += line_total
            item_entry = {
                'id': db_item.id,
                'name': db_item.description,
                'price': price,
                'quantity': qty,
                'subtotal': line_total,
            }
            if size_name:
                item_entry['size'] = size_name
                item_entry['size_id'] = size.id
            order_items.append(item_entry)

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

        # Send confirmation email
        if customer_email:
            try:
                _send_order_confirmation_email(request, order, tenant, slug)
            except Exception as e:
                logger.error(f"Failed to send confirmation email for order {order.id}: {e}")

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
def retail_orders_api(request):
    """List retail orders for the current tenant (used by View Orders page)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'orders': []})

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
def retail_order_update_status(request, order_id):
    """Update a retail order's status (used by View Orders page)."""
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        order = FishOrder.all_objects.get(id=order_id, tenant=tenant)
        data = json.loads(request.body)
        order.status = data.get('status', order.status)
        order.save()
        return JsonResponse({'success': True})
    except FishOrder.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)


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


# ── Email Helpers ────────────────────────────────────────────────────────────

def _send_order_confirmation_email(request, order, tenant, slug):
    """Send an order confirmation email with a status tracking link."""
    from django.core.mail import EmailMultiAlternatives

    status_url = request.build_absolute_uri(f'/fish-market/{slug}/order/{order.id}/status/')

    # Plain-text fallback
    items_text = ''
    for item in order.items_json:
        size = f" ({item['size']})" if item.get('size') else ''
        items_text += f"  - {item['quantity']}x {item['name']}{size}  ${item['subtotal']:.2f}\n"

    plain = (
        f"Hi {order.customer_name},\n\n"
        f"Thank you for your order from {tenant.name}!\n\n"
        f"Order #{order.id}\n"
        f"{items_text}\n"
        f"Total: ${float(order.subtotal):.2f}\n\n"
        f"Delivery Address: {order.customer_address}\n\n"
        f"Track your order status: {status_url}\n\n"
        f"Thank you for choosing {tenant.name}!"
    )

    # HTML email
    items_html = ''
    for item in order.items_json:
        size = f' <span style="color:#b8960c;">({item["size"]})</span>' if item.get('size') else ''
        items_html += (
            f'<tr>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eee;font-size:14px;color:#1a1a2e;">'
            f'{item["name"]}{size}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:center;font-size:14px;color:#1a1a2e;">'
            f'{item["quantity"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #eee;text-align:right;font-size:14px;color:#1a1a2e;">'
            f'${item["subtotal"]:.2f}</td>'
            f'</tr>'
        )

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:system-ui,-apple-system,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:30px 0;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- Header -->
  <tr><td style="background:#1a1a2e;padding:30px 40px;text-align:center;">
    <h1 style="margin:0;color:#d4af37;font-size:24px;font-weight:700;letter-spacing:1px;">{tenant.name}</h1>
  </td></tr>

  <!-- Gold accent bar -->
  <tr><td style="background:#d4af37;height:4px;"></td></tr>

  <!-- Confirmation badge -->
  <tr><td style="padding:30px 40px 10px;text-align:center;">
    <div style="display:inline-block;background:#1a1a2e;color:#d4af37;font-size:13px;font-weight:700;letter-spacing:2px;text-transform:uppercase;padding:8px 24px;border-radius:50px;">Order Confirmed</div>
  </td></tr>

  <!-- Greeting -->
  <tr><td style="padding:20px 40px 5px;text-align:center;">
    <p style="margin:0;font-size:16px;color:#1a1a2e;">Hi <strong>{order.customer_name}</strong>,</p>
    <p style="margin:8px 0 0;font-size:14px;color:#666;">Thank you for your order! Here are the details.</p>
  </td></tr>

  <!-- Order number -->
  <tr><td style="padding:20px 40px 10px;text-align:center;">
    <span style="font-size:13px;color:#999;text-transform:uppercase;letter-spacing:1px;">Order Number</span><br>
    <span style="font-size:28px;font-weight:700;color:#1a1a2e;">#{order.id}</span>
  </td></tr>

  <!-- Items table -->
  <tr><td style="padding:10px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      <tr style="background:#1a1a2e;">
        <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#d4af37;text-transform:uppercase;letter-spacing:1px;">Item</td>
        <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#d4af37;text-transform:uppercase;letter-spacing:1px;text-align:center;">Qty</td>
        <td style="padding:10px 12px;font-size:12px;font-weight:700;color:#d4af37;text-transform:uppercase;letter-spacing:1px;text-align:right;">Price</td>
      </tr>
      {items_html}
    </table>
  </td></tr>

  <!-- Total -->
  <tr><td style="padding:15px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="font-size:16px;font-weight:700;color:#1a1a2e;">Total</td>
        <td style="font-size:22px;font-weight:700;color:#d4af37;text-align:right;">${float(order.subtotal):.2f}</td>
      </tr>
    </table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #eee;margin:5px 0;"></td></tr>

  <!-- Delivery address -->
  <tr><td style="padding:15px 40px;">
    <p style="margin:0 0 4px;font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;">Delivery Address</p>
    <p style="margin:0;font-size:14px;color:#1a1a2e;">{order.customer_address}</p>
  </td></tr>

  <!-- Track button -->
  <tr><td style="padding:25px 40px;text-align:center;">
    <a href="{status_url}" style="display:inline-block;background:#d4af37;color:#1a1a2e;font-size:14px;font-weight:700;text-decoration:none;padding:14px 40px;border-radius:50px;letter-spacing:0.5px;text-transform:uppercase;">Track Your Order</a>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#1a1a2e;padding:20px 40px;text-align:center;">
    <p style="margin:0;font-size:12px;color:#888;">Thank you for choosing <span style="color:#d4af37;">{tenant.name}</span></p>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>'''

    msg = EmailMultiAlternatives(
        subject=f"Order #{order.id} Confirmed — {tenant.name}",
        body=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.customer_email],
    )
    msg.attach_alternative(html, "text/html")
    msg.send(fail_silently=False)
