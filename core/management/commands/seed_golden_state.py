"""
Seed demo data for the Golden State Seafood tenant.
Populates all tables EXCEPT HACCP-related ones.

Usage:  python manage.py seed_golden_state
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta, time
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Seed demo data for Golden State Seafood (excludes HACCP pages)'

    def handle(self, *args, **options):
        from core.models import (
            Tenant, TenantUser, User, Zone, SOP, SOPParent, SOPChild,
            CompanyOperationConfig, CompanyHoliday,
            Customer, ContactEmail, Vendor, Receipt, License, Vehicle,
            InboundMessage, CustomerProfile,
            ItemGroup, Product, Inventory,
            SalesOrder, SalesOrderItem, PurchaseOrder, PurchaseOrderItem,
            ProcessBatch, ProcessBatchSource, ProcessBatchOutput,
            FishOrder, APExpense, ARInvoice,
        )

        # --- Find the tenant ---
        try:
            tenant = Tenant.objects.get(subdomain='goldenstateseafood')
        except Tenant.DoesNotExist:
            try:
                tenant = Tenant.objects.get(name__icontains='Golden State')
            except (Tenant.DoesNotExist, Tenant.MultipleObjectsReturned):
                self.stderr.write(self.style.ERROR(
                    'Could not find Golden State Seafood tenant. '
                    'Please check the tenant name/subdomain.'
                ))
                return

        self.stdout.write(f'Seeding data for tenant: {tenant.name} (id={tenant.id})')
        today = date.today()

        # =====================================================================
        # USERS (business users, not Django auth users)
        # =====================================================================
        users_data = [
            {'userid': 1, 'name': 'Mike Torres', 'email': 'mike@gsfood.com', 'cellnumber': '(310) 555-0101', 'usercode': 'MT', 'commission': 5},
            {'userid': 2, 'name': 'Sarah Chen', 'email': 'sarah@gsfood.com', 'cellnumber': '(310) 555-0102', 'usercode': 'SC', 'commission': 5},
            {'userid': 3, 'name': 'David Kim', 'email': 'david@gsfood.com', 'cellnumber': '(310) 555-0103', 'usercode': 'DK', 'commission': 3},
            {'userid': 4, 'name': 'Lisa Nguyen', 'email': 'lisa@gsfood.com', 'cellnumber': '(310) 555-0104', 'usercode': 'LN', 'commission': 4},
            {'userid': 5, 'name': 'Carlos Rivera', 'email': 'carlos@gsfood.com', 'cellnumber': '(310) 555-0105', 'usercode': 'CR', 'commission': 3},
        ]
        users = []
        for u in users_data:
            obj, _ = User.all_objects.update_or_create(tenant=tenant, userid=u['userid'], defaults=u)
            users.append(obj)
        self.stdout.write(self.style.SUCCESS(f'  {len(users)} users'))

        # =====================================================================
        # ITEM GROUPS
        # =====================================================================
        group_names = ['Salmon', 'Tuna', 'Shrimp', 'Oysters', 'Crab', 'Lobster', 'Halibut', 'Cod', 'Clams', 'Scallops']
        item_groups = []
        for i, name in enumerate(group_names):
            obj, _ = ItemGroup.all_objects.update_or_create(tenant=tenant, name=name, defaults={'sort_order': i, 'is_active': True})
            item_groups.append(obj)
        self.stdout.write(self.style.SUCCESS(f'  {len(item_groups)} item groups'))

        # =====================================================================
        # PRODUCTS
        # =====================================================================
        products_data = [
            {'product_id': 'SAL-001', 'item_number': '1001', 'description': 'Atlantic Salmon Fillet', 'unit_type': 'Lbs', 'pack_size': 10, 'default_price': 12.50, 'origin': 'Norway', 'item_group': item_groups[0], 'species': 'Atlantic Salmon', 'department': 'Fin Fish', 'habitat_production_method': 'Farm Raised'},
            {'product_id': 'SAL-002', 'item_number': '1002', 'description': 'King Salmon Whole', 'unit_type': 'Lbs', 'pack_size': 1, 'default_price': 28.00, 'origin': 'Alaska', 'item_group': item_groups[0], 'species': 'King Salmon', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'SAL-003', 'item_number': '1003', 'description': 'Sockeye Salmon Fillet', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 18.75, 'origin': 'Alaska', 'item_group': item_groups[0], 'species': 'Sockeye Salmon', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'TUN-001', 'item_number': '2001', 'description': 'Yellowfin Tuna Loin', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 22.00, 'origin': 'Hawaii', 'item_group': item_groups[1], 'species': 'Yellowfin Tuna', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'TUN-002', 'item_number': '2002', 'description': 'Ahi Tuna Sashimi Grade', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 34.00, 'origin': 'Japan', 'item_group': item_groups[1], 'species': 'Bigeye Tuna', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'SHR-001', 'item_number': '3001', 'description': 'White Shrimp 16/20 Headless', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 9.50, 'origin': 'Ecuador', 'item_group': item_groups[2], 'species': 'White Shrimp', 'department': 'Shellfish', 'habitat_production_method': 'Farm Raised'},
            {'product_id': 'SHR-002', 'item_number': '3002', 'description': 'Tiger Shrimp 8/12 Head-On', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 14.00, 'origin': 'Vietnam', 'item_group': item_groups[2], 'species': 'Tiger Shrimp', 'department': 'Shellfish', 'habitat_production_method': 'Farm Raised'},
            {'product_id': 'OYS-001', 'item_number': '4001', 'description': 'Kumamoto Oysters', 'unit_type': 'Each', 'pack_size': 100, 'default_price': 1.25, 'origin': 'Washington', 'item_group': item_groups[3], 'species': 'Kumamoto Oyster', 'department': 'Shellfish', 'habitat_production_method': 'Aquaculture'},
            {'product_id': 'OYS-002', 'item_number': '4002', 'description': 'Pacific Gold Oysters', 'unit_type': 'Each', 'pack_size': 100, 'default_price': 0.95, 'origin': 'California', 'item_group': item_groups[3], 'species': 'Pacific Oyster', 'department': 'Shellfish', 'habitat_production_method': 'Aquaculture'},
            {'product_id': 'CRB-001', 'item_number': '5001', 'description': 'Dungeness Crab Whole Cooked', 'unit_type': 'Lbs', 'pack_size': 1, 'default_price': 16.50, 'origin': 'Oregon', 'item_group': item_groups[4], 'species': 'Dungeness Crab', 'department': 'Shellfish', 'habitat_production_method': 'Wild'},
            {'product_id': 'CRB-002', 'item_number': '5002', 'description': 'King Crab Legs', 'unit_type': 'Lbs', 'pack_size': 10, 'default_price': 45.00, 'origin': 'Alaska', 'item_group': item_groups[4], 'species': 'Red King Crab', 'department': 'Shellfish', 'habitat_production_method': 'Wild'},
            {'product_id': 'LOB-001', 'item_number': '6001', 'description': 'Maine Lobster Tail 6oz', 'unit_type': 'Each', 'pack_size': 1, 'default_price': 18.00, 'origin': 'Maine', 'item_group': item_groups[5], 'species': 'American Lobster', 'department': 'Shellfish', 'habitat_production_method': 'Wild'},
            {'product_id': 'HAL-001', 'item_number': '7001', 'description': 'Pacific Halibut Fillet', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 26.00, 'origin': 'Alaska', 'item_group': item_groups[6], 'species': 'Pacific Halibut', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'COD-001', 'item_number': '8001', 'description': 'Pacific Cod Fillet', 'unit_type': 'Lbs', 'pack_size': 10, 'default_price': 8.50, 'origin': 'Alaska', 'item_group': item_groups[7], 'species': 'Pacific Cod', 'department': 'Fin Fish', 'habitat_production_method': 'Wild'},
            {'product_id': 'CLM-001', 'item_number': '9001', 'description': 'Manila Clams', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 6.50, 'origin': 'Washington', 'item_group': item_groups[8], 'species': 'Manila Clam', 'department': 'Shellfish', 'habitat_production_method': 'Wild'},
            {'product_id': 'SCA-001', 'item_number': '10001', 'description': 'Dry Sea Scallops U/10', 'unit_type': 'Lbs', 'pack_size': 5, 'default_price': 32.00, 'origin': 'Massachusetts', 'item_group': item_groups[9], 'species': 'Atlantic Sea Scallop', 'department': 'Shellfish', 'habitat_production_method': 'Wild'},
        ]
        products = []
        for p in products_data:
            obj, _ = Product.all_objects.update_or_create(
                tenant=tenant, product_id=p['product_id'],
                defaults={k: v for k, v in p.items() if k != 'product_id'}
            )
            products.append(obj)
        self.stdout.write(self.style.SUCCESS(f'  {len(products)} products'))

        # =====================================================================
        # CUSTOMERS
        # =====================================================================
        customers_data = [
            {'customer_id': 1001, 'name': 'Pacific Rim Restaurant Group', 'contact_name': 'James Tanaka', 'email': 'orders@pacificrimrg.com', 'phone': '(415) 555-1001', 'address': '450 Market St', 'city': 'San Francisco', 'state': 'CA', 'zipcode': '94105'},
            {'customer_id': 1002, 'name': 'Ocean Blue Sushi Bar', 'contact_name': 'Yuki Sato', 'email': 'yuki@oceanbluepoke.com', 'phone': '(310) 555-1002', 'address': '2201 Abbot Kinney Blvd', 'city': 'Venice', 'state': 'CA', 'zipcode': '90291'},
            {'customer_id': 1003, 'name': 'Harbor Fresh Markets', 'contact_name': 'Tom Bradley', 'email': 'purchasing@harborfresh.com', 'phone': '(562) 555-1003', 'address': '890 Pine Ave', 'city': 'Long Beach', 'state': 'CA', 'zipcode': '90802'},
            {'customer_id': 1004, 'name': 'The Catch House', 'contact_name': 'Maria Gonzalez', 'email': 'maria@catchhouse.com', 'phone': '(858) 555-1004', 'address': '1544 Coast Blvd', 'city': 'La Jolla', 'state': 'CA', 'zipcode': '92037'},
            {'customer_id': 1005, 'name': 'Downtown Bistro & Wine', 'contact_name': 'Robert Chen', 'email': 'chef@downtownbistro.com', 'phone': '(213) 555-1005', 'address': '655 S Hope St', 'city': 'Los Angeles', 'state': 'CA', 'zipcode': '90017'},
            {'customer_id': 1006, 'name': 'Bayshore Catering Co.', 'contact_name': 'Jennifer Park', 'email': 'jen@bayshorecatering.com', 'phone': '(408) 555-1006', 'address': '1100 Alameda Blvd', 'city': 'San Jose', 'state': 'CA', 'zipcode': '95126'},
            {'customer_id': 1007, 'name': 'Sunset Grill', 'contact_name': 'Alex Morgan', 'email': 'alex@sunsetgrill.com', 'phone': '(714) 555-1007', 'address': '305 Main St', 'city': 'Huntington Beach', 'state': 'CA', 'zipcode': '92648'},
            {'customer_id': 1008, 'name': 'Pier 39 Seafood Shack', 'contact_name': 'Danny Liu', 'email': 'danny@pier39shack.com', 'phone': '(415) 555-1008', 'address': '39 Pier', 'city': 'San Francisco', 'state': 'CA', 'zipcode': '94133'},
            {'customer_id': 1009, 'name': 'Napa Valley Fish Co.', 'contact_name': 'William Frost', 'email': 'will@napafish.com', 'phone': '(707) 555-1009', 'address': '2140 Main St', 'city': 'Napa', 'state': 'CA', 'zipcode': '94559'},
            {'customer_id': 1010, 'name': 'Santa Monica Seafood Market', 'contact_name': 'Rachel Adams', 'email': 'rachel@smseafood.com', 'phone': '(310) 555-1010', 'address': '1000 Wilshire Blvd', 'city': 'Santa Monica', 'state': 'CA', 'zipcode': '90401'},
        ]
        customers = []
        for c in customers_data:
            obj, _ = Customer.all_objects.update_or_create(tenant=tenant, customer_id=c['customer_id'], defaults=c)
            customers.append(obj)
        self.stdout.write(self.style.SUCCESS(f'  {len(customers)} customers'))

        # =====================================================================
        # CONTACT EMAILS
        # =====================================================================
        for cust in customers:
            ContactEmail.all_objects.update_or_create(
                tenant=tenant, contact_type='customer', entity_id=cust.customer_id, email=cust.email,
                defaults={'label': 'Primary'}
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(customers)} contact emails'))

        # =====================================================================
        # VENDORS
        # =====================================================================
        vendors_data = [
            {'vendor_id': 2001, 'name': 'Alaska Wild Harvest', 'contact_name': 'John Erikson', 'email': 'sales@alaskawild.com', 'phone': '(907) 555-2001', 'address': '1200 Glacier Hwy', 'city': 'Juneau', 'state': 'AK', 'zipcode': '99801', 'vendor_type': 'Harvester', 'cert': 'AK-WILD-2024-0887'},
            {'vendor_id': 2002, 'name': 'Pacific Shellfish Co.', 'contact_name': 'Linda Tran', 'email': 'linda@pacshellfish.com', 'phone': '(360) 555-2002', 'address': '450 Oyster Bay Rd', 'city': 'Shelton', 'state': 'WA', 'zipcode': '98584', 'vendor_type': 'Dealer', 'cert': 'WA-SHELL-2024-1455'},
            {'vendor_id': 2003, 'name': 'Gulf Coast Shrimp Ltd.', 'contact_name': 'Ray Boudreaux', 'email': 'ray@gulfshrimp.com', 'phone': '(985) 555-2003', 'address': '78 Bayou Rd', 'city': 'Houma', 'state': 'LA', 'zipcode': '70360', 'vendor_type': 'Harvester', 'cert': 'LA-GCS-2024-0223'},
            {'vendor_id': 2004, 'name': 'Nordic Salmon Imports', 'contact_name': 'Erik Johansson', 'email': 'erik@nordicsalmon.com', 'phone': '(206) 555-2004', 'address': '3200 Waterfront Pl', 'city': 'Seattle', 'state': 'WA', 'zipcode': '98101', 'vendor_type': 'Exporter', 'cert': 'NOAA-IMP-2024-7721'},
            {'vendor_id': 2005, 'name': 'Baja Seafood Supply', 'contact_name': 'Manuel Reyes', 'email': 'manuel@bajaseafood.com', 'phone': '(619) 555-2005', 'address': '1900 Harbor Dr', 'city': 'San Diego', 'state': 'CA', 'zipcode': '92101', 'vendor_type': 'Dealer', 'cert': 'CA-BSS-2024-3341'},
            {'vendor_id': 2006, 'name': 'Maine Lobster Direct', 'contact_name': 'Paul Sawyer', 'email': 'paul@mainelobster.com', 'phone': '(207) 555-2006', 'address': '55 Commercial St', 'city': 'Portland', 'state': 'ME', 'zipcode': '04101', 'vendor_type': 'Dealer', 'cert': 'ME-LOB-2024-0098'},
        ]
        vendors = []
        for v in vendors_data:
            obj, _ = Vendor.all_objects.update_or_create(tenant=tenant, vendor_id=v['vendor_id'], defaults=v)
            vendors.append(obj)
        self.stdout.write(self.style.SUCCESS(f'  {len(vendors)} vendors'))

        # =====================================================================
        # LICENSES
        # =====================================================================
        licenses_data = [
            {'title': 'California Wholesale Fish Dealer License', 'filename': 'ca_wholesale_license.pdf', 'issuance_date': date(2025, 1, 15), 'expiration_date': date(2026, 1, 14)},
            {'title': 'LA County Health Permit', 'filename': 'la_health_permit.pdf', 'issuance_date': date(2025, 3, 1), 'expiration_date': date(2026, 2, 28)},
            {'title': 'USDA Seafood Inspection Certificate', 'filename': 'usda_inspection.pdf', 'issuance_date': date(2025, 6, 1), 'expiration_date': date(2026, 5, 31)},
            {'title': 'FDA Food Facility Registration', 'filename': 'fda_registration.pdf', 'issuance_date': date(2024, 10, 1), 'expiration_date': date(2026, 9, 30)},
            {'title': 'Business License - City of Los Angeles', 'filename': 'city_business_license.pdf', 'issuance_date': date(2025, 7, 1), 'expiration_date': date(2026, 6, 30)},
        ]
        for lic in licenses_data:
            License.all_objects.update_or_create(tenant=tenant, title=lic['title'], defaults=lic)
        self.stdout.write(self.style.SUCCESS(f'  {len(licenses_data)} licenses'))

        # =====================================================================
        # VEHICLES
        # =====================================================================
        vehicles_data = [
            {'year': 2023, 'make': 'Ford', 'model': 'Transit 250', 'vin': '1FTBW2CM5NKA12345', 'license_plate': '8ABC123', 'number': 'T-01', 'driver': 'Carlos Rivera', 'status': 'Active', 'dmv_renewal_date': date(2026, 8, 15)},
            {'year': 2022, 'make': 'Mercedes-Benz', 'model': 'Sprinter 2500', 'vin': 'W1Y4EBVY1NT123456', 'license_plate': '8DEF456', 'number': 'T-02', 'driver': 'Mike Torres', 'status': 'Active', 'dmv_renewal_date': date(2026, 5, 20)},
            {'year': 2024, 'make': 'Isuzu', 'model': 'NPR-HD Reefer', 'vin': 'JALC4W163R7654321', 'license_plate': '8GHI789', 'number': 'R-01', 'driver': 'David Kim', 'status': 'Active', 'dmv_renewal_date': date(2026, 11, 3)},
            {'year': 2021, 'make': 'Ford', 'model': 'E-350 Cutaway', 'vin': '1FDWE3FS1MDA98765', 'license_plate': '8JKL012', 'number': 'R-02', 'driver': '', 'status': 'Inactive', 'dmv_renewal_date': date(2026, 2, 10)},
        ]
        for v in vehicles_data:
            Vehicle.all_objects.update_or_create(tenant=tenant, vin=v['vin'], defaults=v)
        self.stdout.write(self.style.SUCCESS(f'  {len(vehicles_data)} vehicles'))

        # =====================================================================
        # ZONES & SOPs (Operations / Daily Inspections)
        # =====================================================================
        zones_sops = {
            'Processing Room': [
                (1, 'Floors, walls, ceilings clean and in good repair', True, True, True, False, False),
                (2, 'Equipment sanitized before use', True, False, False, False, False),
                (3, 'Drains clear and flowing', True, True, True, False, False),
                (4, 'Cutting boards sanitized', True, True, False, False, False),
            ],
            'Cold Storage A': [
                (5, 'Temperature at or below 38°F', True, True, True, True, False),
                (6, 'Door gaskets intact, no gaps', True, False, False, False, False),
                (7, 'Product stored off floor on shelving', True, True, True, False, False),
                (8, 'No cross-contamination between raw and cooked', True, True, True, False, False),
            ],
            'Cold Storage B': [
                (9, 'Temperature at or below 38°F', True, True, True, True, False),
                (10, 'Products properly labeled and dated', True, True, True, False, False),
            ],
            'Receiving Dock': [
                (11, 'Dock area clean, no standing water', True, False, True, False, False),
                (12, 'Incoming product temperature checked', True, True, True, True, False),
                (13, 'Pest control stations intact', True, False, False, False, False),
            ],
            'Shipping Area': [
                (14, 'Truck refrigeration unit functional', True, True, True, True, False),
                (15, 'Ice supply adequate', True, True, True, False, False),
                (16, 'Shipping labels legible and accurate', False, True, True, False, False),
            ],
            'Restrooms': [
                (17, 'Hand wash stations stocked (soap, towels)', True, True, True, False, False),
                (18, 'Restrooms clean and sanitary', True, False, True, False, False),
            ],
            'Exterior': [
                (19, 'Dumpster area clean, lids closed', True, False, True, False, False),
                (20, 'No pest activity observed', True, False, True, False, True),
            ],
        }
        zones = []
        sops = []
        for zone_name, sop_list in zones_sops.items():
            zone, _ = Zone.all_objects.update_or_create(tenant=tenant, name=zone_name)
            zones.append(zone)
            for sop_did, desc, pre, mid, post, inp, img in sop_list:
                sop, _ = SOP.all_objects.update_or_create(
                    tenant=tenant, sop_did=sop_did,
                    defaults={'description': desc, 'zone': zone, 'pre': pre, 'mid': mid, 'post': post, 'input_required': inp, 'image_required': img}
                )
                sops.append(sop)
        self.stdout.write(self.style.SUCCESS(f'  {len(zones)} zones, {len(sops)} SOPs'))

        # =====================================================================
        # COMPANY OPERATION CONFIG
        # =====================================================================
        CompanyOperationConfig.all_objects.update_or_create(
            tenant=tenant,
            defaults={
                'start_date': date(2025, 1, 1),
                'monday': True, 'tuesday': True, 'wednesday': True,
                'thursday': True, 'friday': True, 'saturday': True, 'sunday': False,
            }
        )

        # =====================================================================
        # COMPANY HOLIDAYS
        # =====================================================================
        holidays = [
            date(2026, 1, 1),   # New Year's Day
            date(2026, 7, 4),   # Fourth of July
            date(2026, 11, 26), # Thanksgiving
            date(2026, 12, 25), # Christmas
        ]
        for h in holidays:
            CompanyHoliday.all_objects.update_or_create(tenant=tenant, date=h)
        self.stdout.write(self.style.SUCCESS(f'  {len(holidays)} holidays'))

        # =====================================================================
        # SOP PARENTS + CHILDREN (last 7 operating days of inspections)
        # =====================================================================
        shifts = ['Pre-Op', 'Mid-Day', 'Post-Op']
        inspection_count = 0
        for days_ago in range(1, 8):
            d = today - timedelta(days=days_ago)
            if d.weekday() == 6:  # skip Sunday
                continue
            for shift in shifts:
                parent, created = SOPParent.all_objects.update_or_create(
                    tenant=tenant, date=d, shift=shift,
                    defaults={
                        'time': time(6, 0) if shift == 'Pre-Op' else (time(12, 0) if shift == 'Mid-Day' else time(18, 0)),
                        'completed': True,
                        'inspector_name': 'Mike Torres',
                        'verified': shift != 'Post-Op' or days_ago > 1,
                        'verifier_name': 'Sarah Chen' if shift != 'Post-Op' or days_ago > 1 else '',
                    }
                )
                if created:
                    # create children for SOPs matching this shift
                    for sop in sops:
                        applies = (shift == 'Pre-Op' and sop.pre) or (shift == 'Mid-Day' and sop.mid) or (shift == 'Post-Op' and sop.post)
                        if applies:
                            SOPChild.objects.update_or_create(
                                sop_parent=parent, sop_did=sop.sop_did,
                                defaults={
                                    'passed': True,
                                    'failed': False,
                                    'notes': '38°F' if sop.input_required else '',
                                }
                            )
                    inspection_count += 1
        self.stdout.write(self.style.SUCCESS(f'  {inspection_count} shift inspections with SOP results'))

        # =====================================================================
        # INVENTORY (current lots on hand)
        # =====================================================================
        inventory_data = []
        for i, prod in enumerate(products):
            qty = Decimal(str(random.randint(50, 500)))
            inv, _ = Inventory.all_objects.update_or_create(
                tenant=tenant, productid=prod.product_id,
                poid=f'PO-100{i+1}',
                defaults={
                    'desc': prod.description,
                    'vendorid': str(vendors[i % len(vendors)].vendor_id),
                    'receivedate': (today - timedelta(days=random.randint(1, 5))).strftime('%m/%d/%Y'),
                    'vendorlot': f'VL-{random.randint(10000,99999)}',
                    'actualcost': (prod.default_price or 10) * Decimal('0.65'),
                    'unittype': prod.unit_type,
                    'unitsonhand': qty,
                    'unitsavailable': qty - Decimal(str(random.randint(0, 30))),
                    'unitsallocated': Decimal(str(random.randint(0, 20))),
                    'unitsin': qty,
                    'unitsout': Decimal('0'),
                    'origin': prod.origin,
                    'shelflife': Decimal('14'),
                    'location': random.choice(['Cooler A', 'Cooler B', 'Freezer 1']),
                    'receive_time': f'{random.randint(5,9)}:{random.randint(10,59)} am',
                }
            )
            inventory_data.append(inv)
        self.stdout.write(self.style.SUCCESS(f'  {len(inventory_data)} inventory lots'))

        # =====================================================================
        # SALES ORDERS (recent)
        # =====================================================================
        sales_orders = []
        for i in range(12):
            cust = customers[i % len(customers)]
            d = today - timedelta(days=random.randint(0, 14))
            status = random.choice(['draft', 'open', 'open', 'open', 'closed'])
            so, _ = SalesOrder.all_objects.update_or_create(
                tenant=tenant, order_number=str(5001 + i),
                defaults={
                    'customer': cust,
                    'customer_name': cust.name,
                    'order_status': status,
                    'order_date': d,
                    'delivery_date': d + timedelta(days=random.randint(1, 3)),
                    'sales_rep': random.choice(['Mike Torres', 'Sarah Chen']),
                    'notes': '',
                    'packed_status': 'packed' if status == 'closed' else 'not_packed',
                }
            )
            sales_orders.append(so)
            # 2-4 line items per order
            num_items = random.randint(2, 4)
            chosen_products = random.sample(products, num_items)
            for j, prod in enumerate(chosen_products):
                qty = Decimal(str(random.randint(5, 50)))
                price = prod.default_price or Decimal('10')
                SalesOrderItem.all_objects.update_or_create(
                    tenant=tenant, sales_order=so, sort_order=j,
                    defaults={
                        'product': prod,
                        'description': prod.description,
                        'quantity': qty,
                        'unit_type': prod.unit_type,
                        'unit_price': price,
                        'amount': qty * price,
                    }
                )
        self.stdout.write(self.style.SUCCESS(f'  {len(sales_orders)} sales orders'))

        # =====================================================================
        # PURCHASE ORDERS (recent)
        # =====================================================================
        purchase_orders = []
        for i in range(8):
            vend = vendors[i % len(vendors)]
            d = today - timedelta(days=random.randint(0, 14))
            status = random.choice(['draft', 'open', 'open', 'closed'])
            po, _ = PurchaseOrder.all_objects.update_or_create(
                tenant=tenant, po_number=str(1001 + i),
                defaults={
                    'vendor': vend,
                    'vendor_name': vend.name,
                    'order_status': status,
                    'receive_status': 'received' if status == 'closed' else 'not_received',
                    'order_date': d,
                    'expected_date': d + timedelta(days=random.randint(2, 5)),
                    'buyer': 'David Kim',
                }
            )
            purchase_orders.append(po)
            num_items = random.randint(2, 3)
            chosen_products = random.sample(products, num_items)
            for j, prod in enumerate(chosen_products):
                qty = Decimal(str(random.randint(20, 200)))
                cost = (prod.default_price or Decimal('10')) * Decimal('0.65')
                PurchaseOrderItem.all_objects.update_or_create(
                    tenant=tenant, purchase_order=po, sort_order=j,
                    defaults={
                        'product': prod,
                        'description': prod.description,
                        'quantity': qty,
                        'unit_type': prod.unit_type,
                        'unit_price': cost,
                        'amount': qty * cost,
                    }
                )
        self.stdout.write(self.style.SUCCESS(f'  {len(purchase_orders)} purchase orders'))

        # =====================================================================
        # PROCESSING BATCHES
        # =====================================================================
        process_types = ['fish_cutting', 'commingle', 'shucking', 'freeze', 'lot_breaking']
        batches = []
        for i in range(5):
            batch, created = ProcessBatch.all_objects.update_or_create(
                tenant=tenant, batch_number=f'BATCH-{3001 + i}',
                defaults={
                    'process_type': process_types[i],
                    'status': 'completed' if i < 3 else 'in_progress',
                    'notes': '',
                }
            )
            batches.append(batch)
            if created and len(inventory_data) > i * 2 + 1:
                ProcessBatchSource.all_objects.create(
                    tenant=tenant, batch=batch,
                    inventory=inventory_data[i * 2],
                    quantity=Decimal('50'), unit_type='Lbs'
                )
                ProcessBatchOutput.all_objects.create(
                    tenant=tenant, batch=batch,
                    product=products[i],
                    quantity=Decimal('42'), unit_type='Lbs',
                    lot_id=f'OUT-{3001 + i}',
                    yield_percent=Decimal('84.00'),
                )
        self.stdout.write(self.style.SUCCESS(f'  {len(batches)} processing batches'))

        # =====================================================================
        # INBOUND MESSAGES
        # =====================================================================
        messages_data = [
            {'source': 'email', 'subject': 'Re: Order for Friday delivery', 'sender': 'orders@pacificrimrg.com', 'sender_name': 'James Tanaka', 'body': 'Hi, can we add 20 lbs of Yellowfin Tuna to our Friday order? Thanks!', 'status': 'Unassigned'},
            {'source': 'voicemail', 'subject': 'Voicemail from (858) 555-1004', 'sender_phone': '(858) 555-1004', 'sender_name': 'Maria Gonzalez', 'transcription': 'Hey this is Maria from The Catch House. Just wanted to confirm our Saturday order is still on track. Call me back when you get a chance.', 'duration': 22, 'status': 'Unassigned'},
            {'source': 'email', 'subject': 'Price inquiry - King Crab Legs', 'sender': 'will@napafish.com', 'sender_name': 'William Frost', 'body': 'Good morning, what is your current price on King Crab Legs? We are looking to order 50 lbs for a special event.', 'status': 'Unassigned'},
            {'source': 'sms', 'subject': 'SMS from (310) 555-1010', 'sender_phone': '(310) 555-1010', 'sender_name': 'Rachel Adams', 'body': 'Can you send me updated availability for scallops and halibut? Need ASAP', 'status': 'Unassigned'},
        ]
        for i, m in enumerate(messages_data):
            m['received_at'] = timezone.now() - timedelta(hours=random.randint(1, 48))
            InboundMessage.all_objects.update_or_create(
                tenant=tenant, subject=m.get('subject', ''), sender=m.get('sender', ''), sender_phone=m.get('sender_phone', ''),
                defaults=m
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(messages_data)} inbound messages'))

        # =====================================================================
        # AP EXPENSES
        # =====================================================================
        expenses_data = [
            {'vendor': 'Alaska Wild Harvest', 'description': 'PO-1001 - Salmon shipment', 'amount': Decimal('8450.00'), 'category': 'Inventory', 'due_date': today + timedelta(days=15), 'status': 'Unpaid'},
            {'vendor': 'Pacific Shellfish Co.', 'description': 'PO-1002 - Oyster order', 'amount': Decimal('3200.00'), 'category': 'Inventory', 'due_date': today + timedelta(days=10), 'status': 'Unpaid'},
            {'vendor': 'LA Ice & Cold Storage', 'description': 'Monthly cold storage rental', 'amount': Decimal('2800.00'), 'category': 'Facilities', 'due_date': today + timedelta(days=5), 'status': 'Unpaid'},
            {'vendor': 'CalPacific Logistics', 'description': 'Freight - March deliveries', 'amount': Decimal('4100.00'), 'category': 'Shipping', 'paid_date': today - timedelta(days=3), 'status': 'Paid'},
            {'vendor': 'SoCal Pest Control', 'description': 'Quarterly pest service', 'amount': Decimal('650.00'), 'category': 'Maintenance', 'paid_date': today - timedelta(days=7), 'status': 'Paid'},
            {'vendor': 'Gulf Coast Shrimp Ltd.', 'description': 'PO-1003 - Shrimp order', 'amount': Decimal('5600.00'), 'category': 'Inventory', 'due_date': today - timedelta(days=2), 'status': 'Overdue'},
        ]
        for e in expenses_data:
            APExpense.all_objects.update_or_create(
                tenant=tenant, vendor=e['vendor'], description=e['description'],
                defaults=e
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(expenses_data)} AP expenses'))

        # =====================================================================
        # AR INVOICES
        # =====================================================================
        invoices_data = [
            {'customer': 'Pacific Rim Restaurant Group', 'description': 'SO-5001 - Weekly order', 'amount': Decimal('6780.00'), 'invoice_date': today - timedelta(days=12), 'due_date': today + timedelta(days=18), 'status': 'Unpaid'},
            {'customer': 'Ocean Blue Sushi Bar', 'description': 'SO-5002 - Tuna & Salmon', 'amount': Decimal('4350.00'), 'invoice_date': today - timedelta(days=10), 'due_date': today + timedelta(days=20), 'status': 'Unpaid'},
            {'customer': 'Harbor Fresh Markets', 'description': 'SO-5003 - Mixed shellfish', 'amount': Decimal('9200.00'), 'invoice_date': today - timedelta(days=20), 'due_date': today - timedelta(days=5), 'status': 'Overdue'},
            {'customer': 'The Catch House', 'description': 'SO-5004 - Weekly order', 'amount': Decimal('3150.00'), 'invoice_date': today - timedelta(days=25), 'paid_date': today - timedelta(days=5), 'status': 'Paid'},
            {'customer': 'Downtown Bistro & Wine', 'description': 'SO-5005 - Halibut & Scallops', 'amount': Decimal('5400.00'), 'invoice_date': today - timedelta(days=30), 'paid_date': today - timedelta(days=10), 'status': 'Paid'},
            {'customer': 'Bayshore Catering Co.', 'description': 'SO-5006 - Event catering order', 'amount': Decimal('12800.00'), 'invoice_date': today - timedelta(days=8), 'due_date': today + timedelta(days=22), 'status': 'Unpaid'},
            {'customer': 'Sunset Grill', 'description': 'SO-5007 - Weekly order', 'amount': Decimal('2890.00'), 'invoice_date': today - timedelta(days=15), 'paid_date': today - timedelta(days=2), 'status': 'Paid'},
        ]
        for inv in invoices_data:
            ARInvoice.all_objects.update_or_create(
                tenant=tenant, customer=inv['customer'], description=inv['description'],
                defaults=inv
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(invoices_data)} AR invoices'))

        # =====================================================================
        # FISH ORDERS (retail / fish market)
        # =====================================================================
        fish_orders_data = [
            {'customer_name': 'Angela Martinez', 'customer_email': 'angela.m@email.com', 'customer_phone': '(310) 555-8001', 'customer_address': '1234 Ocean Ave, Santa Monica, CA 90401', 'items_json': [{'name': 'Kumamoto Oysters', 'quantity': 24, 'price': 1.25, 'subtotal': 30.00}], 'subtotal': Decimal('30.00'), 'status': 'Confirmed'},
            {'customer_name': 'Brian Cho', 'customer_email': 'brian.cho@email.com', 'customer_phone': '(626) 555-8002', 'customer_address': '567 Valley Blvd, Alhambra, CA 91801', 'items_json': [{'name': 'Atlantic Salmon Fillet', 'quantity': 5, 'price': 12.50, 'subtotal': 62.50}, {'name': 'Dry Sea Scallops U/10', 'quantity': 2, 'price': 32.00, 'subtotal': 64.00}], 'subtotal': Decimal('126.50'), 'status': 'Pending'},
            {'customer_name': 'Diana Reeves', 'customer_email': 'diana.r@email.com', 'customer_phone': '(818) 555-8003', 'customer_address': '890 Ventura Blvd, Sherman Oaks, CA 91403', 'items_json': [{'name': 'Maine Lobster Tail 6oz', 'quantity': 4, 'price': 18.00, 'subtotal': 72.00}], 'subtotal': Decimal('72.00'), 'status': 'Ready'},
        ]
        for fo in fish_orders_data:
            FishOrder.all_objects.update_or_create(
                tenant=tenant, customer_name=fo['customer_name'], customer_phone=fo['customer_phone'],
                defaults=fo
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(fish_orders_data)} fish market orders'))

        self.stdout.write(self.style.SUCCESS('\nDone! Demo data seeded for Golden State Seafood.'))
