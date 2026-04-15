/**
 * Reusable signature capture widget.
 *
 * Usage:
 *   const sig = new SignaturePad('#myCanvas');       // attach to any <canvas>
 *   sig.clear();                                      // wipe
 *   sig.isEmpty();                                    // true if blank
 *   sig.toDataURL();                                  // base64 PNG
 *   sig.loadImage(dataUrl);                           // draw an existing sig
 *
 * Modal helper (optional):
 *   SignatureModal.open({
 *       title: 'Sign here',
 *       headerColor: '#0d6efd',
 *       existingSignature: 'data:image/png;base64,...',
 *       onSave: function(dataUrl) { ... }
 *   });
 */

// ── SignaturePad ────────────────────────────────────────────────────────────

class SignaturePad {
    constructor(canvasOrSelector) {
        this.canvas = typeof canvasOrSelector === 'string'
            ? document.querySelector(canvasOrSelector)
            : canvasOrSelector;
        this.ctx = this.canvas.getContext('2d');
        this._drawing = false;
        this._hasStrokes = false;
        this._initBackground();
        this._bindEvents();
    }

    _initBackground() {
        this.ctx.fillStyle = '#fff';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.strokeStyle = '#000';
        this.ctx.lineWidth = 2.5;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
    }

    _getPos(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        if (e.touches && e.touches.length) {
            return {
                x: (e.touches[0].clientX - rect.left) * scaleX,
                y: (e.touches[0].clientY - rect.top) * scaleY,
            };
        }
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY,
        };
    }

    _onStart(e) {
        e.preventDefault();
        this._drawing = true;
        const p = this._getPos(e);
        this.ctx.beginPath();
        this.ctx.moveTo(p.x, p.y);
    }

    _onMove(e) {
        if (!this._drawing) return;
        e.preventDefault();
        const p = this._getPos(e);
        this.ctx.lineTo(p.x, p.y);
        this.ctx.stroke();
        this._hasStrokes = true;
    }

    _onEnd() {
        this._drawing = false;
    }

    _bindEvents() {
        // Mouse
        this.canvas.addEventListener('mousedown', e => this._onStart(e));
        this.canvas.addEventListener('mousemove', e => this._onMove(e));
        this.canvas.addEventListener('mouseup', () => this._onEnd());
        this.canvas.addEventListener('mouseout', () => this._onEnd());
        // Touch
        this.canvas.addEventListener('touchstart', e => this._onStart(e), { passive: false });
        this.canvas.addEventListener('touchmove', e => this._onMove(e), { passive: false });
        this.canvas.addEventListener('touchend', () => this._onEnd());
    }

    clear() {
        this._hasStrokes = false;
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this._initBackground();
    }

    isEmpty() {
        return !this._hasStrokes;
    }

    toDataURL() {
        return this.canvas.toDataURL('image/png');
    }

    loadImage(dataUrl) {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                this.clear();
                this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
                this._hasStrokes = true;
                resolve();
            };
            img.src = dataUrl;
        });
    }
}


// ── SignatureModal ──────────────────────────────────────────────────────────

const SignatureModal = (() => {
    let _modal = null;
    let _pad = null;
    let _onSave = null;

    function _ensureDOM() {
        if (document.getElementById('sharedSignatureModal')) return;
        const html = `
        <div class="modal fade" id="sharedSignatureModal" tabindex="-1">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
              <div class="modal-header" id="sigModalHeader" style="background:#0d6efd;">
                <h5 class="modal-title text-white" id="sigModalTitle">Signature</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body text-center">
                <canvas id="sharedSigCanvas" width="600" height="200"
                        style="border:1px solid #dee2e6;border-radius:6px;width:100%;cursor:crosshair;touch-action:none;"></canvas>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-outline-secondary" onclick="SignatureModal.clear()">Clear</button>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="sigModalSaveBtn" onclick="SignatureModal.save()">Save</button>
              </div>
            </div>
          </div>
        </div>`;
        document.body.insertAdjacentHTML('beforeend', html);
    }

    return {
        /**
         * Open the signature modal.
         * @param {Object} opts
         * @param {string}   [opts.title='Signature']
         * @param {string}   [opts.headerColor='#0d6efd']
         * @param {string}   [opts.saveLabel='Save']
         * @param {string}   [opts.existingSignature]  base64 data URL to pre-fill
         * @param {Function} opts.onSave               called with (dataUrl) on save
         */
        open(opts) {
            _ensureDOM();
            const title = opts.title || 'Signature';
            const color = opts.headerColor || '#0d6efd';

            document.getElementById('sigModalTitle').textContent = title;
            document.getElementById('sigModalHeader').style.background = color;
            document.getElementById('sigModalSaveBtn').textContent = opts.saveLabel || 'Save';
            _onSave = opts.onSave || null;

            const canvas = document.getElementById('sharedSigCanvas');
            _pad = new SignaturePad(canvas);

            if (opts.existingSignature) {
                _pad.loadImage(opts.existingSignature);
            }

            _modal = new bootstrap.Modal(document.getElementById('sharedSignatureModal'));
            _modal.show();
        },

        clear() {
            if (_pad) _pad.clear();
        },

        save() {
            if (!_pad || _pad.isEmpty()) {
                alert('Please draw your signature first.');
                return;
            }
            const dataUrl = _pad.toDataURL();
            if (_modal) _modal.hide();
            if (_onSave) _onSave(dataUrl);
        },

        getPad() { return _pad; },
    };
})();
