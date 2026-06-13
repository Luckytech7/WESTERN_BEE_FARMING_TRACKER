/**
 * Western Bee Farming Tracker — Frontend
 * Vanilla JS, no frameworks. Chart.js for visualisation.
 * Role-based UI: write-only elements hidden for 'viewer' role.
 */

const API = '/api';
let charts = {};
let appState = {
  farms: [], role: 'viewer',
  selectedFarm: '', selectedYear: '',
};

// ── Utilities ─────────────────────────────────────────────────────────────────

async function apiFetch(url, opts = {}) {
  // Extract headers and body separately so Content-Type is never overwritten
  const { headers: extraHeaders = {}, body, method = 'GET', ...restOpts } = opts;

  const fetchOpts = {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...extraHeaders,
    },
    ...restOpts,
  };

  if (body !== undefined) {
    fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
  }

  const res = await fetch(url, fetchOpts);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || err.detail || JSON.stringify(err) || `HTTP ${res.status}`);
  }
  return res.json();
}

function toast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type === 'success' ? '✓' : '✗'}</span> ${msg}`;
  document.getElementById('toastContainer').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function badgeHtml(value, prefix = '') {
  const cls = prefix + value.toLowerCase().replace(/\s+/g, '-');
  return `<span class="badge badge-${cls}">${value}</span>`;
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB',
    { day: '2-digit', month: 'short', year: 'numeric' });
}

function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

function getCookie(name) {
  const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return v ? v[2] : '';
}

// ── Auth ──────────────────────────────────────────────────────────────────────

function fillDemo(email, password) {
  document.getElementById('loginEmail').value    = email;
  document.getElementById('loginPassword').value = password;
}

async function doLogin() {
  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errEl    = document.getElementById('loginError');
  const btn      = document.getElementById('loginBtn');

  errEl.style.display = 'none';
  btn.textContent = 'Signing in…';
  btn.disabled = true;

  try {
    const data = await apiFetch(`${API}/auth/login/`, {
      method: 'POST',
      body: JSON.stringify({ email, password }),
      // No X-CSRFToken needed — login endpoint is csrf_exempt
    });
    appState.role = data.role;
    applyRoleUI(data);
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appScreen').style.display   = 'block';
    await initApp();
  } catch (err) {
    errEl.textContent   = err.message;
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'Sign In';
    btn.disabled    = false;
  }
}

async function doLogout() {
  try {
    await apiFetch(`${API}/auth/logout/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
    });
  } catch (_) {}
  location.reload();
}

function applyRoleUI(userData) {
  if (userData.role === 'viewer') {
    document.body.classList.add('role-viewer');
  } else {
    document.body.classList.remove('role-viewer');
  }
  document.getElementById('userPill').innerHTML =
    `${userData.beekeeper_name} &nbsp;${badgeHtml(userData.role)}`;

  document.getElementById('sessionInfo').innerHTML = `
    <div>👤 <strong>${userData.beekeeper_name}</strong></div>
    <div>🔐 Role: ${badgeHtml(userData.role)}</div>
    <div style="margin-top:4px;font-size:.7rem;color:#aaa">
      ${userData.role === 'beekeeper' ? 'Your farms only' : 'All data'}
    </div>`;
}

// ── App init ──────────────────────────────────────────────────────────────────

async function initApp() {
  await Promise.all([
    loadFarms(),
    loadDashboardStats(),
    loadSeasonalChart(),
    loadHarvestTable(),
    loadHoneytypeChart(),
  ]);
}

// ── Dashboard stats ───────────────────────────────────────────────────────────

async function loadDashboardStats() {
  const data = await apiFetch(`${API}/dashboard/`);
  document.getElementById('statBeekeepers').textContent = data.total_beekeepers;
  document.getElementById('statFarms').textContent      = data.total_farms;
  document.getElementById('statHives').textContent      = data.total_active_hives;
  document.getElementById('statHarvests').textContent   = data.total_harvests;
  document.getElementById('statYield').textContent      = data.total_yield_kg.toLocaleString() + ' kg';
  document.getElementById('statBest').textContent       = data.best_single_harvest_kg + ' kg';
}

// ── Farms ─────────────────────────────────────────────────────────────────────

async function loadFarms() {
  const resp  = await apiFetch(`${API}/farms/`);
  appState.farms = resp.results || resp;

  ['filterFarm', 'formFarm', 'hiveFarm', 'hiveFarmModal'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const isFilter = id === 'filterFarm' || id === 'hiveFarm';
    el.innerHTML = `<option value="">${isFilter ? 'All Farms' : 'Select farm…'}</option>`;
    appState.farms.forEach(f => {
      el.innerHTML += `<option value="${f.id}">${f.name}</option>`;
    });
  });
}

async function loadHivesForFarm(farmId, targetSelectId) {
  const el = document.getElementById(targetSelectId);
  if (!el) return;
  if (!farmId) { el.innerHTML = '<option value="">Select farm first</option>'; return; }
  el.innerHTML = '<option value="">Loading…</option>';
  const resp  = await apiFetch(`${API}/hives/?farm_id=${farmId}&status=active`);
  const hives = resp.results || resp;
  el.innerHTML = '<option value="">Select hive…</option>';
  hives.forEach(h => {
    el.innerHTML += `<option value="${h.id}">Hive ${h.hive_number} (${h.hive_type})</option>`;
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const formFarm = document.getElementById('formFarm');
  if (formFarm) {
    formFarm.addEventListener('change', e => loadHivesForFarm(e.target.value, 'formHive'));
  }
});

// ── Seasonal yield chart ──────────────────────────────────────────────────────

async function loadSeasonalChart() {
  let url = `${API}/yields/`;
  const params = [];
  if (appState.selectedFarm) params.push(`farm_id=${appState.selectedFarm}`);
  if (appState.selectedYear) params.push(`year=${appState.selectedYear}`);
  if (params.length) url += '?' + params.join('&');

  const data = await apiFetch(url);

  // Populate year dropdown
  const yearSel = document.getElementById('filterYear');
  const cur = yearSel.value;
  yearSel.innerHTML = '<option value="">All Years</option>';
  data.available_years.forEach(y => yearSel.innerHTML += `<option value="${y}">${y}</option>`);
  if (cur) yearSel.value = cur;

  const order  = ['Spring', 'Summer', 'Fall', 'Winter'];
  const clrMap = { Spring: '#4CAF50', Summer: '#F5A623', Fall: '#FF7043', Winter: '#42A5F5' };
  const labels = [], totals = [], avgs = [], bgs = [];

  order.forEach(s => {
    const d = data.yields_by_season[s];
    if (d) { labels.push(s); totals.push(d.total_kg); avgs.push(d.avg_kg); bgs.push(clrMap[s]); }
  });

  let html = '';
  order.forEach(s => {
    const d = data.yields_by_season[s];
    if (d) html += `
      <div style="text-align:center">
        <div style="font-size:1.05rem;font-weight:800;color:${clrMap[s]}">${d.total_kg} kg</div>
        <div style="font-size:.7rem;color:#6B7280">${s} · ${d.harvests} harvests</div>
      </div>`;
  });
  document.getElementById('seasonSummary').innerHTML = html;

  if (charts.seasonal) charts.seasonal.destroy();
  charts.seasonal = new Chart(
    document.getElementById('seasonalChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Total Yield (kg)', data: totals,
            backgroundColor: bgs.map(c => c + 'CC'), borderColor: bgs,
            borderWidth: 2, borderRadius: 6, order: 2 },
          { label: 'Avg per Harvest (kg)', data: avgs, type: 'line',
            borderColor: '#9A5E10', backgroundColor: 'transparent',
            borderWidth: 2.5, pointBackgroundColor: '#9A5E10',
            pointRadius: 5, tension: 0.3, order: 1 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          tooltip: { callbacks: { label: c => ` ${c.dataset.label}: ${c.parsed.y} kg` } }
        },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: 'Yield (kg)' } },
          x: { grid: { display: false } }
        }
      }
    }
  );
}

// ── Honey type donut ──────────────────────────────────────────────────────────

async function loadHoneytypeChart() {
  let url = `${API}/harvests/?page_size=500`;
  if (appState.selectedFarm) url += `&farm_id=${appState.selectedFarm}`;
  if (appState.selectedYear) url += `&year=${appState.selectedYear}`;

  const resp    = await apiFetch(url);
  const results = resp.results || resp;
  const counts  = {};
  results.forEach(h => { counts[h.honey_type] = (counts[h.honey_type] || 0) + h.yield_kg; });
  const labels  = Object.keys(counts);
  const values  = labels.map(k => Math.round(counts[k] * 10) / 10);
  const palette = ['#F5A623','#4CAF50','#42A5F5','#AB47BC','#26C6DA','#EF5350'];

  if (charts.honeytype) charts.honeytype.destroy();
  charts.honeytype = new Chart(
    document.getElementById('honeytypeChart').getContext('2d'), {
      type: 'doughnut',
      data: { labels, datasets: [{ data: values, backgroundColor: palette, borderWidth: 2, borderColor: '#fff' }] },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '60%',
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 } } },
          tooltip: { callbacks: { label: c => ` ${c.label}: ${c.parsed} kg` } }
        }
      }
    }
  );
}

// ── Harvest table ─────────────────────────────────────────────────────────────

async function loadHarvestTable() {
  const tbody = document.getElementById('harvestTableBody');
  tbody.innerHTML = '<tr><td colspan="7"><div class="loading"><div class="spinner"></div> Loading…</div></td></tr>';

  let url = `${API}/harvests/?`;
  if (appState.selectedFarm) url += `farm_id=${appState.selectedFarm}&`;
  if (appState.selectedYear) url += `year=${appState.selectedYear}&`;

  const resp = await apiFetch(url);
  const rows = resp.results || resp;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">🍯</div><p>No harvests found.</p></div></td></tr>';
    return;
  }

  tbody.innerHTML = rows.slice(0, 50).map(h => `
    <tr>
      <td>${formatDate(h.harvest_date)}</td>
      <td><strong>${h.farm_name}</strong></td>
      <td>Hive ${h.hive_number}</td>
      <td><strong>${h.yield_kg} kg</strong></td>
      <td>${badgeHtml(h.honey_type)}</td>
      <td>${h.season_name ? badgeHtml(h.season_name) : '—'}</td>
      <td style="color:#9E9E9E;font-size:.78rem">${h.notes || '—'}</td>
    </tr>`).join('');

  document.getElementById('harvestCount').textContent = `${rows.length} records`;
}

// ── Hives table ───────────────────────────────────────────────────────────────

async function loadHivesTable() {
  const tbody  = document.getElementById('hivesTableBody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div> Loading…</div></td></tr>';
  const farmId = document.getElementById('hiveFarm').value;
  let url = `${API}/hives/?`;
  if (farmId) url += `farm_id=${farmId}&`;

  const resp = await apiFetch(url);
  const rows = resp.results || resp;

  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">🐝</div><p>No hives found.</p></div></td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(h => `
    <tr>
      <td><strong>${h.hive_number}</strong></td>
      <td>${h.farm_name}</td>
      <td>${h.hive_type.replace('_', '-')}</td>
      <td>${badgeHtml(h.status)}</td>
      <td>${h.queen_status}</td>
      <td>${formatDate(h.install_date)}</td>
    </tr>`).join('');
}

// ── Filters ───────────────────────────────────────────────────────────────────

function applyFilters() {
  appState.selectedFarm = document.getElementById('filterFarm').value;
  appState.selectedYear = document.getElementById('filterYear').value;
  loadSeasonalChart();
  loadHarvestTable();
  loadHoneytypeChart();
  loadDashboardStats();
}

function resetFilters() {
  document.getElementById('filterFarm').value = '';
  document.getElementById('filterYear').value = '';
  appState.selectedFarm = '';
  appState.selectedYear = '';
  applyFilters();
}

// ── Add Harvest ───────────────────────────────────────────────────────────────

function openAddHarvest() {
  document.getElementById('harvestForm').reset();
  document.getElementById('formHive').innerHTML = '<option value="">Select farm first</option>';
  document.getElementById('harvestError').textContent = '';
  const sel = document.getElementById('formFarm');
  sel.innerHTML = '<option value="">Select farm…</option>';
  appState.farms.forEach(f => sel.innerHTML += `<option value="${f.id}">${f.name}</option>`);
  openModal('harvestModal');
}

async function submitHarvest() {
  const errEl = document.getElementById('harvestError');
  errEl.textContent = '';

  const hiveId    = document.getElementById('formHive').value;
  const dateVal   = document.getElementById('formDate').value;
  const yieldKg   = parseFloat(document.getElementById('formYield').value);
  const honeyType = document.getElementById('formHoneyType').value;
  const notes     = document.getElementById('formNotes').value.trim();

  if (!hiveId || !dateVal || isNaN(yieldKg)) {
    errEl.textContent = 'Please fill in all required fields.'; return;
  }

  try {
    await apiFetch(`${API}/harvests/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({
        hive: parseInt(hiveId), harvest_date: dateVal,
        yield_kg: yieldKg, honey_type: honeyType, notes,
      }),
    });
    closeModal('harvestModal');
    toast('Harvest recorded successfully!');
    loadDashboardStats(); loadSeasonalChart(); loadHarvestTable(); loadHoneytypeChart();
  } catch (err) { errEl.textContent = err.message; }
}

// ── Add Hive ──────────────────────────────────────────────────────────────────

function openAddHive() {
  document.getElementById('hiveForm').reset();
  document.getElementById('hiveError').textContent = '';
  const sel = document.getElementById('hiveFarmModal');
  sel.innerHTML = '<option value="">Select farm…</option>';
  appState.farms.forEach(f => sel.innerHTML += `<option value="${f.id}">${f.name}</option>`);
  openModal('hiveModal');
}

async function submitHive() {
  const errEl = document.getElementById('hiveError');
  errEl.textContent = '';

  const farmId      = document.getElementById('hiveFarmModal').value;
  const hiveNumber  = document.getElementById('hiveNumber').value.trim();
  const hiveType    = document.getElementById('hiveType').value;
  const installDate = document.getElementById('hiveInstallDate').value;
  const queenStatus = document.getElementById('hiveQueenStatus').value;

  if (!farmId || !hiveNumber || !installDate) {
    errEl.textContent = 'Please fill in all required fields.'; return;
  }

  try {
    await apiFetch(`${API}/hives/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({
        farm: parseInt(farmId), hive_number: hiveNumber,
        hive_type: hiveType, install_date: installDate,
        queen_status: queenStatus, status: 'active',
      }),
    });
    closeModal('hiveModal');
    toast('Hive added successfully!');
    loadDashboardStats(); loadHivesTable();
  } catch (err) { errEl.textContent = err.message; }
}

// ── Tab navigation ────────────────────────────────────────────────────────────

function showTab(tab) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.nav-btn[data-tab]').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).style.display = 'block';
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  if (tab === 'hives') loadHivesTable();
}

// ── Session check on page load ────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
  try {
    const session = await apiFetch(`${API}/auth/whoami/`);
    if (session.beekeeper_id) {
      appState.role = session.role;
      applyRoleUI({ ...session, beekeeper_name: session.beekeeper_name });
      document.getElementById('loginScreen').style.display = 'none';
      document.getElementById('appScreen').style.display   = 'block';
      await initApp();
    }
  } catch (_) {
    // Not logged in — show login screen
  }
});