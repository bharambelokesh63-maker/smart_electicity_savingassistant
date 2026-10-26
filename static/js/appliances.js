(() => {
  const { api, esc, num, hour, toast, errorToast, confirmDialog, busy } = SEA;
  const FIELDS = ['name', 'category', 'power_w', 'quantity', 'hours_per_day', 'days_per_month', 'preferred_start',
    'priority', 'min_hours', 'max_hours', 'standby_w', 'window_start', 'window_end'];
  let items = [], templates = [], editingId = null;
  const form = document.getElementById('appl-form');
  const modal = new bootstrap.Modal(document.getElementById('appl-modal'));
  const $ = (id) => document.getElementById('f-' + id);
  const PRIORITY = { 1: ['High', 'badge-soft-red'], 2: ['Medium', 'badge-soft-amber'], 3: ['Low', 'badge-soft-green'] };

  function hourOptions(sel, from, to) {
    sel.innerHTML = '';
    for (let h = from; h <= to; h++) sel.add(new Option(h === 24 ? '24:00 (end of day)' : hour(h), h));
  }

  async function init() {
    hourOptions($('preferred_start'), 0, 23);
    hourOptions($('window_start'), 0, 23);
    hourOptions($('window_end'), 1, 24);
    $('window_end').value = 24;
    try {
      const t = await api.get('/api/appliance-templates');
      templates = t.data;
      t.categories.forEach((c) => $('category').add(new Option(c, c)));
      templates.forEach((tpl, i) => $('template').add(new Option(tpl.template, i)));
    } catch (e) { errorToast(e); }
    await load();
  }

  async function load() {
    try {
      items = (await api.get('/api/appliances')).data;
      render();
    } catch (e) {
      document.getElementById('appl-body').innerHTML = `<tr><td colspan="10" class="text-danger">${esc(e.message)}</td></tr>`;
    }
  }

  function render() {
    const body = document.getElementById('appl-body');
    document.getElementById('count-label').textContent = `${items.length} appliance(s) registered`;
    if (!items.length) {
      body.innerHTML = `<tr><td colspan="10"><div class="empty-state"><i class="bi bi-plug"></i>
        <h5 class="mt-2">No appliances yet</h5><p class="text-muted mb-0">Click "Add appliance" or load the demonstration data from the Demo data menu.</p></div></td></tr>`;
      return;
    }
    body.innerHTML = items.map((a) => `<tr>
      <td><strong>${esc(a.name)}</strong>${a.is_demo ? ' <span class="badge badge-soft-blue">demo</span>' : ''}<div class="small text-muted">${esc(a.category)}${a.standby_w > 0 ? ` &middot; standby ${num(a.standby_w, 1)} W` : ''}</div></td>
      <td>${num(a.power_w, 0)} W</td><td>${a.quantity}</td><td>${num(a.hours_per_day, 2).replace(/\.?0+$/, '')}</td><td>${a.days_per_month}</td>
      <td>${hour(a.preferred_start)}</td>
      <td>${a.flexible ? `<span class="badge badge-soft-green">Yes ${hour(a.window_start)}-${hour(a.window_end)}</span>` : '<span class="badge text-bg-light border">Fixed</span>'}</td>
      <td><span class="badge ${PRIORITY[a.priority][1]}">${PRIORITY[a.priority][0]}</span></td>
      <td>${num(a.monthly_kwh)}</td>
      <td class="text-nowrap"><button class="btn btn-sm btn-outline-secondary" data-edit="${a.id}" aria-label="Edit"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger" data-del="${a.id}" aria-label="Delete"><i class="bi bi-trash"></i></button></td></tr>`).join('');
  }

  function clearErrors() {
    form.querySelectorAll('.is-invalid').forEach((e) => e.classList.remove('is-invalid'));
    document.getElementById('form-error').classList.add('d-none');
  }
  function showErrors(errors) {
    let shown = false;
    Object.entries(errors).forEach(([k, msg]) => {
      const input = $(k);
      if (input) {
        input.classList.add('is-invalid');
        const fb = input.parentElement.querySelector('.invalid-feedback');
        if (fb) fb.textContent = msg;
        shown = true;
      }
    });
    if (!shown) {
      const box = document.getElementById('form-error');
      box.textContent = Object.values(errors)[0];
      box.classList.remove('d-none');
    }
  }

  function readForm() {
    const v = {};
    FIELDS.forEach((f) => { v[f] = $(f).value.trim(); });
    v.flexible = $('flexible').checked;
    return v;
  }

  function clientValidate(v) {
    const e = {};
    const n = (k) => (v[k] === '' ? NaN : Number(v[k]));
    if (!v.name) e.name = 'Name is required.';
    if (!(n('power_w') > 0 && n('power_w') <= 20000)) e.power_w = 'Enter a power between 0 and 20000 W.';
    if (!(Number.isInteger(n('quantity')) && n('quantity') >= 1 && n('quantity') <= 100)) e.quantity = 'Quantity must be a whole number from 1 to 100.';
    if (!(n('hours_per_day') > 0 && n('hours_per_day') <= 24)) e.hours_per_day = 'Hours per day must be greater than 0 and at most 24.';
    if (!(Number.isInteger(n('days_per_month')) && n('days_per_month') >= 1 && n('days_per_month') <= 31)) e.days_per_month = 'Days must be a whole number from 1 to 31.';
    if (v.min_hours !== '' && !(n('min_hours') >= 0)) e.min_hours = 'Minimum hours cannot be negative.';
    else if (!e.hours_per_day && n('min_hours') > n('hours_per_day')) e.min_hours = 'Minimum hours cannot exceed average hours per day.';
    if (v.max_hours !== '' && !e.hours_per_day && n('max_hours') < n('hours_per_day')) e.max_hours = 'Maximum hours cannot be less than average hours per day.';
    if (v.standby_w !== '' && !(n('standby_w') >= 0)) e.standby_w = 'Standby power cannot be negative.';
    if (Number(v.window_end) <= Number(v.window_start)) e.window_end = 'Window end must be later than window start.';
    else if (v.flexible && !e.hours_per_day && Number(v.window_end) - Number(v.window_start) < Math.ceil(n('hours_per_day')))
      e.window_end = `Window must be at least ${Math.ceil(n('hours_per_day'))} h long for this appliance.`;
    return e;
  }

  function fill(a) {
    FIELDS.forEach((f) => { $(f).value = a[f] === null || a[f] === undefined ? '' : a[f]; });
    $('flexible').checked = !!a.flexible;
    toggleWindow();
  }
  function toggleWindow() { document.getElementById('window-row').style.opacity = $('flexible').checked ? 1 : .45; }

  function openForm(a) {
    clearErrors();
    editingId = a ? a.id : null;
    document.getElementById('appl-modal-title').textContent = a ? 'Edit appliance' : 'Add appliance';
    $('template').value = '';
    $('template').disabled = !!a;
    fill(a || { name: '', category: 'Other', power_w: '', quantity: 1, hours_per_day: '', days_per_month: 30, preferred_start: 18,
      priority: 2, min_hours: 0, max_hours: '', standby_w: 0, window_start: 0, window_end: 24, flexible: false });
    modal.show();
  }

  $('template').addEventListener('change', (e) => { if (e.target.value !== '') fill(templates[Number(e.target.value)]); });
  $('flexible').addEventListener('change', toggleWindow);
  document.getElementById('btn-add').addEventListener('click', () => openForm(null));

  document.getElementById('appl-body').addEventListener('click', async (e) => {
    const edit = e.target.closest('[data-edit]'), del = e.target.closest('[data-del]');
    if (edit) openForm(items.find((a) => a.id === Number(edit.dataset.edit)));
    if (del) {
      const a = items.find((x) => x.id === Number(del.dataset.del));
      if (!await confirmDialog(`Delete "${a.name}"? This cannot be undone.`, { title: 'Delete appliance', okText: 'Delete' })) return;
      try { await api.del(`/api/appliances/${a.id}`); toast('Appliance deleted.'); load(); } catch (err) { errorToast(err); }
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();
    const v = readForm();
    const errors = clientValidate(v);
    if (Object.keys(errors).length) { showErrors(errors); return; }
    const payload = { ...v, max_hours: v.max_hours === '' ? null : Number(v.max_hours) };
    ['power_w', 'quantity', 'hours_per_day', 'days_per_month', 'preferred_start', 'priority', 'min_hours', 'standby_w', 'window_start', 'window_end']
      .forEach((k) => { payload[k] = Number(v[k] === '' ? 0 : v[k]); });
    const btn = document.getElementById('btn-save');
    busy(btn, true, 'Saving...');
    try {
      if (editingId) await api.put(`/api/appliances/${editingId}`, payload); else await api.post('/api/appliances', payload);
      modal.hide();
      toast(editingId ? 'Appliance updated.' : 'Appliance added.');
      load();
    } catch (err) {
      if (err.details) showErrors(err.details); else { showErrors({ _: err.message }); }
    } finally { busy(btn, false); }
  });

  document.addEventListener('sea:data-changed', load);
  init();
})();
