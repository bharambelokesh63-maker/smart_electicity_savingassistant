(() => {
  const { api, esc, num, rs, toast, errorToast, busy } = SEA;
  const KIND = {
    reschedule: ['Reschedule', 'bi-clock-history', 'badge-soft-blue'],
    standby: ['Standby', 'bi-power', 'badge-soft-amber'],
    reduce_hours: ['Reduce hours', 'bi-hourglass-split', 'badge-soft-green'],
  };

  function card(r) {
    const k = KIND[r.kind] || [r.kind, 'bi-lightbulb', 'badge-soft-green'];
    return `<div class="card rec-card"><div class="d-flex gap-3 align-items-start">
      <span class="rank">${r.rank}</span>
      <div class="flex-grow-1">
        <div class="d-flex flex-wrap gap-2 align-items-center mb-2">
          <h5 class="mb-0">${esc(r.appliance)}</h5>
          <span class="badge ${k[2]}"><i class="bi ${k[1]}"></i> ${k[0]}</span>
          <span class="saving-pill ms-auto">${rs(r.monthly_rs_saved)} / month</span>
        </div>
        <div class="row g-3">
          <div class="col-md-6"><div class="rec-field">Detected issue</div>${esc(r.issue)}</div>
          <div class="col-md-6"><div class="rec-field">Suggested action</div><strong>${esc(r.action)}</strong></div>
          <div class="col-12"><div class="rec-field">Reason</div>${esc(r.reason)}</div>
        </div>
        <div class="row g-2 mt-2 text-center">
          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Daily energy</div><strong>${num(r.daily_kwh_saved, 3)} kWh</strong></div></div>
          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Monthly energy</div><strong>${num(r.monthly_kwh_saved)} kWh</strong></div></div>
          <div class="col-4"><div class="border rounded p-2"><div class="small text-muted">Monthly money</div><strong class="text-saving">${rs(r.monthly_rs_saved)}</strong></div></div>
        </div>
        <details class="mt-2"><summary class="small text-muted">Estimate assumptions &amp; ranking</summary>
          <div class="small mt-1">${esc(r.assumptions)}<br>Feasibility ${num(r.feasibility * 100, 0)}% &middot; ranking score ${num(r.score)} (saving &times; feasibility).</div></details>
      </div></div></div>`;
  }

  function render(d) {
    const t = d.totals;
    document.getElementById('rec-summary').innerHTML = `
      <div class="col-sm-4"><div class="card stat-card good"><div class="label">Recommendations</div><div class="value">${t.count}</div><div class="sub">${d.flagged_for_review.length} appliance(s) flagged as high consumers</div></div></div>
      <div class="col-sm-4"><div class="card stat-card good"><div class="label">Estimated energy saved</div><div class="value text-saving">${num(t.monthly_kwh_saved)} kWh</div><div class="sub">per month</div></div></div>
      <div class="col-sm-4"><div class="card stat-card good"><div class="label">Estimated money saved</div><div class="value text-saving">${rs(t.monthly_rs_saved)}</div><div class="sub">per month (best option per appliance)</div></div></div>`;
    const list = document.getElementById('rec-list');
    list.innerHTML = d.recommendations.length ? d.recommendations.map(card).join('') : `<div class="card"><div class="empty-state">
      <i class="bi bi-check2-circle"></i><h5 class="mt-2">No savings opportunities found</h5>
      <p class="text-muted mb-0">Recommendations appear when appliances are flexible (with a cheaper time slot under your ToU tariff), have standby watts,
      or are high consumers running above their minimum hours. Edit appliance details to unlock more.</p></div></div>`;
    const notes = document.getElementById('rec-notes');
    notes.classList.remove('d-none');
    notes.firstElementChild.innerHTML = '<ul class="mb-0">' + d.notes.map((n) => `<li>${esc(n)}</li>`).join('') + '</ul>';
  }

  async function generate(silent) {
    const btn = document.getElementById('btn-generate');
    const body = {};
    ['high_share_pct', 'high_monthly_kwh', 'standby_avoidable_pct', 'reduce_fraction'].forEach((k) => {
      const v = document.getElementById('p-' + k).value;
      if (v !== '') body[k] = Number(v);
    });
    busy(btn, true, 'Analysing...');
    try {
      render((await api.post('/api/recommendations', body)).data);
      if (!silent) toast('Recommendations updated from your current appliance data.');
    } catch (e) {
      document.getElementById('rec-summary').innerHTML = '';
      document.getElementById('rec-list').innerHTML = `<div class="alert alert-warning">${esc(e.message)}</div>`;
    } finally { busy(btn, false); }
  }

  document.getElementById('btn-generate').addEventListener('click', () => generate(false));
  document.addEventListener('sea:data-changed', () => generate(true));
  generate(true);
})();
