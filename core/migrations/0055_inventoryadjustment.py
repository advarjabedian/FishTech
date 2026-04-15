from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_salesorder_actual_delivery_date_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='InventoryAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('adjustment_type', models.CharField(choices=[('increase', 'Increase'), ('decrease', 'Decrease'), ('set_count', 'Set Count')], max_length=20)),
                ('reason_code', models.CharField(choices=[('count_correction', 'Count Correction'), ('damage', 'Damage'), ('shrinkage', 'Shrinkage'), ('spoilage', 'Spoilage'), ('waste', 'Waste'), ('sample', 'Sample / QA Pull'), ('return', 'Return / Restock'), ('other', 'Other')], max_length=30)),
                ('quantity_before', models.DecimalField(decimal_places=4, max_digits=12)),
                ('quantity_delta', models.DecimalField(decimal_places=4, max_digits=12)),
                ('quantity_after', models.DecimalField(decimal_places=4, max_digits=12)),
                ('notes', models.TextField(blank=True)),
                ('created_by_name', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_adjustments', to=settings.AUTH_USER_MODEL)),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adjustments', to='core.inventory')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.product')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.tenant')),
            ],
            options={
                'db_table': 'inventory_adjustment',
                'ordering': ['-created_at'],
            },
        ),
    ]
