# Custom migration: move ProductImage from CustomerProfile to TenantProduct

import django.db.models.deletion
from django.db import migrations, models


def migrate_images_to_tenant_product(apps, schema_editor):
    """Link existing ProductImage rows to TenantProduct via their profile's tenant_product FK."""
    ProductImage = apps.get_model('core', 'ProductImage')
    TenantProduct = apps.get_model('core', 'TenantProduct')

    for img in ProductImage.objects.select_related('profile').all():
        profile = img.profile
        if not profile:
            img.delete()
            continue

        if profile.tenant_product_id:
            img.tenant_product_id = profile.tenant_product_id
        else:
            # Profile has no tenant_product link — find or create one
            tp = TenantProduct.objects.filter(
                tenant_id=profile.tenant_id,
                description=profile.description,
            ).first()
            if not tp:
                tp = TenantProduct.objects.create(
                    tenant_id=profile.tenant_id,
                    description=profile.description,
                    unit_type=profile.unit_type or '',
                    pack_size=profile.pack_size,
                    default_price=profile.sales_price,
                    is_active=True,
                    sort_order=0,
                )
            img.tenant_product_id = tp.id
        img.save(update_fields=['tenant_product_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_tenant_product'),
    ]

    operations = [
        # 1. Add new FK (nullable) while keeping old FK
        migrations.AddField(
            model_name='productimage',
            name='tenant_product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='images', to='core.tenantproduct'),
        ),
        # 2. Migrate data
        migrations.RunPython(migrate_images_to_tenant_product, migrations.RunPython.noop),
        # 3. Drop old unique_together and FK
        migrations.AlterUniqueTogether(
            name='productimage',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='productimage',
            name='profile',
        ),
        # 4. Set new unique_together
        migrations.AlterUniqueTogether(
            name='productimage',
            unique_together={('tenant_product', 'slot')},
        ),
    ]
