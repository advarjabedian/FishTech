import uuid
from django.db import migrations, models


def gen_unique_tokens(apps, schema_editor):
    Customer = apps.get_model('core', 'Customer')
    for customer in Customer.objects.all():
        customer.public_token = uuid.uuid4()
        customer.save(update_fields=['public_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_so_assigned_to_so_completed_at_so_completed_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='public_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
            preserve_default=False,
        ),
        migrations.RunPython(gen_unique_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer',
            name='public_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False),
        ),
    ]
