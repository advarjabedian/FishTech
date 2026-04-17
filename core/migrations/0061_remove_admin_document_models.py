from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0060_remove_compliance_models"),
    ]

    operations = [
        migrations.DeleteModel(
            name="InboundMessage",
        ),
        migrations.DeleteModel(
            name="License",
        ),
        migrations.DeleteModel(
            name="Vehicle",
        ),
        migrations.DeleteModel(
            name="TenantDocument",
        ),
        migrations.DeleteModel(
            name="Lead",
        ),
    ]
