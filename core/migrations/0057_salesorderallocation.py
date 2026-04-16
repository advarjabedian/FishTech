from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0056_processbatchwaste'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SalesOrderAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=12)),
                ('unit_type', models.CharField(blank=True, max_length=50)),
                ('allocated_by_name', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('allocated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sales_order_allocations', to=settings.AUTH_USER_MODEL)),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sales_allocations', to='core.inventory')),
                ('sales_order_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='allocations', to='core.salesorderitem')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.tenant')),
            ],
            options={
                'db_table': 'sales_order_allocation',
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
