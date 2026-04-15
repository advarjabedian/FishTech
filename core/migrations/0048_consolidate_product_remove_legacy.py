# Consolidate TenantProduct into Product, remove SO/SOD and FishMenuItem

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_add_sales_order_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Add new fields to Product ──────────────────────────────────────
        migrations.AddField(
            model_name='product',
            name='unit_type',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='product',
            name='pack_size',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='default_price',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='sort_order',
            field=models.IntegerField(default=0),
        ),

        # ── Make product_id optional ───────────────────────────────────────
        migrations.AlterField(
            model_name='product',
            name='product_id',
            field=models.CharField(blank=True, max_length=100),
        ),

        # ── Update Product Meta ────────────────────────────────────────────
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['sort_order', 'description']},
        ),
        migrations.AlterUniqueTogether(
            name='product',
            unique_together=set(),
        ),

        # ── Add fields to SalesOrder ───────────────────────────────────────
        migrations.AddField(
            model_name='salesorder',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='salesorder',
            name='is_completed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='salesorder',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='salesorder',
            name='completed_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='completed_orders',
                to=settings.AUTH_USER_MODEL,
            ),
        ),

        # ── Rename CustomerProfile FK from tenant_product to product ──────
        migrations.RenameField(
            model_name='customerprofile',
            old_name='tenant_product',
            new_name='product',
        ),
        migrations.AlterField(
            model_name='customerprofile',
            name='product',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assignments',
                to='core.product',
            ),
        ),

        # ── Rename ProductImage FK from tenant_product to product ─────────
        migrations.RenameField(
            model_name='productimage',
            old_name='tenant_product',
            new_name='product',
        ),
        migrations.AlterField(
            model_name='productimage',
            name='product',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='images',
                to='core.product',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='productimage',
            unique_together={('product', 'slot')},
        ),

        # ── Remove legacy models ──────────────────────────────────────────
        migrations.DeleteModel(name='SOD'),
        migrations.DeleteModel(name='SO'),
        migrations.DeleteModel(name='FishMenuItem'),
        migrations.DeleteModel(name='TenantProduct'),
    ]
