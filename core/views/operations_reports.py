from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth.models import User
from core.models import SOP, SOPParent, SOPChild, Company
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
import base64


@login_required
@xframe_options_sameorigin
def generate_operational_report(request, parent_id):
    """Generate the Operational Report PDF"""
    sop_parent = SOPParent.objects.get(id=parent_id)
    children = SOPChild.objects.filter(sop_parent=sop_parent).order_by('sop_did')
    
    # Get company info
    company = sop_parent.company
    company_name = company.companyname if company else f"Company {parent_id}"
    
    # Get SOP details
    sop_ids = [c.sop_did for c in children]
    sops = {s.sop_did: s for s in SOP.objects.filter(sop_did__in=sop_ids, company=company)}
    
    # Get inspector name
    inspector = None
    if sop_parent.user_inspected:
        inspector = sop_parent.user_inspected
    inspector_name = inspector.get_full_name() if inspector else 'Unknown'
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor('#1a5276'))
    
    elements = []
    
    # Header with company info and date box
    date_box = Table([
        ['Date:', sop_parent.date.strftime('%m/%d/%Y')],
        ['Time:', sop_parent.time.strftime('%I:%M %p') if sop_parent.time else ''],
        ['Shift:', sop_parent.shift],
    ], colWidths=[50, 80], style=TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
    ]))
    
    header_data = [[Paragraph(f"<b>{company_name}</b>", styles['Normal']), '', '', date_box]]
    header_table = Table(header_data, colWidths=[250, 50, 50, 150])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Title
    elements.append(Paragraph(f"{sop_parent.shift} Operational Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Main table
    table_data = [['Zone', 'Description', 'Notes', 'Status']]
    
    for child in children:
        sop = sops.get(child.sop_did)
        zone = sop.zone.name if sop and sop.zone else ''
        description = sop.description if sop else f'Item {child.sop_did}'
        notes_text = child.notes or ''
        status = 'Pass' if child.passed else 'Fail' if child.failed else ''
        
        table_data.append([
            zone,
            Paragraph(description, ParagraphStyle('Desc', fontSize=8, leading=10)),
            notes_text,
            Paragraph(f"<b>{status}</b>", ParagraphStyle('Status', fontSize=9, textColor=colors.red if status == 'Fail' else colors.black))
        ])
    
    main_table = Table(table_data, colWidths=[70, 320, 50, 60])
    main_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d6eaf8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a5276')),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 0), (3, -1), 'CENTER'),
    ]))
    elements.append(main_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Signatures section
    inspector_sig_img = None
    verifier_sig_img = None
    
    if sop_parent.inspector_signature:
        try:
            sig_data = sop_parent.inspector_signature
            if ',' in sig_data:
                sig_data = sig_data.split(',')[1]
            sig_data_bytes = base64.b64decode(sig_data)
            inspector_sig_img = Image(BytesIO(sig_data_bytes), width=1.5*inch, height=0.5*inch)
        except:
            pass
    
    if sop_parent.verifier_signature:
        try:
            sig_data = sop_parent.verifier_signature
            if ',' in sig_data:
                sig_data = sig_data.split(',')[1]
            sig_data_bytes = base64.b64decode(sig_data)
            verifier_sig_img = Image(BytesIO(sig_data_bytes), width=1.5*inch, height=0.5*inch)
        except:
            pass
    
    inspector_name_display = sop_parent.inspector_name or inspector_name
    verifier_name_display = sop_parent.verifier_name or ''
    
    sig_table_data = [
        [Paragraph("<b>Inspected By</b>", styles['Normal']), '', Paragraph("<b>Reviewed & Verified By</b>", styles['Normal'])],
        [inspector_sig_img if inspector_sig_img else '', '', verifier_sig_img if verifier_sig_img else ''],
        [Paragraph(f"<font color='blue'>{inspector_name_display}</font>", styles['Normal']), '', Paragraph(f"<font color='blue'>{verifier_name_display}</font>", styles['Normal'])],
        [Paragraph(f"<font color='blue'>{sop_parent.date.strftime('%A, %B %d, %Y')}</font>", styles['Normal']), '', Paragraph(f"<font color='blue'>{sop_parent.date.strftime('%A, %B %d, %Y')}</font>", styles['Normal'])],
    ]
    
    sig_table = Table(sig_table_data, colWidths=[200, 100, 200])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(sig_table)
    
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="OperationalReport_{sop_parent.shift}_{sop_parent.date}.pdf"'
    return response


@login_required
def generate_deviations_report(request, parent_id):
    """Generate the Deviations/Corrective Actions Report PDF"""
    sop_parent = SOPParent.objects.get(id=parent_id)
    company = sop_parent.company
    
    # Get only failed items with deviations
    deviations = SOPChild.objects.filter(
        sop_parent=sop_parent,
        failed=True
    ).exclude(deviation_reason__isnull=True).exclude(deviation_reason='')
    
    # Get SOP details
    sop_ids = [c.sop_did for c in deviations]
    sops = {s.sop_did: s for s in SOP.objects.filter(sop_did__in=sop_ids, company=company)}
    
    # Get inspector name
    inspector_name = sop_parent.user_inspected.get_full_name() if sop_parent.user_inspected else 'Unknown'
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor('#c0392b'))
    
    elements = []
    
    # Title
    elements.append(Paragraph("Deviations / Corrective Actions", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Header info
    header_data = [
        [Paragraph(f"<b>{len(deviations)}</b>", ParagraphStyle('Big', fontSize=24, alignment=TA_CENTER)), 
         Paragraph(f"<b>Inspected By</b><br/><font color='blue'>{inspector_name}</font>", styles['Normal']),
         Table([
             ['Date:', sop_parent.date.strftime('%m/%d/%Y')],
             ['Time:', sop_parent.time.strftime('%I:%M %p') if sop_parent.time else ''],
             ['Shift:', sop_parent.shift],
         ], colWidths=[50, 80], style=TableStyle([
             ('GRID', (0, 0), (-1, -1), 1, colors.black),
             ('FONTSIZE', (0, 0), (-1, -1), 10),
         ]))]
    ]
    header_table = Table(header_data, colWidths=[80, 250, 150])
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Deviations table
    if deviations:
        table_data = [['Item / Zone', 'Deviation', 'Action']]
        
        for dev in deviations:
            sop = sops.get(dev.sop_did)
            description = sop.description if sop else f'Item {dev.sop_did}'
            zone = sop.zone.name if sop and sop.zone else ''
            
            table_data.append([
                Paragraph(f"<font color='red'>{description}</font><br/><br/>{zone}", ParagraphStyle('Item', fontSize=8, leading=10)),
                Paragraph(f"<font color='#c0392b'>{dev.deviation_reason or ''}</font>", ParagraphStyle('Dev', fontSize=8, leading=10)),
                Paragraph(dev.corrective_action or '', ParagraphStyle('Action', fontSize=8, leading=10)),
            ])
        
        main_table = Table(table_data, colWidths=[150, 200, 150])
        main_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5b7b1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#922b21')),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#fcf3cf')),
        ]))
        elements.append(main_table)
    else:
        elements.append(Paragraph("No deviations recorded.", styles['Normal']))
    
    elements.append(Spacer(1, 0.5*inch))
    
    # Signature section
    verifier_sig_img = None
    if sop_parent.verifier_signature:
        try:
            sig_data = sop_parent.verifier_signature
            if ',' in sig_data:
                sig_data = sig_data.split(',')[1]
            sig_data_bytes = base64.b64decode(sig_data)
            verifier_sig_img = Image(BytesIO(sig_data_bytes), width=1.5*inch, height=0.5*inch)
        except:
            pass
    
    sig_data = [
        ['', verifier_sig_img if verifier_sig_img else ''],
        ['', Paragraph(f"<font color='blue'>Verified By: {sop_parent.verifier_name or ''}</font>", styles['Normal'])],
        ['', Paragraph(f"<font color='blue'>{sop_parent.date.strftime('%A, %B %d, %Y')}</font>", styles['Normal'])],
    ]
    
    sig_table = Table(sig_data, colWidths=[300, 200])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (1, 0), (1, -1), 'MIDDLE'),
    ]))
    elements.append(sig_table)
    
    doc.build(elements)
    
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="DeviationsReport_{sop_parent.shift}_{sop_parent.date}.pdf"'
    return response


@login_required
def generate_bulk_report(request):
    """Generate bulk PDF report for multiple days"""
    from PyPDF2 import PdfMerger
    
    company_id = request.GET.get('company_id')
    dates_str = request.GET.get('dates', '')
    include_operational = request.GET.get('include_operational') == '1'
    include_deviations = request.GET.get('include_deviations') == '1'
    
    if not company_id or not dates_str:
        return HttpResponse('Missing parameters', status=400)
    
    dates = dates_str.split(',')
    
    # Get all SOPParent records for these dates and company
    parents = SOPParent.objects.filter(
        company_id=company_id,
        date__in=dates,
        completed=True
    ).order_by('date', 'shift')
    
    if not parents:
        return HttpResponse('No completed inspections found for selected dates', status=404)
    
    # Create combined PDF
    buffer = BytesIO()
    merger = PdfMerger()
    
    for parent in parents:
        # Generate operational report
        if include_operational:
            op_response = generate_operational_report(request, parent.id)
            op_buffer = BytesIO(op_response.content)
            merger.append(op_buffer)
        
        # Generate deviations report if there are deviations
        if include_deviations:
            dev_count = SOPChild.objects.filter(
                sop_parent=parent,
                failed=True
            ).exclude(deviation_reason__isnull=True).exclude(deviation_reason='').count()
            
            if dev_count > 0:
                dev_response = generate_deviations_report(request, parent.id)
                dev_buffer = BytesIO(dev_response.content)
                merger.append(dev_buffer)
    
    merger.write(buffer)
    merger.close()
    
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="BulkReport_{company_id}_{dates[0]}_to_{dates[-1]}.pdf"'
    return response
