from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .haccp import *
from .auth import *
from .tenant import *
from .operations import *
from .operations_api import *
from .operations_reports import *
from .documents import *

# This allows: from core.views import haccp, login_view, operations_dashboard, etc.





@login_required
def documents_home(request):
    """Display the documents home page"""
    if not request.tenant:
        return redirect('login')
    
    return render(request, 'core/documents/documents_home.html')


@login_required
def so_documents(request):
    """Display sales order documents"""
    if not request.tenant:
        return redirect('login')
    
    soid = request.GET.get('soid', None)
    return render(request, 'core/documents/so_documents.html', {'soid': soid})


@login_required
def po_documents(request):
    """Display purchase order documents"""
    if not request.tenant:
        return redirect('login')
    
    poid = request.GET.get('poid', None)
    return render(request, 'core/documents/po_documents.html', {'poid': poid})


@login_required
def customer_documents(request):
    """Display customer documents"""
    if not request.tenant:
        return redirect('login')
    
    customer_id = request.GET.get('customer_id', None)
    return render(request, 'core/documents/customer_documents.html', {'customer_id': customer_id})

@login_required
def vendor_documents(request):
    """Display vendor documents"""
    if not request.tenant:
        return redirect('login')
    
    vendor_id = request.GET.get('vendor_id', None)
    return render(request, 'core/Documents/vendor_documents.html', {'vendor_id': vendor_id})


@login_required
def licenses(request):
    """Display licenses page"""
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/documents/licenses.html')


@login_required
def vehicles(request):
    """Display vehicles page"""
    if not request.tenant:
        return redirect('login')
    return render(request, 'core/documents/vehicles.html')