(() => {
  const { api, esc, num, rs, chart, palette } = SEA;
  const root = document.getElementById('report-root');
  let data = null;

  async function load() {
    SEA.loading(root, 'Building report...');
    try { data = (await api.get('/api/energy-report')).data; render(); }
    catch (e) { root.innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`; }
  }

  function render() {
    const csv = document.getElementById('btn-csv');
    if (data.empty) {
      csv.classList.add('disabled');
      root.innerHTML = `<div class="card"><div class="empty-state"><i class="bi bi-bar-chart-line"></i>
        <h5 class="mt-2">No data to report yet</h5><p class="text-muted">${esc(data.message)}</p>
        <a class="btn btn-success" href="/appliances">Add appliances</a></div></div>`;
      return;
    }
    csv.classList.remove('disabled');
    const t = data.totals, s = data.scheduler, c = s.comparison, rt = data.recommendation_totals;
    const rows = data.rows.map((r) => `<tr><td>${esc(r.name)}</td><td>${esc(r.category)}</td>
      <td class="text-end">${num(r.power_w, 0)}</td><td class="text-end">${r.quantity}</td>
      <td class="text-end">${num(r.daily_kwh, 3)}</td><td class="text-end">${num(r.monthly_kwh)}</td>
      <td class="text-end">${rs(r.energy_charge)}</td>
      <td style="min-width:110px"><div class="share-bar"><span style="width:${Math.min(100, r.share_percent)}%"></span></div><small>${num(r.share_percent, 1)}%</small></td>
      <td>${esc(r.original_start || '-')}</td><td>${esc(r.optimized_start || '-')}</td></tr>`).join('');
    const recs = data.recommendations.length ? data.recommendations.map((r) => `<tr><td>${r.rank}</td>
      <td>${esc(r.appliance)}</td><td>${esc(r.kind)}</td><td>${esc(r.action)}</td>
      <td class="text-end">${num(r.monthly_kwh_saved)}</td><td class="text-end text-saving">${rs(r.monthly_rs_saved)}</td></tr>`).join('')
      : '<tr><td colspan="6" class="text-muted text-center">No recommendations for the current data.</td></tr>';
    const runs = data.algorithm_runs.length ? data.algorithm_runs.map((r) => `<tr><td>${esc(r.algorithm)}</td>
      <td>${r.found ? '<span class="badge badge-soft-green">solution</span>' : '<span class="badge badge-soft-red">no solution</span>'}</td>
      <td class="text-end">${r.run_count}</td><td>${esc(r.created_at || '')}</td>
      <td class="small">${esc(Object.entries(r.summary || {}).map(([k, v]) => k + ': ' + v).join('; '))}</td></tr>`).join('')
      : '<tr><td colspan="5" class="text-muted text-center">No algorithm has been run yet. Open the Algorithm Lab.</td></tr>';

    root.innerHTML = `
      <div class="row g-3 mb-3">
        <div class="col-6 col-lg-3"><div class="card stat-card info"><div class="label">Daily</div><div class="value">${num(t.daily_kwh)} kWh</div></div></div>
        <div class="col-6 col-lg-3"><div class="card stat-card info"><div class="label">Monthly</div><div class="value">${num(t.monthly_kwh)} kWh</div></div></div>
        <div class="col-6 col-lg-3"><div class="card stat-card warn"><div class="label">Energy charge</div><div class="value">${rs(t.energy_charge)}</div><div class="sub">not a full bill</div></div></div>
        <div class="col-6 col-lg-3"><div class="card stat-card good"><div class="label">Est. saving</div><div class="value text-saving">${num(rt.monthly_kwh_saved)} kWh</div><div class="sub">${rs(rt.monthly_rs_saved)} / month</div></div></div>
      </div>
      <div class="row g-3 mb-3">
        <div class="col-lg-6"><div class="card h-100"><div class="card-header">Daily consumption (kWh)</div><div class="card-body"><div class="chart-box"><canvas id="rc-daily"></canvas></div></div></div></div>
        <div class="col-lg-6"><div class="card h-100"><div class="card-header">Monthly consumption (kWh) &amp; energy charge (₹)</div><div class="card-body"><div class="chart-box"><canvas id="rc-monthly"></canvas></div></div></div></div>
      </div>
      <div class="card mb-3"><div class="card-header">Appliance-wise consumption</div><div class="table-wrap"><table class="table mb-0">
        <thead><tr><th>Appliance</th><th>Category</th><th class="text-end">W</th><th class="text-end">Qty</th><th class="text-end">kWh/day</th><th class="text-end">kWh/month</th><th class="text-end">Energy charge</th><th>Share</th><th>Original start</th><th>Optimized start</th></tr></thead>
        <tbody>${rows}</tbody>
        <tfoot><tr class="fw-bold"><td colspan="4">Total</td><td class="text-end">${num(t.daily_kwh, 3)}</td><td class="text-end">${num(t.monthly_kwh)}</td><td class="text-end">${rs(t.energy_charge)}</td><td colspan="3">Est. bill incl. fixed charge &amp; tax: ${rs(t.estimated_bill)}</td></tr></tfoot>
      </table></div></div>
      <div class="card mb-3"><div class="card-header">Current vs optimized schedule <span class="badge badge-soft-blue ms-2">${esc(s.method)}</span></div><div class="card-body">
        ${c ? `<div class="row g-3 mb-3 text-center">
          <div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Original energy cost</div><strong>${rs(c.original_cost)}</strong></div></div>
          <div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Optimized energy cost</div><strong>${rs(c.optimized_cost)}</strong></div></div>
          <div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Saving / month</div><strong class="text-saving">${rs(c.cost_saving)}</strong></div></div></div>` : ''}
        <p class="small text-muted">${esc(s.explanation || '')}</p>
        ${s.hourly_optimized ? '<div class="chart-box"><canvas id="rc-hourly"></canvas></div>' : '<div class="alert alert-warning mb-0">No feasible optimized schedule was found, so only the original load is available.</div>'}
      </div></div>
      <div class="card mb-3"><div class="card-header">Recommendation ranking</div><div class="table-wrap"><table class="table mb-0">
        <thead><tr><th>#</th><th>Appliance</th><th>Type</th><th>Action</th><th class="text-end">kWh/month</th><th class="text-end">₹/month</th></tr></thead><tbody>${recs}</tbody></table></div></div>
      <div class="card mb-3"><div class="card-header">Algorithm execution summary (latest run of each)</div><div class="table-wrap"><table class="table mb-0">
        <thead><tr><th>Algorithm</th><th>Result</th><th class="text-end">Runs</th><th>Last run</th><th>Summary</th></tr></thead><tbody>${runs}</tbody></table></div></div>
      <div class="alert alert-light border small"><ul class="mb-0">${data.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>`;

    const names = data.rows.map((r) => r.name);
    chart('rc-daily', { type: 'bar', data: { labels: names, datasets: [{ label: 'kWh/day', data: data.rows.map((r) => r.daily_kwh), backgroundColor: palette[0] }] }, options: { plugins: { legend: { display: false } } } });
    chart('rc-monthly', { type: 'bar', data: { labels: names, datasets: [
      { label: 'kWh/month', data: data.rows.map((r) => r.monthly_kwh), backgroundColor: palette[1], yAxisID: 'y' },
      { label: '₹ energy charge', data: data.rows.map((r) => r.energy_charge), backgroundColor: palette[2], yAxisID: 'y1' }] },
      options: { scales: { y: { position: 'left' }, y1: { position: 'right', grid: { drawOnChartArea: false } } } } });
    if (s.hourly_optimized) {
      chart('rc-hourly', { type: 'line', data: { labels: s.hourly_labels, datasets: [
        { label: 'Original', data: s.hourly_original, borderColor: palette[5], backgroundColor: palette[5], tension: .25 },
        { label: 'Optimized', data: s.hourly_optimized, borderColor: palette[0], backgroundColor: palette[0], tension: .25 }] },
        options: { scales: { y: { title: { display: true, text: 'kWh per hour' } } } } });
    }
  }

  document.getElementById('btn-refresh').addEventListener('click', load);
  document.addEventListener('sea:data-changed', load);
  document.addEventListener('sea:redraw', () => data && render());
  load();
})();
