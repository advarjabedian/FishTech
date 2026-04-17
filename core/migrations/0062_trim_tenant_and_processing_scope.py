from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0061_remove_admin_document_models"),
    ]

    operations = [
        migrations.RemoveField(model_name="tenant", name="stripe_customer_id"),
        migrations.RemoveField(model_name="tenant", name="stripe_subscription_id"),
        migrations.RemoveField(model_name="tenant", name="subscription_status"),
        migrations.RemoveField(model_name="tenant", name="trial_ends_at"),
        migrations.RemoveField(model_name="tenant", name="subscription_ends_at"),
        migrations.RemoveField(model_name="tenant", name="reply_to_email"),
        migrations.RemoveField(model_name="tenant", name="reply_to_name"),
        migrations.RemoveField(model_name="tenant", name="inbound_email_address"),
        migrations.RemoveField(model_name="tenant", name="inbound_email_password"),
        migrations.RemoveField(model_name="tenant", name="inbound_email_imap_server"),
        migrations.RemoveField(model_name="tenant", name="smtp_host"),
        migrations.RemoveField(model_name="tenant", name="smtp_port"),
        migrations.RemoveField(model_name="tenant", name="smtp_use_tls"),
        migrations.RemoveField(model_name="tenant", name="smtp_user"),
        migrations.RemoveField(model_name="tenant", name="smtp_password"),
        migrations.RemoveField(model_name="tenant", name="smtp_from_email"),
        migrations.RemoveField(model_name="tenant", name="twilio_account_sid"),
        migrations.RemoveField(model_name="tenant", name="twilio_auth_token"),
        migrations.RemoveField(model_name="tenant", name="twilio_phone_number"),
        migrations.AlterField(
            model_name="processbatch",
            name="process_type",
            field=models.CharField(choices=[("fish_cutting", "Fish Cutting")], max_length=30),
        ),
        migrations.AlterField(
            model_name="salesorderitem",
            name="process_type",
            field=models.CharField(blank=True, choices=[("fish_cutting", "Fish Cutting")], max_length=30),
        ),
    ]
