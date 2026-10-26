(() => {
  const { api, esc, num, rs, chart, palette } = SEA;
  const root = document.getElementById('dash-root');
  let data = null;

  async function load() {
    SEA.loading(root, 'Loading dashboard...');
    try {
      data = (await api.get('/api/dashboard')).data;
      render();
    } catch (e) {
      root.innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`;
    }
  }

  function stat(label, value, sub, icon, cls) {
    return `<div class="col-6 col-xl-4"><div class="card stat-card ${cls}"><i class="bi ${icon} icon"></i>
      <div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub || ''}</div></div></div>`;
  }

  function render() {
    if (data.empty) {
      root.innerHTML = `<div class="card"><div class="empty-state">
        <i class="bi bi-lightning-charge"></i>
        <h4 class="mt-3">Welcome! Let's start saving electricity.</h4>
        <p class="text-muted mb-4">You haven't added any appliances yet. Add the appliances in your home, or load the
        clearly-labelled demonstration data to explore every feature.</p>
        <a class="btn btn-success me-2" href="/appliances"><i class="bi bi-plus-circle"></i> Add appliances</a>
        <button class="btn btn-outline-success" id="empty-demo"><i class="bi bi-download"></i> Load demonstration data</button>
      </div></div>`;
      document.getElementById('empty-demo').onclick = async () => {
        try { await api.post('/api/sample-data/load'); SEA.toast('Demonstration data loaded.'); load(); } catch (e) { SEA.errorToast(e); }
      };
      return;
    }
    const t = data.totals, ps = data.potential_savings, top = data.top_appliance, cmp = data.comparison;
    const hasSavings = ps.count > 0;
    root.innerHTML = `
      <div class="row g-3 mb-3">
        ${stat('Daily consumption', `${num(t.daily_kwh)} kWh`, `${num(t.active_daily_kwh)} kWh active + standby`, 'bi-sun', 'info')}
        ${stat('Estimated monthly consumption', `${num(t.monthly_kwh)} kWh`, 'daily kWh x operating days', 'bi-calendar-month', 'info')}
        ${stat('Estimated monthly bill', rs(t.estimated_bill), `Energy ${rs(t.energy_charge)} at ${rs(t.tariff_rate)}/kWh` + (t.fixed_charge || t.tax ? ` + fixed &amp; tax` : '') + ' (estimate)', 'bi-currency-rupee', 'warn')}
        ${stat('Potential monthly savings', hasSavings ? `<span class="text-saving">${rs(ps.monthly_rs_saved)}</span>` : rs(0), hasSavings ? `${num(ps.monthly_kwh_saved)} kWh saved &middot; ${ps.count} recommendation(s)` : 'No savings opportunities found yet', 'bi-piggy-bank', 'good')}
        ${stat('Registered appliances', t.appliance_count, 'in your home profile', 'bi-plug', 'info')}
        ${stat('Highest consumer', esc(top.name), `${num(top.monthly_kwh)} kWh/month (${num(top.share_percent, 1)}%)`, 'bi-exclamation-triangle', 'warn')}
      </div>
      <div class="alert alert-light border small py-2"><i class="bi bi-info-circle"></i> ${esc(data.disclaimer)}</div>

      <div class="row g-3 mb-3">
        <div class="col-lg-6"><div class="card h-100"><div class="card-header"><i class="bi bi-bar-chart"></i> Daily consumption by appliance (kWh)</div>
          <div class="card-body"><div class="chart-box"><canvas id="ch-daily"></canvas></div></div></div></div>
        <div class="col-lg-6"><div class="card h-100"><div class="card-header"><i class="bi bi-calendar3"></i> Monthly consumption &amp; energy charge</div>
          <div class="card-body"><div class="chart-box"><canvas id="ch-monthly"></canvas></div></div></div></div>
      </div>
      <div class="row g-3 mb-3">
        <div class="col-lg-4"><div class="card h-100"><div class="card-header"><i class="bi bi-pie-chart"></i> Appliance-wise breakdown</div>
          <div class="card-body"><div class="chart-box"><canvas id="ch-share"></canvas></div></div></div></div>
        <div class="col-lg-8"><div class="card h-100"><div class="card-header"><i class="bi bi-graph-up"></i> Hourly load: current vs optimized schedule
          <span class="badge badge-soft-blue ms-auto">${esc(data.scheduler_method)}</span></div>
          <div class="card-body"><div class="chart-box"><canvas id="ch-hourly"></canvas></div></div></div></div>
      </div>
      <div class="row g-3">
        <div class="col-lg-5"><div class="card h-100"><div class="card-header"><i class="bi bi-arrow-left-right"></i> Current vs optimized usage</div>
          <div class="card-body">${cmp ? `<div class="chart-box" style="height:220px"><canvas id="ch-compare"></canvas></div>
            <p class="small mt-3 mb-0">Scheduling alone lowers the estimated energy cost by <strong class="text-saving">${rs(cmp.cost_saving)}</strong>
            per month (${num(cmp.cost_saving_percent, 1)}%) with no change in kWh. Time-of-use rates are an editable assumption (see Calculator).</p>`
            : '<p class="text-muted mb-0">No feasible optimized schedule with the current scheduler settings. Open the AI Scheduler page for details.</p>'}</div></div></div>
        <div class="col-lg-7"><div class="card h-100"><div class="card-header"><i class="bi bi-lightbulb"></i> Recent recommendations
          <a href="/recommendations" class="ms-auto small">View all</a></div>
          <div class="list-group list-group-flush" id="dash-recs"></div></div></div>
      </div>`;
    draw();
  }

  function draw() {
    if (!data || data.empty) return;
    const a = data.charts.appliances, labels = a.map((x) => x.name);
    chart('ch-daily', { type: 'bar', data: { labels, datasets: [{ label: 'kWh / day', data: a.map((x) => x.daily_kwh), backgroundColor: '#16a34a', borderRadius: 6 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } } });
    chart('ch-monthly', { data: { labels, datasets: [
      { type: 'bar', label: 'kWh / month', data: a.map((x) => x.monthly_kwh), backgroundColor: '#2563eb', borderRadius: 6, yAxisID: 'y' },
      { type: 'line', label: 'Energy charge (₹)', data: a.map((x) => x.energy_charge), borderColor: '#f59e0b', backgroundColor: '#f59e0b', yAxisID: 'y1', tension: .3 }] },
      options: { scales: { y: { beginAtZero: true, title: { display: true, text: 'kWh' } }, y1: { beginAtZero: true, position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: '₹' } } } } });
    chart('ch-share', { type: 'doughnut', data: { labels, datasets: [{ data: a.map((x) => x.monthly_kwh), backgroundColor: palette }] },
      options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } } });
    const h = data.charts.hourly_load;
    const ds = [{ label: 'Current schedule', data: h.original, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,.12)', fill: true, stepped: true }];
    if (h.optimized) ds.push({ label: 'Optimized schedule', data: h.optimized, borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,.12)', fill: true, stepped: true });
    chart('ch-hourly', { type: 'line', data: { labels: h.labels, datasets: ds }, options: { scales: { y: { beginAtZero: true, title: { display: true, text: 'kWh per hour (kW)' } } }, plugins: { tooltip: { mode: 'index', intersect: false } } } });
    if (data.comparison) {
      const c = data.comparison;
      chart('ch-compare', { type: 'bar', data: { labels: ['Current', 'Optimized'], datasets: [{ label: 'Monthly energy cost (₹, time-of-use)', data: [c.original_cost, c.optimized_cost], backgroundColor: ['#2563eb', '#16a34a'], borderRadius: 8 }] },
        options: { plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } } });
    }
    const recs = document.getElementById('dash-recs');
    recs.innerHTML = data.recent_recommendations.length ? data.recent_recommendations.map((r) => `
      <div class="list-group-item bg-transparent"><div class="d-flex gap-2 align-items-start">
        <span class="rank" style="width:1.6rem;height:1.6rem;border-radius:50%;background:var(--navy);color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:.75rem">${r.rank}</span>
        <div class="flex-grow-1"><strong>${esc(r.appliance)}</strong><div class="small text-muted">${esc(r.action)}</div></div>
        <span class="saving-pill">${rs(r.monthly_rs_saved)}/mo</span></div></div>`).join('')
      : '<div class="list-group-item bg-transparent text-muted">No recommendations yet. Mark appliances as flexible, add standby watts or minimum hours to unlock suggestions.</div>';
  }

  document.addEventListener('sea:data-changed', load);
  document.addEventListener('sea:redraw', draw);
  load();
})();
