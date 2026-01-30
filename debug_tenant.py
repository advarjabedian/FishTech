#!/usr/bin/env python
"""
Debug script to check tenant and company setup.
Run from project root with: python debug_tenant.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fishtech.settings')
django.setup()

from django.contrib.auth.models import User as DjangoUser
from core.models import Tenant, TenantUser, Company, get_current_tenant, set_current_tenant

print("=" * 60)
print("FISHTECH TENANT DEBUG")
print("=" * 60)

# 1. Check Tenants
print("\n1. TENANTS:")
tenants = Tenant.objects.all()
if tenants.exists():
    for t in tenants:
        print(f"   - ID: {t.id}, Name: {t.name}, Subdomain: {t.subdomain}, Active: {t.is_active}")
else:
    print("   ❌ NO TENANTS FOUND - You need to create a tenant first!")

# 2. Check Django Users
print("\n2. DJANGO USERS:")
users = DjangoUser.objects.all()
if users.exists():
    for u in users:
        print(f"   - ID: {u.id}, Username: {u.username}, Email: {u.email}")
else:
    print("   ❌ NO USERS FOUND")

# 3. Check TenantUser links
print("\n3. TENANT-USER LINKS:")
tenant_users = TenantUser.objects.select_related('user', 'tenant').all()
if tenant_users.exists():
    for tu in tenant_users:
        print(f"   - User: {tu.user.username} -> Tenant: {tu.tenant.name} (Admin: {tu.is_admin})")
else:
    print("   ❌ NO TENANT-USER LINKS FOUND - Users need to be linked to tenants!")

# 4. Check Companies (bypassing tenant filter)
print("\n4. ALL COMPANIES (using all_objects to bypass tenant filter):")
all_companies = Company.all_objects.all()
if all_companies.exists():
    for c in all_companies:
        print(f"   - ID: {c.companyid}, Name: {c.companyname}, Tenant ID: {c.tenant_id}")
else:
    print("   ❌ NO COMPANIES FOUND - You need to create companies!")

# 5. Test tenant filtering
print("\n5. TESTING TENANT FILTER:")
if tenants.exists():
    test_tenant = tenants.first()
    print(f"   Setting current tenant to: {test_tenant.name} (ID: {test_tenant.id})")
    set_current_tenant(test_tenant)
    
    print(f"   get_current_tenant() = {get_current_tenant()}")
    
    filtered_companies = Company.objects.all()
    print(f"   Companies visible with filter: {filtered_companies.count()}")
    for c in filtered_companies:
        print(f"      - {c.companyname}")
    
    if filtered_companies.count() == 0 and all_companies.exists():
        print("\n   ⚠️  PROBLEM: Companies exist but aren't visible!")
        print("      Check that companies have the correct tenant_id")
        
        # Show tenant IDs
        print("\n   Company tenant assignments:")
        for c in all_companies:
            match = "✓" if c.tenant_id == test_tenant.id else "✗"
            print(f"      {match} {c.companyname}: tenant_id={c.tenant_id} (expected {test_tenant.id})")
else:
    print("   ❌ Cannot test - no tenants exist")

# 6. Summary and recommendations
print("\n" + "=" * 60)
print("SUMMARY & RECOMMENDATIONS:")
print("=" * 60)

issues = []
if not tenants.exists():
    issues.append("Create a tenant: Tenant.objects.create(name='My Company', subdomain='mycompany', is_active=True)")
if not users.exists():
    issues.append("Create a Django user via admin or createsuperuser")
if not tenant_users.exists():
    issues.append("Link user to tenant: TenantUser.objects.create(user=user, tenant=tenant, is_admin=True)")
if not all_companies.exists():
    issues.append("Create a company: Company.objects.create(tenant=tenant, companyname='Facility 1')")

if issues:
    print("\n⚠️  ISSUES TO FIX:")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
else:
    print("\n✓ Basic setup looks good!")
    
    # Check if filtering is working
    if tenants.exists():
        set_current_tenant(tenants.first())
        if Company.objects.count() == 0 and all_companies.exists():
            print("\n⚠️  BUT: Tenant filtering isn't matching any companies.")
            print("   Make sure your companies have the correct tenant_id.")

print("\n" + "=" * 60)