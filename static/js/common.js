/* Shared helpers: API client, toasts, formatting, charts, timeline renderer, demo-data menu. */
const SEA = (() => {
  // ---------- API ----------
  async function request(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let res, json;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw new Error('Cannot reach the server. Is the Flask app still running?');
    }
    try { json = await res.json(); } catch (e) { json = null; }
    if (!res.ok || !json || json.success === false) {
      const err = new Error((json && json.error) || `Request failed (${res.status}).`);
      err.details = json && json.details;
      err.status = res.status;
      throw err;
    }
    return json;
  }
  const api = {
    get: (u) => request('GET', u),
    post: (u, b) => request('POST', u, b === undefined ? {} : b),
    put: (u, b) => request('PUT', u, b),
    del: (u) => request('DELETE', u),
  };

  // ---------- formatting ----------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (n, d = 2) => (n === null || n === undefined || isNaN(n)) ? '-' : Number(n).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
  const rs = (n, d = 2) => (n === null || n === undefined || isNaN(n)) ? '-' : '₹' + num(n, d);
  const hour = (h) => String(h % 24).padStart(2, '0') + ':00';

  // ---------- UI ----------
  function toast(message, type = 'success') {
    const colors = { success: 'text-bg-success', danger: 'text-bg-danger', warning: 'text-bg-warning', info: 'text-bg-primary' };
    const el = document.createElement('div');
    el.className = `toast align-items-center border-0 ${colors[type] || colors.info}`;
    el.setAttribute('role', 'alert');
    el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(message)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
    document.getElementById('toasts').appendChild(el);
    const t = new bootstrap.Toast(el, { delay: type === 'danger' ? 7000 : 3500 });
    el.addEventListener('hidden.bs.toast', () => el.remove());
    t.show();
  }
  const errorToast = (e) => toast(e.message || 'Something went wrong.', 'danger');

  function confirmDialog(message, { title = 'Please confirm', okText = 'Confirm', okClass = 'btn-danger' } = {}) {
    return new Promise((resolve) => {
      const modalEl = document.getElementById('confirm-modal');
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      document.getElementById('confirm-title').textContent = title;
      document.getElementById('confirm-body').textContent = message;
      const ok = document.getElementById('confirm-ok');
      ok.textContent = okText;
      ok.className = 'btn ' + okClass;
      let answered = false;
      const done = (v) => { if (!answered) { answered = true; resolve(v); } };
      ok.onclick = () => { done(true); modal.hide(); };
      modalEl.addEventListener('hidden.bs.modal', () => done(false), { once: true });
      modal.show();
    });
  }

  function busy(btn, on, label) {
    if (!btn) return;
    if (on) {
      btn.dataset.html = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner-border spinner-inline me-1"></span>${esc(label || 'Working...')}`;
    } else {
      btn.disabled = false;
      if (btn.dataset.html) btn.innerHTML = btn.dataset.html;
    }
  }
  const loading = (el, text = 'Loading...') => { el.innerHTML = `<div class="loading-overlay"><span class="spinner-border spinner-border-sm me-2"></span>${esc(text)}</div>`; };

  // ---------- charts ----------
  const charts = {};
  const palette = ['#16a34a', '#2563eb', '#f59e0b', '#0ea5e9', '#a855f7', '#ef4444', '#14b8a6', '#84cc16', '#f97316', '#64748b'];
  function chartText() { return getComputedStyle(document.documentElement).getPropertyValue('--muted').trim() || '#64748b'; }
  function chart(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    if (charts[id]) charts[id].destroy();
    Chart.defaults.color = chartText();
    Chart.defaults.borderColor = 'rgba(148,163,184,.25)';
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false }, config.options || {});
    charts[id] = new Chart(canvas, config);
    return charts[id];
  }

  // ---------- timeline ----------
  function hourClass(h, tariff) {
    if (!tariff || !tariff.tou_enabled) return '';
    const inR = (s, e) => (s < e ? h >= s && h < e : (s !== e && (h >= s || h < e)));
    if (inR(tariff.peak_start, tariff.peak_end)) return 'peak';
    if (inR(tariff.offpeak_start, tariff.offpeak_end)) return 'offpeak';
    return '';
  }
  function timeline(el, entries, tariff, unavailable = []) {
    const blocked = new Set(unavailable);
    let html = '<div class="table-wrap"><div class="tl"><div class="tl-row tl-head"><div class="tl-label"></div><div class="tl-cells">';
    for (let h = 0; h < 24; h++) html += `<div class="tl-cell ${hourClass(h, tariff)}">${h}</div>`;
    html += '</div></div>';
    entries.forEach((e) => {
      const on = new Set(e.slots);
      html += `<div class="tl-row"><div class="tl-label" title="${esc(e.name)} ${e.start_label}-${e.end_label}">${esc(e.name)}</div><div class="tl-cells">`;
      for (let h = 0; h < 24; h++) {
        const cls = ['tl-cell'];
        if (on.has(h)) cls.push(e.flexible ? 'on-flex' : 'on-fixed');
        if (e.flexible && blocked.has(h)) cls.push('blocked');
        html += `<div class="${cls.join(' ')}"></div>`;
      }
      html += '</div></div>';
    });
    html += '</div></div>';
    el.innerHTML = html;
  }
  const timelineLegend = `<div class="small text-muted mt-2">
    <span class="legend-dot" style="background:var(--green)"></span>flexible
    <span class="legend-dot ms-2" style="background:var(--navy-2)"></span>fixed
    <span class="legend-dot ms-2" style="background:#fde68a"></span>peak tariff
    <span class="legend-dot ms-2" style="background:#bbf7d0"></span>off-peak tariff
    <span class="legend-dot ms-2" style="background:#fecaca"></span>unavailable</div>`;

  // ---------- theme + demo menu ----------
  function initShell() {
    const toggle = document.getElementById('theme-toggle');
    if (toggle) toggle.addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-bs-theme', cur);
      try { localStorage.setItem('sea-theme', cur); } catch (e) { /* storage may be blocked */ }
      document.dispatchEvent(new CustomEvent('sea:theme'));
    });
    const load = document.getElementById('btn-load-demo');
    if (load) load.addEventListener('click', async () => {
      try {
        await api.post('/api/sample-data/load');
        toast('Demonstration data loaded (clearly marked as demo).');
        document.dispatchEvent(new CustomEvent('sea:data-changed'));
      } catch (e) { e.status === 409 ? toast(e.message, 'warning') : errorToast(e); }
    });
    const reset = document.getElementById('btn-reset-demo');
    if (reset) reset.addEventListener('click', async () => {
      if (!await confirmDialog('This permanently deletes all appliances that were loaded as demonstration data. Your own appliances are kept.', { title: 'Reset demonstration data', okText: 'Delete demo data' })) return;
      try {
        const r = await api.post('/api/sample-data/reset', { confirm: true });
        toast(`Removed ${r.data.removed} demonstration appliance(s).`);
        document.dispatchEvent(new CustomEvent('sea:data-changed'));
      } catch (e) { errorToast(e); }
    });
    document.addEventListener('sea:theme', () => document.dispatchEvent(new CustomEvent('sea:redraw')));
  }
  document.addEventListener('DOMContentLoaded', initShell);

  return { api, esc, num, rs, hour, toast, errorToast, confirmDialog, busy, loading, chart, palette, timeline, timelineLegend, hourClass };
})();
