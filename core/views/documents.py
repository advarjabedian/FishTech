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