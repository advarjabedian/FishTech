# Remove deprecated Company model and all company FK fields.
# Tenant is now the sole organizational unit.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_consolidate_contact_email'),
    ]

    operations = [
        # Remove company FK fields from all models
        migrations.RemoveField(model_name='companyproducttype', name='company'),
        migrations.RemoveField(model_name='companyhaccpowner', name='company'),
        migrations.RemoveField(model_name='haccpdocument', name='company'),
        migrations.RemoveField(model_name='zone', name='company'),
        migrations.RemoveField(model_name='sop', name='company'),
        migrations.RemoveField(model_name='sopparent', name='company'),
        migrations.RemoveField(model_name='companyoperationconfig', name='company'),
        migrations.RemoveField(model_name='companyholiday', name='company'),
        migrations.RemoveField(model_name='companycertificate', name='company'),
        migrations.RemoveField(model_name='po', name='company'),
        migrations.RemoveField(model_name='license', name='company'),
        migrations.RemoveField(model_name='inventory', name='company'),

        # Remove UserCompany model
        migrations.DeleteModel(name='UserCompany'),

        # Remove Company model
        migrations.DeleteModel(name='Company'),
    ]
