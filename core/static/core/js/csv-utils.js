/**
 * CSV Export / Import utilities.
 */

/* ── Export ──────────────────────────────────────────────────────── */

function exportCSV(rows, filename, columns) {
    if (!rows || !rows.length) { alert('Nothing to export.'); return; }
    const cols = columns || Object.keys(rows[0]).map(k => ({ key: k, label: k }));
    const header = cols.map(c => _csvCell(c.label)).join(',');
    const lines = rows.map(row => cols.map(c => _csvCell(row[c.key] ?? '')).join(','));
    const csv = [header, ...lines].join('\r\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function _csvCell(val) {
    const s = String(val);
    return (s.includes(',') || s.includes('"') || s.includes('\n'))
        ? '"' + s.replace(/"/g, '""') + '"' : s;
}

/* ── CSV parser (handles quoted fields) ─────────────────────────── */

function _parseCSVText(text) {
    const lines = [];
    let row = []; let cell = ''; let inQuote = false;
    for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (inQuote) {
            if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
            else if (ch === '"') { inQuote = false; }
            else { cell += ch; }
        } else {
            if (ch === '"') { inQuote = true; }
            else if (ch === ',') { row.push(cell.trim()); cell = ''; }
            else if (ch === '\n' || ch === '\r') {
                if (ch === '\r' && text[i + 1] === '\n') i++;
                row.push(cell.trim()); if (row.some(c => c)) lines.push(row);
                row = []; cell = '';
            } else { cell += ch; }
        }
    }
    row.push(cell.trim());
    if (row.some(c => c)) lines.push(row);
    return lines;
}

/* ── Import with preview modal ──────────────────────────────────── */

let _importState = {};

function openImportCSV(apiUrl, onSuccess, expectedFields) {
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.csv';
    input.onchange = () => {
        const file = input.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            const lines = _parseCSVText(reader.result);
            if (lines.length < 2) { alert('CSV file is empty or has no data rows.'); return; }
            _importState = { apiUrl, onSuccess, csvHeaders: lines[0], csvRows: lines.slice(1) };
            _showImportModal(expectedFields);
        };
        reader.readAsText(file);
    };
    input.click();
}

function _showImportModal(expectedFields) {
    // Remove existing modal
    const existing = document.getElementById('csvImportOverlay');
    if (existing) existing.remove();

    const { csvHeaders, csvRows } = _importState;

    // Auto-detect expected fields from CSV headers if not provided
    const fields = expectedFields || csvHeaders.map(h => h);

    // Build mapping rows — auto-match by name
    const mapRows = fields.map(f => {
        const match = csvHeaders.findIndex(h =>
            h.toLowerCase().replace(/[\s_-]/g, '') === f.toLowerCase().replace(/[\s_-]/g, '')
        );
        return { field: f, csvIdx: match };
    }).filter(m => m.csvIdx !== -1);  // only show matched + unmatched csv columns

    // Find unmatched CSV columns
    const mappedIdxs = new Set(mapRows.map(m => m.csvIdx));
    const unmatchedCsv = csvHeaders.map((h, i) => ({ header: h, idx: i })).filter(x => !mappedIdxs.has(x.idx));

    const optionsHtml = '<option value="-1">(skip)</option>' +
        csvHeaders.map((h, i) => `<option value="${i}">${_esc(h)}</option>`).join('');

    // Preview first 5 rows
    const previewRows = csvRows.slice(0, 5);

    const overlay = document.createElement('div');
    overlay.id = 'csvImportOverlay';
    overlay.className = 'csv-import-overlay';
    overlay.innerHTML = `
        <div class="csv-import-modal" onclick="event.stopPropagation()">
            <div class="csv-import-header">
                <h4>Import Preview</h4>
                <button class="csv-close-btn" onclick="_closeImportModal()"><i class="bi bi-x-lg"></i></button>
            </div>
            <div class="csv-import-body">
                <div class="csv-import-info">
                    <span><i class="bi bi-file-earmark-text me-1"></i>${csvRows.length} row(s) found</span>
                    <span><i class="bi bi-columns-gap me-1"></i>${csvHeaders.length} column(s)</span>
                </div>

                <h6 style="font-weight:700; margin:1rem 0 0.5rem;">Column Mapping</h6>
                <p style="font-size:0.8rem; color:#64748b; margin-bottom:0.75rem;">
                    Match CSV columns to the expected fields. Columns are auto-matched by name.
                </p>
                <div class="csv-mapping-table">
                    <div class="csv-mapping-row csv-mapping-header">
                        <div>Target Field</div>
                        <div></div>
                        <div>CSV Column</div>
                        <div>Status</div>
                    </div>
                    ${fields.map((f, i) => {
                        const matchIdx = csvHeaders.findIndex(h =>
                            h.toLowerCase().replace(/[\s_-]/g, '') === f.toLowerCase().replace(/[\s_-]/g, '')
                        );
                        return `
                        <div class="csv-mapping-row">
                            <div class="csv-field-name">${_esc(f)}</div>
                            <div style="color:#94a3b8;"><i class="bi bi-arrow-left"></i></div>
                            <div><select class="csv-map-select" data-field="${_esc(f)}" id="csv-map-${i}">
                                ${optionsHtml}
                            </select></div>
                            <div class="csv-match-status" id="csv-status-${i}"></div>
                        </div>`;
                    }).join('')}
                </div>

                <h6 style="font-weight:700; margin:1.25rem 0 0.5rem;">Data Preview</h6>
                <div style="overflow-x:auto;">
                    <table class="csv-preview-table">
                        <thead><tr>${csvHeaders.map(h => `<th>${_esc(h)}</th>`).join('')}</tr></thead>
                        <tbody>${previewRows.map(row =>
                            `<tr>${csvHeaders.map((_, i) => `<td>${_esc(row[i] || '')}</td>`).join('')}</tr>`
                        ).join('')}</tbody>
                    </table>
                </div>
                ${csvRows.length > 5 ? `<div style="font-size:0.8rem; color:#94a3b8; margin-top:0.5rem;">... and ${csvRows.length - 5} more row(s)</div>` : ''}
            </div>
            <div class="csv-import-footer">
                <span id="csv-import-summary" style="font-size:0.85rem; color:#64748b;"></span>
                <div style="display:flex; gap:0.5rem;">
                    <button class="btn-inv-outline" onclick="_closeImportModal()">Cancel</button>
                    <button class="csv-import-btn" id="csvConfirmBtn" onclick="_confirmImport()">
                        <i class="bi bi-upload me-1"></i>Import ${csvRows.length} Row(s)
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // Set auto-matched values and statuses
    fields.forEach((f, i) => {
        const sel = document.getElementById(`csv-map-${i}`);
        const matchIdx = csvHeaders.findIndex(h =>
            h.toLowerCase().replace(/[\s_-]/g, '') === f.toLowerCase().replace(/[\s_-]/g, '')
        );
        sel.value = matchIdx;
        _updateMapStatus(i, matchIdx);
        sel.onchange = () => _updateMapStatus(i, parseInt(sel.value));
    });

    _updateImportSummary(fields);

    // Click outside to close
    overlay.onclick = (e) => { if (e.target === overlay) _closeImportModal(); };

    // Animate open
    requestAnimationFrame(() => overlay.classList.add('open'));
}

function _esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function _updateMapStatus(idx, csvIdx) {
    const el = document.getElementById(`csv-status-${idx}`);
    if (csvIdx >= 0) {
        el.innerHTML = '<span class="csv-badge-match"><i class="bi bi-check-circle me-1"></i>Matched</span>';
    } else {
        el.innerHTML = '<span class="csv-badge-skip"><i class="bi bi-dash-circle me-1"></i>Skipped</span>';
    }
}

function _updateImportSummary(fields) {
    const mapped = fields.filter((_, i) => {
        const sel = document.getElementById(`csv-map-${i}`);
        return sel && parseInt(sel.value) >= 0;
    }).length;
    const el = document.getElementById('csv-import-summary');
    if (el) el.textContent = `${mapped} of ${fields.length} fields mapped`;
}

function _closeImportModal() {
    const overlay = document.getElementById('csvImportOverlay');
    if (overlay) { overlay.classList.remove('open'); setTimeout(() => overlay.remove(), 200); }
    _importState = {};
}

async function _confirmImport() {
    const { apiUrl, onSuccess, csvHeaders, csvRows } = _importState;
    const btn = document.getElementById('csvConfirmBtn');
    btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Importing...';

    // Build mapping: field -> csvIdx
    const selects = document.querySelectorAll('.csv-map-select');
    const mapping = {};
    selects.forEach(sel => {
        const idx = parseInt(sel.value);
        if (idx >= 0) mapping[sel.dataset.field] = idx;
    });

    // Build rows as objects using the mapping
    const rows = csvRows.map(row => {
        const obj = {};
        for (const [field, idx] of Object.entries(mapping)) {
            obj[field] = row[idx] || '';
        }
        return obj;
    });

    try {
        const res = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
            body: JSON.stringify({ rows }),
        });
        const data = await res.json();
        if (!res.ok) {
            btn.disabled = false; btn.innerHTML = '<i class="bi bi-upload me-1"></i>Retry';
            alert(data.error || 'Import failed.');
            return;
        }
        _closeImportModal();
        alert(`Successfully imported ${data.imported} record(s).${data.skipped ? ` ${data.skipped} skipped (duplicates).` : ''}`);
        if (onSuccess) onSuccess(data);
    } catch (e) {
        console.error('Import error', e);
        btn.disabled = false; btn.innerHTML = '<i class="bi bi-upload me-1"></i>Retry';
        alert('Import failed: ' + e.message);
    }
}
