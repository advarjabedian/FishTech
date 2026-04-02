import csv
from django.core.management.base import BaseCommand
from core.models import SOP, Zone, Company, Tenant


class Command(BaseCommand):
    help = 'Import SOP data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--tenant-id', type=int, required=True, help='Tenant ID to associate records with')
        parser.add_argument('--company-id', type=int, required=True, help='Force all records to this company ID')
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        tenant_id = options['tenant_id']
        company_id = options['company_id']
        dry_run = options['dry_run']

        try:
            tenant = Tenant.objects.get(pk=tenant_id)
        except Tenant.DoesNotExist:
            self.stderr.write(f'Tenant with ID {tenant_id} does not exist.')
            return

        try:
            company = Company.all_objects.get(pk=company_id, tenant=tenant)
        except Company.DoesNotExist:
            self.stderr.write(f'Company with ID {company_id} not found in tenant {tenant_id}.')
            return

        zones = {}  # zone_name -> Zone
        for z in Zone.all_objects.filter(tenant=tenant, company=company):
            zones[z.name] = z

        created_zones = 0
        created_sops = 0
        skipped = 0
        errors = []

        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f'Found {len(rows)} rows in CSV')

        for i, row in enumerate(rows):
            try:
                zone_name = row['Zones_Zone'].strip() if row['Zones_Zone'] else None
                sop_did = int(row['SopDId'])

                # Find or create zone
                zone = None
                if zone_name:
                    if zone_name not in zones:
                        if not dry_run:
                            zone, was_created = Zone.all_objects.get_or_create(
                                tenant=tenant,
                                company=company,
                                name=zone_name,
                            )
                            zones[zone_name] = zone
                            if was_created:
                                created_zones += 1
                        else:
                            created_zones += 1
                    else:
                        zone = zones[zone_name]

                if dry_run:
                    created_sops += 1
                    continue

                SOP.all_objects.update_or_create(
                    tenant=tenant,
                    company=company,
                    sop_did=sop_did,
                    defaults={
                        'description': row['Description'].strip(),
                        'zone': zone,
                        'pre': bool(int(row['Pre'])),
                        'mid': bool(int(row['Mid'])),
                        'post': bool(int(row['Post'])),
                        'input_required': bool(int(row['Input'])),
                        'image_required': bool(int(row['ImageRequired'])),
                    }
                )
                created_sops += 1

            except Exception as e:
                errors.append(f'Row {i+1} (id={row.get("id", "?")}): {e}')
                skipped += 1

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(f'{prefix}Zones created: {created_zones}'))
        self.stdout.write(self.style.SUCCESS(f'{prefix}SOPs imported: {created_sops}'))
        self.stdout.write(self.style.WARNING(f'{prefix}Skipped: {skipped}'))

        if errors:
            self.stdout.write(self.style.ERROR(f'\nErrors:'))
            for err in errors:
                self.stdout.write(self.style.ERROR(f'  {err}'))
