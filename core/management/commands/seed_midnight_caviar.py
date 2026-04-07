"""
Seed the Midnight Caviar tenant with products and size variants.

Usage:
    python manage.py seed_midnight_caviar
"""
from django.core.management.base import BaseCommand
from core.models import Tenant, TenantUser, Customer, CustomerProfile, ProductSize


PRODUCTS = [
    {
        'name': 'Ossetra',
        'category': 'Caviar',
        'sizes': ['1oz', '2oz', '4oz', '8oz', '16oz'],
    },
    {
        'name': 'Kaluga',
        'category': 'Caviar',
        'sizes': ['1oz', '2oz', '4oz', '8oz', '16oz'],
    },
    {
        'name': 'California White Sturgeon',
        'category': 'Caviar',
        'sizes': ['1oz', '2oz', '4oz', '8oz', '16oz'],
    },
]


class Command(BaseCommand):
    help = 'Seed Midnight Caviar tenant with products and size variants'

    def handle(self, *args, **options):
        # Get or report on the tenant
        try:
            tenant = Tenant.objects.get(subdomain='midnight-caviar')
            self.stdout.write(f'Found tenant: {tenant.name} (id={tenant.id})')
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                'Tenant "midnight-caviar" not found. '
                'Please create the tenant first (register or admin), then re-run.'
            ))
            return

        # Get or create Retail customer
        retail, created = Customer.all_objects.get_or_create(
            tenant=tenant, is_retail=True,
            defaults={'name': 'Retail'}
        )
        if created:
            self.stdout.write(f'  Created Retail customer (id={retail.id})')
        else:
            self.stdout.write(f'  Using existing Retail customer (id={retail.id})')

        for i, prod in enumerate(PRODUCTS):
            profile, created = CustomerProfile.all_objects.get_or_create(
                tenant=tenant,
                customer=retail,
                description=prod['name'],
                defaults={
                    'category': prod['category'],
                    'sort_order': i,
                    'is_active': True,
                    'sales_price': 0,  # price is per-size
                }
            )
            status = 'Created' if created else 'Already exists'
            self.stdout.write(f'  {status}: {prod["name"]} (id={profile.id})')

            # Create sizes (skip if sizes already exist)
            existing_sizes = set(profile.sizes.values_list('name', flat=True))
            for j, size_name in enumerate(prod['sizes']):
                if size_name not in existing_sizes:
                    ProductSize.objects.create(
                        profile=profile,
                        name=size_name,
                        price=0,  # prices to be set by manager
                        sort_order=j,
                    )
                    self.stdout.write(f'    + Size: {size_name}')
                else:
                    self.stdout.write(f'    ~ Size exists: {size_name}')

        self.stdout.write(self.style.SUCCESS(
            '\nDone! Set prices via the fish market manager page.'
        ))
