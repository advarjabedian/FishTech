/**
 * FishTech shared utilities — loaded globally via base.html.
 *
 *   getCookie(name)        — read a cookie (needed for Django CSRF)
 *   esc(s)                 — HTML-escape a string for safe innerHTML use
 *   escapeHtml(s)          — alias for esc()
 *   escHtml(s)             — alias for esc()
 *   fmt(n)                 — format a number with up to 2 decimal places
 *   debounce(fn, ms)       — debounce a function call
 *   formatDate(dateStr)    — format ISO date to "14 Apr 2026"
 */

function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : '';
}

function esc(s) {
    const d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
}

// Aliases used in various templates
const escapeHtml = esc;
const escHtml = esc;

function fmt(n) {
    return n ? Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '0';
}

function debounce(fn, ms) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms || 300);
    };
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });
}
