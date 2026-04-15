/* Operations page JavaScript — extracted from operations.html */

let currentReportParentId = null;
let currentReportType = 'operational';

function handleDateChange(dateValue) {
    const selectedCompanyId = OPERATIONS_CONFIG.tenantId;
    window.location.href = `/operations/daily/?date=${dateValue}&company_id=${selectedCompanyId}`;
}

function handleShiftClick(shift) {
    startInspection(shift, OPERATIONS_CONFIG.currentUserId);
}

function startInspection(shift, inspectorId) {
    const companyId = OPERATIONS_CONFIG.tenantId;
    const date = OPERATIONS_CONFIG.selectedDate;

    fetch('/api/operations/start-inspection/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            shift: shift,
            company_id: companyId,
            date: date,
            user_id: inspectorId
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.href = data.redirect_url;
        } else {
            alert('Error starting inspection');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error starting inspection');
    });
}

function editInspection(parentId) {
    window.location.href = `/operations/inspection/${parentId}/`;
}

function toggleHoliday() {
    const companyId = OPERATIONS_CONFIG.tenantId;
    const date = OPERATIONS_CONFIG.selectedDate;

    fetch('/api/operations/toggle-holiday/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            company_id: companyId,
            date: date
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert('Error toggling holiday');
        }
    });
}

// Reports Modal Functions
function openReportsModal(parentId, shiftName) {
    currentReportParentId = parentId;
    document.getElementById('reports-shift-name').textContent = shiftName;

    document.querySelectorAll('#reportTabs .nav-link').forEach(tab => tab.classList.remove('active'));
    document.querySelector('#reportTabs .nav-link').classList.add('active');

    showReport('operational');
    new bootstrap.Modal(document.getElementById('reportsModal')).show();
}

function showReport(type) {
    currentReportType = type;

    document.querySelectorAll('#reportTabs .nav-link').forEach(tab => {
        tab.classList.remove('active');
        if ((type === 'operational' && tab.textContent.includes('Operational')) ||
            (type === 'deviations' && tab.textContent.includes('Deviations')) ||
            (type === 'images' && tab.textContent.includes('Images'))) {
            tab.classList.add('active');
        }
    });

    const pdfContainer = document.getElementById('pdf-viewer-container');
    const imagesContainer = document.getElementById('images-viewer-container');

    if (type === 'images') {
        pdfContainer.style.display = 'none';
        imagesContainer.style.display = 'block';
        loadInspectionImages();
    } else {
        pdfContainer.style.display = 'block';
        imagesContainer.style.display = 'none';

        const iframe = document.getElementById('pdf-iframe');
        if (type === 'operational') {
            iframe.src = `/operations/report/operational/${currentReportParentId}/#zoom=125`;
        } else {
            iframe.src = `/operations/report/deviations/${currentReportParentId}/#zoom=125`;
        }
    }
}

function loadInspectionImages() {
    fetch(`/api/operations/get-inspection-images/${currentReportParentId}/`)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('images-content');

            if (!data.success || !data.images || data.images.length === 0) {
                container.innerHTML = '<div class="text-center text-muted p-5">No images captured for this inspection</div>';
                return;
            }

            let html = '<div class="row g-3 p-3">';

            data.images.forEach(img => {
                const statusBadge = img.passed ?
                    '<span class="badge bg-success">PASS</span>' :
                    '<span class="badge bg-danger">FAIL</span>';

                html += `
                    <div class="col-md-6 col-lg-4">
                        <div class="card h-100">
                            <img src="${img.image}" class="card-img-top" style="height: 300px; object-fit: contain; background: #f8f9fa; cursor: pointer;" onclick="viewFullImage(event, '${img.image}')">
                            <div class="card-body">
                                <h6 class="card-title">ID: ${img.sop_did} ${statusBadge}</h6>
                                <p class="card-text">${img.description}</p>
                                ${img.notes ? `<p class="card-text"><small class="text-muted">Notes: ${img.notes}</small></p>` : ''}
                                ${img.deviation_reason ? `<p class="card-text text-danger"><small>Deviation: ${img.deviation_reason}</small></p>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
            container.innerHTML = html;
        })
        .catch(error => {
            console.error('Error loading images:', error);
            document.getElementById('images-content').innerHTML = '<div class="text-center text-danger p-5">Error loading images</div>';
        });
}

function viewFullImage(event, imageSrc) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    const win = window.open('', '_blank');
    if (!win) {
        alert('Please allow popups to view the image');
        return;
    }

    win.document.write(`
        <html>
            <head>
                <title>Inspection Image</title>
                <style>
                    body { margin: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #000; }
                    img { max-width: 100%; max-height: 100vh; object-fit: contain; }
                </style>
            </head>
            <body>
                <img src="${imageSrc}">
            </body>
        </html>
    `);

    return false;
}

function downloadCurrentReport() {
    const params = new URLSearchParams({
        company_id: OPERATIONS_CONFIG.tenantId,
        dates: OPERATIONS_CONFIG.selectedDate,
        include_operational: '1',
        include_deviations: '1'
    });
    window.open(`/operations/bulk-report/?${params.toString()}`, '_blank');
}

// Verification Modal Functions
let currentVerificationParentId = null;
let currentDeviations = [];
let isDrawing = false;
let isAssignedVerifier = false;

function startVerification(parentId, shiftName) {
    const currentUserId = OPERATIONS_CONFIG.currentUserId;
    const verifierUserId = OPERATIONS_CONFIG.verifierUserId;

    isAssignedVerifier = (verifierUserId && currentUserId === verifierUserId);

    if (!isAssignedVerifier) {
        if (!confirm('Are you HACCP certified and would you like to verify this record?')) {
            return;
        }
    }

    currentVerificationParentId = parentId;
    document.getElementById('verify-shift-name').textContent = shiftName;

    fetch(`/api/operations/get-deviations/${parentId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentDeviations = data.deviations;

                document.getElementById('corrective-actions-section').style.display = 'none';
                document.getElementById('review-section').style.display = 'none';
                document.getElementById('signature-section').style.display = 'none';
                document.getElementById('submit-verification-btn').style.display = 'none';

                if (currentDeviations.length > 0) {
                    showCorrectiveActions();
                } else {
                    showReview(data.all_items);
                }

                new bootstrap.Modal(document.getElementById('verificationModal')).show();
            } else {
                alert('Error loading inspection data');
            }
        });
}

function showCorrectiveActions() {
    const container = document.getElementById('deviations-list');
    container.innerHTML = '';

    currentDeviations.forEach((dev, index) => {
        const existingAction = dev.corrective_action || '';
        container.innerHTML += `
            <div class="card mb-2">
                <div class="card-body">
                    <p class="mb-1"><strong>${dev.description}</strong></p>
                    <p class="text-danger mb-2">Deviation: ${dev.deviation_reason}</p>
                    <textarea class="form-control corrective-action-input"
                              data-child-id="${dev.child_id}"
                              placeholder="Enter corrective action..."
                              rows="2">${existingAction}</textarea>
                </div>
            </div>
        `;
    });

    document.getElementById('corrective-actions-section').style.display = 'block';
}

function proceedToReview() {
    const inputs = document.querySelectorAll('.corrective-action-input');
    let allFilled = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            allFilled = false;
            input.classList.add('is-invalid');
        } else {
            input.classList.remove('is-invalid');
        }
    });

    if (!allFilled) {
        alert('Please enter corrective actions for all deviations');
        return;
    }

    const actions = [];
    inputs.forEach(input => {
        actions.push({
            child_id: input.dataset.childId,
            corrective_action: input.value.trim()
        });
    });

    fetch('/api/operations/save-corrective-actions/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            parent_id: currentVerificationParentId,
            actions: actions
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fetch(`/api/operations/get-deviations/${currentVerificationParentId}/`)
                .then(response => response.json())
                .then(data => {
                    showReview(data.all_items);
                });
        }
    });
}

function showReview(items) {
    document.getElementById('corrective-actions-section').style.display = 'none';

    const container = document.getElementById('review-content');
    let html = '<table class="table table-sm"><thead><tr><th>Item</th><th>Status</th><th>Notes</th></tr></thead><tbody>';

    items.forEach(item => {
        const status = item.passed ? '<span class="text-success">Pass</span>' :
                       item.failed ? '<span class="text-danger">Fail</span>' : '-';
        html += `<tr>
            <td>${item.description}</td>
            <td>${status}</td>
            <td>${item.notes || ''}</td>
        </tr>`;

        if (item.failed && item.deviation_reason) {
            html += `<tr class="table-warning">
                <td colspan="3">
                    <small><strong>Deviation:</strong> ${item.deviation_reason}</small><br>
                    <small><strong>Corrective Action:</strong> ${item.corrective_action || 'N/A'}</small>
                </td>
            </tr>`;
        }
    });

    html += '</tbody></table>';
    container.innerHTML = html;

    document.getElementById('review-section').style.display = 'block';
}

function proceedToSignature() {
    document.getElementById('review-section').style.display = 'none';
    document.getElementById('signature-section').style.display = 'block';
    document.getElementById('submit-verification-btn').style.display = 'inline-block';

    const verifierNameInput = document.getElementById('verifier-name');
    if (verifierNameInput && !verifierNameInput.value) {
        verifierNameInput.value = OPERATIONS_CONFIG.userName;
    }

    const savedSigBtn = document.getElementById('use-saved-sig-btn');
    if (savedSigBtn) {
        savedSigBtn.style.display = isAssignedVerifier ? 'inline-block' : 'none';
    }

    initSignaturePad();
}

function initSignaturePad() {
    const canvas = document.getElementById('signature-pad');
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';

    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseout', stopDrawing);

    canvas.addEventListener('touchstart', handleTouch);
    canvas.addEventListener('touchmove', handleTouchMove);
    canvas.addEventListener('touchend', stopDrawing);
}

function startDrawing(e) {
    isDrawing = true;
    const canvas = document.getElementById('signature-pad');
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    ctx.beginPath();
    ctx.moveTo(e.clientX - rect.left, e.clientY - rect.top);
}

function draw(e) {
    if (!isDrawing) return;
    const canvas = document.getElementById('signature-pad');
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    ctx.lineTo(e.clientX - rect.left, e.clientY - rect.top);
    ctx.stroke();
}

function stopDrawing() {
    isDrawing = false;
}

function handleTouch(e) {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousedown', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    document.getElementById('signature-pad').dispatchEvent(mouseEvent);
}

function handleTouchMove(e) {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
        clientX: touch.clientX,
        clientY: touch.clientY
    });
    document.getElementById('signature-pad').dispatchEvent(mouseEvent);
}

function clearSignature() {
    const canvas = document.getElementById('signature-pad');
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function useSavedSignature() {
    const companyId = OPERATIONS_CONFIG.tenantId;

    if (!isAssignedVerifier) {
        alert('Only the assigned verifier can use the saved signature.');
        return;
    }

    fetch(`/api/operations/get-verifier-signature/?company_id=${companyId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.signature) {
                const canvas = document.getElementById('signature-pad');
                const ctx = canvas.getContext('2d');
                const img = new Image();
                img.onload = function() {
                    ctx.fillStyle = 'white';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                };
                img.src = data.signature;
            } else {
                alert('No saved signature found. Please capture one in Operations Admin first.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error loading saved signature');
        });
}

function submitVerification() {
    const name = document.getElementById('verifier-name').value.trim();
    if (!name) {
        alert('Please enter your name');
        return;
    }

    const canvas = document.getElementById('signature-pad');
    const signature = canvas.toDataURL('image/png');

    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    let isBlank = true;
    for (let i = 0; i < imageData.data.length; i += 4) {
        if (imageData.data[i] < 250 || imageData.data[i+1] < 250 || imageData.data[i+2] < 250) {
            isBlank = false;
            break;
        }
    }

    if (isBlank) {
        alert('Please sign before submitting');
        return;
    }

    fetch('/api/operations/submit-verification/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            parent_id: currentVerificationParentId,
            verifier_name: name,
            verifier_signature: signature
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('verificationModal')).hide();
            location.reload();
        } else {
            alert('Error submitting verification');
        }
    });
}

// Bulk Report Functions
var bulkCurrentDate = new Date();
var bulkCalendarData = {};
var selectedDays = new Set();

function openBulkReportModal() {
    selectedDays.clear();
    updateSelectedCount();
    const companySelect = document.getElementById('bulk-report-company');
    if (companySelect.value) {
        loadBulkReportCalendar();
    }
    new bootstrap.Modal(document.getElementById('bulkReportModal')).show();
}

function loadBulkReportCalendar() {
    const companyId = document.getElementById('bulk-report-company').value;
    if (!companyId) {
        document.getElementById('bulk-calendar-body').innerHTML = '<div class="text-center text-muted p-4" style="grid-column: span 7;">Select a company to load calendar</div>';
        return;
    }

    fetch(`/api/operations/get-calendar-data/?company_id=${companyId}`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                bulkCalendarData = data.calendar_data;
                renderBulkCalendar();
            }
        });
}

function renderBulkCalendar() {
    const year = bulkCurrentDate.getFullYear();
    const month = bulkCurrentDate.getMonth();

    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December'];

    document.getElementById('bulk-calendar-month-year').textContent = `${monthNames[month]} ${year}`;

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startingDay = firstDay.getDay();
    const totalDays = lastDay.getDate();

    let html = '';

    for (let i = 0; i < startingDay; i++) {
        html += '<div class="bulk-calendar-day empty"></div>';
    }

    for (let day = 1; day <= totalDays; day++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const dayData = bulkCalendarData[dateStr] || {};
        const hasCompleted = dayData.preop === true || dayData.midday === true || dayData.postop === true;
        const hasVerified = dayData.preop_verified || dayData.midday_verified || dayData.postop_verified;
        const isSelected = selectedDays.has(dateStr);
        const isOperatingDay = dayData.is_operating_day;

        let classes = 'bulk-calendar-day';
        if (isSelected) classes += ' selected';
        else if (hasVerified) classes += ' has-verified';
        else if (hasCompleted) classes += ' has-completed';
        if (!isOperatingDay) classes += ' no-data';

        let badges = '<div class="day-badges">';
        if (dayData.preop_verified) badges += '<span class="badge bg-purple" style="background-color: #6f42c1 !important;">Pre</span>';
        else if (dayData.preop === true) badges += '<span class="badge bg-success">Pre</span>';
        else if (dayData.preop === false) badges += '<span class="badge bg-warning text-dark">Pre</span>';
        else if (isOperatingDay) badges += '<span class="badge bg-secondary">Pre</span>';

        if (dayData.midday_verified) badges += '<span class="badge bg-purple" style="background-color: #6f42c1 !important;">Mid</span>';
        else if (dayData.midday === true) badges += '<span class="badge bg-success">Mid</span>';
        else if (dayData.midday === false) badges += '<span class="badge bg-warning text-dark">Mid</span>';
        else if (isOperatingDay) badges += '<span class="badge bg-secondary">Mid</span>';

        if (dayData.postop_verified) badges += '<span class="badge bg-purple" style="background-color: #6f42c1 !important;">Post</span>';
        else if (dayData.postop === true) badges += '<span class="badge bg-success">Post</span>';
        else if (dayData.postop === false) badges += '<span class="badge bg-warning text-dark">Post</span>';
        else if (isOperatingDay) badges += '<span class="badge bg-secondary">Post</span>';
        badges += '</div>';

        const clickable = hasCompleted ? `onclick="toggleDaySelection('${dateStr}')"` : '';

        html += `<div class="${classes}" data-date="${dateStr}" ${clickable}>
            <div class="day-number">${day}</div>
            ${badges}
        </div>`;
    }

    const remainingCells = (7 - ((startingDay + totalDays) % 7)) % 7;
    for (let i = 0; i < remainingCells; i++) {
        html += '<div class="bulk-calendar-day empty"></div>';
    }

    document.getElementById('bulk-calendar-body').innerHTML = html;
}

function changeBulkMonth(delta) {
    bulkCurrentDate.setMonth(bulkCurrentDate.getMonth() + delta);
    renderBulkCalendar();
}

function toggleDaySelection(dateStr) {
    const dayData = bulkCalendarData[dateStr];
    if (!dayData || (!dayData.preop && !dayData.midday && !dayData.postop)) return;

    if (selectedDays.has(dateStr)) selectedDays.delete(dateStr);
    else selectedDays.add(dateStr);

    const el = document.querySelector(`.bulk-calendar-day[data-date="${dateStr}"]`);
    if (el) el.classList.toggle('selected');

    updateSelectedCount();
}

function selectAllDays() {
    Object.keys(bulkCalendarData).forEach(dateStr => {
        const dayData = bulkCalendarData[dateStr];
        if (dayData.preop === true || dayData.midday === true || dayData.postop === true) {
            selectedDays.add(dateStr);
        }
    });
    renderBulkCalendar();
    updateSelectedCount();
}

function clearAllDays() {
    selectedDays.clear();
    renderBulkCalendar();
    updateSelectedCount();
}

function updateSelectedCount() {
    const count = selectedDays.size;
    document.getElementById('selected-days-count').textContent = `${count} day${count !== 1 ? 's' : ''} selected`;
    document.getElementById('generate-btn').disabled = count === 0;
}

function generateBulkReports() {
    const companyId = document.getElementById('bulk-report-company').value;
    const includeOperational = document.getElementById('include-operational').checked;
    const includeDeviations = document.getElementById('include-deviations').checked;

    if (!companyId || selectedDays.size === 0) {
        alert('Please select a company and at least one day');
        return;
    }

    if (!includeOperational && !includeDeviations) {
        alert('Please select at least one report type');
        return;
    }

    const dates = Array.from(selectedDays).sort();
    const params = new URLSearchParams({
        company_id: companyId,
        dates: dates.join(','),
        include_operational: includeOperational ? '1' : '0',
        include_deviations: includeDeviations ? '1' : '0'
    });

    window.open(`/operations/bulk-report/?${params.toString()}`, '_blank');
}
