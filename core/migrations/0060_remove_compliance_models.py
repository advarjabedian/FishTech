from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_salesorderitem_process_batch_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SOPChild",
        ),
        migrations.DeleteModel(
            name="SOPParent",
        ),
        migrations.DeleteModel(
            name="SOP",
        ),
        migrations.DeleteModel(
            name="Zone",
        ),
        migrations.DeleteModel(
            name="CompanyHoliday",
        ),
        migrations.DeleteModel(
            name="CompanyOperationConfig",
        ),
        migrations.DeleteModel(
            name="CompanyCertificate",
        ),
        migrations.DeleteModel(
            name="CompanyHACCPOwner",
        ),
        migrations.DeleteModel(
            name="HACCPDocument",
        ),
        migrations.DeleteModel(
            name="CompanyProductType",
        ),
        migrations.DeleteModel(
            name="HACCPProductType",
        ),
    ]
