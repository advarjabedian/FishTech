from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Customer,
    Inventory,
    ProcessBatch,
    ProcessBatchOutput,
    ProcessBatchSource,
    ProcessBatchWaste,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    ReceivingQualityCheck,
    SalesOrder,
    SalesOrderAllocation,
    SalesOrderItem,
    Tenant,
    TenantUser,
    Vendor,
)


DEMO_PO_PREFIX = "DEMO-PO-"
DEMO_SO_PREFIX = "DEMO-SO-"
DEMO_BATCH_PREFIX = "DEMO-PB-"
DEMO_LOT_PREFIX = "DEMO-LOT-"


class Command(BaseCommand):
    help = "Seed Golden State Seafood with reusable demo data for operations screens."

    @transaction.atomic
    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name="Golden State Seafood").first()
        if not tenant:
            raise CommandError("Tenant 'Golden State Seafood' was not found.")

        tenant_user = TenantUser.objects.select_related("user").filter(tenant=tenant).first()
        user = tenant_user.user if tenant_user else get_user_model().objects.filter(is_superuser=True).first()
        if not user:
            raise CommandError("No user available to own demo records.")

        self.stdout.write("Refreshing demo records for Golden State Seafood...")
        self._purge_demo_data(tenant)

        vendors = self._pick_vendors(tenant)
        products = self._pick_products(tenant)
        customers = self._pick_customers(tenant)

        purchases = self._create_purchase_orders(tenant, user, vendors, products)
        lots = self._create_receiving_lots(tenant, user, products, purchases)
        self._create_sales_orders(tenant, user, customers, products, lots)
        self._create_process_batches(tenant, user, products, lots)

        self.stdout.write(self.style.SUCCESS("Golden State Seafood demo data refreshed."))

    def _purge_demo_data(self, tenant):
        SalesOrder.objects.filter(tenant=tenant, order_number__startswith=DEMO_SO_PREFIX).delete()
        PurchaseOrder.objects.filter(tenant=tenant, po_number__startswith=DEMO_PO_PREFIX).delete()
        ProcessBatch.objects.filter(tenant=tenant, batch_number__startswith=DEMO_BATCH_PREFIX).delete()
        Inventory.objects.filter(tenant=tenant, vendorlot__startswith=DEMO_LOT_PREFIX).delete()

    def _pick_vendors(self, tenant):
        names = [
            "Alaska Wild Harvest",
            "Nordic Salmon Imports",
            "Baja Seafood Supply",
            "Maine Lobster Direct",
        ]
        vendors = {vendor.name: vendor for vendor in Vendor.objects.filter(tenant=tenant, name__in=names)}
        if len(vendors) < 3:
            raise CommandError("Not enough vendor records exist for Golden State Seafood.")
        return vendors

    def _pick_products(self, tenant):
        codes = {
            "salmon": "SAL-001",
            "tuna": "TUN-002",
            "scallops": "SCA-001",
            "crab": "CRB-001",
            "halibut": "HAL-001",
        }
        products = {}
        for key, code in codes.items():
            product = Product.objects.filter(tenant=tenant, product_id=code).first()
            if not product:
                product = Product.objects.filter(tenant=tenant).exclude(product_id="").order_by("description").first()
            if not product:
                raise CommandError("Not enough product records exist for Golden State Seafood.")
            products[key] = product
        return products

    def _pick_customers(self, tenant):
        names = [
            "Pacific Rim Restaurant Group",
            "Ocean Blue Sushi Bar",
            "Bayshore Catering Co.",
            "Santa Monica Seafood Market",
        ]
        customers = {customer.name: customer for customer in Customer.objects.filter(tenant=tenant, name__in=names)}
        if len(customers) < 3:
            raise CommandError("Not enough customer records exist for Golden State Seafood.")
        return customers

    def _create_purchase_orders(self, tenant, user, vendors, products):
        today = timezone.localdate()

        po_specs = [
            {
                "number": f"{DEMO_PO_PREFIX}1001",
                "vendor": vendors["Alaska Wild Harvest"],
                "status": "open",
                "receive_status": "partial",
                "buyer": "Marco Ruiz",
                "order_date": today - timezone.timedelta(days=7),
                "expected_date": today - timezone.timedelta(days=2),
                "items": [
                    (products["halibut"], "item", Decimal("220"), Decimal("14.75")),
                    (products["scallops"], "item", Decimal("90"), Decimal("28.00")),
                    (None, "fee", None, Decimal("165.00"), "Cold-chain freight"),
                ],
            },
            {
                "number": f"{DEMO_PO_PREFIX}1002",
                "vendor": vendors["Nordic Salmon Imports"],
                "status": "closed",
                "receive_status": "received",
                "buyer": "Ariana Chen",
                "order_date": today - timezone.timedelta(days=5),
                "expected_date": today - timezone.timedelta(days=1),
                "items": [
                    (products["salmon"], "item", Decimal("320"), Decimal("12.50")),
                    (products["tuna"], "item", Decimal("140"), Decimal("33.50")),
                ],
            },
            {
                "number": f"{DEMO_PO_PREFIX}1003",
                "vendor": vendors["Baja Seafood Supply"],
                "status": "draft",
                "receive_status": "not_received",
                "buyer": "Jordan Lee",
                "order_date": today - timezone.timedelta(days=1),
                "expected_date": today + timezone.timedelta(days=3),
                "items": [
                    (products["crab"], "item", Decimal("180"), Decimal("16.50")),
                    (products["scallops"], "item", Decimal("60"), Decimal("31.25")),
                ],
            },
            {
                "number": f"{DEMO_PO_PREFIX}1004",
                "vendor": vendors["Maine Lobster Direct"],
                "status": "open",
                "receive_status": "not_received",
                "buyer": "Marco Ruiz",
                "order_date": today,
                "expected_date": today + timezone.timedelta(days=4),
                "items": [
                    (products["crab"], "item", Decimal("75"), Decimal("44.00")),
                ],
            },
        ]

        orders = {}
        for spec in po_specs:
            order = PurchaseOrder.objects.create(
                tenant=tenant,
                po_number=spec["number"],
                vendor=spec["vendor"],
                vendor_name=spec["vendor"].name,
                order_status=spec["status"],
                receive_status=spec["receive_status"],
                buyer=spec["buyer"],
                qb_po_number=spec["number"].replace(DEMO_PO_PREFIX, "QB-"),
                order_date=spec["order_date"],
                expected_date=spec["expected_date"],
                notes="Demo purchasing flow for customer presentation.",
                created_by=user,
            )
            for idx, item_spec in enumerate(spec["items"]):
                product, item_type, quantity, unit_price, *extra = item_spec
                description = extra[0] if extra else (product.item_name or product.description)
                amount = unit_price if item_type == "fee" else quantity * unit_price
                PurchaseOrderItem.objects.create(
                    tenant=tenant,
                    purchase_order=order,
                    item_type=item_type,
                    product=product,
                    description=description,
                    notes="Demo line",
                    quantity=quantity,
                    unit_type=(product.unit_type or "Lbs") if product else "",
                    unit_price=unit_price,
                    amount=amount,
                    sort_order=idx,
                )
            orders[spec["number"]] = order
        return orders

    def _create_receiving_lots(self, tenant, user, products, purchases):
        today = timezone.localdate()
        po1 = purchases[f"{DEMO_PO_PREFIX}1001"]
        po2 = purchases[f"{DEMO_PO_PREFIX}1002"]
        po1_items = list(po1.items.filter(item_type="item").order_by("id"))
        po2_items = list(po2.items.filter(item_type="item").order_by("id"))

        lot_specs = [
            {
                "lot": f"{DEMO_LOT_PREFIX}001",
                "product": products["halibut"],
                "po": po1,
                "po_item": po1_items[0],
                "vendor": po1.vendor,
                "date": today - timezone.timedelta(days=2),
                "qty": Decimal("150"),
                "cost": Decimal("14.75"),
                "location": "Cooler A1",
                "status": "pass",
                "score": 9,
            },
            {
                "lot": f"{DEMO_LOT_PREFIX}002",
                "product": products["scallops"],
                "po": po1,
                "po_item": po1_items[1],
                "vendor": po1.vendor,
                "date": today - timezone.timedelta(days=2),
                "qty": Decimal("40"),
                "cost": Decimal("28.00"),
                "location": "Cooler B2",
                "status": "hold",
                "score": 7,
            },
            {
                "lot": f"{DEMO_LOT_PREFIX}003",
                "product": products["salmon"],
                "po": po2,
                "po_item": po2_items[0],
                "vendor": po2.vendor,
                "date": today - timezone.timedelta(days=1),
                "qty": Decimal("320"),
                "cost": Decimal("12.50"),
                "location": "Cooler C1",
                "status": "pass",
                "score": 10,
            },
            {
                "lot": f"{DEMO_LOT_PREFIX}004",
                "product": products["tuna"],
                "po": po2,
                "po_item": po2_items[1],
                "vendor": po2.vendor,
                "date": today - timezone.timedelta(days=1),
                "qty": Decimal("140"),
                "cost": Decimal("33.50"),
                "location": "Freezer A3",
                "status": "pass",
                "score": 9,
            },
            {
                "lot": f"{DEMO_LOT_PREFIX}005",
                "product": products["crab"],
                "po": None,
                "po_item": None,
                "vendor": Vendor.objects.filter(tenant=tenant, name="Baja Seafood Supply").first(),
                "date": today,
                "qty": Decimal("85"),
                "cost": Decimal("17.25"),
                "location": "Cooler D4",
                "status": "reject",
                "score": 4,
            },
        ]

        lots = {}
        for spec in lot_specs:
            product = spec["product"]
            lot = Inventory.objects.create(
                tenant=tenant,
                productid=product.product_id,
                desc=product.item_name or product.description,
                vendorid=spec["vendor"].name if spec["vendor"] else "",
                vendorlot=spec["lot"],
                actualcost=spec["cost"],
                unittype=product.unit_type or "Lbs",
                unitsonhand=spec["qty"],
                unitsavailable=spec["qty"],
                unitsin=spec["qty"],
                receivedate=spec["date"].strftime("%Y-%m-%d"),
                poid=spec["po"].po_number if spec["po"] else "",
                purchase_order=spec["po"],
                po_item=spec["po_item"],
                origin=product.origin or "West Coast",
                location=spec["location"],
                receive_time="8:15 am",
                vendor_type=spec["vendor"].vendor_type if spec["vendor"] else "",
                age=Decimal("1"),
            )
            ReceivingQualityCheck.objects.create(
                tenant=tenant,
                inventory=lot,
                freshness_score=spec["score"],
                appearance_ok=spec["status"] != "reject",
                odor_ok=spec["status"] == "pass",
                texture_ok=spec["status"] != "reject",
                packaging_ok=True,
                temp_ok=spec["status"] == "pass",
                status=spec["status"],
                notes=f"Demo receiving check: {spec['status']}.",
                checked_by=user,
                checked_by_name=user.get_username(),
            )
            if spec["po_item"]:
                spec["po_item"].received_quantity = spec["qty"]
                spec["po_item"].save(update_fields=["received_quantity"])
            lots[spec["lot"]] = lot
        return lots

    def _create_sales_orders(self, tenant, user, customers, products, lots):
        today = timezone.localdate()
        sales_specs = [
            {
                "number": f"{DEMO_SO_PREFIX}2001",
                "customer": customers["Pacific Rim Restaurant Group"],
                "status": "open",
                "packed": "need_to_send",
                "order_date": today,
                "items": [
                    (products["salmon"], Decimal("48"), Decimal("18.75"), lots[f"{DEMO_LOT_PREFIX}003"]),
                    (products["scallops"], Decimal("18"), Decimal("38.50"), lots[f"{DEMO_LOT_PREFIX}002"]),
                ],
            },
            {
                "number": f"{DEMO_SO_PREFIX}2002",
                "customer": customers["Ocean Blue Sushi Bar"],
                "status": "needs_review",
                "packed": "not_packed",
                "order_date": today - timezone.timedelta(days=1),
                "items": [
                    (products["tuna"], Decimal("24"), Decimal("44.00"), lots[f"{DEMO_LOT_PREFIX}004"]),
                ],
            },
            {
                "number": f"{DEMO_SO_PREFIX}2003",
                "customer": customers["Bayshore Catering Co."],
                "status": "closed",
                "packed": "packed",
                "order_date": today - timezone.timedelta(days=2),
                "items": [
                    (products["halibut"], Decimal("32"), Decimal("21.50"), lots[f"{DEMO_LOT_PREFIX}001"]),
                ],
            },
            {
                "number": f"{DEMO_SO_PREFIX}2004",
                "customer": customers["Santa Monica Seafood Market"],
                "status": "open",
                "packed": "not_packed",
                "order_date": today,
                "items": [
                    (products["crab"], Decimal("12"), Decimal("24.00"), lots[f"{DEMO_LOT_PREFIX}005"]),
                ],
            },
        ]

        for spec in sales_specs:
            order = SalesOrder.objects.create(
                tenant=tenant,
                order_number=spec["number"],
                customer=spec["customer"],
                customer_name=spec["customer"].name,
                order_status=spec["status"],
                packed_status=spec["packed"],
                qb_invoice_number=spec["number"].replace(DEMO_SO_PREFIX, "INV-"),
                sales_rep="Demo Team",
                po_number=f"PO-{spec['number'][-4:]}",
                order_date=spec["order_date"],
                ship_date=spec["order_date"] + timezone.timedelta(days=1),
                delivery_date=spec["order_date"] + timezone.timedelta(days=1),
                shipper="West Coast Cold Chain",
                shipping_route="Bay Area",
                notes="Demo outbound order.",
                created_by=user,
                assigned_to=user,
            )
            for idx, (product, qty, unit_price, lot) in enumerate(spec["items"]):
                item = SalesOrderItem.objects.create(
                    tenant=tenant,
                    sales_order=order,
                    product=product,
                    description=product.item_name or product.description,
                    notes="Demo line",
                    quantity=qty,
                    unit_type=product.unit_type or "Lbs",
                    unit_price=unit_price,
                    amount=qty * unit_price,
                    sort_order=idx,
                )
                SalesOrderAllocation.objects.create(
                    tenant=tenant,
                    sales_order_item=item,
                    inventory=lot,
                    quantity=min(qty, lot.unitsavailable or qty),
                    unit_type=product.unit_type or "Lbs",
                    allocated_by=user,
                    allocated_by_name=user.get_username(),
                )

    def _create_process_batches(self, tenant, user, products, lots):
        now = timezone.now()
        batch_specs = [
            {
                "number": f"{DEMO_BATCH_PREFIX}3001",
                "type": "fish_cutting",
                "status": "completed",
                "source": lots[f"{DEMO_LOT_PREFIX}003"],
                "input_qty": Decimal("120"),
                "output_product": products["salmon"],
                "output_qty": Decimal("104"),
                "waste_qty": Decimal("8"),
                "note": "Portion-cut salmon fillets for restaurant accounts.",
            },
            {
                "number": f"{DEMO_BATCH_PREFIX}3002",
                "type": "commingle",
                "status": "in_progress",
                "source": lots[f"{DEMO_LOT_PREFIX}001"],
                "input_qty": Decimal("80"),
                "output_product": products["halibut"],
                "output_qty": Decimal("76"),
                "waste_qty": Decimal("2"),
                "note": "Combining day lots for production staging.",
            },
            {
                "number": f"{DEMO_BATCH_PREFIX}3003",
                "type": "freeze",
                "status": "draft",
                "source": lots[f"{DEMO_LOT_PREFIX}004"],
                "input_qty": Decimal("60"),
                "output_product": products["tuna"],
                "output_qty": Decimal("58"),
                "waste_qty": Decimal("1"),
                "note": "Blast-freeze premium sashimi trim for reserve stock.",
            },
        ]

        for idx, spec in enumerate(batch_specs):
            batch = ProcessBatch.objects.create(
                tenant=tenant,
                batch_number=spec["number"],
                process_type=spec["type"],
                status=spec["status"],
                notes=spec["note"],
                created_by=user,
                completed_at=now if spec["status"] == "completed" else None,
            )
            ProcessBatchSource.objects.create(
                tenant=tenant,
                batch=batch,
                inventory=spec["source"],
                quantity=spec["input_qty"],
                unit_type=spec["source"].unittype or "Lbs",
            )
            ProcessBatchOutput.objects.create(
                tenant=tenant,
                batch=batch,
                product=spec["output_product"],
                quantity=spec["output_qty"],
                unit_type=spec["output_product"].unit_type or "Lbs",
                lot_id=f"{DEMO_LOT_PREFIX}OUT-{idx + 1}",
            )
            ProcessBatchWaste.objects.create(
                tenant=tenant,
                batch=batch,
                source_inventory=spec["source"],
                entry_type="waste",
                category="trim",
                quantity=spec["waste_qty"],
                unit_type=spec["source"].unittype or "Lbs",
                estimated_value=Decimal("45.00"),
                notes="Demo trim/waste entry.",
                created_by=user,
                created_by_name=user.get_username(),
            )
            if spec["status"] == "completed":
                batch.calculate_yield()
                batch.save()
