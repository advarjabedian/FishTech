import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fishtech.settings')
django.setup()

from django.contrib.auth.models import User as DjangoUser
from core.models import TenantUser

# Get your Django user
user = DjangoUser.objects.get(username='arevvarjabedian')

# Update TenantUser to be admin
tenant_user = TenantUser.objects.get(user=user)
tenant_user.is_admin = True
tenant_user.save()

print(f"✓ {user.username} is now an admin!")