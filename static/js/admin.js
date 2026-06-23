/**
 * Admin Panel JS — Western Bee Farming Tracker
 * Full CRUD for all entities, charts, season-per-year management.
 */

const API = '/api';
let charts = {};
let adminState = { farms: [], beekeepers: [], seasons: [], hives: [] };
let pendingDelete = null;

// ── Utilities ─────────────────────────────────────────────────────────────────

async function apiFetch(url, opts = {}) {
  const { headers: extraHeaders = {}, body, method = 'GET', ...rest } = opts;
  const fetchOpts = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', ...extraHeaders },
    ...rest,
  };
  if (body !== undefined) fetchOpts.body = typeof body === 'string' ? body : JSON.stringify(body);
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

function getCookie(name) {
  const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
  return v ? v[2] : '';
}

function badgeHtml(val, prefix = '') {
  const cls = prefix + val.toLowerCase().replace(/[\s_]+/g, '-');
  return `<span class="badge badge-${cls}">${val.replace('_', ' ')}</span>`;
}

function formatDate(d) {
  if (!d) return '—';
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB',
    { day: '2-digit', month: 'short', year: 'numeric' });
}

const MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function openModal(id) {
  if (id === 'addFarmModal')    populateFarmOwners();
  if (id === 'addHiveModal')    populateHiveFarms();
  if (id === 'addHarvestModal') populateHarvestModal();  // async, modal opens immediately
  document.getElementById(id).classList.add('open');
}
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

// ── Auth ──────────────────────────────────────────────────────────────────────

function fillDemo(e, p) {
  document.getElementById('loginEmail').value    = e;
  document.getElementById('loginPassword').value = p;
}

async function doLogin() {
  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errEl    = document.getElementById('loginError');
  const btn      = document.getElementById('loginBtn');
  errEl.style.display = 'none';
  btn.textContent = 'Signing in…'; btn.disabled = true;

  try {
    const data = await apiFetch(`${API}/auth/login/`, {
      method: 'POST', body: JSON.stringify({ email, password }),
    });
    if (data.role !== 'admin') {
      errEl.textContent  = 'Admin access required. This panel is for admins only.';
      errEl.style.display= 'block';
      await apiFetch(`${API}/auth/logout/`, { method: 'POST' });
      return;
    }
    document.getElementById('userPill').innerHTML =
      `${data.beekeeper_name} &nbsp;<span class="badge badge-admin">admin</span>`;
    document.getElementById('sessionInfo').innerHTML =
      `<div>👤 <strong>${data.beekeeper_name}</strong></div><div>🔐 Role: ${badgeHtml('admin')}</div>`;
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('appScreen').style.display   = 'block';
    await initAdmin();
  } catch (err) {
    errEl.textContent   = err.message;
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'Sign In'; btn.disabled = false;
  }
}

async function doLogout() {
  await apiFetch(`${API}/auth/logout/`, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') } }).catch(() => {});
  location.reload();
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function initAdmin() {
  await Promise.all([loadDashboardStats(), loadSeasonalChart(), loadFarmChart(),
                     loadRoleChart(), loadHiveTypeChart(), loadAdminFilters()]);
  loadBeekeepers();
}

async function loadAdminFilters() {
  // Year dropdown
  const yields  = await apiFetch(`${API}/yields/`);
  const yearSel = document.getElementById('adminYear');
  yearSel.innerHTML = '<option value="">All Years</option>';
  (yields.available_years || []).forEach(y =>
    yearSel.innerHTML += `<option value="${y}">${y}</option>`);

  // Farm dropdown
  const resp = await apiFetch(`${API}/farms/`);
  adminState.farms = resp.results || resp;
  const farmSel = document.getElementById('adminFarm');
  farmSel.innerHTML = '<option value="">All Farms</option>';
  adminState.farms.forEach(f =>
    farmSel.innerHTML += `<option value="${f.id}">${f.name}</option>`);

  // Cache hives for the harvest modal
  const hResp = await apiFetch(`${API}/hives/`);
  adminState.hives = hResp.results || hResp;
}

function refreshAll() {
  loadDashboardStats();
  loadSeasonalChart();
  loadFarmChart();
  const activeTab = document.querySelector('.nav-btn.active[data-tab]');
  if (activeTab) {
    const tab = activeTab.dataset.tab;
    if (tab === 'harvests') loadHarvests();
  }
}

// ── Stats ─────────────────────────────────────────────────────────────────────

async function loadDashboardStats() {
  const data = await apiFetch(`${API}/dashboard/`);
  document.getElementById('stBeekeepers').textContent = data.total_beekeepers;
  document.getElementById('stFarms').textContent      = data.total_farms;
  document.getElementById('stHives').textContent      = data.total_active_hives;
  document.getElementById('stHarvests').textContent   = data.total_harvests;
  document.getElementById('stYield').textContent      = data.total_yield_kg.toLocaleString() + ' kg';
  document.getElementById('stBest').textContent       = data.best_single_harvest_kg + ' kg';
}

// ── Charts ────────────────────────────────────────────────────────────────────

async function loadSeasonalChart() {
  const year   = document.getElementById('adminYear').value;
  const farmId = document.getElementById('adminFarm').value;
  let url = `${API}/yields/?`;
  if (year)   url += `year=${year}&`;
  if (farmId) url += `farm_id=${farmId}&`;
  const data   = await apiFetch(url);
  const labels = Object.keys(data.yields_by_season);
  const values = labels.map(k => data.yields_by_season[k].total_kg);
  const palette= ['#4CAF50','#F5A623','#FF7043','#42A5F5','#AB47BC','#26C6DA','#EF5350','#FFCA28'];

  if (charts.season) charts.season.destroy();
  charts.season = new Chart(document.getElementById('seasonChart').getContext('2d'), {
    type: 'bar',
    data: { labels, datasets: [{ label:'Total Yield (kg)', data:values,
      backgroundColor: palette.map(c=>c+'CC'), borderColor:palette, borderWidth:2, borderRadius:5 }] },
    options: { responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{ y:{beginAtZero:true, title:{display:true,text:'kg'}}, x:{grid:{display:false}} } }
  });
}

async function loadFarmChart() {
  const stats = await apiFetch(`${API}/admin-stats/`);
  const rows  = stats.harvests_per_farm || [];
  const labels= rows.map(r => r['hive__farm__name'] || 'Unknown');
  const values= rows.map(r => r.total || 0);
  const pal   = ['#C17817','#2E7D32','#1565C0','#6A1B9A','#E65100','#BF360C','#004D40','#37474F'];

  if (charts.farm) charts.farm.destroy();
  charts.farm = new Chart(document.getElementById('farmChart').getContext('2d'), {
    type: 'horizontalBar' in Chart ? 'horizontalBar' : 'bar',
    data: { labels, datasets:[{ label:'Total kg', data:values,
      backgroundColor:pal, borderWidth:1, borderRadius:4 }] },
    options: { indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false}},
      scales:{ x:{beginAtZero:true}, y:{grid:{display:false}} } }
  });

  // Role chart
  const roleData = stats.beekeepers_by_role || [];
  const rLabels  = roleData.map(r => r.role);
  const rValues  = roleData.map(r => r.count);
  const rPal     = { admin:'#AB47BC', beekeeper:'#F5A623', farm_user:'#4CAF50', viewer:'#42A5F5' };
  if (charts.role) charts.role.destroy();
  charts.role = new Chart(document.getElementById('roleChart').getContext('2d'), {
    type: 'doughnut',
    data: { labels:rLabels, datasets:[{ data:rValues,
      backgroundColor:rLabels.map(l=>rPal[l]||'#999'), borderWidth:2, borderColor:'#fff' }] },
    options: { responsive:true, maintainAspectRatio:false, cutout:'55%',
      plugins:{ legend:{ position:'right', labels:{font:{size:11}} } } }
  });

  // Hive type chart
  const htData = stats.hives_by_type || [];
  const htLabs = htData.map(r => r.hive_type.replace('_','-'));
  const htVals = htData.map(r => r.count);
  if (charts.hiveType) charts.hiveType.destroy();
  charts.hiveType = new Chart(document.getElementById('hiveTypeChart').getContext('2d'), {
    type: 'doughnut',
    data: { labels:htLabs, datasets:[{ data:htVals,
      backgroundColor:['#C17817','#2E7D32','#1565C0','#6A1B9A'], borderWidth:2, borderColor:'#fff' }] },
    options: { responsive:true, maintainAspectRatio:false, cutout:'55%',
      plugins:{ legend:{ position:'right', labels:{font:{size:11}} } } }
  });
}

async function loadRoleChart() {}   // handled in loadFarmChart
async function loadHiveTypeChart() {}

// ── Beekeepers CRUD ───────────────────────────────────────────────────────────

async function loadBeekeepers() {
  const tbody = document.getElementById('beekeepersBody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';
  const resp = await apiFetch(`${API}/beekeepers/`);
  const rows = resp.results || resp;
  adminState.beekeepers = rows;
  if (!rows.length) { tbody.innerHTML = '<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">👨‍🌾</div><p>No beekeepers found.</p></div></td></tr>'; return; }
  tbody.innerHTML = rows.map(b => `
    <tr>
      <td><strong>${b.name}</strong></td>
      <td style="color:var(--text-muted)">${b.email}</td>
      <td>${badgeHtml(b.role)}</td>
      <td>${b.farm_count}</td>
      <td style="color:var(--text-muted)">${formatDate(b.created_at)}</td>
      <td>
        <button class="action-btn" style="margin-right:4px" onclick="openResetPasswordModal(${b.id},'${b.name.replace(/'/g,"\\'")}')">Reset Password</button>
        <button class="action-btn action-btn-delete" onclick="deleteRecord('beekeepers',${b.id},'${b.name}')">Delete</button>
      </td>
    </tr>`).join('');
}

async function submitBeekeeper() {
  const errEl = document.getElementById('bkError'); errEl.textContent = '';
  const name=document.getElementById('bkName').value.trim();
  const email=document.getElementById('bkEmail').value.trim();
  const pw=document.getElementById('bkPassword').value;
  const role=document.getElementById('bkRole').value;
  if (!name||!email||!pw) { errEl.textContent='All fields are required.'; return; }
  try {
    await apiFetch(`${API}/beekeepers/`, { method:'POST',
      headers:{'X-CSRFToken':getCookie('csrftoken')},
      body:JSON.stringify({name,email,password_hash:pw,role}) });
    closeModal('addBeekeeperModal');
    document.getElementById('bkName').value=''; document.getElementById('bkEmail').value='';
    document.getElementById('bkPassword').value='';
    toast('Beekeeper added!'); loadBeekeepers(); loadDashboardStats();
  } catch(e) { errEl.textContent=e.message; }
}

// ── Farms CRUD ────────────────────────────────────────────────────────────────

async function loadFarms() {
  const tbody = document.getElementById('farmsBody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';
  const resp = await apiFetch(`${API}/farms/`);
  const rows = resp.results || resp;
  adminState.farms = rows;
  tbody.innerHTML = rows.map(f => `
    <tr>
      <td><strong>${f.name}</strong></td>
      <td style="color:var(--text-muted)">${f.location}</td>
      <td>${f.beekeeper_name}</td>
      <td>${f.active_hive_count}</td>
      <td style="color:var(--text-muted)">${formatDate(f.established_date)}</td>
      <td><button class="action-btn action-btn-delete" onclick="deleteRecord('farms',${f.id},'${f.name}')">Delete</button></td>
    </tr>`).join('');
}

function populateFarmOwners() {
  const sel = document.getElementById('farmOwner');
  sel.innerHTML = '<option value="">Select owner…</option>';
  adminState.beekeepers.forEach(b => sel.innerHTML += `<option value="${b.id}">${b.name}</option>`);
}

async function submitFarm() {
  const errEl = document.getElementById('farmError'); errEl.textContent = '';
  const name=document.getElementById('farmName').value.trim();
  const loc=document.getElementById('farmLocation').value.trim();
  const dt=document.getElementById('farmDate').value;
  const ownerId=document.getElementById('farmOwner').value;
  if (!name||!loc||!dt||!ownerId) { errEl.textContent='All fields are required.'; return; }
  try {
    await apiFetch(`${API}/farms/`, { method:'POST',
      headers:{'X-CSRFToken':getCookie('csrftoken')},
      body:JSON.stringify({name,location:loc,established_date:dt,beekeeper:parseInt(ownerId)}) });
    closeModal('addFarmModal');
    toast('Farm added!'); loadFarms(); loadAdminFilters(); loadDashboardStats();
  } catch(e) { errEl.textContent=e.message; }
}

// ── Hives CRUD ────────────────────────────────────────────────────────────────

async function loadHives() {
  const tbody = document.getElementById('hivesBody');
  tbody.innerHTML = '<tr><td colspan="7"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';
  const farmId = document.getElementById('adminFarm').value;
  let url = `${API}/hives/?`;
  if (farmId) url += `farm_id=${farmId}&`;
  const resp = await apiFetch(url);
  const rows = resp.results || resp;
  tbody.innerHTML = rows.map(h => `
    <tr>
      <td><strong>${h.hive_number}</strong></td>
      <td>${h.farm_name}</td>
      <td>${h.hive_type.replace('_','-')}</td>
      <td>${badgeHtml(h.status)}</td>
      <td style="color:var(--text-muted)">${h.queen_status}</td>
      <td style="color:var(--text-muted)">${formatDate(h.install_date)}</td>
      <td><button class="action-btn action-btn-delete" onclick="deleteRecord('hives',${h.id},'Hive ${h.hive_number}')">Delete</button></td>
    </tr>`).join('');
}

function populateHiveFarms() {
  const sel = document.getElementById('hiveFarmSel');
  sel.innerHTML = '<option value="">Select farm…</option>';
  adminState.farms.forEach(f => sel.innerHTML += `<option value="${f.id}">${f.name}</option>`);
}

async function submitHive() {
  const errEl = document.getElementById('hiveError'); errEl.textContent = '';
  const farmId=document.getElementById('hiveFarmSel').value;
  const num=document.getElementById('hiveNum').value.trim();
  const type=document.getElementById('hiveTypeSel').value;
  const dt=document.getElementById('hiveDate').value;
  const queen=document.getElementById('hiveQueen').value;
  if (!farmId||!num||!dt) { errEl.textContent='Farm, Hive Number and Date are required.'; return; }
  try {
    await apiFetch(`${API}/hives/`, { method:'POST',
      headers:{'X-CSRFToken':getCookie('csrftoken')},
      body:JSON.stringify({farm:parseInt(farmId),hive_number:num,hive_type:type,
        install_date:dt,queen_status:queen,status:'active'}) });
    closeModal('addHiveModal');
    toast('Hive added!'); loadHives(); loadDashboardStats();
  } catch(e) { errEl.textContent=e.message; }
}

// ── Seasons CRUD ──────────────────────────────────────────────────────────────

async function loadSeasons() {
  const tbody = document.getElementById('seasonsBody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';
  const year = document.getElementById('adminYear').value;
  let url = `${API}/seasons/?`;
  if (year) url += `year=${year}&`;
  const resp = await apiFetch(url);
  const rows = resp.results || resp;
  adminState.seasons = rows;

  // Group by year for display
  const byYear = {};
  rows.forEach(s => { byYear[s.year] = byYear[s.year] || []; byYear[s.year].push(s); });

  tbody.innerHTML = Object.keys(byYear).sort((a,b)=>b-a).flatMap(yr =>
    byYear[yr].map((s, i) => `
      <tr>
        <td>${badgeHtml(s.name.replace(' ','-').toLowerCase(),'')}<span style="margin-left:6px">${s.name}</span></td>
        <td><strong>${s.year}</strong></td>
        <td><span class="month-tag">${MONTHS[s.start_month]}</span></td>
        <td><span class="month-tag">${MONTHS[s.end_month]}</span></td>
        <td style="color:var(--text-muted)">—</td>
        <td><button class="action-btn action-btn-delete" onclick="deleteRecord('seasons',${s.id},'${s.name} ${s.year}')">Delete</button></td>
      </tr>`)
  ).join('');
}

async function submitSeason() {
  const errEl = document.getElementById('seasonError'); errEl.textContent = '';
  const name=document.getElementById('seasonName').value;
  const year=parseInt(document.getElementById('seasonYear').value);
  const start=parseInt(document.getElementById('seasonStart').value);
  const end=parseInt(document.getElementById('seasonEnd').value);
  if (!year||!start||!end) { errEl.textContent='All fields are required.'; return; }
  try {
    await apiFetch(`${API}/seasons/`, { method:'POST',
      headers:{'X-CSRFToken':getCookie('csrftoken')},
      body:JSON.stringify({name,year,start_month:start,end_month:end}) });
    closeModal('addSeasonModal');
    toast('Season added!'); loadSeasons(); loadAdminFilters();
  } catch(e) { errEl.textContent=e.message; }
}

// ── Harvests CRUD ─────────────────────────────────────────────────────────────

async function populateHarvestModal() {
  const farmSel   = document.getElementById('harvestFarmSel');
  const seasonSel = document.getElementById('harvestSeasonSel');
  farmSel.innerHTML   = '<option value="">Loading farms…</option>';
  seasonSel.innerHTML = '<option value="">Loading seasons…</option>';
  document.getElementById('harvestHiveSel').innerHTML = '<option value="">Select farm first…</option>';

  const [farmsResp, seasonsResp] = await Promise.all([
    apiFetch(`${API}/farms/`).catch(e => { console.error('farms fetch error:', e); return null; }),
    apiFetch(`${API}/seasons/`).catch(e => { console.error('seasons fetch error:', e); return null; }),
  ]);

  if (farmsResp) {
    const farms = farmsResp.results || farmsResp;
    adminState.farms = farms;
    farmSel.innerHTML = '<option value="">Select farm…</option>';
    farms.forEach(f => farmSel.innerHTML += `<option value="${f.id}">${f.name}</option>`);
  } else {
    farmSel.innerHTML = '<option value="">Failed to load farms</option>';
  }

  if (seasonsResp) {
    const seasons = seasonsResp.results || seasonsResp;
    adminState.seasons = seasons;
    seasonSel.innerHTML = '<option value="">Select season…</option>';
    seasons.forEach(s => seasonSel.innerHTML += `<option value="${s.id}">${s.name} ${s.year}</option>`);
  } else {
    seasonSel.innerHTML = '<option value="">Failed to load seasons</option>';
  }
}

async function filterHarvestHives() {
  const farmId  = document.getElementById('harvestFarmSel').value;
  const hiveSel = document.getElementById('harvestHiveSel');
  if (!farmId) { hiveSel.innerHTML = '<option value="">Select farm first…</option>'; return; }
  hiveSel.innerHTML = '<option value="">Loading hives…</option>';
  try {
    const resp = await apiFetch(`${API}/hives/?farm_id=${farmId}`);
    const hives = resp.results || resp;
    if (!hives.length) { hiveSel.innerHTML = '<option value="">No hives on this farm</option>'; return; }
    hiveSel.innerHTML = '<option value="">Select hive…</option>';
    hives.forEach(h => hiveSel.innerHTML += `<option value="${h.id}">Hive ${h.hive_number}</option>`);
  } catch(e) {
    console.error('filterHarvestHives error:', e);
    hiveSel.innerHTML = `<option value="">Error: ${e.message}</option>`;
  }
}

async function submitHarvest() {
  const errEl    = document.getElementById('harvestError'); errEl.textContent = '';
  const hiveId   = document.getElementById('harvestHiveSel').value;
  const seasonId = document.getElementById('harvestSeasonSel').value;
  const dt       = document.getElementById('harvestDate').value;
  const yield_   = parseFloat(document.getElementById('harvestYield').value);
  const notes    = document.getElementById('harvestNotes').value.trim();
  if (!hiveId || !seasonId || !dt || !yield_) {
    errEl.textContent = 'Farm, Hive, Season, Date and Yield are all required.'; return;
  }
  try {
    await apiFetch(`${API}/harvests/`, { method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ hive: parseInt(hiveId), season: parseInt(seasonId),
                             harvest_date: dt, yield_kg: yield_, notes }) });
    closeModal('addHarvestModal');
    document.getElementById('harvestYield').value = '';
    document.getElementById('harvestNotes').value = '';
    toast('Harvest added!'); loadHarvests(); loadDashboardStats();
  } catch(e) { errEl.textContent = e.message; }
}

// ── Harvests list ──────────────────────────────────────────────────────────────

async function loadHarvests() {
  const tbody = document.getElementById('harvestsBody');
  tbody.innerHTML = '<tr><td colspan="7"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';
  const year   = document.getElementById('adminYear').value;
  const farmId = document.getElementById('adminFarm').value;
  let url = `${API}/harvests/?`;
  if (year)   url += `year=${year}&`;
  if (farmId) url += `farm_id=${farmId}&`;
  const resp = await apiFetch(url);
  const rows = resp.results || resp;
  document.getElementById('harvestCountBadge').textContent = `${rows.length} records`;
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">🍯</div><p>No harvest records found.</p></div></td></tr>';
    return;
  }
  tbody.innerHTML = rows.slice(0,100).map(h => `
    <tr>
      <td>${formatDate(h.harvest_date)}</td>
      <td><strong>${h.farm_name}</strong></td>
      <td>Hive ${h.hive_number}</td>
      <td><strong>${h.yield_kg} kg</strong></td>
      <td>${h.season_name ? `<span class="badge badge-${h.season_name.split(' ')[0].toLowerCase().replace(' ','-')}">${h.season_name}</span>` : '—'}</td>
      <td style="color:var(--text-muted);font-size:.78rem">${h.notes||'—'}</td>
      <td><button class="action-btn action-btn-delete" onclick="deleteRecord('harvests',${h.id},'Harvest on ${h.harvest_date}')">Delete</button></td>
    </tr>`).join('');
}

// ── Delete ────────────────────────────────────────────────────────────────────

function deleteRecord(resource, id, label) {
  pendingDelete = { resource, id };
  document.getElementById('deleteMsg').textContent =
    `Are you sure you want to delete "${label}"? This cannot be undone.`;
  openModal('deleteModal');
}

async function confirmDelete() {
  if (!pendingDelete) return;
  const { resource, id } = pendingDelete;
  try {
    await apiFetch(`${API}/${resource}/${id}/`, { method:'DELETE',
      headers:{'X-CSRFToken':getCookie('csrftoken')} });
    closeModal('deleteModal');
    pendingDelete = null;
    toast('Record deleted.', 'success');
    if (resource === 'beekeepers') loadBeekeepers();
    else if (resource === 'farms') loadFarms();
    else if (resource === 'hives') loadHives();
    else if (resource === 'seasons') loadSeasons();
    else if (resource === 'harvests') loadHarvests();
    loadDashboardStats();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Export ────────────────────────────────────────────────────────────────────

function exportAdmin(resource, fmt) {
  const p = new URLSearchParams({ resource, export_format: fmt });
  const year   = document.getElementById('adminYear').value;
  const farmId = document.getElementById('adminFarm').value;
  if (year   && ['harvests','seasons'].includes(resource)) p.set('year',    year);
  if (farmId && ['hives','harvests'].includes(resource))   p.set('farm_id', farmId);
  window.open(`/api/export/?${p}`, '_blank');
}

// ── Audit Log ─────────────────────────────────────────────────────────────────

let auditPage = 1;
let auditDebounceTimer = null;

const AUDIT_ACTION_ICONS = {
  create: '➕', update: '✏️', delete: '🗑️',
  login: '🔓', logout: '🔒', export: '📥', password_change: '🔑',
};
const AUDIT_ACTION_COLORS = {
  create: '#2E7D32', update: '#1565C0', delete: '#C62828',
  login: '#6A1B9A', logout: '#455A64', export: '#00695C', password_change: '#E65100',
};

function debounceAudit() {
  clearTimeout(auditDebounceTimer);
  auditDebounceTimer = setTimeout(() => { auditPage = 1; loadAuditLog(); }, 350);
}

function resetAuditFilters() {
  document.getElementById('auditAction').value   = '';
  document.getElementById('auditResource').value = '';
  document.getElementById('auditActor').value    = '';
  document.getElementById('auditFrom').value     = '';
  document.getElementById('auditTo').value       = '';
  auditPage = 1;
  loadAuditLog();
}

async function loadAuditLog() {
  const tbody = document.getElementById('auditBody');
  tbody.innerHTML = '<tr><td colspan="8"><div class="loading"><div class="spinner"></div>Loading…</div></td></tr>';

  const params = new URLSearchParams({ page: auditPage, page_size: 100 });
  const action   = document.getElementById('auditAction').value;
  const resource = document.getElementById('auditResource').value;
  const actor    = document.getElementById('auditActor').value.trim();
  const from     = document.getElementById('auditFrom').value;
  const to       = document.getElementById('auditTo').value;
  if (action)   params.set('action',    action);
  if (resource) params.set('resource',  resource);
  if (actor)    params.set('actor',     actor);
  if (from)     params.set('date_from', from);
  if (to)       params.set('date_to',   to);

  try {
    const data = await apiFetch(`${API}/audit/?${params}`);
    document.getElementById('auditTotal').textContent = `${data.total.toLocaleString()} entries`;

    if (!data.results.length) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="empty-state"><div class="empty-icon">📋</div><p>No audit entries found.</p></div></td></tr>';
      document.getElementById('auditPager').innerHTML = '';
      return;
    }

    tbody.innerHTML = data.results.map(e => {
      const icon  = AUDIT_ACTION_ICONS[e.action]  || '•';
      const color = AUDIT_ACTION_COLORS[e.action] || '#555';
      return `
      <tr>
        <td style="white-space:nowrap;font-size:.78rem;color:var(--text-muted)">${e.timestamp}</td>
        <td><strong>${e.actor_name || '—'}</strong></td>
        <td>${e.actor_role ? badgeHtml(e.actor_role) : '—'}</td>
        <td><span style="color:${color};font-weight:700;font-size:.8rem">${icon} ${e.action.replace('_',' ')}</span></td>
        <td style="font-size:.8rem">${e.resource || '—'}</td>
        <td style="font-size:.78rem;color:var(--text-muted)">${e.resource_id || '—'}</td>
        <td style="font-size:.78rem;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.detail}">${e.detail || '—'}</td>
        <td style="font-size:.75rem;color:var(--text-muted)">${e.ip_address || '—'}</td>
      </tr>`;
    }).join('');

    // Pagination controls
    const totalPages = Math.ceil(data.total / data.page_size);
    const pager = document.getElementById('auditPager');
    if (totalPages <= 1) { pager.innerHTML = ''; return; }
    pager.innerHTML = `
      <button class="btn btn-outline btn-sm" onclick="auditPage=${Math.max(1,auditPage-1)};loadAuditLog()" ${auditPage<=1?'disabled':''}>← Prev</button>
      <span>Page ${auditPage} of ${totalPages}</span>
      <button class="btn btn-outline btn-sm" onclick="auditPage=${Math.min(totalPages,auditPage+1)};loadAuditLog()" ${auditPage>=totalPages?'disabled':''}>Next →</button>`;
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:#C62828;padding:20px">Error: ${e.message}</td></tr>`;
  }
}

// ── Tab navigation ────────────────────────────────────────────────────────────

function showTab(tab) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.nav-btn[data-tab]').forEach(b => b.classList.remove('active'));
  document.getElementById(`tab-${tab}`).style.display = 'block';
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  const loaders = {
    beekeepers: loadBeekeepers,
    farms:      loadFarms,
    hives:      loadHives,
    seasons:    loadSeasons,
    harvests:   loadHarvests,
    audit:      loadAuditLog,
    overview:   () => { loadSeasonalChart(); loadFarmChart(); },
  };
  if (loaders[tab]) loaders[tab]();
}

// ── Session check on load ─────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
  try {
    const s = await apiFetch(`${API}/auth/whoami/`);
    if (s.beekeeper_id && s.role === 'admin') {
      document.getElementById('userPill').innerHTML =
        `${s.beekeeper_name} &nbsp;<span class="badge badge-admin">admin</span>`;
      document.getElementById('sessionInfo').innerHTML =
        `<div>👤 <strong>${s.beekeeper_name}</strong></div><div>🔐 Role: ${badgeHtml('admin')}</div>`;
      document.getElementById('loginScreen').style.display = 'none';
      document.getElementById('appScreen').style.display   = 'block';
      await initAdmin();
    }
  } catch (_) {}
});

// ── Reset Password (admin) ────────────────────────────────────────────────────

let resetTargetId = null;

function openResetPasswordModal(id, name) {
  resetTargetId = id;
  document.getElementById('resetPwTitle').textContent = `Reset password for ${name}`;
  document.getElementById('resetPwNew').value = '';
  document.getElementById('resetPwConfirm').value = '';
  document.getElementById('resetPwError').textContent = '';
  openModal('resetPasswordModal');
}

async function submitResetPassword() {
  const errEl   = document.getElementById('resetPwError');
  const newPw   = document.getElementById('resetPwNew').value;
  const confirm = document.getElementById('resetPwConfirm').value;
  errEl.textContent = '';
  if (!newPw || !confirm) { errEl.textContent = 'Both fields are required.'; return; }
  if (newPw !== confirm)  { errEl.textContent = 'Passwords do not match.';   return; }
  if (newPw.length < 6)  { errEl.textContent = 'Password must be at least 6 characters.'; return; }
  try {
    const data = await apiFetch(`${API}/beekeepers/${resetTargetId}/set_password/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCookie('csrftoken') },
      body: JSON.stringify({ new_password: newPw, confirm_password: confirm }),
    });
    closeModal('resetPasswordModal');
    toast(data.message || 'Password reset successfully.');
  } catch (e) { errEl.textContent = e.message; }
}
