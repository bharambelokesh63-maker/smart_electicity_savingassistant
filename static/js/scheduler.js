(() => {
  const { api, esc, num, rs, hour, toast, errorToast, busy, chart, timeline } = SEA;
  const $ = (id) => document.getElementById(id);
  const blocked = new Set(), preferred = new Set();
  let last = null, tariff = null;

  function makeChips(containerId, set, cls) {
    const box = $(containerId);
    box.innerHTML = '';
    for (let h = 0; h < 24; h++) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip'; b.textContent = String(h).padStart(2, '0');
      b.title = hour(h);
      if (set.has(h)) b.classList.add(cls);
      b.onclick = () => { set.has(h) ? set.delete(h) : set.add(h); b.classList.toggle(cls); };
      box.appendChild(b);
    }
  }

  async function init() {
    try {
      tariff = (await api.get('/api/tariff')).data;
      const cfg = (await api.get('/api/schedule-config')).data || {};
      (cfg.unavailable_hours || []).forEach((h) => blocked.add(h));
      (cfg.preferred_hours || []).forEach((h) => preferred.add(h));
      if (cfg.capacity_kw) $('s-capacity').value = cfg.capacity_kw;
      if (cfg.shift_penalty !== undefined) $('s-shift').value = cfg.shift_penalty;
    } catch (e) { errorToast(e); }
    makeChips('chips-block', blocked, 'sel-block');
    makeChips('chips-pref', preferred, 'sel-pref');
    $('tl-legend').innerHTML = SEA.timelineLegend;
  }

  function summary(r) {
    const box = $('sched-summary');
    if (!r.found) {
      box.innerHTML = `<div class="fail-box"><strong><i class="bi bi-x-octagon"></i> No feasible schedule found.</strong><p class="mb-1 mt-2">${esc(r.explanation)}</p>
        ${r.diagnosis && r.diagnosis.length ? '<ul class="mb-0">' + r.diagnosis.map((d) => `<li>${esc(d)}</li>`).join('') + '</ul>' : ''}</div>
        <p class="small text-muted mt-2 mb-0">Relax the constraints (fewer unavailable hours, higher capacity, wider appliance windows) and run again. Nothing has been saved.</p>`;
      return;
    }
    const c = r.comparison;
    box.innerHTML = `
      ${r.fallback ? `<div class="alert alert-warning py-2 small">${esc(r.fallback)}</div>` : ''}
      ${r.original_violations.length ? `<div class="alert alert-warning py-2 small"><strong>Your original schedule breaks ${r.original_violations.length} constraint(s):</strong><ul class="mb-0">${r.original_violations.map((v) => `<li>${esc(v.message)}</li>`).join('')}</ul></div>` : ''}
      <div class="row g-2 text-center">
        <div class="col-6 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Energy consumption</div><strong>${num(c.optimized_kwh)} kWh/mo</strong><div class="small text-muted">${c.kwh_change === 0 ? 'unchanged (only timing moves)' : (c.kwh_change > 0 ? '+' : '') + num(c.kwh_change) + ' kWh'}</div></div></div>
        <div class="col-6 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Energy cost (ToU)</div><strong>${rs(c.optimized_cost)}</strong><div class="small text-muted">was ${rs(c.original_cost)}</div></div></div>
        <div class="col-12 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Estimated saving</div><strong class="${c.cost_saving > 0 ? 'text-saving' : ''}">${rs(c.cost_saving)} / month</strong><div class="small text-muted">${num(c.cost_saving_percent, 1)}%</div></div></div>
        <div class="col-6 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Peak load</div><strong>${num(c.optimized_peak_kw)} kW</strong><div class="small text-muted">was ${num(c.original_peak_kw)} kW</div></div></div>
        <div class="col-6 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Comfort penalty</div><strong>${rs(c.optimized_penalty)}</strong><div class="small text-muted">objective ${rs(c.optimized_objective)}</div></div></div>
        <div class="col-12 col-md-4"><div class="border rounded p-2"><div class="small text-muted">Algorithm</div><strong>${esc(r.method)}</strong><div class="small text-muted">${num(r.algorithm_result.runtime_ms, 2)} ms</div></div></div>
      </div>
      <p class="small text-muted mt-2 mb-0">Energy cost uses your time-of-use hourly rates (an editable assumption). Savings are estimates for a typical month.</p>`;
  }

  function changes(r) {
    const box = $('sched-changes');
    if (!r.found) { box.innerHTML = '<p class="text-muted mb-0">No changes - see the explanation at the top.</p>'; return; }
    box.innerHTML = (r.moved.length ? `<ul class="list-group list-group-flush mb-3">${r.moved.map((m) => `<li class="list-group-item bg-transparent px-0"><strong>${esc(m.appliance)}</strong>: ${m.from} <i class="bi bi-arrow-right"></i> <span class="text-saving fw-semibold">${m.to}</span></li>`).join('')}</ul>`
      : `<p class="text-muted">${r.has_flexible ? 'No flexible appliance could be moved to a cheaper valid slot, so the original timing already is the best result under these constraints.' : 'No appliance is marked flexible. Edit an appliance and enable "Flexible" to let the scheduler move it.'}</p>`)
      + `<div class="explain small">${esc(r.explanation)}</div>`;
  }

  function loadChart(r) {
    const labels = Array.from({ length: 24 }, (_, h) => hour(h));
    const ds = [{ label: 'Original', data: r.original.hourly_load_kwh, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.15)', fill: true, stepped: true }];
    if (r.optimized) ds.push({ label: 'Optimized', data: r.optimized.hourly_load_kwh, borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,.15)', fill: true, stepped: true });
    const cap = r.problem.capacity_kw;
    if (cap) ds.push({ label: 'Capacity limit', data: Array(24).fill(cap), borderColor: '#dc2626', borderDash: [6, 4], pointRadius: 0, fill: false });
    chart('ch-sched-load', { type: 'line', data: { labels, datasets: ds }, options: { scales: { y: { beginAtZero: true, title: { display: true, text: 'kW (kWh per hour)' } } }, plugins: { tooltip: { mode: 'index', intersect: false } } } });
  }

  function draw() {
    if (!last) return;
    const r = last, un = [...blocked];
    $('sched-results').classList.remove('d-none');
    timeline($('tl-orig'), r.original.entries, tariff, un);
    $('orig-cost').textContent = `${rs(r.original.energy_cost)} / month`;
    if (r.optimized) { timeline($('tl-opt'), r.optimized.entries, tariff, un); $('opt-cost').textContent = `${rs(r.optimized.energy_cost)} / month`; }
    else { $('tl-opt').innerHTML = '<p class="text-muted">No feasible optimized schedule.</p>'; $('opt-cost').textContent = 'n/a'; }
    loadChart(r);
  }

  $('btn-run').addEventListener('click', async () => {
    $('s-capacity').classList.remove('is-invalid');
    const body = { method: $('s-method').value, unavailable_hours: [...blocked], preferred_hours: [...preferred] };
    if ($('s-capacity').value !== '') {
      const cap = Number($('s-capacity').value);
      if (!(cap > 0)) { $('s-capacity').classList.add('is-invalid'); $('s-capacity').parentElement.querySelector('.invalid-feedback').textContent = 'Capacity must be greater than 0 (or leave blank for no limit).'; return; }
      body.capacity_kw = cap;
    }
    if ($('s-shift').value !== '') body.shift_penalty = Number($('s-shift').value);
    const btn = $('btn-run');
    busy(btn, true, 'Optimizing...');
    try {
      tariff = (await api.get('/api/tariff')).data;
      last = (await api.post('/api/optimize-schedule', body)).data;
      summary(last); changes(last); draw();
      if (last.found) toast('Optimized schedule saved.'); else toast('No feasible schedule with these constraints.', 'warning');
    } catch (e) { errorToast(e); } finally { busy(btn, false); }
  });

  document.addEventListener('sea:redraw', draw);
  init();
})();
