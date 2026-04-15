# Consolidate CustomerEmail, VendorEmail, TenantEmail into ContactEmail

from django.db import migrations, models
import django.db.models.deletion


def migrate_emails_forward(apps, schema_editor):
    """Copy existing emails into the new ContactEmail table."""
    ContactEmail = apps.get_model('core', 'ContactEmail')
    CustomerEmail = apps.get_model('core', 'CustomerEmail')
    VendorEmail = apps.get_model('core', 'VendorEmail')
    TenantEmail = apps.get_model('core', 'TenantEmail')

    for e in CustomerEmail.objects.all():
        ContactEmail.objects.get_or_create(
            tenant_id=e.tenant_id,
            contact_type='customer',
            entity_id=e.customer_id,
            email=e.email,
            defaults={'label': e.label},
        )

    for e in VendorEmail.objects.all():
        ContactEmail.objects.get_or_create(
            tenant_id=e.tenant_id,
            contact_type='vendor',
            entity_id=e.vendor_id,
            email=e.email,
            defaults={'label': e.label},
        )

    for e in TenantEmail.objects.all():
        ContactEmail.objects.get_or_create(
            tenant_id=e.tenant_id,
            contact_type='tenant',
            entity_id=None,
            email=e.email,
            defaults={'label': e.label},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_consolidate_product_remove_legacy'),
    ]

    operations = [
        # Create the new unified model
        migrations.CreateModel(
            name='ContactEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contact_type', models.CharField(choices=[('customer', 'Customer'), ('vendor', 'Vendor'), ('tenant', 'Tenant')], max_length=20)),
                ('entity_id', models.IntegerField(blank=True, help_text='Customer or Vendor ID (null for tenant-wide)', null=True)),
                ('email', models.EmailField(max_length=254)),
                ('label', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.tenant')),
            ],
            options={
                'db_table': 'contact_email',
                'unique_together': {('tenant', 'contact_type', 'entity_id', 'email')},
            },
        ),

        # Copy data from old tables
        migrations.RunPython(migrate_emails_forward, migrations.RunPython.noop),

        # Remove old models
        migrations.DeleteModel(name='CustomerEmail'),
        migrations.DeleteModel(name='VendorEmail'),
        migrations.DeleteModel(name='TenantEmail'),
    ]
