from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_inventoryadjustment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcessBatchWaste',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry_type', models.CharField(choices=[('waste', 'Waste'), ('byproduct', 'Byproduct')], max_length=20)),
                ('category', models.CharField(choices=[('trim', 'Trim'), ('shell', 'Shell'), ('spoilage', 'Spoilage'), ('damage', 'Damage'), ('sample', 'QA Sample'), ('rework', 'Rework'), ('donation', 'Donation'), ('other', 'Other')], max_length=30)),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=12)),
                ('unit_type', models.CharField(blank=True, max_length=50)),
                ('estimated_value', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_by_name', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='waste_entries', to='core.processbatch')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='process_batch_waste_entries', to=settings.AUTH_USER_MODEL)),
                ('source_inventory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.inventory')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.tenant')),
            ],
            options={
                'db_table': 'processing_batch_waste',
                'ordering': ['-created_at'],
            },
        ),
    ]
