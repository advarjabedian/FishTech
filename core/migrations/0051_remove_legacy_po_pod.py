# Remove legacy PO and POD models (replaced by PurchaseOrder/PurchaseOrderItem)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_remove_company_model'),
    ]

    operations = [
        migrations.DeleteModel(name='POD'),
        migrations.DeleteModel(name='PO'),
    ]
