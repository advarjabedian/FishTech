import json
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Tenant


def _import_stripe():
    try:
        import stripe
    except ImportError:
        return None

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _stripe_ready():
    return bool(settings.STRIPE_SECRET_KEY)


def _subscription_status_from_stripe(status):
    mapping = {
        "active": "active",
        "trialing": "trialing",
        "past_due": "past_due",
        "unpaid": "unpaid",
        "canceled": "canceled",
        "incomplete_expired": "canceled",
    }
    return mapping.get(status, "past_due")


def _from_unix_timestamp(value):
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=dt_timezone.utc)


def _sync_tenant_subscription(tenant, subscription_obj, customer_id=None):
    tenant.stripe_customer_id = customer_id or getattr(subscription_obj, "customer", "") or tenant.stripe_customer_id
    tenant.stripe_subscription_id = getattr(subscription_obj, "id", "") or tenant.stripe_subscription_id
    tenant.subscription_status = _subscription_status_from_stripe(getattr(subscription_obj, "status", ""))
    tenant.trial_ends_at = _from_unix_timestamp(getattr(subscription_obj, "trial_end", None))
    tenant.subscription_ends_at = _from_unix_timestamp(getattr(subscription_obj, "current_period_end", None))
    tenant.save(
        update_fields=[
            "stripe_customer_id",
            "stripe_subscription_id",
            "subscription_status",
            "trial_ends_at",
            "subscription_ends_at",
        ]
    )


def _get_or_create_customer(stripe, tenant, email):
    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id

    customer = stripe.Customer.create(
        name=tenant.name,
        email=email or None,
        metadata={"tenant_id": str(tenant.id), "tenant_name": tenant.name},
    )
    tenant.stripe_customer_id = customer.id
    tenant.save(update_fields=["stripe_customer_id"])
    return customer.id


def _build_checkout_line_item():
    if settings.STRIPE_PRICE_ID:
        return {"price": settings.STRIPE_PRICE_ID, "quantity": 1}

    return {
        "price_data": {
            "currency": settings.STRIPE_CURRENCY,
            "unit_amount": settings.STRIPE_MONTHLY_PRICE_CENTS,
            "recurring": {"interval": "month"},
            "product_data": {
                "name": "FishTeck Subscription",
                "description": "Monthly access to FishTeck operations and traceability",
            },
        },
        "quantity": 1,
    }


@login_required
def billing_page(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return redirect("home")

    checkout_state = request.GET.get("checkout")
    portal_state = request.GET.get("portal")
    if checkout_state == "success":
        messages.success(request, "Subscription checkout completed. Billing status will update shortly.")
    elif portal_state == "return":
        messages.success(request, "Billing portal closed.")

    return render(
        request,
        "core/billing.html",
        {
            "tenant": tenant,
            "billing_ready": _stripe_ready(),
            "monthly_price": settings.STRIPE_MONTHLY_PRICE_CENTS / 100,
            "billing_enforced": settings.ENFORCE_SUBSCRIPTION_BILLING,
        },
    )


@login_required
@require_POST
def billing_checkout(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return redirect("home")

    if not _stripe_ready():
        messages.error(request, "Stripe billing is not configured yet.")
        return redirect("billing_page")

    stripe = _import_stripe()
    if stripe is None:
        messages.error(request, "Stripe package is not installed on this environment yet.")
        return redirect("billing_page")

    customer_id = _get_or_create_customer(stripe, tenant, request.user.email)
    success_url = request.build_absolute_uri(f"{reverse('billing_page')}?checkout=success")
    cancel_url = request.build_absolute_uri(reverse("billing_page"))

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(tenant.id),
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[_build_checkout_line_item()],
        metadata={"tenant_id": str(tenant.id)},
        subscription_data={"metadata": {"tenant_id": str(tenant.id)}},
    )
    return redirect(session.url, permanent=False)


@login_required
@require_POST
def billing_portal(request):
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return redirect("home")

    if not _stripe_ready():
        messages.error(request, "Stripe billing is not configured yet.")
        return redirect("billing_page")

    if not tenant.stripe_customer_id:
        messages.error(request, "No Stripe customer is linked to this account yet.")
        return redirect("billing_page")

    stripe = _import_stripe()
    if stripe is None:
        messages.error(request, "Stripe package is not installed on this environment yet.")
        return redirect("billing_page")

    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=request.build_absolute_uri(f"{reverse('billing_page')}?portal=return"),
    )
    return redirect(session.url, permanent=False)


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    if not _stripe_ready():
        return JsonResponse({"ok": False, "error": "Stripe not configured"}, status=503)

    stripe = _import_stripe()
    if stripe is None:
        return JsonResponse({"ok": False, "error": "Stripe package missing"}, status=503)

    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(
                values=json.loads(payload.decode("utf-8")),
                key=settings.STRIPE_SECRET_KEY,
            )
    except Exception:
        return HttpResponseBadRequest("Invalid payload")

    data = event["data"]["object"]
    event_type = event["type"]
    tenant = None
    tenant_id = None
    customer_id = data.get("customer")
    subscription_id = data.get("subscription") or data.get("id")

    tenant_id = data.get("metadata", {}).get("tenant_id") or data.get("client_reference_id")

    if tenant_id:
        tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant and customer_id:
        tenant = Tenant.objects.filter(stripe_customer_id=customer_id).first()
    if not tenant and subscription_id:
        tenant = Tenant.objects.filter(stripe_subscription_id=subscription_id).first()

    if not tenant:
        return JsonResponse({"ok": True, "ignored": True})

    if event_type == "checkout.session.completed":
        tenant.stripe_customer_id = customer_id or tenant.stripe_customer_id
        if subscription_id:
            tenant.stripe_subscription_id = subscription_id
        if tenant.subscription_status in {"canceled", "past_due", "unpaid"}:
            tenant.subscription_status = "active"
        tenant.save(update_fields=["stripe_customer_id", "stripe_subscription_id", "subscription_status"])
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        _sync_tenant_subscription(tenant, data, customer_id=customer_id)
    elif event_type == "customer.subscription.deleted":
        tenant.subscription_status = "canceled"
        tenant.subscription_ends_at = timezone.now()
        tenant.save(update_fields=["subscription_status", "subscription_ends_at"])
    elif event_type == "invoice.payment_failed":
        tenant.subscription_status = "past_due"
        tenant.save(update_fields=["subscription_status"])
    elif event_type == "invoice.paid" and tenant.subscription_status != "trialing":
        tenant.subscription_status = "active"
        tenant.save(update_fields=["subscription_status"])

    return JsonResponse({"ok": True})
