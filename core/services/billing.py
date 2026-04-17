import datetime

import stripe
from django.conf import settings
from django.utils import timezone

from core.models import Tenant, TenantBillingProfile


def billing_is_configured():
    return bool(
        getattr(settings, "STRIPE_SECRET_KEY", "").strip()
        and getattr(settings, "STRIPE_PRICE_ID", "").strip()
    )


def _to_datetime(timestamp):
    if not timestamp:
        return None
    return datetime.datetime.fromtimestamp(int(timestamp), tz=datetime.timezone.utc)


def _stripe_object_get(obj, key, default=None):
    if not obj:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _ensure_api_key():
    secret_key = getattr(settings, "STRIPE_SECRET_KEY", "").strip()
    if not secret_key:
        raise ValueError("Stripe billing is not configured.")
    stripe.api_key = secret_key


def _latest_sessions_by_tenant_id(limit=100):
    sessions_by_tenant_id = {}
    sessions = stripe.checkout.Session.list(limit=limit)
    for item in _stripe_object_get(sessions, "data", []):
        metadata = _stripe_object_get(item, "metadata", {}) or {}
        tenant_id = str(metadata.get("tenant_id", "")).strip()
        if not tenant_id:
            continue
        current = sessions_by_tenant_id.get(tenant_id)
        if current is None or (_stripe_object_get(item, "created") or 0) > (_stripe_object_get(current, "created") or 0):
            sessions_by_tenant_id[tenant_id] = item
    return sessions_by_tenant_id


def sync_billing_profile_from_checkout_session(session_id):
    if not session_id:
        return None

    _ensure_api_key()
    session = stripe.checkout.Session.retrieve(
        session_id,
        expand=["subscription", "customer", "subscription.latest_invoice"],
    )
    tenant_id = ((_stripe_object_get(session, "metadata", {}) or {}).get("tenant_id") or "").strip()
    if not tenant_id:
        return None
    tenant = Tenant.objects.filter(id=tenant_id).first()
    if not tenant:
        return None
    return sync_billing_profile_for_tenant(
        tenant,
        session=session,
        customer=_stripe_object_get(session, "customer"),
        subscription=_stripe_object_get(session, "subscription"),
    )


def sync_billing_profile_for_tenant(tenant, session=None, customer=None, subscription=None, recent_session=None):
    _ensure_api_key()

    profile, _ = TenantBillingProfile.objects.get_or_create(tenant=tenant)

    if session is None and profile.last_checkout_session_id:
        try:
            session = stripe.checkout.Session.retrieve(
                profile.last_checkout_session_id,
                expand=["subscription", "customer", "subscription.latest_invoice"],
            )
        except Exception:
            session = None

    if session:
        profile.last_checkout_session_id = _stripe_object_get(session, "id", "") or profile.last_checkout_session_id
        profile.last_checkout_completed_at = _to_datetime(_stripe_object_get(session, "created"))
        if customer is None:
            customer = _stripe_object_get(session, "customer")
        if subscription is None:
            subscription = _stripe_object_get(session, "subscription")

    if isinstance(customer, str) and customer:
        customer = stripe.Customer.retrieve(customer)
    if isinstance(subscription, str) and subscription:
        subscription = stripe.Subscription.retrieve(subscription, expand=["latest_invoice"])

    if not session and not subscription:
        latest_match = recent_session
        if latest_match:
            session = stripe.checkout.Session.retrieve(
                _stripe_object_get(latest_match, "id"),
                expand=["subscription", "customer", "subscription.latest_invoice"],
            )
            profile.last_checkout_session_id = _stripe_object_get(session, "id", "") or profile.last_checkout_session_id
            profile.last_checkout_completed_at = _to_datetime(_stripe_object_get(session, "created"))
            customer = _stripe_object_get(session, "customer")
            subscription = _stripe_object_get(session, "subscription")

    if isinstance(customer, str) and customer:
        customer = stripe.Customer.retrieve(customer)
    if isinstance(subscription, str) and subscription:
        subscription = stripe.Subscription.retrieve(subscription, expand=["latest_invoice"])

    latest_invoice = _stripe_object_get(subscription, "latest_invoice")
    if isinstance(latest_invoice, str) and latest_invoice:
        latest_invoice = stripe.Invoice.retrieve(latest_invoice)

    profile.stripe_customer_id = _stripe_object_get(customer, "id", "") or profile.stripe_customer_id
    profile.customer_email = _stripe_object_get(customer, "email", "") or _stripe_object_get(session, "customer_email", "") or profile.customer_email
    profile.stripe_subscription_id = _stripe_object_get(subscription, "id", "") or profile.stripe_subscription_id
    profile.stripe_price_id = (
        (((_stripe_object_get(subscription, "items", {}) or {}).get("data") or [{}])[0].get("price", {}) or {}).get("id", "")
        if isinstance(_stripe_object_get(subscription, "items", {}), dict)
        else profile.stripe_price_id
    ) or profile.stripe_price_id
    profile.subscription_status = _stripe_object_get(subscription, "status", "") or profile.subscription_status or "unknown"
    profile.current_period_end = _to_datetime(_stripe_object_get(subscription, "current_period_end"))
    profile.cancel_at = _to_datetime(_stripe_object_get(subscription, "cancel_at"))
    profile.canceled_at = _to_datetime(_stripe_object_get(subscription, "canceled_at"))
    profile.latest_invoice_id = _stripe_object_get(latest_invoice, "id", "") or profile.latest_invoice_id
    profile.latest_invoice_status = _stripe_object_get(latest_invoice, "status", "") or profile.latest_invoice_status
    profile.latest_invoice_amount_due = _stripe_object_get(latest_invoice, "amount_due", None)
    profile.latest_invoice_amount_paid = _stripe_object_get(latest_invoice, "amount_paid", None)
    profile.latest_invoice_currency = (_stripe_object_get(latest_invoice, "currency", "") or profile.latest_invoice_currency or "").upper()
    profile.latest_invoice_created_at = _to_datetime(_stripe_object_get(latest_invoice, "created"))
    profile.save()
    return profile


def system_admin_billing_rows():
    rows = []
    configured = billing_is_configured()
    latest_sessions = {}

    if configured:
        try:
            _ensure_api_key()
            latest_sessions = _latest_sessions_by_tenant_id()
        except Exception:
            latest_sessions = {}

    for tenant in Tenant.objects.all().order_by("name"):
        profile = TenantBillingProfile.objects.filter(tenant=tenant).first()
        sync_error = ""

        if configured:
            try:
                profile = sync_billing_profile_for_tenant(
                    tenant,
                    recent_session=latest_sessions.get(str(tenant.id)),
                )
            except Exception as exc:
                sync_error = str(exc)

        amount_paid_display = "--"
        amount_due_display = "--"
        if profile:
            amount_paid_display = format_money_from_cents(profile.latest_invoice_amount_paid, profile.latest_invoice_currency or "USD")
            amount_due_display = format_money_from_cents(profile.latest_invoice_amount_due, profile.latest_invoice_currency or "USD")

        rows.append({
            "tenant": tenant,
            "profile": profile,
            "user_count": tenant.tenantuser_set.count(),
            "admin_count": tenant.tenantuser_set.filter(is_admin=True).count(),
            "sync_error": sync_error,
            "amount_paid_display": amount_paid_display,
            "amount_due_display": amount_due_display,
        })
    return rows


def format_money_from_cents(amount_cents, currency="USD"):
    if amount_cents in (None, ""):
        return "--"
    return f"{currency.upper()} {(amount_cents or 0) / 100:,.2f}"
