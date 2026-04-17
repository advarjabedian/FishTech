from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.models import ProcessBatch, Product, PurchaseOrder, SalesOrder, SalesOrderAllocation


PROCESS_LABELS = {
    "fish_cutting": "Fish Cutting",
    "commingle": "Commingle",
    "renaming": "Renaming",
    "freeze": "Freeze",
    "lot_breaking": "Lot Breaking",
    "shucking": "Shucking",
    "wet_store": "Wet Store",
}


def _tenant_page(template_name, extra_context=None):
    @login_required
    def view(request):
        if not getattr(request, "tenant", None):
            return redirect("home")
        context = extra_context(request) if callable(extra_context) else (extra_context or {})
        return render(request, template_name, context)

    return view


# ── Core workflow pages ──────────────────────────────────────────
purchases_page = _tenant_page("core/arrivals.html")
receiving_page = _tenant_page("core/arrivals.html")
inventory_item_library = _tenant_page("core/inventory_item_library.html")
@login_required
def processing_hub(request):
    if not getattr(request, "tenant", None):
        return redirect("home")
    sale_mode = request.GET.get("mode", "").strip() == "sale"
    return render(
        request,
        "core/processing_hub.html",
        {
            "sale_mode": sale_mode,
            "selected_lot_id": request.GET.get("lot_id", "").strip(),
        },
    )
sales_orders_page = _tenant_page("core/sales_orders.html")
vendor_list_page = _tenant_page("core/vendor_list.html")
customer_list_page = _tenant_page("core/customer_list.html")
trace_page = _tenant_page("core/trace.html")

# ── Compliance / HACCP ───────────────────────────────────────────
compliance_hub = _tenant_page("core/compliance_hub.html")
operations_dashboard = _tenant_page("core/DailyInspections/operations_admin.html")
operations_admin = _tenant_page("core/DailyInspections/operations_admin.html")


@login_required
def purchase_detail_page(request, po_id):
    if not getattr(request, "tenant", None):
        return redirect("home")
    po = get_object_or_404(PurchaseOrder.objects.filter(tenant=request.tenant), id=po_id)
    return render(request, "core/purchase_detail.html", {"po": po})


@login_required
def inventory_item_detail_page(request, item_id):
    if not getattr(request, "tenant", None):
        return redirect("home")
    product = get_object_or_404(Product.objects.select_related("item_group").filter(tenant=request.tenant), id=item_id)
    base_name = product.item_name or product.description or product.product_id or "Item"
    initials = "".join(part[0] for part in base_name.split()[:2]).upper() or "IT"
    return render(
        request,
        "core/inventory_item_detail.html",
        {
            "product": product,
            "initials": initials,
            "sc": [
                "Small", "Medium", "Large", "Jumbo", "Mixed", "Choice", "Select",
                "1x", "1+ Per Lb", "2-3 Per Lb", "10 Dozen", "50 CT Bag", "100 Ct Bag", "10 # Bag",
            ],
            "h": [
                "Wild", "Farm Raised", "Aquaculture", "Line Caught",
                "Net Caught", "Dredged", "Dive Harvested",
            ],
            "c": [
                "USA", "Canada", "Mexico", "Chile", "Ecuador", "Japan", "China",
                "Vietnam", "Thailand", "Indonesia", "India", "Norway", "Iceland",
                "Spain", "Portugal", "UK", "Australia", "New Zealand",
            ],
        },
    )


@login_required
def settings_page(request):
    if not getattr(request, "tenant", None):
        return redirect("home")
    return render(request, "core/settings.html", {"tenant": request.tenant})


@login_required
def processing_new(request):
    if not getattr(request, "tenant", None):
        return redirect("home")
    process_type = request.GET.get("type", "").strip()
    sale_mode = request.GET.get("mode", "").strip() == "sale"
    return render(
        request,
        "core/processing_sale_new.html" if sale_mode else "core/processing_new.html",
        {
            "process_type": process_type,
            "process_type_label": PROCESS_LABELS.get(process_type, "Process"),
            "sale_mode": sale_mode,
        },
    )


@login_required
def sales_order_detail(request, order_id):
    if not getattr(request, "tenant", None):
        return redirect("home")
    so = get_object_or_404(SalesOrder, id=order_id, tenant=request.tenant)
    # Traceability: find allocated lots and their source POs
    allocs = SalesOrderAllocation.objects.filter(
        tenant=request.tenant, sales_order_item__sales_order=so
    ).select_related("inventory__purchase_order")
    trace_lots = {}
    trace_pos = {}
    for a in allocs:
        inv = a.inventory
        if inv and inv.id not in trace_lots:
            trace_lots[inv.id] = {"trace_lot": inv.vendorlot or f"LOT-{inv.id}"}
            po = inv.purchase_order
            if po and po.id not in trace_pos:
                trace_pos[po.id] = {"id": po.id, "po_number": po.po_number}
    return render(request, "core/sales_order_detail.html", {
        "so": so,
        "trace_lots": list(trace_lots.values()),
        "trace_pos": list(trace_pos.values()),
    })


@login_required
def shipping_hub(request):
    return redirect("sales_orders_page")


@login_required
def shipping_picking(request):
    return redirect("sales_orders_page")


@login_required
def shipping_packing(request):
    return redirect("sales_orders_page")


@login_required
def shipping_loading(request):
    return redirect("sales_orders_page")


@login_required
def processing_detail(request, batch_id):
    if not getattr(request, "tenant", None):
        return redirect("home")
    batch = get_object_or_404(
        ProcessBatch.objects.prefetch_related("sources__inventory__purchase_order"),
        id=batch_id, tenant=request.tenant,
    )
    source_pos = {}
    source_lots = []
    for src in batch.sources.all():
        if src.inventory:
            source_lots.append({"trace_lot": src.inventory.vendorlot or f"LOT-{src.inventory_id}"})
            po = src.inventory.purchase_order
            if po and po.id not in source_pos:
                source_pos[po.id] = {"id": po.id, "po_number": po.po_number}
    return render(request, "core/processing_detail.html", {
        "batch": batch,
        "source_pos": list(source_pos.values()),
        "source_lots_trace": source_lots,
    })
