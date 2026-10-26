(() => {
  const { api, esc, num, rs, toast, errorToast, busy } = SEA;
  const $ = (id) => document.getElementById(id);
  const T_FIELDS = ['base_rate', 'fixed_charge', 'tax_percent', 'peak_start', 'peak_end', 'peak_multiplier', 'offpeak_start', 'offpeak_end', 'offpeak_multiplier'];

  function fillTariff(t) {
    T_FIELDS.forEach((f) => { $('t-' + f).value = t[f]; });
    $('t-tou_enabled').checked = !!t.tou_enabled;
    $('tou-fields').style.opacity = t.tou_enabled ? 1 : .45;
  }
  $('t-tou_enabled').addEventListener('change', (e) => { $('tou-fields').style.opacity = e.target.checked ? 1 : .45; });

  $('tariff-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    document.querySelectorAll('#tariff-form .is-invalid').forEach((x) => x.classList.remove('is-invalid'));
    const body = { tou_enabled: $('t-tou_enabled').checked };
    T_FIELDS.forEach((f) => { body[f] = $('t-' + f).value === '' ? null : Number($('t-' + f).value); });
    if (!(body.base_rate > 0)) { $('t-base_rate').classList.add('is-invalid'); $('t-base_rate').parentElement.querySelector('.invalid-feedback').textContent = 'Enter a tariff greater than 0.'; return; }
    const btn = $('btn-save-tariff');
    busy(btn, true, 'Saving...');
    try {
      const r = await api.put('/api/tariff', body);
      fillTariff(r.data);
      toast('Tariff saved. All calculations now use it.');
      await loadCalc();
    } catch (err) {
      if (err.details) Object.entries(err.details).forEach(([k, m]) => {
        const el = $('t-' + k);
        if (el) { el.classList.add('is-invalid'); const fb = el.parentElement.querySelector('.invalid-feedback'); if (fb) fb.textContent = m; }
      });
      errorToast(err);
    } finally { busy(btn, false); }
  });

  $('whatif-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {};
    ['power_w', 'quantity', 'hours_per_day', 'days_per_month', 'standby_w', 'base_rate'].forEach((k) => { body[k] = $('w-' + k).value === '' ? null : Number($('w-' + k).value); });
    try {
      const d = (await api.post('/api/calculate', body)).data;
      $('whatif-out').innerHTML = `<div class="row g-2 text-center">
        <div class="col-4"><div class="p-2 border rounded"><div class="small text-muted">Daily</div><strong>${num(d.daily_kwh)} kWh</strong></div></div>
        <div class="col-4"><div class="p-2 border rounded"><div class="small text-muted">Monthly</div><strong>${num(d.monthly_kwh)} kWh</strong></div></div>
        <div class="col-4"><div class="p-2 border rounded"><div class="small text-muted">Energy charge</div><strong>${rs(d.energy_charge)}</strong></div></div></div>
        ${d.standby_daily_kwh > 0 ? `<div class="small text-muted mt-2">Includes ${num(d.standby_daily_kwh, 3)} kWh/day standby (active: ${num(d.active_daily_kwh)} kWh/day).</div>` : ''}`;
    } catch (err) { $('whatif-out').innerHTML = `<div class="alert alert-danger mb-0">${esc(err.message)}</div>`; }
  });

  async function loadCalc() {
    try {
      const r = await api.get('/api/calculator');
      const rows = r.data.rows, tot = r.data.totals;
      $('calc-body').innerHTML = rows.length ? rows.map((x) => `<tr>
        <td><strong>${esc(x.name)}</strong></td><td>${num(x.power_w, 0)} W &times; ${x.quantity}</td><td>${num(x.hours_per_day, 1)}</td><td>${x.days_per_month}</td>
        <td>${num(x.daily_kwh, 3)}</td><td>${num(x.standby_daily_kwh, 3)}</td><td>${num(x.monthly_kwh)}</td><td>${rs(x.energy_charge)}</td>
        <td style="min-width:90px"><div class="share-bar ${x.share_percent > 25 ? 'hot' : ''}"><span style="width:${Math.min(100, x.share_percent)}%"></span></div><span class="small text-muted">${num(x.share_percent, 1)}%</span></td></tr>`).join('')
        : '<tr><td colspan="9" class="text-center text-muted py-4">No appliances yet. Add appliances or load the demonstration data.</td></tr>';
      $('calc-foot').innerHTML = rows.length ? `<tr class="fw-bold"><td>Total</td><td></td><td></td><td></td><td>${num(tot.daily_kwh, 3)}</td><td></td><td>${num(tot.monthly_kwh)}</td><td>${rs(tot.energy_charge)}</td><td></td></tr>` : '';
      $('bill-box').innerHTML = rows.length ? `<table class="table table-sm mb-2"><tbody>
        <tr><td>Energy charge <span class="text-muted small">(${num(tot.monthly_kwh)} kWh &times; ${rs(tot.tariff_rate)})</span></td><td class="text-end">${rs(tot.energy_charge)}</td></tr>
        <tr><td>Fixed charge <span class="text-muted small">(your entry)</span></td><td class="text-end">${rs(tot.fixed_charge)}</td></tr>
        <tr><td>Tax / duty <span class="text-muted small">(${num(r.tariff.tax_percent, 1)}% of the above)</span></td><td class="text-end">${rs(tot.tax)}</td></tr>
        <tr class="fw-bold"><td>Estimated bill</td><td class="text-end">${rs(tot.estimated_bill)}</td></tr></tbody></table>
        <div class="small text-muted">An estimate only; slabs, surcharges and rounding are not modelled.</div>` : '<p class="text-muted mb-0">Add appliances to see an estimate.</p>';
      fillTariff(r.tariff);
    } catch (e) { errorToast(e); }
    loadSnaps();
  }

  async function loadSnaps() {
    try {
      const recs = (await api.get('/api/usage-records')).data;
      $('snap-body').innerHTML = recs.length ? recs.map((s) => `<tr><td>${esc(s.recorded_at)}</td><td>${s.appliance_count}</td><td>${num(s.monthly_kwh)}</td><td>${rs(s.tariff_rate)}</td><td>${rs(s.energy_charge)}</td><td>${rs(s.estimated_bill)}</td></tr>`).join('')
        : '<tr><td colspan="6" class="text-center text-muted py-3">No snapshots saved yet.</td></tr>';
    } catch (e) { errorToast(e); }
  }

  $('btn-snapshot').addEventListener('click', async () => {
    try { await api.post('/api/usage-records'); toast('Snapshot saved.'); loadSnaps(); } catch (e) { errorToast(e); }
  });
  document.addEventListener('sea:data-changed', loadCalc);
  loadCalc();
})();
