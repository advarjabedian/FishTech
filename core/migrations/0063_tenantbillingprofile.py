from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0062_trim_tenant_and_processing_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantBillingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stripe_customer_id", models.CharField(blank=True, max_length=255)),
                ("stripe_subscription_id", models.CharField(blank=True, max_length=255)),
                ("stripe_price_id", models.CharField(blank=True, max_length=255)),
                ("subscription_status", models.CharField(choices=[("unknown", "Unknown"), ("incomplete", "Incomplete"), ("incomplete_expired", "Incomplete Expired"), ("trialing", "Trialing"), ("active", "Active"), ("past_due", "Past Due"), ("canceled", "Canceled"), ("unpaid", "Unpaid"), ("paused", "Paused")], default="unknown", max_length=32)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at", models.DateTimeField(blank=True, null=True)),
                ("canceled_at", models.DateTimeField(blank=True, null=True)),
                ("latest_invoice_id", models.CharField(blank=True, max_length=255)),
                ("latest_invoice_status", models.CharField(blank=True, max_length=64)),
                ("latest_invoice_amount_due", models.IntegerField(blank=True, null=True)),
                ("latest_invoice_amount_paid", models.IntegerField(blank=True, null=True)),
                ("latest_invoice_currency", models.CharField(blank=True, max_length=16)),
                ("latest_invoice_created_at", models.DateTimeField(blank=True, null=True)),
                ("customer_email", models.EmailField(blank=True, max_length=254)),
                ("last_checkout_session_id", models.CharField(blank=True, max_length=255)),
                ("last_checkout_completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_synced_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.OneToOneField(on_delete=models.deletion.CASCADE, related_name="billing_profile", to="core.tenant")),
            ],
            options={
                "ordering": ["tenant__name"],
            },
        ),
    ]
