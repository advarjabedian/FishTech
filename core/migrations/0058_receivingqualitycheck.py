from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_salesorderallocation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReceivingQualityCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('freshness_score', models.PositiveSmallIntegerField(default=0)),
                ('appearance_ok', models.BooleanField(default=False)),
                ('odor_ok', models.BooleanField(default=False)),
                ('texture_ok', models.BooleanField(default=False)),
                ('packaging_ok', models.BooleanField(default=False)),
                ('temp_ok', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pass', 'Pass'), ('hold', 'Hold'), ('reject', 'Reject')], default='pass', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('checked_by_name', models.CharField(blank=True, max_length=100)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('checked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receiving_quality_checks', to=settings.AUTH_USER_MODEL)),
                ('inventory', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quality_check', to='core.inventory')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.tenant')),
            ],
            options={
                'db_table': 'receiving_quality_check',
            },
        ),
    ]
