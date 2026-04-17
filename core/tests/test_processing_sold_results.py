import json

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Customer, Inventory, Product, Tenant, TenantUser


class ProcessingSoldResultsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test-tenant",
            is_active=True,
        )
        self.user = User.objects.create_user(username="tester", password="password123")
        TenantUser.objects.create(user=self.user, tenant=self.tenant, is_admin=True)
        self.client.force_login(self.user)

        self.customer = Customer.objects.create(
            tenant=self.tenant,
            customer_id=1,
            name="Retail Buyer",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            product_id="SALMON-FILLET",
            description="Salmon Fillet",
            item_name="Salmon Fillet",
            unit_type="lb",
            is_active=True,
        )
        self.source_inventory = Inventory.objects.create(
            tenant=self.tenant,
            productid="WHOLE-SALMON",
            desc="Whole Salmon",
            vendorid="ACME",
            vendorlot="LOT-RAW-1",
            unittype="lb",
            unitsonhand=100,
            unitsavailable=100,
            unitsin=100,
            receivedate="2026-04-17",
        )

    def test_processed_output_appears_before_and_after_sale(self):
        batch_response = self.client.post(
            "/api/processing/batches/create/",
            data=json.dumps(
                {
                    "process_type": "fish_cutting",
                    "sources": [
                        {
                            "inventory_id": self.source_inventory.id,
                            "quantity": 20,
                            "unit_type": "lb",
                        }
                    ],
                    "outputs": [
                        {
                            "product_id": self.product.product_id,
                            "description": self.product.description,
                            "quantity": 15,
                            "unit_type": "lb",
                            "yield_percent": 75,
                            "lot_id": "",
                        }
                    ],
                    "notes": "Regression test batch",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(batch_response.status_code, 200, batch_response.content)
        batch_data = batch_response.json()
        self.assertTrue(batch_data["ok"])
        self.assertEqual(len(batch_data["outputs"]), 1)

        unsold_response = self.client.get("/api/processing/sold-results/")
        self.assertEqual(unsold_response.status_code, 200, unsold_response.content)
        unsold_rows = unsold_response.json()["results"]
        self.assertEqual(len(unsold_rows), 1)
        self.assertFalse(unsold_rows[0]["is_sold"])
        self.assertEqual(unsold_rows[0]["customer_name"], "Not Sold Yet")
        self.assertEqual(unsold_rows[0]["product"], "Salmon Fillet")
        self.assertEqual(unsold_rows[0]["source_lot"], "LOT-RAW-1")

        order_response = self.client.post(
            "/api/sales/orders/create/",
            data=json.dumps({"customer_name": self.customer.name}),
            content_type="application/json",
        )
        self.assertEqual(order_response.status_code, 200, order_response.content)
        order_id = order_response.json()["id"]

        item_response = self.client.post(
            f"/api/sales/orders/{order_id}/items/add/",
            data=json.dumps(
                {
                    "item_type": "item",
                    "product_id": self.product.product_id,
                    "description": self.product.description,
                    "quantity": 15,
                    "unit_type": "lb",
                    "unit_price": 12.5,
                    "process_batch_id": batch_data["id"],
                    "output_inventory_id": batch_data["outputs"][0]["inventory_id"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(item_response.status_code, 200, item_response.content)

        sold_response = self.client.get("/api/processing/sold-results/")
        self.assertEqual(sold_response.status_code, 200, sold_response.content)
        sold_rows = sold_response.json()["results"]
        self.assertEqual(len(sold_rows), 1)
        self.assertTrue(sold_rows[0]["is_sold"])
        self.assertEqual(sold_rows[0]["customer_name"], self.customer.name)
        self.assertEqual(sold_rows[0]["sold_qty"], 15.0)
        self.assertEqual(sold_rows[0]["unit_price"], 12.5)
        self.assertEqual(sold_rows[0]["amount"], 187.5)

    def test_processed_output_appears_when_sale_uses_new_customer_flow(self):
        batch_response = self.client.post(
            "/api/processing/batches/create/",
            data=json.dumps(
                {
                    "process_type": "fish_cutting",
                    "sources": [
                        {
                            "inventory_id": self.source_inventory.id,
                            "quantity": 10,
                            "unit_type": "lb",
                        }
                    ],
                    "outputs": [
                        {
                            "product_id": self.product.product_id,
                            "description": self.product.description,
                            "quantity": 8,
                            "unit_type": "lb",
                            "yield_percent": 80,
                            "lot_id": "",
                        }
                    ],
                    "notes": "New customer regression test batch",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(batch_response.status_code, 200, batch_response.content)
        batch_data = batch_response.json()

        create_customer_response = self.client.post(
            "/api/sales/customers/create/",
            data=json.dumps(
                {
                    "name": "Brand New Buyer",
                    "email": "buyer@example.com",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(create_customer_response.status_code, 200, create_customer_response.content)

        order_response = self.client.post(
            "/api/sales/orders/create/",
            data=json.dumps({"customer_name": "Brand New Buyer"}),
            content_type="application/json",
        )
        self.assertEqual(order_response.status_code, 200, order_response.content)
        order_id = order_response.json()["id"]

        item_response = self.client.post(
            f"/api/sales/orders/{order_id}/items/add/",
            data=json.dumps(
                {
                    "item_type": "item",
                    "product_id": self.product.product_id,
                    "description": self.product.description,
                    "quantity": 8,
                    "unit_type": "lb",
                    "unit_price": 14,
                    "process_batch_id": batch_data["id"],
                    "output_inventory_id": batch_data["outputs"][0]["inventory_id"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(item_response.status_code, 200, item_response.content)

        sold_response = self.client.get("/api/processing/sold-results/")
        self.assertEqual(sold_response.status_code, 200, sold_response.content)
        sold_rows = sold_response.json()["results"]
        self.assertEqual(len(sold_rows), 1)
        self.assertTrue(sold_rows[0]["is_sold"])
        self.assertEqual(sold_rows[0]["customer_name"], "Brand New Buyer")
        self.assertEqual(sold_rows[0]["sold_qty"], 8.0)
        self.assertEqual(sold_rows[0]["amount"], 112.0)
