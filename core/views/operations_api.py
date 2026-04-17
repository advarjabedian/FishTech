import csv
import io
import json
from decimal import Decimal

from django.contrib.auth.models import User as DjangoUser
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import constants as C
from core.models import (
    Customer,
    Inventory,
    InventoryAdjustment,
    ItemGroup,
    ProcessBatch,
    ProcessBatchOutput,
    ProcessBatchSource,
    ProcessBatchWaste,
    Product,
    ProductImage,
    PurchaseOrder,
    PurchaseOrderItem,
    ReceivingQualityCheck,
    CustomerProfile,
    SalesOrder,
    SalesOrderAllocation,
    SalesOrderItem,
    TenantUser,
    Vendor,
    ProcessBatchOutput,
)


def _tenant(request):
    return getattr(request, "tenant", None)


def _require_tenant(request):
    tenant = _tenant(request)
    if not tenant:
        return None, JsonResponse({"error": "No tenant context"}, status=400)
    return tenant, None


def _require_tenant_admin(request, tenant):
    tenant_user = TenantUser.objects.filter(tenant=tenant, user=request.user).first()
    if not tenant_user or not tenant_user.is_admin:
        return JsonResponse({"error": "Admin access is required."}, status=403)
    return None


def _restore_and_delete_process_batch(batch):
    tenant = batch.tenant

    for source in batch.sources.select_related("inventory").all():
        if source.inventory_id and source.inventory:
            source.inventory.unitsonhand = (source.inventory.unitsonhand or 0) + source.quantity
            source.inventory.save(update_fields=["unitsonhand"])

    output_inventory_ids = [output.inventory_id for output in batch.outputs.all() if output.inventory_id]
    if output_inventory_ids:
        SalesOrderAllocation.objects.filter(tenant=tenant, inventory_id__in=output_inventory_ids).delete()
        Inventory.objects.filter(tenant=tenant, id__in=output_inventory_ids).delete()

    batch.sources.all().delete()
    batch.outputs.all().delete()
    batch.waste_entries.all().delete()
    batch.delete()


def _lot_qc_status(lot):
    try:
        return lot.quality_check.status
    except Exception:
        return "pending"


def _to_float(value):
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _to_str(value):
    return "" if value is None else str(value)


def _date_str(value):
    return value.strftime("%Y-%m-%d") if value else ""


def _time_str(value):
    if not value:
        return ""
    hour = value.hour
    minute = value.minute
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix}"


def _parse_json(request):
    if not request.body:
        return {}
    return json.loads(request.body)


def _ensure_products_for_inventory_lots(tenant):
    existing_product_ids = set(
        Product.objects.filter(tenant=tenant)
        .exclude(product_id="")
        .values_list("product_id", flat=True)
    )
    orphan_lots = (
        Inventory.objects.filter(tenant=tenant, unitsonhand__gt=0)
        .exclude(productid="")
        .exclude(productid__in=existing_product_ids)
        .values("productid", "desc", "unittype")
        .distinct()
    )
    for lot in orphan_lots:
        product_id = (lot.get("productid") or "").strip()
        if not product_id:
            continue
        name = (lot.get("desc") or product_id).strip()
        Product.objects.create(
            tenant=tenant,
            is_active=True,
            product_id=product_id,
            description=name,
            item_name=name,
            unit_type=(lot.get("unittype") or "").strip(),
        )
        existing_product_ids.add(product_id)


def _paginate(request, queryset, default_page_size=100):
    page = max(int(request.GET.get("page", 1) or 1), 1)
    page_size = max(int(request.GET.get("page_size", default_page_size) or default_page_size), 1)
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    return queryset[start:end], total


def _po_to_dict(order):
    item_rows = [item for item in order.items.all() if item.item_type == "item"]
    expected = getattr(order, "expected_total", None)
    if expected is None:
        expected = sum((item.quantity or 0) for item in item_rows)
    arrived = sum((item.received_quantity or 0) for item in item_rows)
    total = getattr(order, "order_total", None)
    if total is None:
        total = order.total or 0
    vendor_type = ""
    if order.vendor_id and order.vendor:
        vendor_type = order.vendor.vendor_type or ""
    unit_types = sorted(set(filter(None, [
        (item.unit_type or (item.product.unit_type if item.product_id and item.product else ""))
        for item in item_rows
    ])))
    any_received = any((item.received_quantity or 0) > 0 for item in item_rows)
    all_received = bool(item_rows) and all((item.received_quantity or 0) >= (item.quantity or 0) for item in item_rows)
    derived_receive_status = "received" if all_received else ("partial" if any_received else "not_received")
    receive_status = derived_receive_status if item_rows else order.receive_status
    receive_status_display = {
        "not_received": "Not Received",
        "partial": "Partial",
        "received": "Received",
    }.get(receive_status, receive_status.replace("_", " ").title())
    return {
        "id": order.id,
        "po_number": order.po_number,
        "order_status": order.order_status,
        "order_status_display": order.get_order_status_display(),
        "receive_status": receive_status,
        "receive_status_display": receive_status_display,
        "qb_po_number": order.qb_po_number,
        "vendor_name": order.vendor_name,
        "vendor_type": vendor_type,
        "buyer": order.buyer,
        "total": _to_float(total) or 0,
        "expected": _to_float(expected) or 0,
        "arrived": _to_float(arrived) or 0,
        "unit_type": ", ".join(unit_types) or "",
        "order_date": _date_str(order.order_date),
        "expected_date": _date_str(order.expected_date),
        "products": ", ".join(sorted(set(filter(None, (
            (item.product.species or item.product.item_name or "") if item.product else item.description
            for item in order.items.all() if item.item_type == "item"
        ))))) or "",
    }


def _product_to_dict(product, totals=None):
    totals = totals or {}
    display_name = product.description or product.item_name or product.friendly_name or product.qb_item_name or product.product_id
    return {
        "id": product.id,
        "product_id": product.product_id,
        "item_name": product.item_name or product.description or product.product_id,
        "display_name": display_name,
        "item_group": product.item_group.name if product.item_group_id and product.item_group else "",
        "item_group_id": product.item_group_id,
        "qb_item_name": product.qb_item_name or "",
        "friendly_name": product.friendly_name or "",
        "description": product.description or "",
        "size_cull": product.size_cull or "",
        "sku": product.sku or "",
        "tasting_notes": product.tasting_notes or "",
        "quantity_description": product.quantity_description or "",
        "country_of_origin": product.country_of_origin or "",
        "origin": product.origin or "",
        "brand": product.brand or "",
        "inventory_unit_of_measure": product.inventory_unit_of_measure or product.unit_type or "",
        "unit_type": product.inventory_unit_of_measure or product.unit_type or "",
        "selling_unit_of_measure": product.selling_unit_of_measure or "",
        "buying_unit_of_measure": product.buying_unit_of_measure or "",
        "raw_cost": _to_float(product.raw_cost),
        "list_price": _to_float(product.list_price),
        "wholesale_price": _to_float(product.wholesale_price),
        "habitat_production_method": product.habitat_production_method or "",
        "species": product.species or "",
        "department": product.department or "",
        "upc": product.upc or "",
        "is_active": product.is_active,
        "expected": _to_float(totals.get("expected")) or 0,
        "allocated": _to_float(totals.get("allocated")) or 0,
        "on_hand": _to_float(totals.get("on_hand")) or 0,
    }


def _next_product_id(tenant):
    existing_ids = Product.objects.filter(tenant=tenant).values_list("product_id", flat=True)
    highest = 0
    for value in existing_ids:
        if not value:
            continue
        value = str(value).strip()
        if not value.startswith("ITEM-"):
            continue
        suffix = value[5:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"ITEM-{highest + 1:04d}"


def _sales_order_total(order):
    total = getattr(order, "order_total", None)
    if total is None:
        total = order.items.aggregate(total=Sum("amount"))["total"]
    return _to_float(total) or 0


def _filter_sales_orders_for_shipping(request, queryset):
    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(order_number__icontains=search)
            | Q(customer_name__icontains=search)
            | Q(shipper__icontains=search)
            | Q(shipping_route__icontains=search)
        )

    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if date_from:
        queryset = queryset.filter(ship_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(ship_date__lte=date_to)
    return queryset


def _sales_item_name(item):
    if item.description:
        return item.description
    if item.product_id and item.product:
        return item.product.description or item.product.item_name or item.product.product_id
    return ""


def _selected_source_lot_ids(data):
    raw = data.get("process_source_lot_ids")
    if raw in (None, ""):
        return []
    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw).split(",")
    lot_ids = []
    for value in values:
        try:
            lot_ids.append(int(str(value).strip()))
        except Exception:
            continue
    return list(dict.fromkeys(lot_ids))


def _rollback_process_batch(batch):
    source_rows = list(batch.sources.select_related("inventory").all())
    output_inventory_ids = [output.inventory_id for output in batch.outputs.all() if output.inventory_id]

    for source in source_rows:
        if not source.inventory_id or not source.inventory:
            continue
        source.inventory.unitsonhand = (source.inventory.unitsonhand or 0) + (source.quantity or 0)
        source.inventory.unitsavailable = (source.inventory.unitsavailable or 0) + (source.quantity or 0)
        source.inventory.save(update_fields=["unitsonhand", "unitsavailable"])

    if output_inventory_ids:
        Inventory.objects.filter(id__in=output_inventory_ids).delete()

    batch.delete()


def _create_processing_batch_for_sales_item(request, tenant, sales_item, data):
    process_type = (data.get("process_type") or "").strip()
    if not process_type or sales_item.item_type != "item":
        return None

    lot_ids = _selected_source_lot_ids(data)
    if not lot_ids:
        raise ValueError("Choose at least one source lot for processed sales items.")

    requested_qty = Decimal(str(sales_item.quantity or 0))
    if requested_qty <= 0:
        raise ValueError("Processed sales items need a quantity greater than zero.")
    if not sales_item.product_id or not sales_item.product or not sales_item.product.product_id:
        raise ValueError("Choose a product before processing this sales item.")

    lot_map = {
        lot.id: lot for lot in Inventory.objects.filter(tenant=tenant, id__in=lot_ids, unitsonhand__gt=0)
    }
    selected_lots = [lot_map[lot_id] for lot_id in lot_ids if lot_id in lot_map]
    if not selected_lots:
        raise ValueError("Selected source lots are not available.")

    remaining = requested_qty
    source_payloads = []
    for lot in selected_lots:
        available = Decimal(str(lot.unitsonhand or 0))
        if available <= 0:
            continue
        take = min(available, remaining)
        if take <= 0:
            continue
        source_payloads.append({
            "inventory": lot,
            "quantity": take,
            "unit_type": (lot.unittype or sales_item.unit_type or "").strip(),
        })
        remaining -= take
        if remaining <= 0:
            break

    if remaining > 0:
        raise ValueError("Not enough quantity in the selected source lots to cover this sale.")

    last = ProcessBatch.objects.filter(tenant=tenant).order_by("-id").first()
    next_num = (last.id + 1) if last else 1
    batch_number = f"PB-{next_num:04d}"
    batch = ProcessBatch.objects.create(
        tenant=tenant,
        batch_number=batch_number,
        process_type=process_type,
        status="completed",
        completed_at=timezone.now(),
        notes=f"Created from sales order {sales_item.sales_order.order_number}",
        created_by=request.user,
    )

    for source in source_payloads:
        lot = source["inventory"]
        ProcessBatchSource.objects.create(
            tenant=tenant,
            batch=batch,
            inventory=lot,
            quantity=source["quantity"],
            unit_type=source["unit_type"],
        )
        lot.unitsonhand = max(Decimal("0"), (lot.unitsonhand or 0) - source["quantity"])
        lot.unitsavailable = max(Decimal("0"), (lot.unitsavailable or 0) - source["quantity"])
        lot.save(update_fields=["unitsonhand", "unitsavailable"])

    output_inventory = Inventory.objects.create(
        tenant=tenant,
        productid=sales_item.product.product_id,
        desc=sales_item.description or sales_item.product.description or sales_item.product.item_name or sales_item.product.product_id,
        vendorid=selected_lots[0].vendorid if selected_lots else "",
        vendorlot=f"LOT-{batch.batch_number}-{sales_item.id}",
        unittype=(sales_item.unit_type or selected_lots[0].unittype if selected_lots else "").strip(),
        unitsonhand=requested_qty,
        unitsavailable=requested_qty,
        unitsin=requested_qty,
        receivedate=timezone.now().date().isoformat(),
        vendor_type=selected_lots[0].vendor_type if selected_lots else "",
        purchase_order=selected_lots[0].purchase_order if selected_lots and hasattr(selected_lots[0], "purchase_order") else None,
    )
    ProcessBatchOutput.objects.create(
        tenant=tenant,
        batch=batch,
        inventory=output_inventory,
        product=sales_item.product,
        quantity=requested_qty,
        unit_type=sales_item.unit_type or output_inventory.unittype,
        lot_id=output_inventory.vendorlot,
        yield_percent=Decimal("100"),
    )
    SalesOrderAllocation.objects.create(
        tenant=tenant,
        sales_order_item=sales_item,
        inventory=output_inventory,
        quantity=requested_qty,
        unit_type=sales_item.unit_type or output_inventory.unittype,
        allocated_by=request.user,
        allocated_by_name=request.user.get_full_name() or request.user.username,
    )
    sales_item.process_batch = batch
    sales_item.save(update_fields=["process_batch"])
    batch.calculate_yield()
    batch.save(update_fields=["total_input_weight", "total_output_weight", "actual_yield_pct", "expected_yield_pct", "yield_variance_pct", "yield_flagged"])
    return batch


def _sales_item_spec(item):
    if item.product_id and item.product:
        return " · ".join(filter(None, [item.product.quantity_description or "", item.product.size_cull or ""]))
    return ""


def _packed_status_display(value):
    mapping = {
        "not_packed": "Not Packed",
        "packed": "Packed",
        "need_to_send": "Need To Send",
        "partial": "Partial",
    }
    return mapping.get(value, value.replace("_", " ").title())


def _po_item_to_dict(item):
    product_id = ""
    if item.product_id and item.product:
        product_id = item.product.product_id
    return {
        "id": item.id,
        "item_type": item.item_type,
        "product_id": product_id,
        "description": item.description or (item.product.item_name if item.product_id and item.product else ""),
        "notes": item.notes or "",
        "quantity": _to_float(item.quantity),
        "ordered_qty": _to_float(item.quantity) or 0,
        "received_qty": _to_float(item.received_quantity) or 0,
        "remaining_qty": _to_float(item.remaining_quantity) or 0,
        "unit_type": item.unit_type or (item.product.unit_type if item.product_id and item.product else ""),
        "unit_price": _to_float(item.unit_price) or 0,
        "amount": _to_float(item.amount) or 0,
    }


def _quality_to_dict(check):
    if not check:
        return None
    return {
        "freshness_score": check.freshness_score,
        "appearance_ok": check.appearance_ok,
        "odor_ok": check.odor_ok,
        "texture_ok": check.texture_ok,
        "packaging_ok": check.packaging_ok,
        "temp_ok": check.temp_ok,
        "status": check.status,
        "status_display": check.get_status_display(),
        "notes": check.notes or "",
        "checked_by": check.checked_by_name or (check.checked_by.get_username() if check.checked_by else ""),
        "checked_at": check.checked_at.strftime("%Y-%m-%d %I:%M %p") if check.checked_at else "",
    }


@login_required
def purchasing_orders(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = (
        PurchaseOrder.objects.filter(tenant=tenant)
        .select_related("vendor")
        .prefetch_related("items__product")
        .annotate(
            order_total=Sum("items__amount"),
            expected_total=Sum("items__quantity", filter=Q(items__item_type="item")),
        )
    )

    search = request.GET.get("search", "").strip()
    if search:
        orders = orders.filter(
            Q(po_number__icontains=search)
            | Q(vendor_name__icontains=search)
            | Q(qb_po_number__icontains=search)
            | Q(buyer__icontains=search)
        )

    for key, lookup in {
        "vendor": "vendor_name__iexact",
        "vendor_type": "vendor__vendor_type__iexact",
        "buyer": "buyer__iexact",
        "order_status": "order_status",
        "receive_status": "receive_status",
    }.items():
        value = request.GET.get(key, "").strip()
        if value:
            orders = orders.filter(**{lookup: value})

    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    expected_from = request.GET.get("expected_from", "").strip()
    expected_to = request.GET.get("expected_to", "").strip()
    if date_from:
        orders = orders.filter(order_date__gte=date_from)
    if date_to:
        orders = orders.filter(order_date__lte=date_to)
    if expected_from:
        orders = orders.filter(expected_date__gte=expected_from)
    if expected_to:
        orders = orders.filter(expected_date__lte=expected_to)

    orders = orders.order_by("-order_date", "-created_at")
    paged, total = _paginate(request, orders)
    return JsonResponse({"orders": [_po_to_dict(order) for order in paged], "total": total})


@login_required
def shipping_log(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = SalesOrder.objects.filter(tenant=tenant).annotate(order_total=Sum("items__amount"))
    orders = _filter_sales_orders_for_shipping(request, orders).order_by("-ship_date", "-created_at")
    paged, total = _paginate(request, orders)
    return JsonResponse(
        {
            "orders": [
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer": order.customer_name or "",
                    "ship_date": _date_str(order.ship_date),
                    "shipper": order.shipper or "",
                    "shipping_route": order.shipping_route or "",
                    "packed_status": order.packed_status,
                    "packed_status_display": order.get_packed_status_display(),
                    "total": _sales_order_total(order),
                }
                for order in paged
            ],
            "total": total,
        }
    )


@login_required
def operations_summary(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    sales = SalesOrder.objects.filter(tenant=tenant)
    purchases = PurchaseOrder.objects.filter(tenant=tenant)
    inventory = Inventory.objects.filter(tenant=tenant, unitsonhand__gt=0)

    return JsonResponse(
        {
            "open_sales_orders": sales.filter(order_status__in=["open", "needs_review"]).count(),
            "pending_shipments": sales.exclude(order_status__in=["closed", "cancelled"]).exclude(packed_status="packed").count(),
            "open_purchase_orders": purchases.filter(order_status__in=["open", "draft"]).count(),
            "items_in_stock": inventory.values("productid").exclude(productid="").distinct().count(),
        }
    )


@login_required
def shipping_picking(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = SalesOrder.objects.filter(tenant=tenant).prefetch_related(
        "items__product",
        "items__allocations__inventory",
    )
    orders = _filter_sales_orders_for_shipping(request, orders)
    sort = request.GET.get("sort", "department")
    search = request.GET.get("search", "").strip().lower()

    departments = {}
    for order in orders:
        for item in order.items.all():
            item_name = _sales_item_name(item)
            department = item.product.department if item.product_id and item.product and item.product.department else "Unassigned"
            fifo_lots = [
                allocation.inventory.vendorlot or f"LOT-{allocation.inventory_id}"
                for allocation in item.allocations.select_related("inventory").all()
                if allocation.inventory_id
            ]
            row = {
                "item_name": item_name,
                "order_number": order.order_number,
                "so_id": order.id,
                "fifo_lots": fifo_lots,
                "quantity": _to_float(item.quantity) or 0,
                "unit_type": item.unit_type or (item.product.unit_type if item.product_id and item.product else ""),
            }
            haystack = " ".join([department, item_name, order.order_number, order.customer_name or ""]).lower()
            if search and search not in haystack:
                continue
            departments.setdefault(department, []).append(row)

    department_names = sorted(departments.keys(), reverse=(sort == "department_desc"))
    payload = [{"department": name, "items": departments[name]} for name in department_names]
    return JsonResponse({"departments": payload, "total_departments": len(payload)})


@login_required
def shipping_packing(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = SalesOrder.objects.filter(tenant=tenant).prefetch_related("items__product")
    orders = _filter_sales_orders_for_shipping(request, orders)
    sort = request.GET.get("sort", "old_to_new")
    search = request.GET.get("search", "").strip().lower()
    orders = orders.order_by("ship_date" if sort == "old_to_new" else "-ship_date", "order_number")

    payload = []
    for order in orders:
        order_haystack = f"{order.order_number} {order.customer_name or ''}".lower()
        items = []
        for item in order.items.all():
            item_name = _sales_item_name(item)
            packed_status = "packed" if order.packed_status == "packed" else ("partial" if order.packed_status == "need_to_send" else "not_packed")
            item_haystack = f"{order_haystack} {item_name} {item.notes or ''}".lower()
            if search and search not in item_haystack:
                continue
            items.append(
                {
                    "item_name": item_name,
                    "notes": item.notes or "",
                    "quantity": _to_float(item.quantity) or 0,
                    "unit_type": item.unit_type or (item.product.unit_type if item.product_id and item.product else ""),
                    "packed_status": packed_status,
                    "packed_status_display": _packed_status_display(packed_status),
                }
            )
        if items:
            payload.append(
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer": order.customer_name or "",
                    "items": items,
                }
            )
    return JsonResponse({"orders": payload, "total_orders": len(payload)})


@login_required
def shipping_loading(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = SalesOrder.objects.filter(tenant=tenant).prefetch_related("items__product")
    orders = _filter_sales_orders_for_shipping(request, orders).order_by("ship_date", "shipper", "order_number")
    sort = request.GET.get("sort", "old_to_new")
    search = request.GET.get("search", "").strip().lower()

    grouped = {}
    for order in orders:
        key = _date_str(order.ship_date) or "No Ship Date"
        order_haystack = f"{order.shipper or ''} {order.order_number} {order.customer_name or ''}".lower()
        if search and search not in order_haystack:
            continue
        order_payload = {
            "id": order.id,
            "order_number": order.order_number,
            "customer": order.customer_name or "",
            "ship_date": _date_str(order.ship_date),
            "items": [
                {
                    "item_name": _sales_item_name(item),
                    "notes": item.notes or "",
                    "quantity": _to_float(item.quantity) or 0,
                    "unit_type": item.unit_type or (item.product.unit_type if item.product_id and item.product else ""),
                    "packed_status": order.packed_status,
                    "packed_status_display": order.get_packed_status_display(),
                }
                for item in order.items.all()
            ],
        }
        grouped.setdefault(key, []).append(order_payload)

    ship_dates = sorted(grouped.keys(), reverse=(sort == "new_to_old"))
    payload = [{"ship_date": ship_date, "orders": grouped[ship_date]} for ship_date in ship_dates]
    total_sequences = sum(len(group["orders"]) for group in payload)
    return JsonResponse({"groups": payload, "total_sequences": total_sequences})


@login_required
def inventory_groups(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    groups = ItemGroup.objects.filter(tenant=tenant, is_active=True)
    return JsonResponse(
        {
            "groups": [
                {"id": group.id, "name": group.name, "sort_order": group.sort_order}
                for group in groups
            ]
        }
    )


@login_required
def inventory_group_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    data = _parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Group name is required."}, status=400)
    group, _ = ItemGroup.objects.get_or_create(tenant=tenant, name=name, defaults={"is_active": True})
    if not group.is_active:
        group.is_active = True
        group.save(update_fields=["is_active"])
    return JsonResponse({"id": group.id, "name": group.name})


@login_required
def purchasing_order_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    data = _parse_json(request)
    vendor_name = (data.get("vendor_name") or "").strip()
    if not vendor_name:
        return JsonResponse({"error": "Vendor name is required."}, status=400)

    vendor = Vendor.objects.filter(tenant=tenant, name=vendor_name).first()
    next_id = PurchaseOrder.objects.filter(tenant=tenant).count() + 1
    po_number = f"{next_id:05d}"
    while PurchaseOrder.objects.filter(tenant=tenant, po_number=po_number).exists():
        next_id += 1
        po_number = f"{next_id:05d}"

    order = PurchaseOrder.objects.create(
        tenant=tenant,
        po_number=po_number,
        vendor=vendor,
        vendor_name=vendor_name,
        buyer=(request.user.get_full_name() or request.user.get_username() or "").strip(),
        order_date=timezone.localdate(),
        created_by=request.user,
    )
    return JsonResponse({"id": order.id, "po_number": order.po_number})


@login_required
def purchasing_order_detail(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error

    order = get_object_or_404(
        PurchaseOrder.objects.filter(tenant=tenant).select_related("vendor").prefetch_related("items__product"),
        id=order_id,
    )
    vendor = order.vendor
    received_lots = Inventory.objects.filter(tenant=tenant, purchase_order=order)
    return JsonResponse(
        {
            **_po_to_dict(order),
            "vendor_invoice_number": order.vendor_invoice_number or "",
            "notes": order.notes or "",
            "items": [_po_item_to_dict(item) for item in order.items.all()],
            "vendor_info": {
                "id": vendor.id if vendor else None,
                "name": vendor.name if vendor else order.vendor_name,
                "contact_name": vendor.contact_name if vendor else "",
                "phone": vendor.phone if vendor else "",
                "email": vendor.email if vendor else "",
                "type": vendor.vendor_type if vendor else "",
                "cert": vendor.cert if vendor else "",
            },
            "received_lots": [
                {
                    "id": lot.id,
                    "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
                    "product_name": lot.desc or lot.productid or "",
                    "on_hand": _to_float(lot.unitsonhand) or 0,
                    "unit_type": lot.unittype or "",
                    "receive_date": lot.receivedate or "",
                }
                for lot in received_lots
            ],
        }
    )


@login_required
def purchasing_order_update(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    order = get_object_or_404(PurchaseOrder.objects.filter(tenant=tenant), id=order_id)
    data = _parse_json(request)

    # Allow status corrections on locked POs without reopening them first.
    if order.order_status in ("closed", "cancelled"):
        new_status = (data.get("order_status") or "").strip()
        new_receive_status = (data.get("receive_status") or "").strip()
        updated_fields = []
        if new_status and new_status != order.order_status:
            order.order_status = new_status
            updated_fields.append("order_status")
        if new_receive_status and new_receive_status != order.receive_status:
            order.receive_status = new_receive_status
            updated_fields.append("receive_status")
        if updated_fields:
            order.save(update_fields=updated_fields)
            return JsonResponse({"success": True})
        return JsonResponse({"error": "This purchase order is locked. Reopen it to make changes."}, status=400)

    for field in ["buyer", "vendor_invoice_number", "qb_po_number", "notes", "order_status", "receive_status"]:
        if field in data:
            setattr(order, field, data.get(field) or "")

    if "order_date" in data:
        order.order_date = data.get("order_date") or None
    if "expected_date" in data:
        order.expected_date = data.get("expected_date") or None

    order.save()
    return JsonResponse({"success": True})


@login_required
def purchasing_order_item_add(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    order = get_object_or_404(PurchaseOrder.objects.filter(tenant=tenant), id=order_id)
    if order.order_status in ("closed", "cancelled"):
        return JsonResponse({"error": "This purchase order is locked."}, status=400)
    data = _parse_json(request)
    product = None
    product_id = (data.get("product_id") or "").strip()
    if product_id:
        product = Product.objects.filter(tenant=tenant, product_id=product_id).first()

    quantity = _to_float(data.get("quantity")) or 0
    unit_price = _to_float(data.get("unit_price")) or 0
    amount = unit_price if data.get("item_type") == "fee" else quantity * unit_price

    item = PurchaseOrderItem.objects.create(
        tenant=tenant,
        purchase_order=order,
        item_type=(data.get("item_type") or "item").strip() or "item",
        product=product,
        description=(data.get("description") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        quantity=data.get("quantity") or None,
        received_quantity=data.get("received_qty") or data.get("received_quantity") or 0,
        unit_type=(data.get("unit_type") or "").strip(),
        unit_price=data.get("unit_price") or None,
        amount=amount,
        sort_order=order.items.count(),
    )
    all_items = order.items.filter(item_type="item")
    all_received = all((item.received_quantity or 0) >= (item.quantity or 0) for item in all_items)
    any_received = any((item.received_quantity or 0) > 0 for item in all_items)
    order.receive_status = "received" if all_received and all_items.exists() else ("partial" if any_received else "not_received")
    order.save(update_fields=["receive_status"])
    return JsonResponse({"success": True, "id": item.id})


@login_required
def purchasing_order_item_delete(request, order_id, item_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    item = get_object_or_404(
        PurchaseOrderItem.objects.filter(tenant=tenant, purchase_order_id=order_id),
        id=item_id,
    )
    if item.purchase_order.order_status in ("closed", "cancelled"):
        return JsonResponse({"error": "This purchase order is locked."}, status=400)
    item.delete()
    return JsonResponse({"success": True})


@login_required
def receiving_vendors(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    vendors = Vendor.objects.filter(tenant=tenant, is_active=True).order_by("name")
    return JsonResponse(
        {
            "vendors": [
                {"id": vendor.id, "name": vendor.name, "vendor_type": vendor.vendor_type or ""}
                for vendor in vendors
            ]
        }
    )


@login_required
@require_POST
def vendor_update(request, vendor_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    vendor = get_object_or_404(Vendor, id=vendor_id, tenant=tenant)
    data = json.loads(request.body)
    for field in ("name", "contact_name", "email", "phone", "address", "city",
                  "state", "zipcode", "vendor_type", "cert", "fax", "billing_email"):
        if field in data:
            setattr(vendor, field, (data[field] or "").strip())
    vendor.save()
    return JsonResponse({"ok": True})


@login_required
def vendors_list(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    vendors = Vendor.objects.filter(tenant=tenant, is_active=True).order_by("name")
    return JsonResponse({
        "vendors": [
            {
                "id": v.id,
                "vendor_id": v.vendor_id,
                "name": v.name,
                "vendor_type": v.vendor_type or "",
                "contact_name": v.contact_name or "",
                "email": v.email or "",
                "phone": v.phone or "",
                "phone_extension": v.phone_extension or "",
                "fax": v.fax or "",
                "billing_email": v.billing_email or "",
                "address": v.address or "",
                "city": v.city or "",
                "state": v.state or "",
                "zipcode": v.zipcode or "",
                "mailing_address": v.mailing_address or "",
                "mailing_city": v.mailing_city or "",
                "mailing_state": v.mailing_state or "",
                "mailing_zipcode": v.mailing_zipcode or "",
                "cert": v.cert or "",
            }
            for v in vendors
        ]
    })


@login_required
@require_POST
def vendors_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    data = json.loads(request.body)
    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Company name is required."}, status=400)
    max_id = Vendor.objects.filter(tenant=tenant).order_by("-vendor_id").values_list("vendor_id", flat=True).first() or 0
    v = Vendor(tenant=tenant, vendor_id=max_id + 1, name=name)
    for field in ("vendor_type", "contact_name", "email", "phone", "phone_extension",
                  "fax", "billing_email", "address", "city", "state", "zipcode",
                  "mailing_address", "mailing_city", "mailing_state", "mailing_zipcode", "cert"):
        val = data.get(field)
        if val is not None:
            setattr(v, field, val.strip())
    v.save()
    return JsonResponse({"ok": True, "id": v.id})


@login_required
def receiving_lots(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    lots = Inventory.objects.filter(tenant=tenant).select_related("purchase_order", "quality_check")

    search = request.GET.get("search", "").strip()
    if search:
        lots = lots.filter(
            Q(desc__icontains=search)
            | Q(vendorid__icontains=search)
            | Q(vendorlot__icontains=search)
            | Q(poid__icontains=search)
        )

    vendor = request.GET.get("vendor", "").strip()
    if vendor:
        lots = lots.filter(vendorid__iexact=vendor)
    vendor_type = request.GET.get("vendor_type", "").strip()
    if vendor_type:
        lots = lots.filter(vendor_type__iexact=vendor_type)
    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        lots = lots.filter(receivedate__gte=date_from)
    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        lots = lots.filter(receivedate__lte=date_to)

    lots = lots.order_by("-receivedate", "-id")
    paged, total = _paginate(request, lots)
    return JsonResponse(
        {
            "lots": [
                {
                    "id": lot.id,
                    "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
                    "location": lot.location or "",
                    "receive_date": lot.receivedate or "",
                    "purchase_order": lot.purchase_order.po_number if lot.purchase_order_id and lot.purchase_order else lot.poid,
                    "receive_time": lot.receive_time or "",
                    "received_at": f"{lot.receivedate or ''} {lot.receive_time or ''}".strip(),
                    "product_name": lot.desc or lot.productid or "",
                    "vendor": lot.vendorid or "",
                    "vendor_type": lot.vendor_type or "",
                    "cost": _to_float(lot.actualcost),
                    "on_hand": _to_float(lot.unitsonhand) or 0,
                    "unit_type": lot.unittype or "",
                    "qc_status": _lot_qc_status(lot),
                }
                for lot in paged
            ],
            "total": total,
        }
    )


@login_required
def receiving_lot_detail(request, lot_id):
    tenant, error = _require_tenant(request)
    if error:
        return error

    lot = get_object_or_404(
        Inventory.objects.filter(tenant=tenant).select_related("purchase_order", "po_item", "quality_check"),
        id=lot_id,
    )
    vendor = Vendor.objects.filter(tenant=tenant, name=lot.vendorid).first()
    qc = getattr(lot, "quality_check", None)

    # Traceability links
    batch_sources = ProcessBatchSource.objects.filter(tenant=tenant, inventory=lot).select_related("batch")
    batch_links = [{"id": bs.batch.id, "batch_number": bs.batch.batch_number, "process_type": bs.batch.process_type} for bs in batch_sources]
    so_allocs = SalesOrderAllocation.objects.filter(tenant=tenant, inventory=lot).select_related("sales_order_item__sales_order")
    so_links = list({a.sales_order_item.sales_order_id: {"id": a.sales_order_item.sales_order_id, "order_number": a.sales_order_item.sales_order.order_number} for a in so_allocs}.values())

    return JsonResponse(
        {
            "id": lot.id,
            "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
            "item_name": lot.desc or lot.productid or "",
            "initial_qty": _to_float(lot.unitsin or lot.unitsonhand) or 0,
            "on_hand": _to_float(lot.unitsonhand) or 0,
            "unit_type": lot.unittype or "",
            "lot_age": int(lot.age) if lot.age is not None else None,
            "vendor": lot.vendorid or "",
            "vendor_type": lot.vendor_type or "",
            "vendor_info": {
                "name": vendor.name if vendor else lot.vendorid,
                "type": vendor.vendor_type if vendor else lot.vendor_type,
                "cert": vendor.cert if vendor else "",
            },
            "receive_date": lot.receivedate or "",
            "location": lot.location or "",
            "origin": lot.origin or "",
            "cost": _to_float(lot.actualcost),
            "quality_check": _quality_to_dict(qc),
            "quality_status_choices": [
                {"value": value, "label": label} for value, label in ReceivingQualityCheck.STATUS_CHOICES
            ],
            "po_id": lot.purchase_order_id,
            "po_number": lot.purchase_order.po_number if lot.purchase_order_id and lot.purchase_order else (lot.poid or ""),
            "po_items": [
                _po_item_to_dict(item)
                for item in lot.purchase_order.items.filter(item_type="item").select_related("product").all()
            ] if lot.purchase_order_id and lot.purchase_order else [],
            "processing_batches": batch_links,
            "sales_orders": so_links,
            "activities": [
                {
                    "type": "Received",
                    "order": lot.purchase_order.po_number if lot.purchase_order_id and lot.purchase_order else (lot.poid or "--"),
                    "customer_vendor": lot.vendorid or "--",
                    "date": lot.receivedate or "",
                    "quantity": f"{_to_str(lot.unitsin or lot.unitsonhand or 0)} {lot.unittype or ''}".strip(),
                }
            ],
        }
    )


@login_required
def receiving_lot_quality(request, lot_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    lot = get_object_or_404(Inventory.objects.filter(tenant=tenant), id=lot_id)
    data = _parse_json(request)
    quality_check, _ = ReceivingQualityCheck.objects.get_or_create(
        tenant=tenant,
        inventory=lot,
        defaults={"checked_by": request.user, "checked_by_name": request.user.get_username()},
    )

    quality_check.freshness_score = int(data.get("freshness_score") or 0)
    quality_check.status = (data.get("status") or "pass").strip() or "pass"
    quality_check.appearance_ok = bool(data.get("appearance_ok"))
    quality_check.odor_ok = bool(data.get("odor_ok"))
    quality_check.texture_ok = bool(data.get("texture_ok"))
    quality_check.packaging_ok = bool(data.get("packaging_ok"))
    quality_check.temp_ok = bool(data.get("temp_ok"))
    quality_check.notes = (data.get("notes") or "").strip()
    quality_check.checked_by = request.user
    quality_check.checked_by_name = request.user.get_username()
    quality_check.save()

    return JsonResponse({"success": True, "quality_check": _quality_to_dict(quality_check)})


@login_required
def receiving_open_pos(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = (
        PurchaseOrder.objects.filter(tenant=tenant)
        .exclude(order_status="cancelled")
        .select_related("vendor")
        .prefetch_related("items__product")
        .order_by("-order_date", "-created_at")
    )
    payload = []
    for order in orders:
        items = [item for item in order.items.all() if (item.remaining_quantity or 0) > 0]
        payload.append(
            {
                "id": order.id,
                "po_number": order.po_number,
                "vendor_name": order.vendor_name,
                "vendor_type": order.vendor.vendor_type if order.vendor_id and order.vendor else "",
                "items": [_po_item_to_dict(item) for item in items],
            }
        )
    return JsonResponse({"purchase_orders": payload})


@login_required
def receiving_lot_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    data = _parse_json(request)
    product_id = (data.get("product_id") or "").strip()
    description = (data.get("description") or "").strip()
    quantity = _to_float(data.get("quantity"))
    if not product_id and not description:
        return JsonResponse({"error": "Please select a product."}, status=400)
    if not quantity or quantity <= 0:
        return JsonResponse({"error": "Please enter a valid quantity."}, status=400)

    purchase_order = None
    po_item = None
    po_number = (data.get("purchase_order") or "").strip()
    if po_number:
        purchase_order = PurchaseOrder.objects.filter(tenant=tenant, po_number=po_number).first()
    po_id = data.get("purchase_order_id")
    if po_id:
        purchase_order = PurchaseOrder.objects.filter(tenant=tenant, id=po_id).first()
        if purchase_order:
            po_number = purchase_order.po_number
    po_item_id = data.get("po_item_id")
    if po_item_id:
        po_item = PurchaseOrderItem.objects.filter(tenant=tenant, id=po_item_id).first()

    receive_time = (data.get("receive_time") or "").strip() or _time_str(timezone.localtime().time())

    lot = Inventory.objects.create(
        tenant=tenant,
        productid=product_id or description,
        desc=(Product.objects.filter(tenant=tenant, product_id=product_id).values_list("item_name", flat=True).first() if product_id else None) or description or product_id,
        vendorid=(data.get("vendor") or "").strip(),
        vendorlot=f"LOT-{timezone.now().strftime('%Y%m%d')}-{Inventory.objects.filter(tenant=tenant).count() + 1}",
        actualcost=data.get("cost") or None,
        unittype=(data.get("unit_type") or "").strip(),
        unitsonhand=quantity,
        unitsavailable=quantity,
        unitsin=quantity,
        receivedate=(data.get("receive_date") or "").strip(),
        poid=po_number,
        purchase_order=purchase_order,
        po_item=po_item,
        origin=(data.get("origin") or "").strip(),
        location=(data.get("location") or "").strip(),
        receive_time=receive_time,
        vendor_type=(data.get("vendor_type") or "").strip(),
    )

    if lot.productid and not Product.objects.filter(tenant=tenant, product_id=lot.productid).exists():
        item_name = (lot.desc or lot.productid).strip()
        Product.objects.create(
            tenant=tenant,
            is_active=True,
            product_id=lot.productid,
            description=item_name,
            item_name=item_name,
            unit_type=(lot.unittype or "").strip(),
        )

    if po_item:
        po_item.received_quantity = (po_item.received_quantity or 0) + Decimal(str(quantity))
        po_item.save(update_fields=["received_quantity"])
        if purchase_order:
            # Check all items on the PO to determine overall receive status
            all_items = purchase_order.items.filter(item_type="item")
            all_received = all((_to_float(i.remaining_quantity) or 0) <= 0 for i in all_items)
            any_received = any((_to_float(i.received_quantity) or 0) > 0 for i in all_items)
            if all_received:
                receive_status = "received"
            elif any_received:
                receive_status = "partial"
            else:
                receive_status = "not_received"
            purchase_order.receive_status = receive_status
            purchase_order.save(update_fields=["receive_status"])

    quality_data = data.get("quality_check") or {}
    quality_check, _ = ReceivingQualityCheck.objects.get_or_create(
        tenant=tenant,
        inventory=lot,
        defaults={
            "checked_by": request.user,
            "checked_by_name": request.user.get_username(),
        },
    )
    if quality_data:
        quality_check.freshness_score = int(quality_data.get("freshness_score") or 0)
        quality_check.appearance_ok = bool(quality_data.get("appearance_ok"))
        quality_check.odor_ok = bool(quality_data.get("odor_ok"))
        quality_check.texture_ok = bool(quality_data.get("texture_ok"))
        quality_check.packaging_ok = bool(quality_data.get("packaging_ok"))
        quality_check.temp_ok = bool(quality_data.get("temp_ok"))
        quality_check.status = (quality_data.get("status") or "pass").strip() or "pass"
        quality_check.notes = (quality_data.get("notes") or "").strip()
        quality_check.checked_by = request.user
        quality_check.checked_by_name = request.user.get_username()
        quality_check.save()

    return JsonResponse({"success": True, "id": lot.id})


@login_required
def processing_products(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    products = list(
        Product.objects.filter(tenant=tenant, is_active=True)
        .select_related("item_group")
        .order_by("sort_order", "description")[:1000]
    )
    product_ids = [product.product_id for product in products if product.product_id]
    inventory_totals = {
        row["productid"]: row
        for row in Inventory.objects.filter(
            tenant=tenant,
            productid__in=product_ids,
        ).filter(
            Q(quality_check__status="pass") | Q(quality_check__isnull=True)
        )
        .values("productid")
        .annotate(
            expected=Sum("unitsin"),
            allocated=Sum("unitsallocated"),
            on_hand=Sum("unitsonhand"),
        )
    }
    recent_cutoff = timezone.now() - timezone.timedelta(days=14)
    recent_processed = {}
    outputs = (
        ProcessBatchOutput.objects.filter(tenant=tenant)
        .filter(Q(product__product_id__in=product_ids) | Q(inventory__productid__in=product_ids))
        .select_related("product", "inventory", "batch")
        .order_by("-batch__started_at", "-id")
    )
    for output in outputs:
        product_key = ""
        if output.product_id and output.product:
            product_key = output.product.product_id or ""
        elif output.inventory_id and output.inventory:
            product_key = output.inventory.productid or ""
        if not product_key or product_key in recent_processed:
            continue
        processed_at = output.batch.started_at if output.batch_id and output.batch else None
        recent_processed[product_key] = {
            "recently_processed": bool(processed_at and processed_at >= recent_cutoff),
            "processed_at": processed_at.strftime("%Y-%m-%d %H:%M") if processed_at else "",
        }
    return JsonResponse(
        {
            "products": [
                {
                    **_product_to_dict(product, inventory_totals.get(product.product_id)),
                    "pack_size": _to_float(product.pack_size),
                    "default_price": _to_float(product.default_price),
                    "recently_processed": (recent_processed.get(product.product_id) or {}).get("recently_processed", False),
                    "processed_at": (recent_processed.get(product.product_id) or {}).get("processed_at", ""),
                }
                for product in products
            ]
        }
    )


@login_required
def processing_source_lots(request):
    """Return original received inventory lots available for processing."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    lots = Inventory.objects.filter(
        tenant=tenant,
        unitsonhand__gt=0,
    ).filter(
        Q(purchase_order__isnull=False) | ~Q(poid="")
    ).filter(
        Q(quality_check__status="pass") | Q(quality_check__isnull=True)
    ).select_related("quality_check").order_by("-id")
    search = request.GET.get("search", "").strip()
    if search:
        lots = lots.filter(
            Q(desc__icontains=search) | Q(vendorlot__icontains=search)
            | Q(vendorid__icontains=search) | Q(productid__icontains=search)
        )
    product_ids = list({lot.productid for lot in lots if lot.productid})
    product_map = {
        product.product_id: product
        for product in Product.objects.filter(tenant=tenant, is_active=True, product_id__in=product_ids)
    }
    processable_lots = [lot for lot in lots if not lot.productid or lot.productid in product_map]
    return JsonResponse({
        "lots": [
            {
                "id": lot.id,
                "lot_id": lot.vendorlot or f"LOT-{lot.id}",
                "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
                "item_name": ((product_map.get(lot.productid).description or product_map.get(lot.productid).item_name) if product_map.get(lot.productid) else (lot.desc or lot.productid or "")),
                "product_id": lot.productid or "",
                "product": ((product_map.get(lot.productid).description or product_map.get(lot.productid).item_name) if product_map.get(lot.productid) else (lot.desc or lot.productid or "")),
                "product_spec": " · ".join(filter(None, [
                    (product_map.get(lot.productid).quantity_description if product_map.get(lot.productid) else ""),
                    (product_map.get(lot.productid).size_cull if product_map.get(lot.productid) else ""),
                ])),
                "vendor": lot.vendorid or "",
                "vendor_lot": lot.vendorlot or "",
                "on_hand": _to_float(lot.unitsonhand) or 0,
                "unit_type": lot.unittype or "",
                "cost": _to_float(lot.actualcost) or 0,
                "location": lot.location or "",
                "origin": lot.origin or "",
                "receive_date": lot.receivedate or "",
            }
            for lot in processable_lots
        ]
    })


@login_required
def processing_sold_results(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    outputs = list(
        ProcessBatchOutput.objects.filter(tenant=tenant, inventory__isnull=False)
        .select_related("inventory", "batch", "product")
        .order_by("-id")
    )
    if not outputs:
        return JsonResponse({"results": []})

    output_by_inventory = {output.inventory_id: output for output in outputs if output.inventory_id}
    batch_ids = {output.batch_id for output in outputs if output.batch_id}

    source_map = {}
    for source in ProcessBatchSource.objects.filter(tenant=tenant, batch_id__in=batch_ids).select_related("inventory"):
        source_map.setdefault(source.batch_id, []).append(source)

    allocs = (
        SalesOrderAllocation.objects.filter(tenant=tenant, inventory_id__in=output_by_inventory.keys())
        .select_related("inventory", "sales_order_item__sales_order", "sales_order_item__product")
        .order_by("-created_at", "-id")
    )

    results = []
    for alloc in allocs:
        output = output_by_inventory.get(alloc.inventory_id)
        if not output or not alloc.sales_order_item_id or not alloc.sales_order_item.sales_order_id:
            continue

        sales_item = alloc.sales_order_item
        order = sales_item.sales_order
        batch_sources = source_map.get(output.batch_id, [])
        source_lots = ", ".join(
            dict.fromkeys(
                (src.inventory.vendorlot or f"LOT-{src.inventory_id}")
                for src in batch_sources if src.inventory_id and src.inventory
            )
        ) or (alloc.inventory.vendorlot or f"LOT-{alloc.inventory_id}")
        source_product = ", ".join(
            dict.fromkeys(
                (src.inventory.desc or src.inventory.productid or "")
                for src in batch_sources if src.inventory_id and src.inventory
            )
        ) or (alloc.inventory.desc or alloc.inventory.productid or "")

        sold_qty = Decimal(str(alloc.quantity or 0))
        unit_price = Decimal(str(sales_item.unit_price or 0))
        results.append(
            {
                "id": alloc.id,
                "batch_id": output.batch_id,
                "order_id": order.id,
                "product": sales_item.description or ((sales_item.product.description or sales_item.product.item_name) if sales_item.product_id and sales_item.product else (alloc.inventory.desc or alloc.inventory.productid or "")),
                "source_product": source_product,
                "source_lot": source_lots,
                "sold_qty": _to_float(sold_qty) or 0,
                "unit_type": alloc.unit_type or sales_item.unit_type or alloc.inventory.unittype or "",
                "customer_name": order.customer_name or "",
                "amount": _to_float(sold_qty * unit_price) or 0,
                "order_number": order.order_number or "",
                "sold_at": _date_str(order.order_date),
            }
        )

    return JsonResponse({"results": results})


@login_required
def processing_batches(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    batches = ProcessBatch.objects.filter(tenant=tenant).prefetch_related("sources__inventory")
    status = request.GET.get("status", "").strip()
    search = request.GET.get("search", "").strip()
    if status:
        batches = batches.filter(status=status)
    if search:
        batches = batches.filter(Q(batch_number__icontains=search) | Q(process_type__icontains=search))
    batches = batches.order_by("-started_at")
    page_size = request.GET.get("page_size", "").strip()
    if page_size:
        batches = batches[: max(int(page_size), 1)]
    return JsonResponse(
        {
            "batches": [
                {
                    "id": batch.id,
                    "batch_number": batch.batch_number,
                    "process_type": batch.process_type,
                    "status": batch.status,
                    "status_display": batch.get_status_display(),
                    "started_at": batch.started_at.strftime("%Y-%m-%d %I:%M %p") if batch.started_at else "",
                    "completed_at": batch.completed_at.strftime("%Y-%m-%d %I:%M %p") if batch.completed_at else "",
                    "created_by": batch.created_by.get_full_name() or batch.created_by.username if batch.created_by else "",
                    "products": ", ".join(sorted(set(
                        (s.inventory.desc or s.inventory.productid or "")
                        for s in batch.sources.all() if s.inventory
                    ))) or "",
                }
                for batch in batches
            ]
        }
    )


@login_required
def processing_batch_sources(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    sources = batch.sources.select_related("inventory").all()
    product_ids = list({s.inventory.productid for s in sources if s.inventory and s.inventory.productid})
    product_map = {
        product.product_id: product
        for product in Product.objects.filter(tenant=tenant, product_id__in=product_ids)
    }
    return JsonResponse({
        "sources": [
            {
                "id": s.id,
                "lot_id": s.inventory.vendorlot or f"LOT-{s.inventory_id}" if s.inventory else "--",
                "item_name": (((product_map.get(s.inventory.productid).description or product_map.get(s.inventory.productid).item_name) if s.inventory and product_map.get(s.inventory.productid) else (s.inventory.desc or s.inventory.productid or "")) if s.inventory else ""),
                "product_spec": " · ".join(filter(None, [
                    (product_map.get(s.inventory.productid).quantity_description if s.inventory and product_map.get(s.inventory.productid) else ""),
                    (product_map.get(s.inventory.productid).size_cull if s.inventory and product_map.get(s.inventory.productid) else ""),
                ])),
                "vendor": (s.inventory.vendorid or "") if s.inventory else "",
                "quantity": float(s.quantity),
                "unit_type": s.unit_type or "",
            }
            for s in sources
        ]
    })


@login_required
def processing_batch_outputs(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    outputs = batch.outputs.select_related("inventory", "product").all()
    return JsonResponse({
        "outputs": [
            {
                "id": o.id,
                "lot_id": o.lot_id or (o.inventory.vendorlot if o.inventory else ""),
                "product_name": ((o.product.description or o.product.item_name) if o.product else
                                 (o.inventory.desc if o.inventory else "")),
                "product_spec": (o.product.quantity_description or o.product.size_cull or "") if o.product else "",
                "quantity": float(o.quantity),
                "unit_type": o.unit_type or "",
                "yield_percent": float(o.yield_percent) if o.yield_percent else None,
            }
            for o in outputs
        ]
    })


@login_required
def processing_batch_waste(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    entries = batch.waste_entries.select_related("source_inventory").all()
    sources = batch.sources.select_related("inventory").all()
    outputs = batch.outputs.all()

    waste_qty = sum(float(e.quantity) for e in entries if e.entry_type == "waste")
    byproduct_qty = sum(float(e.quantity) for e in entries if e.entry_type == "byproduct")
    est_value = sum(float(e.estimated_value or 0) for e in entries)
    total_input_qty = sum(float(s.quantity) for s in sources)
    total_output_qty = sum(float(o.quantity) for o in outputs)
    accounted_qty = waste_qty + byproduct_qty
    unaccounted_qty = total_input_qty - total_output_qty - accounted_qty
    default_unit_type = next((s.unit_type for s in sources if s.unit_type), "")

    return JsonResponse({
        "entries": [
            {
                "id": e.id,
                "entry_type": e.entry_type,
                "entry_type_display": e.get_entry_type_display(),
                "category": e.category,
                "category_display": e.get_category_display(),
                "source_lot_id": (e.source_inventory.vendorlot or f"LOT-{e.source_inventory_id}") if e.source_inventory else "",
                "quantity": float(e.quantity),
                "unit_type": e.unit_type or "",
                "estimated_value": float(e.estimated_value) if e.estimated_value is not None else None,
                "notes": e.notes or "",
                "created_at": e.created_at.strftime("%Y-%m-%d %H:%M") if e.created_at else "",
            }
            for e in entries
        ],
        "summary": {
            "waste_qty": waste_qty,
            "byproduct_qty": byproduct_qty,
            "estimated_value": est_value,
            "total_input_qty": total_input_qty,
            "total_output_qty": total_output_qty,
            "accounted_qty": accounted_qty,
            "unaccounted_qty": unaccounted_qty,
            "is_balanced": abs(unaccounted_qty) < 0.0001,
            "default_unit_type": default_unit_type,
        },
        "entry_types": [{"value": v, "label": l} for v, l in C.PROCESS_WASTE_TYPE_CHOICES],
        "categories": [{"value": v, "label": l} for v, l in C.PROCESS_WASTE_CATEGORY_CHOICES],
        "source_options": [
            {
                "inventory_id": s.inventory_id,
                "lot_id": s.inventory.vendorlot or f"LOT-{s.inventory_id}" if s.inventory else "",
                "quantity": float(s.quantity),
                "unit_type": s.unit_type or "",
            }
            for s in sources
        ],
    })


@login_required
@require_POST
def processing_batch_waste_create(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    data = json.loads(request.body)
    try:
        qty = Decimal(str(data.get("quantity", 0)))
    except Exception:
        return JsonResponse({"error": "Invalid quantity."}, status=400)
    source_inv = None
    src_id = data.get("source_inventory_id")
    if src_id:
        source_inv = Inventory.objects.filter(id=src_id, tenant=tenant).first()
    est_val = None
    ev = data.get("estimated_value")
    if ev:
        try:
            est_val = Decimal(str(ev))
        except Exception:
            pass
    ProcessBatchWaste.objects.create(
        tenant=tenant,
        batch=batch,
        source_inventory=source_inv,
        entry_type=data.get("entry_type", "waste"),
        category=data.get("category", "other"),
        quantity=qty,
        unit_type=data.get("unit_type", "").strip(),
        estimated_value=est_val,
        notes=data.get("notes", "").strip(),
        created_by=request.user,
        created_by_name=request.user.get_full_name() or request.user.username,
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def processing_batch_complete(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    total_input = sum((s.quantity or 0) for s in batch.sources.all())
    total_output = sum((o.quantity or 0) for o in batch.outputs.all())
    total_accounted = sum((e.quantity or 0) for e in batch.waste_entries.all())
    unaccounted = total_input - total_output - total_accounted
    if abs(float(unaccounted)) >= 0.0001:
        return JsonResponse(
            {
                "error": f"Batch is not balanced. Remaining quantity to account for: {float(unaccounted):.2f}."
            },
            status=400,
        )
    batch.status = "completed"
    batch.completed_at = timezone.now()
    batch.calculate_yield()
    batch.save()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def processing_batch_cancel(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch, id=batch_id, tenant=tenant)
    batch.status = "cancelled"
    batch.save(update_fields=["status"])
    return JsonResponse({"ok": True})


@login_required
def inventory_items(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    items = Product.objects.filter(tenant=tenant).select_related("item_group")
    show = request.GET.get("show", "").strip()
    if show == "active":
        items = items.filter(is_active=True)
    elif show == "inactive":
        items = items.filter(is_active=False)

    search = request.GET.get("search", "").strip()
    if search:
        items = items.filter(
            Q(item_name__icontains=search)
            | Q(description__icontains=search)
            | Q(sku__icontains=search)
            | Q(product_id__icontains=search)
            | Q(friendly_name__icontains=search)
            | Q(qb_item_name__icontains=search)
        )

    items = list(items.order_by("sort_order", "description")[:1000])
    product_ids = [item.product_id for item in items if item.product_id]
    # Only count lots that passed QC toward inventory totals
    inventory_totals = {
        row["productid"]: row
        for row in Inventory.objects.filter(
            tenant=tenant, productid__in=product_ids
        ).filter(
            Q(quality_check__status="pass") | Q(quality_check__isnull=True)
        )
        .values("productid")
        .annotate(
            expected=Sum("unitsin"),
            allocated=Sum("unitsallocated"),
            on_hand=Sum("unitsonhand"),
        )
    }

    return JsonResponse({"items": [_product_to_dict(item, inventory_totals.get(item.product_id)) for item in items]})


@login_required
def inventory_rejected_lots(request):
    """Return lots that failed QC (hold or reject status)."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    lots = (
        Inventory.objects.filter(tenant=tenant, quality_check__status__in=["hold", "reject"])
        .select_related("quality_check")
        .order_by("-id")
    )
    return JsonResponse({
        "lots": [
            {
                "id": lot.id,
                "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
                "product": lot.desc or lot.productid or "",
                "vendor": lot.vendorid or "",
                "receive_date": lot.receivedate or "",
                "on_hand": _to_float(lot.unitsonhand) or 0,
                "unit_type": lot.unittype or "",
                "qc_status": lot.quality_check.status,
                "qc_notes": lot.quality_check.notes or "",
                "checked_at": lot.quality_check.checked_at.strftime("%Y-%m-%d %H:%M") if lot.quality_check.checked_at else "",
            }
            for lot in lots
        ]
    })


@login_required
def inventory_item_lots(request, item_id):
    """Return inventory lots for a product, with aggregate totals."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    product = get_object_or_404(Product, id=item_id, tenant=tenant)
    lots = Inventory.objects.filter(
        tenant=tenant, productid=product.product_id
    ).filter(
        Q(quality_check__status="pass") | Q(quality_check__isnull=True)
    ).order_by("-id")
    total_expected = 0
    total_allocated = 0
    total_on_hand = 0
    lot_list = []
    for lot in lots:
        on_hand = _to_float(lot.unitsonhand) or 0
        expected = _to_float(lot.unitsin) or 0
        allocated = _to_float(lot.unitsallocated) or 0
        total_expected += expected
        total_allocated += allocated
        total_on_hand += on_hand
        status = "Sold Out" if on_hand <= 0 else "Received"
        lot_list.append({
            "id": lot.id,
            "lot_id": lot.vendorlot or f"LOT-{lot.id}",
            "status": status,
            "date": lot.receivedate or "",
            "on_hand": on_hand,
            "unit_type": lot.unittype or "",
        })
    return JsonResponse({
        "lots": lot_list,
        "expected": total_expected,
        "allocated": total_allocated,
        "on_hand": total_on_hand,
    })


@login_required
def inventory_item_adjustments(request, item_id):
    """Return adjustment history and type/reason choices for a product."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    product = get_object_or_404(Product, id=item_id, tenant=tenant)
    adjustments = InventoryAdjustment.objects.filter(
        product=product, inventory__tenant=tenant
    ).order_by("-created_at")
    return JsonResponse({
        "adjustments": [
            {
                "id": a.id,
                "lot_id": a.inventory.vendorlot or f"LOT-{a.inventory_id}" if a.inventory_id else "--",
                "adjustment_type": a.adjustment_type,
                "adjustment_type_display": a.get_adjustment_type_display(),
                "reason_display": a.get_reason_code_display(),
                "quantity_delta": float(a.quantity_delta),
                "quantity_after": float(a.quantity_after),
                "created_by": a.created_by_name or (a.created_by.get_full_name() if a.created_by else "--"),
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            }
            for a in adjustments
        ],
        "adjustment_types": [{"value": v, "label": l} for v, l in C.INVENTORY_ADJUSTMENT_TYPE_CHOICES],
        "reason_codes": [{"value": v, "label": l} for v, l in C.INVENTORY_ADJUSTMENT_REASON_CHOICES],
    })


@login_required
@require_POST
def inventory_item_adjustment_create(request, item_id):
    """Create an inventory adjustment for a specific lot."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    product = get_object_or_404(Product, id=item_id, tenant=tenant)
    data = json.loads(request.body)
    inv_id = data.get("inventory_id")
    lot = get_object_or_404(Inventory, id=inv_id, tenant=tenant)
    adj_type = data.get("adjustment_type", "").strip()
    reason = data.get("reason_code", "").strip()
    qty_str = data.get("quantity", "")
    try:
        qty = Decimal(str(qty_str))
    except Exception:
        return JsonResponse({"error": "Invalid quantity."}, status=400)
    before = lot.unitsonhand or Decimal("0")
    if adj_type == "increase":
        after = before + qty
    elif adj_type == "decrease":
        after = before - qty
        if after < 0:
            return JsonResponse({"error": "Cannot decrease below zero."}, status=400)
    elif adj_type == "set_count":
        after = qty
        qty = after - before
    else:
        return JsonResponse({"error": "Invalid adjustment type."}, status=400)
    lot.unitsonhand = after
    lot.save(update_fields=["unitsonhand"])
    InventoryAdjustment.objects.create(
        tenant=tenant,
        inventory=lot,
        product=product,
        adjustment_type=adj_type,
        reason_code=reason,
        quantity_before=before,
        quantity_delta=qty,
        quantity_after=after,
        notes=data.get("notes", "").strip(),
        created_by=request.user,
        created_by_name=request.user.get_full_name() or request.user.username,
    )
    return JsonResponse({"ok": True})


@login_required
def inventory_item_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    data = _parse_json(request)
    product = Product(tenant=tenant, is_active=True)
    _apply_product_payload(product, tenant, data)
    if not (product.description or product.item_name or product.friendly_name or product.qb_item_name):
        return JsonResponse({"error": "Please enter at least a name or description."}, status=400)
    if not product.product_id:
        product.product_id = _next_product_id(tenant)
    product.save()
    return JsonResponse({"success": True, "id": product.id, "item": _product_to_dict(product)})


@login_required
def inventory_item_update(request, item_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)

    product = get_object_or_404(Product.objects.filter(tenant=tenant), id=item_id)
    data = _parse_json(request)
    _apply_product_payload(product, tenant, data)
    product.save()
    return JsonResponse({"success": True, "id": product.id, "item": _product_to_dict(product)})


@login_required
def inventory_item_delete(request, item_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)
    product = get_object_or_404(Product.objects.filter(tenant=tenant), id=item_id)
    try:
        with transaction.atomic():
            CustomerProfile.objects.filter(tenant=tenant, product=product).update(product=None)
            PurchaseOrderItem.objects.filter(tenant=tenant, product=product).update(product=None)
            SalesOrderItem.objects.filter(tenant=tenant, product=product).update(product=None)
            ProcessBatchOutput.objects.filter(tenant=tenant, product=product).update(product=None)
            ProductImage.objects.filter(product=product).delete()
            product.delete()
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"error": f"Unable to delete this product right now: {exc}"}, status=400)


@login_required
def inventory_item_toggle_active(request, item_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)
    product = get_object_or_404(Product.objects.filter(tenant=tenant), id=item_id)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active"])
    return JsonResponse({"success": True, "is_active": product.is_active})


@login_required
def settings_profile(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    if request.method == "POST":
        data = _parse_json(request)
        request.user.first_name = (data.get("first_name") or "").strip()
        request.user.last_name = (data.get("last_name") or "").strip()
        request.user.email = (data.get("email") or "").strip()
        request.user.save(update_fields=["first_name", "last_name", "email"])
        return JsonResponse({"success": True})

    return JsonResponse(
        {
            "username": request.user.get_username(),
            "first_name": request.user.first_name or "",
            "last_name": request.user.last_name or "",
            "email": request.user.email or "",
        }
    )


@login_required
def settings_account(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    if request.method == "POST":
        data = _parse_json(request)
        tenant.name = (data.get("name") or "").strip() or tenant.name
        tenant.address = (data.get("address") or "").strip()
        tenant.city = (data.get("city") or "").strip()
        tenant.state = (data.get("state") or "").strip()
        tenant.zipcode = (data.get("zipcode") or "").strip()
        tenant.save(update_fields=["name", "address", "city", "state", "zipcode"])
        return JsonResponse({"success": True})

    return JsonResponse(
        {
            "name": tenant.name or "",
            "address": tenant.address or "",
            "city": tenant.city or "",
            "state": tenant.state or "",
            "zipcode": tenant.zipcode or "",
            "phone": "",
        }
    )


@login_required
def settings_users(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    tenant_users = TenantUser.objects.filter(tenant=tenant).select_related("user").order_by("user__first_name", "user__username")
    return JsonResponse(
        {
            "users": [
                {
                    "id": tenant_user.user_id,
                    "name": (
                        f"{tenant_user.user.first_name} {tenant_user.user.last_name}".strip()
                        or tenant_user.user.get_username()
                    ),
                    "first_name": tenant_user.user.first_name or "",
                    "last_name": tenant_user.user.last_name or "",
                    "email": tenant_user.user.email or "",
                    "username": tenant_user.user.get_username(),
                    "is_admin": tenant_user.is_admin,
                    "is_active": tenant_user.user.is_active,
                }
                for tenant_user in tenant_users
            ]
        }
    )


@login_required
@require_POST
def settings_user_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    admin_error = _require_tenant_admin(request, tenant)
    if admin_error:
        return admin_error

    data = _parse_json(request)
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    password = (data.get("password") or "").strip()
    is_admin = bool(data.get("is_admin"))
    is_active = data.get("is_active")
    is_active = True if is_active is None else bool(is_active)

    if not username:
        return JsonResponse({"error": "Username is required."}, status=400)
    if not password:
        return JsonResponse({"error": "Password is required."}, status=400)
    if DjangoUser.objects.filter(username__iexact=username).exists():
        return JsonResponse({"error": "That username is already in use."}, status=400)

    with transaction.atomic():
        user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
        )
        TenantUser.objects.create(user=user, tenant=tenant, is_admin=is_admin)

    return JsonResponse({"success": True})


@login_required
@require_POST
def settings_user_update(request, user_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    admin_error = _require_tenant_admin(request, tenant)
    if admin_error:
        return admin_error

    tenant_user = get_object_or_404(TenantUser.objects.select_related("user"), tenant=tenant, user_id=user_id)
    data = _parse_json(request)
    user = tenant_user.user

    username = (data.get("username") or user.username).strip()
    email = (data.get("email") or "").strip()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    password = (data.get("password") or "").strip()

    username_taken = DjangoUser.objects.filter(username__iexact=username).exclude(id=user.id).exists()
    if username_taken:
        return JsonResponse({"error": "That username is already in use."}, status=400)

    user.username = username
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = bool(data.get("is_active"))
    if password:
        user.set_password(password)
    user.save()

    tenant_user.is_admin = bool(data.get("is_admin"))
    tenant_user.save(update_fields=["is_admin"])

    return JsonResponse({"success": True})


@login_required
@require_POST
def settings_user_delete(request, user_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    admin_error = _require_tenant_admin(request, tenant)
    if admin_error:
        return admin_error

    tenant_user = get_object_or_404(TenantUser.objects.select_related("user"), tenant=tenant, user_id=user_id)
    if tenant_user.user_id == request.user.id:
        return JsonResponse({"error": "You cannot delete your own user from Settings."}, status=400)

    tenant_user.user.delete()
    return JsonResponse({"success": True})


@login_required
def sales_customers(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    customers = Customer.objects.filter(tenant=tenant).order_by("name")
    return JsonResponse({
        "customers": [
            {
                "id": c.id,
                "name": c.name,
                "contact_name": c.contact_name or "",
                "email": c.email or "",
                "phone": c.phone or "",
                "address": c.address or "",
                "city": c.city or "",
                "state": c.state or "",
                "zipcode": c.zipcode or "",
                "ship_address": c.ship_address or "",
                "ship_city": c.ship_city or "",
                "ship_state": c.ship_state or "",
                "ship_zipcode": c.ship_zipcode or "",
            }
            for c in customers
        ]
    })


@login_required
@require_POST
def customer_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    data = _parse_json(request)
    name = (data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": "Customer name is required."}, status=400)
    last = Customer.objects.filter(tenant=tenant).order_by("-customer_id").first()
    next_id = (last.customer_id + 1) if last else 1
    c = Customer.objects.create(tenant=tenant, customer_id=next_id, name=name)
    for field in ["contact_name", "email", "phone", "address", "city", "state", "zipcode",
                   "ship_address", "ship_city", "ship_state", "ship_zipcode"]:
        val = data.get(field)
        if val is not None:
            setattr(c, field, val.strip())
    c.save()
    return JsonResponse({"success": True, "id": c.id})


@login_required
def customer_update(request, customer_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    c = get_object_or_404(Customer.objects.filter(tenant=tenant), id=customer_id)
    data = _parse_json(request)
    for field in ["name", "contact_name", "email", "phone", "address", "city", "state", "zipcode",
                   "ship_address", "ship_city", "ship_state", "ship_zipcode"]:
        val = data.get(field)
        if val is not None:
            setattr(c, field, val.strip())
    c.save()
    return JsonResponse({"success": True})


@login_required
@require_POST
def customer_delete(request, customer_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    c = get_object_or_404(Customer.objects.filter(tenant=tenant), id=customer_id)
    c.delete()
    return JsonResponse({"success": True})


@login_required
def sales_orders(request):
    tenant, error = _require_tenant(request)
    if error:
        return error

    orders = SalesOrder.objects.filter(tenant=tenant).prefetch_related("items__product").annotate(order_total=Sum("items__amount")).order_by("-order_date", "-created_at")
    paged, total = _paginate(request, orders)
    return JsonResponse(
        {
            "orders": [
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer_name": order.customer_name,
                    "order_status": order.order_status,
                    "order_status_display": order.get_order_status_display(),
                    "packed_status": order.packed_status,
                    "packed_status_display": order.get_packed_status_display(),
                    "order_date": _date_str(order.order_date),
                    "ship_date": _date_str(order.ship_date),
                    "shipping_route": order.shipping_route or "",
                    "sales_rep": order.sales_rep or "",
                    "qb_invoice_number": order.qb_invoice_number or "",
                    "total": _sales_order_total(order),
                    "products": ", ".join(sorted(set(filter(None, (
                        (item.product.species or item.product.item_name or "") if item.product else item.description
                        for item in order.items.all() if item.item_type == "item"
                    ))))) or "",
                }
                for order in paged
            ],
            "total": total,
        }
    )


@login_required
@require_POST
def sales_orders_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    data = json.loads(request.body)
    customer_name = (data.get("customer_name") or "").strip()
    if not customer_name:
        return JsonResponse({"error": "Customer name is required."}, status=400)
    # Auto-generate order number
    last = SalesOrder.objects.filter(tenant=tenant).order_by("-id").first()
    next_num = 1
    if last:
        try:
            next_num = int(last.order_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_num = last.id + 1
    order_number = f"SO-{next_num:04d}"
    customer = Customer.objects.filter(tenant=tenant, name=customer_name).first()
    so = SalesOrder.objects.create(
        tenant=tenant,
        order_number=order_number,
        customer=customer,
        customer_name=customer_name,
        order_status="draft",
        order_date=timezone.now().date(),
        created_by=request.user,
    )
    return JsonResponse({"ok": True, "id": so.id})


@login_required
def sales_order_detail_api(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    so = get_object_or_404(
        SalesOrder.objects.filter(tenant=tenant).select_related("customer").prefetch_related("items__product"),
        id=order_id,
    )
    customer = so.customer

    def _so_item_to_dict(item):
        product_id = ""
        if item.product_id and item.product:
            product_id = item.product.product_id
        return {
            "id": item.id,
            "item_type": item.item_type,
            "product_id": product_id,
            "description": item.description or ((item.product.description or item.product.item_name) if item.product_id and item.product else ""),
            "product_spec": _sales_item_spec(item),
            "notes": item.notes or "",
            "quantity": _to_float(item.quantity),
            "unit_type": item.unit_type or (item.product.inventory_unit_of_measure if item.product_id and item.product else ""),
            "unit_price": _to_float(item.unit_price) or 0,
            "margin": item.margin if hasattr(item, "margin") else "",
            "amount": _to_float(item.amount) or 0,
            "process_type": item.process_type or "",
            "process_source_lot_ids": _selected_source_lot_ids({"process_source_lot_ids": item.process_source_lot_ids}),
            "process_batch_id": item.process_batch_id,
        }

    return JsonResponse({
        "id": so.id,
        "order_number": so.order_number,
        "customer_name": so.customer_name,
        "order_status": so.order_status,
        "order_status_display": so.get_order_status_display(),
        "packed_status": so.packed_status,
        "packed_status_display": so.get_packed_status_display(),
        "qb_invoice_number": so.qb_invoice_number or "",
        "sales_rep": so.sales_rep or "",
        "po_number": so.po_number or "",
        "air_bill_number": so.air_bill_number or "",
        "order_date": _date_str(so.order_date),
        "pack_date": _date_str(so.pack_date),
        "delivery_date": _date_str(so.delivery_date),
        "ship_date": _date_str(so.ship_date),
        "shipper": so.shipper or "",
        "shipping_route": so.shipping_route or "",
        "order_weight": _to_float(so.order_weight),
        "notes": so.notes or "",
        "items": [_so_item_to_dict(item) for item in so.items.all()],
        "contact_info": {
            "name": customer.name if customer else so.customer_name,
            "contact_name": customer.contact_name if customer else "",
            "phone": customer.phone if customer else "",
            "email": customer.email if customer else "",
        } if customer or so.customer_name else None,
        "delivery_address": {
            "address": customer.ship_address or customer.address if customer else "",
            "city": customer.ship_city or customer.city if customer else "",
            "state": customer.ship_state or customer.state if customer else "",
            "zip": customer.ship_zipcode or customer.zipcode if customer else "",
        } if customer else None,
        "mailing_address": {
            "address": customer.address if customer else "",
            "city": customer.city if customer else "",
            "state": customer.state if customer else "",
            "zip": customer.zipcode if customer else "",
        } if customer else None,
    })


@login_required
def sales_order_update(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)
    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)
    data = _parse_json(request)

    for field in ["sales_rep", "po_number", "air_bill_number", "shipper", "shipping_route",
                   "qb_invoice_number", "notes", "order_status", "packed_status"]:
        if field in data:
            setattr(so, field, data.get(field) or "")

    for field in ["order_date", "pack_date", "delivery_date", "ship_date"]:
        if field in data:
            setattr(so, field, data.get(field) or None)

    if "order_weight" in data:
        so.order_weight = data.get("order_weight") or None

    if (so.order_status in ("open", "closed")) and not (so.qb_invoice_number or "").strip():
        so.qb_invoice_number = so.order_number

    so.save()
    return JsonResponse({"success": True})


@login_required
def sales_order_item_add(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)
    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)
    data = _parse_json(request)

    product = None
    product_id = (data.get("product_id") or "").strip()
    if product_id:
        product = Product.objects.filter(tenant=tenant, product_id=product_id).first()

    quantity = _to_float(data.get("quantity")) or 0
    unit_price = _to_float(data.get("unit_price")) or 0
    amount = unit_price if data.get("item_type") == "fee" else quantity * unit_price

    item = SalesOrderItem.objects.create(
        tenant=tenant,
        sales_order=so,
        item_type=(data.get("item_type") or "item").strip() or "item",
        product=product,
        description=(data.get("description") or "").strip(),
        notes=(data.get("notes") or "").strip(),
        quantity=data.get("quantity") or None,
        unit_type=(data.get("unit_type") or "").strip(),
        unit_price=data.get("unit_price") or None,
        amount=amount,
        process_type=(data.get("process_type") or "").strip(),
        process_source_lot_ids=",".join(str(lot_id) for lot_id in _selected_source_lot_ids(data)),
        sort_order=so.items.count(),
    )
    try:
        _create_processing_batch_for_sales_item(request, tenant, item, data)
    except ValueError as exc:
        item.delete()
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"success": True, "id": item.id})


@login_required
def sales_order_item_delete(request, order_id, item_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "GET not allowed"}, status=405)
    item = get_object_or_404(
        SalesOrderItem.objects.filter(tenant=tenant, sales_order_id=order_id),
        id=item_id,
    )
    if item.process_batch_id and item.process_batch:
        _rollback_process_batch(item.process_batch)
    item.delete()
    return JsonResponse({"success": True})


@login_required
def sales_order_allocations(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)
    items = so.items.filter(item_type="item").select_related("product").prefetch_related("allocations__inventory")

    result_items = []
    shortages = []
    for item in items:
        allocs = item.allocations.all()
        allocated_qty = sum(_to_float(a.quantity) or 0 for a in allocs)
        ordered_qty = _to_float(item.quantity) or 0
        lots = [
            {
                "lot_id": a.inventory.vendorlot or f"LOT-{a.inventory_id}" if a.inventory else "",
                "quantity": _to_float(a.quantity) or 0,
                "unit_type": a.unit_type or (a.inventory.unittype if a.inventory else ""),
            }
            for a in allocs if a.inventory_id
        ]
        result_items.append({
            "item_id": item.id,
            "item_name": item.description or ((item.product.description or item.product.item_name) if item.product else ""),
            "product_spec": _sales_item_spec(item),
            "ordered_qty": ordered_qty,
            "allocated_qty": allocated_qty,
            "unit_type": item.unit_type or "",
            "lots": lots,
        })
        if allocated_qty < ordered_qty:
            shortages.append({
                "item_name": item.description or ((item.product.description or item.product.item_name) if item.product else ""),
                "short_qty": ordered_qty - allocated_qty,
            })

    return JsonResponse({"items": result_items, "shortages": shortages})


@login_required
def sales_order_allocate_fifo(request, order_id):
    """Auto-allocate inventory lots to sales order items using FIFO (oldest first)."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)
    items = so.items.filter(item_type="item").select_related("product")

    # Clear existing allocations
    SalesOrderAllocation.objects.filter(tenant=tenant, sales_order_item__sales_order=so).delete()

    shortages = []
    for item in items:
        needed = _to_float(item.quantity) or 0
        if needed <= 0:
            continue

        # Find matching inventory lots, oldest first (FIFO)
        product_filter = Q()
        if item.product:
            product_filter = Q(productid=item.product.product_id) | Q(desc=item.product.item_name)
        elif item.description:
            product_filter = Q(desc__iexact=item.description)
        else:
            continue

        lots = Inventory.objects.filter(
            tenant=tenant
        ).filter(product_filter).filter(
            unitsonhand__gt=0
        ).order_by("receivedate", "id")

        allocated = 0
        for lot in lots:
            if allocated >= needed:
                break
            available = _to_float(lot.unitsonhand) or 0
            if available <= 0:
                continue
            take = min(available - 0, needed - allocated)
            if take <= 0:
                continue
            SalesOrderAllocation.objects.create(
                tenant=tenant,
                sales_order_item=item,
                inventory=lot,
                quantity=take,
                unit_type=item.unit_type or lot.unittype or "",
                allocated_by=request.user,
                allocated_by_name=request.user.get_full_name() or request.user.username,
            )
            allocated += take

        if allocated < needed:
            shortages.append({
                "item_name": item.description or (item.product.item_name if item.product else ""),
                "short_qty": round(needed - allocated, 4),
            })

    return JsonResponse({"success": True, "shortages": shortages})


@login_required
@require_POST
def processing_batches_create(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    data = json.loads(request.body)
    process_type = (data.get("process_type") or "").strip()
    if not process_type:
        return JsonResponse({"error": "Process type is required."}, status=400)
    # Auto-generate batch number
    last = ProcessBatch.objects.filter(tenant=tenant).order_by("-id").first()
    next_num = (last.id + 1) if last else 1
    batch_number = f"PB-{next_num:04d}"
    batch = ProcessBatch.objects.create(
        tenant=tenant,
        batch_number=batch_number,
        process_type=process_type,
        status="in_progress",
        notes=(data.get("notes") or "").strip(),
        created_by=request.user,
    )
    # Create source entries
    for src in data.get("sources") or []:
        inv = Inventory.objects.filter(id=src.get("inventory_id"), tenant=tenant).first()
        if inv:
            ProcessBatchSource.objects.create(
                tenant=tenant,
                batch=batch,
                inventory=inv,
                quantity=Decimal(str(src.get("quantity", 0))),
                unit_type=src.get("unit_type", ""),
            )
    # Deduct quantities from source lots
    total_input = Decimal("0")
    first_source = None
    for src in batch.sources.select_related("inventory").all():
        if src.inventory:
            if not first_source:
                first_source = src.inventory
            src.inventory.unitsonhand = max(Decimal("0"), (src.inventory.unitsonhand or 0) - src.quantity)
            src.inventory.save(update_fields=["unitsonhand"])
            total_input += src.quantity

    # Create output entries with new inventory records
    total_output = Decimal("0")
    lot_counter = Inventory.objects.filter(tenant=tenant).count()
    for out in data.get("outputs") or []:
        product = None
        pid = out.get("product_id")
        if pid:
            product = Product.objects.filter(tenant=tenant, product_id=pid).first()

        qty = Decimal(str(out.get("quantity", 0)))
        total_output += qty
        unit_type = out.get("unit_type", "")
        lot_counter += 1
        lot_id = out.get("lot_id", "").strip() or f"LOT-{batch.batch_number}-{lot_counter}"

        # Determine product name for the output lot
        out_desc = ""
        if product:
            out_desc = product.description or product.item_name or pid
        elif out.get("description"):
            out_desc = out["description"]
        elif first_source:
            out_desc = first_source.desc or first_source.productid or ""

        # Create new inventory record for the output
        out_inv = Inventory.objects.create(
            tenant=tenant,
            productid=pid or (first_source.productid if first_source else ""),
            desc=out_desc,
            vendorid=first_source.vendorid if first_source else "",
            vendorlot=lot_id,
            unittype=unit_type,
            unitsonhand=qty,
            unitsavailable=qty,
            unitsin=qty,
            receivedate=timezone.now().date().isoformat(),
            vendor_type=first_source.vendor_type if first_source else "",
        )

        ProcessBatchOutput.objects.create(
            tenant=tenant,
            batch=batch,
            product=product,
            inventory=out_inv,
            quantity=qty,
            unit_type=unit_type,
            lot_id=lot_id,
            yield_percent=Decimal(str(out["yield_percent"])) if out.get("yield_percent") else None,
        )

    # Auto-create waste entry for the difference
    waste_qty = total_input - total_output
    if waste_qty > 0:
        ProcessBatchWaste.objects.create(
            tenant=tenant,
            batch=batch,
            source_inventory=first_source,
            entry_type="waste",
            category="trim",
            quantity=waste_qty,
            unit_type=first_source.unittype if first_source else "",
            notes="Auto-calculated from input/output difference",
        )

    return JsonResponse({"ok": True, "id": batch.id})


def _apply_product_payload(product, tenant, data):
    group_id = data.get("item_group_id")
    product.item_group = ItemGroup.objects.filter(tenant=tenant, id=group_id).first() if group_id else None
    product.qb_item_name = (data.get("qb_item_name") or "").strip()
    product.friendly_name = (data.get("friendly_name") or "").strip()
    product.description = (data.get("description") or "").strip()
    product.size_cull = (data.get("size_cull") or "").strip()
    product.sku = (data.get("sku") or "").strip()
    product.tasting_notes = (data.get("tasting_notes") or "").strip()
    product.quantity_description = (data.get("quantity_description") or "").strip()
    product.country_of_origin = (data.get("country_of_origin") or "").strip()
    product.origin = product.country_of_origin or product.origin
    product.brand = (data.get("brand") or "").strip()
    product.inventory_unit_of_measure = (data.get("inventory_unit_of_measure") or "").strip()
    product.unit_type = product.inventory_unit_of_measure or product.unit_type
    product.selling_unit_of_measure = (data.get("selling_unit_of_measure") or "").strip()
    product.buying_unit_of_measure = (data.get("buying_unit_of_measure") or "").strip()
    product.raw_cost = data.get("raw_cost") or None
    product.list_price = data.get("list_price") or None
    product.wholesale_price = data.get("wholesale_price") or None
    product.habitat_production_method = (data.get("habitat_production_method") or "").strip()
    product.species = (data.get("species") or "").strip()
    product.department = (data.get("department") or "").strip()
    product.upc = (data.get("upc") or "").strip()
    product.item_name = product.generate_item_name()


# ── CSV helpers ──────────────────────────────────────────────────

def _parse_import(request):
    """Parse import data — accepts JSON {rows: [...]} from the preview modal."""
    try:
        data = json.loads(request.body)
        rows = data.get("rows")
        if not rows or not isinstance(rows, list):
            return None, JsonResponse({"error": "No rows provided."}, status=400)
        return rows, None
    except (json.JSONDecodeError, Exception) as e:
        return None, JsonResponse({"error": f"Invalid request: {e}"}, status=400)


def _csv_response(rows, filename):
    """Build an HttpResponse with CSV content."""
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    if not rows:
        return resp
    writer = csv.DictWriter(resp, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return resp


def _parse_date(val):
    """Parse a date string, returning None if blank/invalid."""
    if not val or not val.strip():
        return None
    try:
        from datetime import datetime
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(val):
    if not val or not val.strip():
        return None
    try:
        return Decimal(val.strip().replace(",", ""))
    except Exception:
        return None


# ── Sales Orders export / import ────────────────────────────────

@login_required
def sales_orders_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    orders = SalesOrder.objects.filter(tenant=tenant).order_by("-order_date", "-created_at")
    rows = [
        {
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "order_status": o.order_status,
            "packed_status": o.packed_status,
            "qb_invoice_number": o.qb_invoice_number,
            "sales_rep": o.sales_rep,
            "po_number": o.po_number,
            "order_date": o.order_date or "",
            "delivery_date": o.delivery_date or "",
            "ship_date": o.ship_date or "",
            "shipper": o.shipper,
            "shipping_route": o.shipping_route,
            "notes": o.notes,
        }
        for o in orders
    ]
    return _csv_response(rows, "sales_orders.csv")


@login_required
@require_POST
def sales_orders_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    existing = set(SalesOrder.objects.filter(tenant=tenant).values_list("order_number", flat=True))
    created = []
    skipped = 0
    for row in rows:
        on = row.get("order_number", "").strip()
        if not on or on in existing:
            skipped += 1
            continue
        created.append(SalesOrder(
            tenant=tenant,
            order_number=on,
            customer_name=row.get("customer_name", "").strip(),
            order_status=row.get("order_status", "draft").strip() or "draft",
            packed_status=row.get("packed_status", "not_packed").strip() or "not_packed",
            qb_invoice_number=row.get("qb_invoice_number", "").strip(),
            sales_rep=row.get("sales_rep", "").strip(),
            po_number=row.get("po_number", "").strip(),
            order_date=_parse_date(row.get("order_date")),
            delivery_date=_parse_date(row.get("delivery_date")),
            ship_date=_parse_date(row.get("ship_date")),
            shipper=row.get("shipper", "").strip(),
            shipping_route=row.get("shipping_route", "").strip(),
            notes=row.get("notes", "").strip(),
            created_by=request.user,
        ))
        existing.add(on)
    SalesOrder.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": skipped})


# ── Purchase Orders export / import ─────────────────────────────

@login_required
def purchasing_orders_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    orders = PurchaseOrder.objects.filter(tenant=tenant).order_by("-order_date", "-created_at")
    rows = [
        {
            "po_number": o.po_number,
            "vendor_name": o.vendor_name,
            "order_status": o.order_status,
            "receive_status": o.receive_status,
            "qb_po_number": o.qb_po_number,
            "buyer": o.buyer,
            "vendor_invoice_number": o.vendor_invoice_number,
            "order_date": o.order_date or "",
            "expected_date": o.expected_date or "",
            "notes": o.notes,
        }
        for o in orders
    ]
    return _csv_response(rows, "purchase_orders.csv")


@login_required
@require_POST
def purchasing_orders_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    existing = set(PurchaseOrder.objects.filter(tenant=tenant).values_list("po_number", flat=True))
    created = []
    skipped = 0
    for row in rows:
        pn = row.get("po_number", "").strip()
        if not pn or pn in existing:
            skipped += 1
            continue
        created.append(PurchaseOrder(
            tenant=tenant,
            po_number=pn,
            vendor_name=row.get("vendor_name", "").strip(),
            order_status=row.get("order_status", "draft").strip() or "draft",
            receive_status=row.get("receive_status", "not_received").strip() or "not_received",
            qb_po_number=row.get("qb_po_number", "").strip(),
            buyer=row.get("buyer", "").strip(),
            vendor_invoice_number=row.get("vendor_invoice_number", "").strip(),
            order_date=_parse_date(row.get("order_date")),
            expected_date=_parse_date(row.get("expected_date")),
            notes=row.get("notes", "").strip(),
            created_by=request.user,
        ))
        existing.add(pn)
    PurchaseOrder.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": skipped})


# ── Receiving Lots export / import ───────────────────────────────

@login_required
def receiving_lots_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    lots = Inventory.objects.filter(tenant=tenant).order_by("-receivedate")
    rows = [
        {
            "vendorlot": lot.vendorlot,
            "productid": lot.productid,
            "desc": lot.desc,
            "vendorid": lot.vendorid,
            "receivedate": lot.receivedate,
            "vendorlot": lot.vendorlot,
            "unittype": lot.unittype,
            "unitsonhand": lot.unitsonhand or "",
            "unitsin": lot.unitsin or "",
            "actualcost": lot.actualcost or "",
        }
        for lot in lots
    ]
    return _csv_response(rows, "receiving_lots.csv")


@login_required
@require_POST
def receiving_lots_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    created = []
    for row in rows:
        lot = Inventory(
            tenant=tenant,
            productid=row.get("productid", "").strip(),
            desc=row.get("desc", "").strip(),
            vendorid=row.get("vendorid", "").strip(),
            receivedate=row.get("receivedate", "").strip(),
            vendorlot=row.get("vendorlot", "").strip(),
            unittype=row.get("unittype", "").strip(),
            unitsonhand=_parse_decimal(row.get("unitsonhand")),
            unitsin=_parse_decimal(row.get("unitsin")),
            actualcost=_parse_decimal(row.get("actualcost")),
        )
        created.append(lot)
    Inventory.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": 0})


# ── Processing Batches export / import ───────────────────────────

@login_required
def processing_batches_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batches = ProcessBatch.objects.filter(tenant=tenant).order_by("-started_at")
    rows = [
        {
            "batch_number": b.batch_number,
            "process_type": b.process_type,
            "status": b.status,
            "started_at": b.started_at.strftime("%Y-%m-%d %H:%M") if b.started_at else "",
            "completed_at": b.completed_at.strftime("%Y-%m-%d %H:%M") if b.completed_at else "",
            "notes": b.notes,
        }
        for b in batches
    ]
    return _csv_response(rows, "processing_batches.csv")


@login_required
@require_POST
def processing_batches_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    existing = set(ProcessBatch.objects.filter(tenant=tenant).values_list("batch_number", flat=True))
    created = []
    skipped = 0
    for row in rows:
        bn = row.get("batch_number", "").strip()
        if not bn or bn in existing:
            skipped += 1
            continue
        created.append(ProcessBatch(
            tenant=tenant,
            batch_number=bn,
            process_type=row.get("process_type", "").strip(),
            status=row.get("status", "draft").strip() or "draft",
            notes=row.get("notes", "").strip(),
            created_by=request.user,
        ))
        existing.add(bn)
    ProcessBatch.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": skipped})


# ── Inventory Items export / import ──────────────────────────────

@login_required
def inventory_items_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    items = Product.objects.filter(tenant=tenant, is_active=True).order_by("item_name")
    rows = [
        {
            "qb_item_name": p.qb_item_name,
            "friendly_name": p.friendly_name,
            "description": p.description,
            "species": p.species,
            "size_cull": p.size_cull,
            "sku": p.sku,
            "quantity_description": p.quantity_description,
            "country_of_origin": p.country_of_origin,
            "brand": p.brand,
            "department": p.department,
            "inventory_unit_of_measure": p.inventory_unit_of_measure,
            "list_price": p.list_price or "",
            "wholesale_price": p.wholesale_price or "",
            "upc": p.upc,
        }
        for p in items
    ]
    return _csv_response(rows, "inventory_items.csv")


@login_required
@require_POST
def inventory_items_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    created = []
    for row in rows:
        p = Product(
            tenant=tenant,
            qb_item_name=row.get("qb_item_name", "").strip(),
            friendly_name=row.get("friendly_name", "").strip(),
            description=row.get("description", "").strip(),
            species=row.get("species", "").strip(),
            size_cull=row.get("size_cull", "").strip(),
            sku=row.get("sku", "").strip(),
            quantity_description=row.get("quantity_description", "").strip(),
            country_of_origin=row.get("country_of_origin", "").strip(),
            brand=row.get("brand", "").strip(),
            department=row.get("department", "").strip(),
            inventory_unit_of_measure=row.get("inventory_unit_of_measure", "").strip(),
            list_price=_parse_decimal(row.get("list_price")),
            wholesale_price=_parse_decimal(row.get("wholesale_price")),
            upc=row.get("upc", "").strip(),
        )
        p.item_name = p.generate_item_name()
        created.append(p)
    Product.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": 0})


# ── Vendors export / import ──────────────────────────────────────

@login_required
def vendors_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    vendors = Vendor.objects.filter(tenant=tenant, is_active=True).order_by("name")
    rows = [
        {
            "name": v.name,
            "vendor_type": v.vendor_type,
            "contact_name": v.contact_name,
            "email": v.email,
            "phone": v.phone,
            "address": v.address,
            "city": v.city,
            "state": v.state,
            "zipcode": v.zipcode,
            "cert": v.cert,
            "fax": v.fax,
            "billing_email": v.billing_email,
        }
        for v in vendors
    ]
    return _csv_response(rows, "vendors.csv")


@login_required
@require_POST
def vendors_import(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    rows, err = _parse_import(request)
    if err:
        return err
    # Auto-assign vendor_id
    max_id = Vendor.objects.filter(tenant=tenant).order_by("-vendor_id").values_list("vendor_id", flat=True).first() or 0
    created = []
    for i, row in enumerate(rows, start=1):
        v = Vendor(
            tenant=tenant,
            vendor_id=max_id + i,
            name=row.get("name", "").strip(),
            vendor_type=row.get("vendor_type", "").strip(),
            contact_name=row.get("contact_name", "").strip(),
            email=row.get("email", "").strip(),
            phone=row.get("phone", "").strip(),
            address=row.get("address", "").strip(),
            city=row.get("city", "").strip(),
            state=row.get("state", "").strip(),
            zipcode=row.get("zipcode", "").strip(),
            cert=row.get("cert", "").strip(),
            fax=row.get("fax", "").strip(),
            billing_email=row.get("billing_email", "").strip(),
        )
        created.append(v)
    Vendor.objects.bulk_create(created)
    return JsonResponse({"imported": len(created), "skipped": 0})


# ── Shipping Log export ──────────────────────────────────────────

@login_required
def shipping_log_export(request):
    tenant, error = _require_tenant(request)
    if error:
        return error
    orders = SalesOrder.objects.filter(tenant=tenant).exclude(
        order_status__in=["draft", "cancelled"]
    ).order_by("-ship_date", "-order_date")
    rows = [
        {
            "order_number": o.order_number,
            "customer_name": o.customer_name,
            "ship_date": o.ship_date or "",
            "shipper": o.shipper,
            "shipping_route": o.shipping_route,
            "packed_status": o.get_packed_status_display(),
            "order_status": o.get_order_status_display(),
        }
        for o in orders
    ]
    return _csv_response(rows, "shipping_log.csv")


# ── Traceability ────────────────────────────────────────────────


@login_required
def trace_lookup(request):
    """Trace a product through the full workflow: PO → Receiving → Processing → Sales."""
    tenant, error = _require_tenant(request)
    if error:
        return error

    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"error": "Search query required."}, status=400)

    # Collect all related inventory lot IDs
    lot_ids = set()

    # Search by PO number
    pos = PurchaseOrder.objects.filter(tenant=tenant, po_number__icontains=q)
    po_ids = set(pos.values_list("id", flat=True))

    # Search by lot code
    lots_by_code = Inventory.objects.filter(tenant=tenant).filter(
        Q(vendorlot__icontains=q) | Q(desc__icontains=q) | Q(productid__icontains=q)
    )
    lot_ids.update(lots_by_code.values_list("id", flat=True))

    # Search by batch number
    batches_by_num = ProcessBatch.objects.filter(tenant=tenant, batch_number__icontains=q)
    for batch in batches_by_num.prefetch_related("sources__inventory"):
        for src in batch.sources.all():
            if src.inventory_id:
                lot_ids.add(src.inventory_id)

    # Search by sales order number
    sos_by_num = SalesOrder.objects.filter(tenant=tenant, order_number__icontains=q)
    so_ids = set(sos_by_num.values_list("id", flat=True))
    sales_product_ids = set()
    sales_item_descriptions = set()
    so_items = SalesOrderItem.objects.filter(
        tenant=tenant,
        sales_order__in=sos_by_num,
        item_type="item",
    ).select_related("product")
    for item in so_items:
        if item.product_id and item.product and item.product.product_id:
            sales_product_ids.add(item.product.product_id)
        elif item.description:
            sales_item_descriptions.add(item.description.strip())
    so_allocs = SalesOrderAllocation.objects.filter(
        tenant=tenant, sales_order_item__sales_order__in=sos_by_num
    )
    lot_ids.update(so_allocs.values_list("inventory_id", flat=True))

    # If the SO has no allocations yet, fall back to matching lots by ordered product.
    if sales_product_ids or sales_item_descriptions:
        matching_sales_lots = Inventory.objects.filter(tenant=tenant).filter(
            Q(productid__in=sales_product_ids) |
            Q(desc__in=sales_item_descriptions)
        )
        lot_ids.update(matching_sales_lots.values_list("id", flat=True))

    # Expand from POs → lots
    if po_ids:
        po_lots = Inventory.objects.filter(tenant=tenant, purchase_order_id__in=po_ids)
        lot_ids.update(po_lots.values_list("id", flat=True))

    # Now build the full chain from all discovered lots
    # Expand lots → POs (backward)
    all_lots = Inventory.objects.filter(tenant=tenant, id__in=lot_ids).select_related("purchase_order")
    for lot in all_lots:
        if lot.purchase_order_id:
            po_ids.add(lot.purchase_order_id)

    # Expand lots → processing batches (forward)
    batch_sources = ProcessBatchSource.objects.filter(tenant=tenant, inventory_id__in=lot_ids).select_related("batch")
    batch_ids = set(bs.batch_id for bs in batch_sources)

    # Also include output lots from those batches
    batch_outputs = ProcessBatchOutput.objects.filter(tenant=tenant, batch_id__in=batch_ids)
    output_lot_ids = set(bo.inventory_id for bo in batch_outputs if bo.inventory_id)
    lot_ids.update(output_lot_ids)

    # Expand lots → sales orders (forward)
    all_allocs = SalesOrderAllocation.objects.filter(
        tenant=tenant, inventory_id__in=lot_ids
    ).select_related("sales_order_item__sales_order")
    so_ids.update(a.sales_order_item.sales_order_id for a in all_allocs)

    # Build response
    purchase_orders = PurchaseOrder.objects.filter(tenant=tenant, id__in=po_ids).prefetch_related("items__product")
    receiving_lots = Inventory.objects.filter(tenant=tenant, id__in=lot_ids).select_related("purchase_order")
    processing = ProcessBatch.objects.filter(tenant=tenant, id__in=batch_ids).prefetch_related("sources__inventory", "outputs")
    sales_orders = SalesOrder.objects.filter(tenant=tenant, id__in=so_ids).prefetch_related("items__allocations__inventory")

    return JsonResponse({
        "purchase_orders": [
            {
                "id": po.id,
                "po_number": po.po_number,
                "vendor_name": po.vendor_name,
                "order_status": po.get_order_status_display(),
                "order_date": _date_str(po.order_date),
                "products": ", ".join(sorted(set(filter(None, (
                    (item.product.species or item.product.item_name or "") if item.product else item.description
                    for item in po.items.all() if item.item_type == "item"
                ))))) or "",
                "total": _to_float(sum((item.amount or 0) for item in po.items.all())),
            }
            for po in purchase_orders
        ],
        "receiving_lots": [
            {
                "id": lot.id,
                "trace_lot": lot.vendorlot or f"LOT-{lot.id}",
                "product_name": lot.desc or lot.productid or "",
                "vendor": lot.vendorid or "",
                "receive_date": lot.receivedate or "",
                "on_hand": _to_float(lot.unitsonhand) or 0,
                "unit_type": lot.unittype or "",
                "po_number": lot.purchase_order.po_number if lot.purchase_order_id and lot.purchase_order else (lot.poid or ""),
                "po_id": lot.purchase_order_id,
            }
            for lot in receiving_lots
        ],
        "processing_batches": [
            {
                "id": batch.id,
                "batch_number": batch.batch_number,
                "process_type": batch.get_process_type_display() if hasattr(batch, 'get_process_type_display') else batch.process_type,
                "status": batch.get_status_display(),
                "started_at": batch.started_at.strftime("%Y-%m-%d %I:%M %p") if batch.started_at else "",
                "source_lots": [
                    {"id": s.inventory_id, "trace_lot": s.inventory.vendorlot or f"LOT-{s.inventory_id}" if s.inventory else ""}
                    for s in batch.sources.all()
                ],
                "products": ", ".join(sorted(set(
                    (s.inventory.desc or s.inventory.productid or "")
                    for s in batch.sources.all() if s.inventory
                ))) or "",
            }
            for batch in processing
        ],
        "sales_orders": [
            {
                "id": so.id,
                "order_number": so.order_number,
                "customer_name": so.customer_name,
                "order_status": so.get_order_status_display(),
                "order_date": _date_str(so.order_date),
                "total": _sales_order_total(so),
                "allocated_lots": list(set(
                    a.inventory.vendorlot or f"LOT-{a.inventory_id}"
                    for item in so.items.all()
                    for a in item.allocations.all()
                    if a.inventory_id and a.inventory
                )),
            }
            for so in sales_orders
        ],
    })


# ── Product orders lookup ───────────────────────────────────────


@login_required
def product_orders(request, item_id):
    """Return sales orders and purchase orders that include this product."""
    tenant, error = _require_tenant(request)
    if error:
        return error
    product = get_object_or_404(Product.objects.filter(tenant=tenant), id=item_id)

    # Sales orders containing this product
    so_items = SalesOrderItem.objects.filter(
        tenant=tenant, product=product
    ).select_related("sales_order").order_by("-sales_order__order_date")
    sales_orders = []
    seen_so = set()
    for item in so_items:
        so = item.sales_order
        if so.id not in seen_so:
            seen_so.add(so.id)
            sales_orders.append({
                "id": so.id,
                "order_number": so.order_number,
                "customer_name": so.customer_name,
                "order_status": so.get_order_status_display(),
                "order_date": _date_str(so.order_date),
                "quantity": _to_float(item.quantity) or 0,
                "unit_type": item.unit_type or "",
                "total": _to_float(item.amount) or 0,
            })

    # Purchase orders containing this product
    po_items = PurchaseOrderItem.objects.filter(
        tenant=tenant, product=product
    ).select_related("purchase_order").order_by("-purchase_order__order_date")
    purchase_orders = []
    seen_po = set()
    for item in po_items:
        po = item.purchase_order
        if po.id not in seen_po:
            seen_po.add(po.id)
            purchase_orders.append({
                "id": po.id,
                "po_number": po.po_number,
                "vendor_name": po.vendor_name,
                "order_status": po.get_order_status_display(),
                "order_date": _date_str(po.order_date),
                "quantity": _to_float(item.quantity) or 0,
                "unit_type": item.unit_type or "",
                "total": _to_float(item.amount) or 0,
            })

    return JsonResponse({
        "sales_orders": sales_orders,
        "purchase_orders": purchase_orders,
    })


# ── Delete endpoints ────────────────────────────────────────────


@login_required
@require_POST
def purchasing_order_delete(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    order = get_object_or_404(PurchaseOrder.objects.filter(tenant=tenant), id=order_id)
    order.items.all().delete()
    order.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def receiving_lot_delete(request, lot_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    lot = get_object_or_404(Inventory.objects.filter(tenant=tenant), id=lot_id)
    lot.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def processing_batch_delete(request, batch_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    batch = get_object_or_404(ProcessBatch.objects.filter(tenant=tenant), id=batch_id)
    _restore_and_delete_process_batch(batch)
    return JsonResponse({"success": True})


@login_required
@require_POST
def processing_sold_result_delete(request, batch_id, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error

    batch = get_object_or_404(ProcessBatch.objects.filter(tenant=tenant), id=batch_id)
    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)

    with transaction.atomic():
        SalesOrderAllocation.objects.filter(tenant=tenant, sales_order_item__sales_order=so).delete()
        so.items.all().delete()
        so.delete()
        _restore_and_delete_process_batch(batch)

    return JsonResponse({"success": True})


@login_required
@require_POST
def sales_order_delete(request, order_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    so = get_object_or_404(SalesOrder.objects.filter(tenant=tenant), id=order_id)
    SalesOrderAllocation.objects.filter(tenant=tenant, sales_order_item__sales_order=so).delete()
    so.items.all().delete()
    so.delete()
    return JsonResponse({"success": True})


@login_required
@require_POST
def vendor_delete(request, vendor_id):
    tenant, error = _require_tenant(request)
    if error:
        return error
    vendor = get_object_or_404(Vendor.objects.filter(tenant=tenant), id=vendor_id)
    vendor.delete()
    return JsonResponse({"success": True})
