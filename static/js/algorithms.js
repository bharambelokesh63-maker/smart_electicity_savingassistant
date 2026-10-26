(() => {
  const { api, esc, num, rs, toast, errorToast, busy, chart, timeline } = SEA;
  const $ = (id) => document.getElementById(id);
  let tariff = null;
  const lastResults = {};

  // ---------- helpers ----------
  const pills = (obj) => '<div class="kv mb-3">' + Object.entries(obj).map(([k, v]) =>
    `<span class="pill"><span class="text-muted">${esc(k.replace(/_/g, ' '))}:</span> <strong>${esc(typeof v === 'number' ? num(v, Number.isInteger(v) ? 0 : 3) : v)}</strong></span>`).join('') + '</div>';

  function statusBox(r) {
    if (r.found) return `<div class="mb-2"><span class="badge badge-soft-green fs-6"><i class="bi bi-check-circle"></i> Solution found</span>
      <span class="text-muted small ms-2">${num(r.runtime_ms, 2)} ms</span></div>`;
    return `<div class="fail-box mb-3"><strong><i class="bi bi-x-octagon"></i> No solution found.</strong><div class="mt-1">${esc(r.explanation)}</div></div>`;
  }

  function compare(r, un) {
    if (!r.original) return '';
    return `<div class="row g-3 mb-3">
      <div class="col-xl-6"><div class="fw-semibold mb-1">Original schedule <span class="badge text-bg-secondary">${rs(r.original.energy_cost)}/mo</span></div><div data-tl="orig"></div></div>
      <div class="col-xl-6"><div class="fw-semibold mb-1">Algorithm result ${r.schedule ? `<span class="badge badge-soft-green">${rs(r.schedule.energy_cost)}/mo</span>` : ''}</div>
        <div data-tl="new">${r.schedule ? '' : '<p class="text-muted small">No schedule produced.</p>'}</div></div></div>
      ${SEA.timelineLegend}`;
  }
  function paintTimelines(out, r, un) {
    const o = out.querySelector('[data-tl="orig"]'), n = out.querySelector('[data-tl="new"]');
    if (o) timeline(o, r.original.entries, tariff, un);
    if (n && r.schedule) timeline(n, r.schedule.entries, tariff, un);
  }
  const moves = (r) => r.found ? (r.moved.length
    ? '<div class="mt-3"><div class="fw-semibold mb-1">Schedule changes</div><ul class="mb-0">' + r.moved.map((m) => `<li><strong>${esc(m.appliance)}</strong>: ${m.from} &rarr; ${m.to}</li>`).join('') + '</ul></div>'
    : '<p class="text-muted small mt-3 mb-0">No appliance moved - the original timing already satisfies the constraints at the lowest modelled cost (or no appliance is flexible).</p>') : '';
  const explain = (r) => r.found ? `<div class="explain small mt-3"><strong>Why this result:</strong> ${esc(r.explanation)}</div>` : (r.diagnosis && r.diagnosis.length ? `<ul class="small mt-2">${r.diagnosis.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>` : '');
  const logTable = (cols, rows) => `<div class="fw-semibold mt-3 mb-1">Search log <span class="text-muted small fw-normal">(${rows.length} row(s) shown)</span></div>
    <div class="log-box"><table class="table table-sm table-striped"><thead><tr>${cols.map((c) => `<th>${c[0]}</th>`).join('')}</tr></thead><tbody>
    ${rows.map((x) => '<tr>' + cols.map((c) => `<td>${esc(c[1](x))}</td>`).join('') + '</tr>').join('')}</tbody></table></div>`;

  // ---------- renderers ----------
  function renderSearch(key, r, un) {
    const out = $('out-' + key);
    let html = statusBox(r) + (r.found ? pills({ objective: r.objective, ...r.stats, optimal_guaranteed: r.optimal ? 'yes' : 'no' }) : pills(r.stats || {}));
    html += `<div class="mb-3"><canvas id="ch-${key}" height="110"></canvas></div>`;
    html += compare(r, un) + moves(r) + explain(r);
    if (r.found && r.path && r.path.length) {
      html += `<div class="fw-semibold mt-3 mb-1">Solution path <span class="text-muted small fw-normal">(selected states, g accumulates)</span></div>
        <div class="table-wrap"><table class="table table-sm"><thead><tr><th>Depth</th><th>Appliance placed</th><th>Start</th><th>Step cost</th><th>g(n)</th></tr></thead><tbody>
        ${r.path.map((p) => `<tr><td>${p.depth}</td><td>${esc(p.appliance)}</td><td>${p.start_label}</td><td>${rs(p.step_cost)}</td><td>${rs(p.g)}</td></tr>`).join('')}</tbody></table></div>`;
    }
    html += logTable([['Step', (x) => x.step], ['Depth', (x) => x.depth], ['Explored state', (x) => x.state], ['Last action', (x) => x.last],
      ['g', (x) => x.g], ['h', (x) => x.h], ['f = g + h', (x) => x.f], ['Goal?', (x) => (x.goal ? 'GOAL' : '')]], r.log);
    out.innerHTML = html;
    paintTimelines(out, r, un);
    if (r.log.length) {
      chart('ch-' + key, { type: 'line', data: { labels: r.log.map((x) => x.step), datasets: [
        { label: 'g(n) cost so far', data: r.log.map((x) => x.g), borderColor: '#2563eb', tension: .2 },
        { label: 'h(n) estimate', data: r.log.map((x) => x.h), borderColor: '#f59e0b', tension: .2 },
        { label: 'f(n) = g + h', data: r.log.map((x) => x.f), borderColor: '#16a34a', borderWidth: 3, tension: .2 }] },
        options: { plugins: { title: { display: true, text: 'Scores of explored states (in expansion order)' } }, scales: { x: { title: { display: true, text: 'expansion step' } }, y: { title: { display: true, text: 'Rs / month' } } } } });
    }
  }

  function renderHill(r, un) {
    const out = $('out-hill-climbing');
    let html = statusBox(r);
    if (r.found) html += pills({ initial_objective: r.initial_objective, final_objective: r.final_objective, iterations: r.stats.iterations, neighbours_evaluated: r.stats.neighbors_evaluated, local_optimum: r.local_optimum ? 'yes' : 'no (iteration limit)' });
    html += `<div class="mb-3"><canvas id="ch-hc" height="110"></canvas></div>` + compare(r, un) + moves(r) + explain(r);
    if (r.found) html += `<div class="small text-muted mt-2">Started from ${esc(r.initial_source)}.</div>`;
    html += r.log.length ? logTable([['Iteration', (x) => x.iteration], ['Move chosen', (x) => x.move], ['Neighbours evaluated', (x) => x.neighbors_evaluated], ['Change', (x) => x.delta], ['Objective (Rs/mo)', (x) => x.objective]], r.log) : '';
    out.innerHTML = html;
    paintTimelines(out, r, un);
    if (r.log.length) chart('ch-hc', { type: 'line', data: { labels: r.log.map((x) => x.iteration), datasets: [{ label: 'Objective (energy cost + penalty)', data: r.log.map((x) => x.objective), borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,.15)', fill: true, stepped: true }] },
      options: { plugins: { title: { display: true, text: 'Objective value per iteration' } }, scales: { x: { title: { display: true, text: 'iteration' } }, y: { title: { display: true, text: 'Rs / month' } } } } });
  }

  function renderCsp(r, un) {
    const out = $('out-csp');
    let html = statusBox(r) + pills(r.stats || {});
    html += `<div class="small mb-3"><div class="fw-semibold">Constraints</div><ul class="mb-1">${(r.constraints || []).map((c) => `<li>${esc(c)}</li>`).join('')}</ul>
      <div class="fw-semibold">Domains (permitted start hours)</div><ul class="mb-0">${Object.entries(r.domains || {}).map(([k, v]) => `<li>${esc(k)}: ${v.length ? v.map((h) => String(h).padStart(2, '0')).join(', ') : '<em>empty</em>'}</li>`).join('')}</ul>
      <div class="mt-1 text-muted">Variable selection: ${esc(r.variable_selection || '')}; value order: ${esc(r.value_order || '')}</div></div>`;
    html += `<div class="mb-3"><canvas id="ch-csp" height="90"></canvas></div>` + compare(r, un);
    if (r.found) {
      html += `<div class="fw-semibold mt-2 mb-1">Assignments</div><ul>${r.schedule.entries.filter((e) => e.flexible).map((e) => `<li>${esc(e.name)} = <strong>${e.start_label}</strong> (until ${e.end_label})</li>`).join('') || '<li class="text-muted">No flexible appliances to assign.</li>'}</ul>
        <div class="small">Hard-constraint violations in the final schedule: <strong>${r.violations_found}</strong></div>`;
    }
    html += moves(r) + explain(r);
    html += r.log.length ? logTable([['Event', (x) => x.event], ['Variable', (x) => x.variable], ['Value / legal values', (x) => (x.value || (x.legal_values || []).join(' ') || '(none)')], ['Capacity rejections', (x) => (x.rejected_for_capacity ?? '')], ['Depth', (x) => x.depth]], r.log) : '';
    out.innerHTML = html;
    paintTimelines(out, r, un);
    const s = r.stats || {};
    chart('ch-csp', { type: 'bar', data: { labels: ['Nodes visited', 'Backtracks', 'Values pruned (window/availability)', 'Capacity violations avoided'], datasets: [{ data: [s.nodes_visited, s.backtracks, s.values_pruned_by_unary_constraints, s.capacity_violations_avoided], backgroundColor: ['#2563eb', '#ef4444', '#f59e0b', '#16a34a'], borderRadius: 6 }] },
      options: { indexAxis: 'y', plugins: { legend: { display: false }, title: { display: true, text: 'Search effort and constraints enforced' } } } });
  }

  function renderFc(r) {
    const out = $('out-forward-chaining');
    let html = statusBox({ ...r, found: true }) + pills(r.stats) + `<div class="explain small mb-3">${esc(r.explanation)}</div>`;
    html += `<details class="mb-3"><summary class="fw-semibold">Initial facts (${r.facts.length})</summary><div class="log-box mt-2"><ul class="small mb-0 py-2">${r.facts.map((f) => `<li><code>${esc(f)}</code></li>`).join('')}</ul></div></details>`;
    html += `<div class="fw-semibold mb-1">Rules</div><div class="table-wrap mb-3"><table class="table table-sm"><thead><tr><th>Rule</th><th>IF</th><th>THEN</th></tr></thead><tbody>
      ${r.rules.map((x) => `<tr><td><strong>${esc(x.name)}</strong></td><td>${esc(x.if)}</td><td><code>${esc(x.then)}</code></td></tr>`).join('')}</tbody></table></div>`;
    html += logTable([['#', (x) => x.step], ['Pass', (x) => x.pass], ['Rule fired', (x) => x.rule], ['Because (facts matched)', (x) => x.matched.join('; ')], ['Derived fact', (x) => x.derived.join('; ')]], r.inference_steps);
    html += `<div class="fw-semibold mt-3 mb-1">Final recommendations</div>` + (r.recommendations.length ? `<div class="table-wrap"><table class="table table-sm"><thead><tr><th>#</th><th>Appliance</th><th>Type</th><th>Action</th><th>kWh/mo</th><th>Rs/mo</th></tr></thead><tbody>
      ${r.recommendations.map((x) => `<tr><td>${x.rank}</td><td>${esc(x.appliance)}</td><td>${esc(x.kind)}</td><td>${esc(x.action)}</td><td>${num(x.monthly_kwh_saved)}</td><td class="text-saving">${rs(x.monthly_rs_saved)}</td></tr>`).join('')}</tbody></table></div>`
      : '<p class="text-muted">No rule produced a recommendation for the current data.</p>');
    if (r.flagged_for_review.length) html += `<p class="small mt-2">Flagged for review (high consumption): ${r.flagged_for_review.map(esc).join(', ')}</p>`;
    out.innerHTML = html;
  }

  function renderBn(r) {
    const out = $('out-bayesian-network');
    const ev = r.evidence, node = (n, cls = '') => `<div class="bn-node ${cls} ${ev[n] ? 'observed' : ''}">${n}${ev[n] ? `<div class="small fw-bold">= ${esc(ev[n])}</div>` : '<div class="small text-muted">unobserved</div>'}</div>`;
    let html = `<div class="bn-graph mb-3"><div class="bn-parents">${node('UsageIntensity')}${node('HighPowerCount')}${node('StandbyLevel')}</div>
      <div class="fs-3 text-muted">&rarr;</div><div class="bn-node target"><strong>ConsumptionCategory</strong><div class="small">query variable</div></div></div>`;
    html += pills({ most_probable_category: r.most_probable, probability: (r.posterior[r.most_probable] * 100).toFixed(1) + '%', 'P(evidence)': r.probability_of_evidence, 'posterior sums to': r.posterior_sum });
    html += `<div class="row g-3 mb-3"><div class="col-lg-6"><canvas id="ch-bn" height="170"></canvas></div><div class="col-lg-6">
      <div class="fw-semibold mb-1">Evidence used</div><ul class="small">${r.evidence_notes.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
      <table class="table table-sm"><thead><tr><th>Category</th><th>Prior</th><th>Posterior</th></tr></thead><tbody>
      ${Object.keys(r.posterior).map((k) => `<tr class="${k === r.most_probable ? 'fw-bold' : ''}"><td>${k}</td><td>${num(r.prior[k] * 100, 1)}%</td><td>${num(r.posterior[k] * 100, 1)}%</td></tr>`).join('')}</tbody></table></div></div>`;
    html += `<div class="explain small">${esc(r.explanation)}</div>`;
    html += `<div class="alert alert-warning small mt-3 mb-2"><i class="bi bi-exclamation-triangle"></i> Educational estimate based on the selected model and assumed probabilities. It is not a measurement of your consumption and not a guaranteed forecast.</div>`;
    if (r.comparison_note) html += `<p class="small text-muted">${esc(r.comparison_note)}</p>`;
    html += `<details><summary class="fw-semibold">Conditional probability table P(Category | parents) &mdash; ${r.cpt.length} rows, each sums to 1</summary>
      <div class="log-box mt-2"><table class="table table-sm table-striped"><thead><tr><th>Usage</th><th>High-power</th><th>Standby</th><th>Low</th><th>Moderate</th><th>High</th><th>Sum</th></tr></thead><tbody>
      ${r.cpt.map((x) => `<tr><td>${x.UsageIntensity}</td><td>${x.HighPowerCount}</td><td>${x.StandbyLevel}</td><td>${x.Low}</td><td>${x.Moderate}</td><td>${x.High}</td><td>${x.row_sum}</td></tr>`).join('')}</tbody></table></div></details>
      <details class="mt-2"><summary class="fw-semibold">Prior probabilities of the parent nodes</summary><ul class="small mt-2">${Object.entries(r.priors).map(([k, v]) => `<li>${k}: ${Object.entries(v).map(([s, p]) => `${s} ${p}`).join(', ')}</li>`).join('')}</ul></details>`;
    out.innerHTML = html;
    const cats = Object.keys(r.posterior);
    chart('ch-bn', { type: 'bar', data: { labels: cats, datasets: [
      { label: 'Prior (no evidence)', data: cats.map((k) => r.prior[k] * 100), backgroundColor: '#94a3b8', borderRadius: 6 },
      { label: 'Posterior (given evidence)', data: cats.map((k) => r.posterior[k] * 100), backgroundColor: '#16a34a', borderRadius: 6 }] },
      options: { plugins: { title: { display: true, text: 'P(ConsumptionCategory) %' } }, scales: { y: { beginAtZero: true, max: 100 } } } });
  }

  // ---------- running ----------
  function constraints() {
    const body = {};
    const cap = $('lab-capacity').value;
    if (cap !== '') {
      if (!(Number(cap) > 0)) throw new Error('Capacity must be greater than 0 (or leave it blank for no limit).');
      body.capacity_kw = Number(cap);
    }
    const hrs = $('lab-blocked').value.split(',').map((s) => s.trim()).filter(Boolean);
    body.unavailable_hours = hrs.map((s) => {
      const n = Number(s);
      if (!Number.isInteger(n) || n < 0 || n > 23) throw new Error(`Unavailable hours must be whole numbers 0-23 (got "${s}").`);
      return n;
    });
    if ($('lab-shift').value !== '') body.shift_penalty = Number($('lab-shift').value);
    return body;
  }
  const numVal = (id) => ($(id).value === '' ? undefined : Number($(id).value));

  async function run(algo, btn) {
    let body;
    try {
      if (['best-first', 'a-star', 'hill-climbing', 'csp'].includes(algo)) {
        body = constraints();
        if (algo === 'best-first') body.max_expansions = numVal('bf-max');
        if (algo === 'a-star') body.max_expansions = numVal('as-max');
        if (algo === 'hill-climbing') body.max_iterations = numVal('hc-max');
        if (algo === 'csp') body.value_order = $('csp-order').value;
      } else if (algo === 'forward-chaining') {
        body = { high_share_pct: numVal('fc-share'), high_monthly_kwh: numVal('fc-kwh'), standby_avoidable_pct: numVal('fc-standby'), reduce_fraction: numVal('fc-reduce') };
        Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);
      } else {
        body = {};
        document.querySelectorAll('.bn-sel').forEach((s) => { body[s.dataset.var] = s.value; });
      }
    } catch (e) { toast(e.message, 'danger'); return; }
    busy(btn, true, 'Running...');
    try {
      tariff = (await api.get('/api/tariff')).data;
      const r = (await api.post('/api/algorithms/' + algo, body)).data;
      lastResults[algo] = { r, un: body.unavailable_hours || [] };
      draw(algo);
    } catch (e) {
      $('out-' + algo).innerHTML = `<div class="fail-box">${esc(e.message)}</div>`;
      errorToast(e);
    } finally { busy(btn, false); }
  }

  function draw(algo) {
    const entry = lastResults[algo];
    if (!entry) return;
    const { r, un } = entry;
    if (algo === 'best-first' || algo === 'a-star') renderSearch(algo, r, un);
    else if (algo === 'hill-climbing') renderHill(r, un);
    else if (algo === 'csp') renderCsp(r, un);
    else if (algo === 'forward-chaining') renderFc(r);
    else renderBn(r);
  }

  document.querySelectorAll('.run-btn').forEach((b) => b.addEventListener('click', () => run(b.dataset.algo, b)));
  document.addEventListener('sea:redraw', () => Object.keys(lastResults).forEach(draw));

  // Bayesian evidence selectors
  const BN_STATES = { UsageIntensity: ['Light', 'Normal', 'Heavy'], HighPowerCount: ['None', 'Few', 'Many'], StandbyLevel: ['Low', 'High'] };
  document.querySelectorAll('.bn-sel').forEach((sel) => {
    sel.add(new Option('Auto (from my appliances)', 'auto'));
    sel.add(new Option('Unobserved', 'none'));
    BN_STATES[sel.dataset.var].forEach((s) => sel.add(new Option(s, s)));
  });
})();
