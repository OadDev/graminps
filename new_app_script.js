/* ============================================================
   GRAMIN PAN SEVA — FRONTEND (API-WIRED)
   Talks to the FastAPI backend via same-origin /api/* routes.
   ============================================================ */
const APP = { role: null, user: null, currentView: 'dashboard', sidebarCollapsed: false };

const ROLE_LABELS = { superadmin:'Super Admin', superdistributor:'Super Distributor', distributor:'Distributor', retailer:'Retailer' };
const ROLE_TABLE = { 'Super Distributor':['users-sd-table','superdistributor'], 'Distributor':['users-dist-table','distributor'], 'Retailer':['users-retailer-table','retailer'] };

/* ---------------- API HELPER ---------------- */
function authHeaders(){ const t = localStorage.getItem('gps_token'); return t ? {'Authorization':'Bearer '+t} : {}; }
async function api(path, {method='GET', body=null}={}){
  const opts = { method, headers:{'Content-Type':'application/json', ...authHeaders()} };
  if(body) opts.body = JSON.stringify(body);
  const res = await fetch('/api'+path, opts);
  let data = null; try{ data = await res.json(); }catch(e){}
  if(!res.ok){
    if(res.status === 401){ localStorage.removeItem('gps_token'); }
    const d = data && data.detail;
    const msg = typeof d === 'string' ? d : (Array.isArray(d) ? d.map(x=>x.msg||'').join(', ') : 'Request failed');
    throw new Error(msg);
  }
  return data;
}
async function apiUpload(file){
  const fd = new FormData(); fd.append('file', file);
  const res = await fetch('/api/uploads', { method:'POST', headers:{...authHeaders()}, body:fd });
  if(!res.ok) throw new Error('Upload failed');
  return res.json();
}

/* ---------------- DOCUMENT UPLOADS ---------------- */
let uploadedDocs = {};
let regPhotoPath = '';
async function onDocChosen(input){
  if(!input.files || !input.files[0]) return;
  const file = input.files[0];
  const key = input.dataset.doc;
  const box = input.closest('.upload-box');
  const status = box ? box.querySelector('.upload-status') : null;
  if(status) status.textContent = 'Uploading...';
  try{
    const up = await apiUpload(file);
    uploadedDocs[key] = up.path;
    if(status) status.textContent = file.name.length > 16 ? file.name.slice(0,14)+'\u2026' : file.name;
    if(box) box.style.borderColor = 'var(--success)';
    showToast('Uploaded', file.name + ' attached.', 'success');
  }catch(err){ if(status) status.textContent = 'Upload failed'; showToast('Upload Failed', err.message, 'danger'); }
}
function onRegPhotoChosen(input){
  if(!input.files || !input.files[0]) return;
  const file = input.files[0];
  regPhotoPath = file.name;
  const label = document.getElementById('profPhotoLabel');
  if(label) label.textContent = file.name;
}

/* ---------------- UI HELPERS ---------------- */
function statusBadgeClass(status){
  const map = { Active:'bd-active', Blocked:'bd-blocked', Pending:'bd-pending', Approved:'bd-approved',
    Rejected:'bd-rejected', Processing:'bd-processing', Processed:'bd-submitted', Hold:'bd-hold',
    Submitted:'bd-submitted', Open:'bd-open', 'In Progress':'bd-inprogress', Closed:'bd-closed' };
  return map[status] || 'bd-pending';
}
function showToast(title, msg, type='success'){
  const icons = {success:'fa-circle-check', danger:'fa-circle-exclamation', info:'fa-circle-info', warning:'fa-triangle-exclamation'};
  const colors = {success:'var(--success)', danger:'var(--danger)', info:'var(--info)', warning:'var(--warning)'};
  const id = 't'+Date.now();
  const el = document.createElement('div');
  el.className = 'card-pane p-3'; el.id = id;
  el.style.cssText = 'animation:fadeUp .25s ease;border-left:4px solid '+colors[type];
  el.innerHTML = `<div class="d-flex gap-2 align-items-start">
      <i class="fa-solid ${icons[type]}" style="color:${colors[type]};margin-top:2px;"></i>
      <div class="flex-grow-1"><div class="fw-semibold" style="font-size:.85rem;">${title}</div>
        <div class="text-soft" style="font-size:.78rem;">${msg}</div></div>
      <button class="btn-close" style="font-size:.65rem;" onclick="document.getElementById('${id}').remove()"></button>
    </div>`;
  document.getElementById('toastStack').appendChild(el);
  setTimeout(()=>{ const e=document.getElementById(id); if(e) e.remove(); }, 4500);
}
function openSidebarOffcanvas(){ new bootstrap.Offcanvas(document.getElementById('mobileSidebarOffcanvas')).show(); }
function toggleSidebar(){
  APP.sidebarCollapsed = !APP.sidebarCollapsed;
  document.getElementById('sidebar').classList.toggle('collapsed', APP.sidebarCollapsed);
  document.getElementById('collapseIcon').className = APP.sidebarCollapsed ? 'fa-solid fa-angles-right' : 'fa-solid fa-angles-left';
}

/* ---------------- NAV CONFIG ---------------- */
function getNavConfig(role){
  const base = [{section:null, items:[{id:'dashboard', icon:'fa-gauge-high', label:'Dashboard'}]}];
  const userMgmt = {section:'User Management', items:[
    role==='superadmin' ? {id:'users-sd', icon:'fa-user-tie', label:'Super Distributors'} : null,
    (role==='superadmin'||role==='superdistributor') ? {id:'users-dist', icon:'fa-user-gear', label:'Distributors'} : null,
    role!=='retailer' ? {id:'users-retailer', icon:'fa-user', label:'Retailers'} : null
  ].filter(Boolean)};
  const panServices = {section:'PAN Services', items:[
    {id:'pan-new', icon:'fa-file-circle-plus', label:'New PAN'},
    {id:'pan-csf', icon:'fa-file-pen', label:'CSF PAN'},
    {id:'pan-hold-new', icon:'fa-file-circle-exclamation', label:'New Hold PAN'},
    {id:'pan-hold-csf', icon:'fa-file-circle-question', label:'CSF Hold PAN'}
  ]};
  const panStatus = {section:null, items:[{id:'pan-status', icon:'fa-list-check', label:'PAN Status'}]};
  const wallet = {section:'Wallet Management', items:[
    {id:'wallet-recharge', icon:'fa-wallet', label: role==='superadmin' ? 'Recharge Approvals' : 'Recharge Request'},
    {id:'wallet-history', icon:'fa-clock-rotate-left', label:'Wallet History'}
  ]};
  const rateSetup = role==='superadmin' ? {section:null, items:[
    {id:'registrations', icon:'fa-user-check', label:'Registration Approvals'},
    {id:'rate-setup', icon:'fa-tags', label:'Rate Setup'},
    {id:'settings', icon:'fa-gear', label:'Settings'}
  ]} : null;
  const tail = [
    {section:null, items:[{id:'support', icon:'fa-headset', label:'Support Center'}, {id:'certificates', icon:'fa-award', label:'Certificates'}]},
    {section:'Account', items:[{id:'profile', icon:'fa-user-circle', label:'Profile'}, {id:'change-password', icon:'fa-key', label:'Change Password'}, {id:'logout', icon:'fa-right-from-bracket', label:'Logout'}]}
  ];
  return [...base, userMgmt, panServices, panStatus, wallet, rateSetup, ...tail].filter(Boolean);
}
function getBottomNavConfig(){
  return [
    {id:'dashboard', icon:'fa-gauge-high', label:'Home'},
    {id:'pan-status', icon:'fa-list-check', label:'PAN Status'},
    {id:'__fab__', icon:'fa-plus', label:'New PAN', target:'pan-new'},
    {id:'wallet-history', icon:'fa-wallet', label:'Wallet'},
    {id:'support', icon:'fa-headset', label:'Support'}
  ];
}
function renderSidebar(){
  const cfg = getNavConfig(APP.role);
  function buildNav(idPrefix){
    let html = '';
    cfg.forEach(group=>{
      if(group.section) html += `<div class="nav-section-label">${group.section}</div>`;
      group.items.forEach(item=>{
        html += `<a class="nav-link ${APP.currentView===item.id?'active':''}" onclick="goTo('${item.id}');${idPrefix==='mobile'?"bootstrap.Offcanvas.getInstance(document.getElementById('mobileSidebarOffcanvas'))?.hide();":''}"><i class="fa-solid ${item.icon}"></i><span>${item.label}</span></a>`;
      });
    });
    return html;
  }
  document.getElementById('sidebarNav').innerHTML = buildNav('desktop');
  document.getElementById('mobileSidebarNav').innerHTML = buildNav('mobile');
}
function renderBottomNav(){
  let html = '';
  getBottomNavConfig().forEach(item=>{
    if(item.id === '__fab__'){
      html += `<a class="bn-item" onclick="goTo('${item.target}')" style="flex:0 0 64px;"><div class="bn-fab"><i class="fa-solid ${item.icon}"></i></div></a>`;
    } else {
      html += `<a class="bn-item ${APP.currentView===item.id?'active':''}" onclick="goTo('${item.id}')"><i class="fa-solid ${item.icon}"></i><span>${item.label}</span></a>`;
    }
  });
  document.getElementById('bottomNav').innerHTML = html;
}

const VIEW_TITLES = {
  dashboard:['Dashboard','Welcome back'], 'users-sd':['Super Distributors','Manage super distributor accounts'],
  'users-dist':['Distributors','Manage distributor accounts'], 'users-retailer':['Retailers','Manage retailer accounts'],
  'pan-new':['New PAN Application','For Major and Minor applicants'], 'pan-csf':['CSF PAN Application','Correction / Change request form'],
  'pan-hold-new':['New Hold PAN','Resubmit held new PAN applications'], 'pan-hold-csf':['CSF Hold PAN','Resubmit held CSF applications'],
  'pan-status':['PAN Status','Track all PAN applications'], 'wallet-recharge':['Recharge Request','Add funds to your wallet'],
  'wallet-recharge-admin':['Recharge Approvals','Verify UTR and amount before accepting'], 'wallet-history':['Wallet History','All wallet transactions'],
  'rate-setup':['Rate Setup','Configure service charges'], registrations:['Registration Approvals','Review and approve new account registrations'],
  settings:['Settings','SMTP, FTP and system configuration'],
  'support':['Support Center','Raise and track tickets'], 'certificates':['Certificates','Your achievement certificates'],
  'profile':['Profile','Manage your account details'], 'change-password':['Change Password','Keep your account secure'], notifications:['Notifications','Recent updates'],
};

function goTo(viewId){
  if(viewId === 'logout'){ doLogout(); return; }
  APP.currentView = viewId;
  document.querySelectorAll('.app-view').forEach(v=>v.classList.remove('active'));
  const target = document.getElementById('view-'+viewId);
  if(target){ target.classList.add('active'); renderViewData(viewId); }
  const [title, sub] = VIEW_TITLES[viewId] || [viewId, ''];
  document.getElementById('desktopPageTitle').textContent = title;
  document.getElementById('desktopPageSub').textContent = sub;
  renderSidebar(); renderBottomNav();
  window.scrollTo({top:0, behavior:'smooth'});
}
function doLogout(){
  localStorage.removeItem('gps_token');
  APP.role = null; APP.user = null;
  history.pushState({}, '', '/');
  route();
}

/* ---------------- AUTH ---------------- */
function showAuthView(viewName){
  document.querySelectorAll('[id^="authView-"]').forEach(v=>v.style.display='none');
  const target = document.getElementById('authView-'+viewName);
  if(target) target.style.display = 'flex';
  if(viewName === 'register') resetRegisterForm();
}
function togglePw(inputId, iconEl){
  const input = document.getElementById(inputId);
  const isPw = input.type === 'password';
  input.type = isPw ? 'text' : 'password';
  iconEl.className = isPw ? 'fa-regular fa-eye-slash position-absolute' : 'fa-regular fa-eye position-absolute';
  iconEl.style.right='.9rem'; iconEl.style.top='50%'; iconEl.style.transform='translateY(-50%)'; iconEl.style.color='var(--ink-soft)'; iconEl.style.cursor='pointer';
}
async function handleLogin(e){
  e.preventDefault();
  const userId = document.getElementById('loginUserId').value.trim();
  const password = document.getElementById('loginPassword').value;
  try{
    const data = await api('/auth/login', {method:'POST', body:{user_id:userId, password}});
    localStorage.setItem('gps_token', data.token);
    APP.user = data.user; APP.role = data.user.role;
    enterApp();
    showToast('Login Successful', 'Welcome back, '+data.user.role_label+'!', 'success');
  }catch(err){ showToast('Login Failed', err.message, 'danger'); }
}
function enterApp(){
  const lp = document.getElementById('landingRoot'); if(lp) lp.style.display = 'none';
  document.getElementById('authRoot').style.display = 'none';
  document.getElementById('appShell').style.display = 'block';
  document.getElementById('mobileRoleLabel').textContent = APP.user.role_label;
  document.getElementById('desktopUserRole').textContent = APP.user.role_label;
  document.getElementById('desktopUserName').textContent = APP.user.name;
  renderSidebar(); renderBottomNav();
  document.querySelectorAll('.dash-view').forEach(d=>d.style.display='none');
  const dashEl = document.getElementById('dash-'+APP.role);
  if(dashEl) dashEl.style.display = 'block';
  goTo('dashboard');
}

/* ---------------- REGISTER (3-step) ---------------- */
let regCurrentStep = 1;
const REG_TOTAL_STEPS = 3;
let regEmailForOtp = '';
function resetRegisterForm(){
  regCurrentStep = 1;
  document.querySelectorAll('.reg-step').forEach(s=>s.style.display='none');
  document.querySelector('.reg-step[data-step="1"]').style.display='block';
  document.getElementById('regBackBtn').style.display='none';
  document.getElementById('regNextBtn').style.display='inline-block';
  document.getElementById('regSubmitBtn').style.display='none';
  renderRegStepDots();
}
function renderRegStepDots(){
  let html = '';
  for(let i=1;i<=REG_TOTAL_STEPS;i++) html += `<div class="dot ${i===regCurrentStep?'active':''}"></div>`;
  document.getElementById('regStepDots').innerHTML = html;
}
function regStep(dir){
  const newStep = regCurrentStep + dir;
  if(newStep < 1 || newStep > REG_TOTAL_STEPS) return;
  document.querySelector(`.reg-step[data-step="${regCurrentStep}"]`).style.display = 'none';
  regCurrentStep = newStep;
  document.querySelector(`.reg-step[data-step="${regCurrentStep}"]`).style.display = 'block';
  document.getElementById('regBackBtn').style.display = regCurrentStep===1 ? 'none' : 'inline-block';
  document.getElementById('regNextBtn').style.display = regCurrentStep===REG_TOTAL_STEPS ? 'none' : 'inline-block';
  document.getElementById('regSubmitBtn').style.display = regCurrentStep===REG_TOTAL_STEPS ? 'inline-block' : 'none';
  renderRegStepDots();
}
async function sendEmailOtp(){
  const inputs = document.querySelectorAll('.reg-step[data-step="1"] input');
  const email = inputs[3] ? inputs[3].value.trim() : '';
  if(!email){ showToast('Email Required','Please enter your email first.','warning'); return; }
  try{
    const r = await api('/auth/register/send-otp', {method:'POST', body:{email}});
    regEmailForOtp = email;
    document.getElementById('emailOtpBox').style.display = 'block';
    showToast('OTP Sent', r.emailed ? 'A 6-digit code was sent to your email.' : 'Enter the code shown to complete verification.', 'info');
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function handleRegisterSubmit(e){
  e.preventDefault();
  const s1 = document.querySelectorAll('.reg-step[data-step="1"] input');
  const s2 = document.querySelector('.reg-step[data-step="2"]');
  const s2inputs = s2.querySelectorAll('input'); const s2text = s2.querySelector('textarea');
  const body = {
    name: (s2inputs[2] && s2inputs[2].value) ? s2inputs[2].value : 'New Retailer',
    aadhaar: s1[0].value, pan: s1[1].value, mobile: s1[2].value, email: s1[3].value.trim(),
    otp: s1[4] ? s1[4].value : '', password: s2inputs[0].value,
    shop_name: s2inputs[2] ? s2inputs[2].value : '', address: s2text ? s2text.value : '',
    photo_path: regPhotoPath,
  };
  if(s2inputs[0].value !== s2inputs[1].value){ showToast('Password Mismatch','Passwords do not match.','danger'); return; }
  try{
    const r = await api('/auth/register', {method:'POST', body});
    const refEl = document.querySelector('#authView-pending strong');
    if(refEl) refEl.textContent = r.reference_id;
    showAuthView('pending');
  }catch(err){ showToast('Registration Failed', err.message, 'danger'); }
}

/* ---------------- VIEW DISPATCHER ---------------- */
function renderViewData(viewId){
  if(viewId === 'dashboard') renderDashboardData();
  if(viewId === 'users-sd') loadUserTable('users-sd-table','superdistributor');
  if(viewId === 'users-dist') loadUserTable('users-dist-table','distributor');
  if(viewId === 'users-retailer') loadUserTable('users-retailer-table','retailer');
  if(viewId === 'pan-new'){ uploadedDocs = {}; initNewPanForm(); }
  if(['pan-csf','pan-hold-new','pan-hold-csf'].includes(viewId)){ uploadedDocs = {}; initPanForms(); }
  if(viewId === 'pan-status') renderPanStatusTable();
  if(viewId === 'wallet-history') renderWalletHistoryTable();
  if(viewId === 'wallet-recharge') renderRechargeTable();
  if(viewId === 'support') renderTicketList();
  if(viewId === 'notifications') renderNotificationsList();
  if(viewId === 'registrations') renderRegistrationsTable();
  if(viewId === 'rate-setup') renderRateSetup();
  if(viewId === 'settings') renderSettingsForms();
  if(viewId === 'certificates') renderPersonalCertificate();
  if(viewId === 'profile') renderPersonalProfile();
}

/* ---------------- DASHBOARD ---------------- */
let chartsInitialized = false;
async function renderDashboardData(){
  document.querySelectorAll('.dash-view').forEach(d=>d.style.display='none');
  const el = document.getElementById('dash-'+APP.role);
  if(el) el.style.display = 'block';
  try{
    const stats = await api('/dashboard/stats'); applyStats(el, stats);
    const act = await api('/dashboard/activity');
    const map = {superadmin:'recentActivityList', superdistributor:'recentActivityList2', distributor:'recentActivityList3', retailer:'recentActivityList4'};
    renderActivityFeed(map[APP.role], act);
  }catch(e){}
  if(APP.role === 'superadmin' && !chartsInitialized){ initDashboardCharts(); chartsInitialized = true; }
}
function applyStats(el, stats){
  if(!el) return;
  const c = stats.cards || {};
  const hero = el.querySelector('.wallet-hero div[style*="1.9rem"]');
  if(hero && stats.wallet) hero.textContent = stats.wallet;
  const vals = el.querySelectorAll('.stat-value');
  let order;
  if(APP.role==='superadmin') order=[c.total_users,c.retailers,c.distributors,c.super_distributors,c.total_pan,c.pending_pan,c.approved_pan,c.hold_pan,null,c.wallet_requests];
  else if(APP.role==='superdistributor') order=[c.distributors,c.retailers,c.total_pan,c.pending_pan];
  else if(APP.role==='distributor') order=[c.retailers,c.total_pan,c.pending_pan];
  else order=[c.total_pan,c.approved_pan,c.hold_pan,c.rejected_pan];
  vals.forEach((v,i)=>{ if(order[i]!=null) v.textContent = Number(order[i]).toLocaleString('en-IN'); });
}
function renderActivityFeed(containerId, items){
  const el = document.getElementById(containerId);
  if(!el) return;
  if(!items || !items.length){ el.innerHTML = `<div class="text-soft py-3" style="font-size:.82rem;">No recent activity.</div>`; return; }
  el.innerHTML = items.map(a => `
    <div class="d-flex align-items-start gap-3 py-2" style="border-bottom:1px solid var(--line);">
      <div class="stat-icon" style="width:36px;height:36px;font-size:.85rem;background:${a.bg};color:${a.color};flex-shrink:0;margin-bottom:0;"><i class="fa-solid ${a.icon}"></i></div>
      <div class="flex-grow-1"><div style="font-size:.85rem;font-weight:600;">${a.title}</div>
        <div class="text-soft" style="font-size:.76rem;">${a.detail}</div></div>
      <div class="text-soft text-end" style="font-size:.72rem;white-space:nowrap;">${a.time||''}</div>
    </div>`).join('');
}
function initDashboardCharts(){
  const trendCtx = document.getElementById('chartPanTrend');
  if(trendCtx){ new Chart(trendCtx, {type:'line', data:{labels:['Jan','Feb','Mar','Apr','May','Jun'],
    datasets:[{label:'Submitted', data:[1820,2010,2240,2380,2510,2690], borderColor:'#1F6FAB', backgroundColor:'rgba(31,111,171,.08)', tension:.4, fill:true},
      {label:'Approved', data:[1540,1780,1990,2120,2260,2430], borderColor:'#1E8449', backgroundColor:'rgba(30,132,73,.08)', tension:.4, fill:true}]},
    options:{plugins:{legend:{position:'bottom', labels:{boxWidth:10,font:{size:11}}}}, scales:{y:{beginAtZero:true, grid:{color:'#EEF1F4'}}, x:{grid:{display:false}}}, maintainAspectRatio:false}}); }
  const revCtx = document.getElementById('chartRevenue');
  if(revCtx){ new Chart(revCtx, {type:'bar', data:{labels:['Jan','Feb','Mar','Apr','May','Jun'],
    datasets:[{label:'Revenue (₹L)', data:[12.4,13.8,14.9,16.2,17.1,18.6], backgroundColor:'#D4A02A', borderRadius:6}]},
    options:{plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true, grid:{color:'#EEF1F4'}}, x:{grid:{display:false}}}, maintainAspectRatio:false}}); }
}

/* ---------------- USER MANAGEMENT ---------------- */
let createUserTargetRole = 'Retailer';
function openCreateUserModal(targetRole){
  createUserTargetRole = targetRole;
  document.getElementById('createUserModalTitle').textContent = 'Add ' + targetRole;
  document.getElementById('createUserForm').reset();
  document.getElementById('createUserRoleDisplay').value = targetRole;
  new bootstrap.Modal(document.getElementById('createUserModal')).show();
}
async function handleCreateUserSubmit(e){
  e.preventDefault();
  const name = document.getElementById('createUserName').value || 'New User';
  const mobile = document.getElementById('createUserMobile').value;
  const email = document.getElementById('createUserEmail').value;
  try{
    const r = await api('/users', {method:'POST', body:{name, mobile, email, role:createUserTargetRole}});
    bootstrap.Modal.getInstance(document.getElementById('createUserModal'))?.hide();
    showToast('Account Created', `${r.message} Default password: ${r.default_password}`, 'success');
    const [tableId, roleKey] = ROLE_TABLE[createUserTargetRole];
    loadUserTable(tableId, roleKey);
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function loadUserTable(containerId, roleKey){
  try{ const data = await api('/users?role='+roleKey); renderUserTable(containerId, data, roleKey); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}
function renderUserTable(containerId, data, roleKey){
  const el = document.getElementById(containerId);
  if(!el) return;
  const isAdmin = APP.role === 'superadmin';
  function actionsHtml(u){
    let btns = `<button class="row-action-btn" title="View" onclick="showToast('View User','Viewing profile for ${u.name}','info')"><i class="fa-regular fa-eye"></i></button>
      <button class="row-action-btn" title="Edit" onclick="editUser('${u.id}','${containerId}','${roleKey}','${u.name}')"><i class="fa-regular fa-pen-to-square"></i></button>`;
    btns += `<button class="row-action-btn" title="${u.status==='Blocked'?'Unblock':'Block'}" onclick="toggleUserBlock('${u.id}','${containerId}','${roleKey}')"><i class="fa-solid fa-${u.status==='Blocked'?'lock-open':'lock'}"></i></button>`;
    if(isAdmin) btns += `<button class="row-action-btn" title="Delete" onclick="deleteUser('${u.id}','${u.name}','${containerId}','${roleKey}')"><i class="fa-regular fa-trash-can"></i></button>`;
    return btns;
  }
  let desktop = `<div class="table-responsive d-none d-md-block"><table class="table table-modern mb-0">
    <thead><tr><th>User ID</th><th>Name</th><th>Mobile</th><th>Wallet</th><th>Status</th><th>Actions</th></tr></thead><tbody>`;
  data.forEach(u=>{ desktop += `<tr><td class="fw-semibold">${u.user_code}</td><td>${u.name}</td><td>${u.mobile}</td><td>${u.wallet}</td>
    <td><span class="badge-pill ${statusBadgeClass(u.status)}">${u.status}</span></td>
    <td><div class="d-flex gap-1">${actionsHtml(u)}</div></td></tr>`; });
  desktop += `</tbody></table></div>`;
  let mobile = `<div class="d-md-none">`;
  data.forEach(u=>{ mobile += `<div class="table-card-mobile">
    <div class="d-flex justify-content-between align-items-start mb-2"><div>
      <div class="fw-semibold">${u.name}</div><div class="text-soft" style="font-size:.78rem;">${u.user_code} • ${u.mobile}</div></div>
      <span class="badge-pill ${statusBadgeClass(u.status)}">${u.status}</span></div>
    <div class="text-soft mb-2" style="font-size:.8rem;">Wallet: <strong style="color:var(--ink);">${u.wallet}</strong></div>
    <div class="d-flex gap-2">${actionsHtml(u)}</div></div>`; });
  mobile += `</div>`;
  el.innerHTML = (data.length ? desktop + mobile : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No users yet.</div>`);
}
async function toggleUserBlock(uid, containerId, roleKey){
  try{ const r = await api('/users/'+uid+'/toggle-block', {method:'POST'});
    showToast(r.status==='Blocked'?'User Blocked':'User Unblocked', `Status updated to ${r.status}. An email notification has been sent.`, 'warning');
    loadUserTable(containerId, roleKey);
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function deleteUser(uid, name, containerId, roleKey){
  if(!confirm(`Delete ${name}? This cannot be undone.`)) return;
  try{ await api('/users/'+uid, {method:'DELETE'}); showToast('Deleted', `${name} removed.`, 'danger'); loadUserTable(containerId, roleKey); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}
async function editUser(uid, containerId, roleKey, currentName){
  const name = prompt('Edit name', currentName);
  if(name === null) return;
  try{ await api('/users/'+uid, {method:'PATCH', body:{name}}); showToast('Updated', 'User details updated.', 'success'); loadUserTable(containerId, roleKey); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- REGISTRATION APPROVALS ---------------- */
let pendingRegs = [];
async function renderRegistrationsTable(){
  const host = document.getElementById('registrationsTableHost');
  const badge = document.getElementById('regPendingCountBadge');
  if(!host) return;
  try{ pendingRegs = await api('/registrations'); }catch(err){ host.innerHTML=''; return; }
  badge.textContent = pendingRegs.length + ' Pending';
  if(!pendingRegs.length){ host.innerHTML = `<div class="text-center text-soft py-4" style="font-size:.88rem;"><i class="fa-regular fa-circle-check mb-2 d-block" style="font-size:1.6rem;"></i>No pending registrations right now.</div>`; return; }
  let desktop = `<div class="table-responsive d-none d-md-block"><table class="table table-modern mb-0">
    <thead><tr><th>Reg. ID</th><th>Name</th><th>Role</th><th>Mobile</th><th>Shop Name</th><th>Date</th><th>Actions</th></tr></thead><tbody>`;
  pendingRegs.forEach(r=>{ desktop += `<tr><td class="fw-semibold">${r.reg_id}</td><td>${r.name}</td><td>${r.role}</td><td>${r.mobile}</td><td>${r.shop_name}</td><td>${r.date}</td>
    <td><button class="row-action-btn" title="Review" onclick="openRegReviewModal('${r.reg_id}')"><i class="fa-regular fa-eye"></i> Review</button></td></tr>`; });
  desktop += `</tbody></table></div>`;
  let mobile = `<div class="d-md-none">`;
  pendingRegs.forEach(r=>{ mobile += `<div class="table-card-mobile"><div class="d-flex justify-content-between align-items-start mb-1">
    <div class="fw-semibold">${r.name}</div><span class="badge-pill bd-pending">${r.role}</span></div>
    <div class="text-soft mb-2" style="font-size:.78rem;">${r.reg_id} • ${r.mobile} • ${r.date}</div>
    <button class="row-action-btn w-100" onclick="openRegReviewModal('${r.reg_id}')"><i class="fa-regular fa-eye me-1"></i> Review</button></div>`; });
  mobile += `</div>`;
  host.innerHTML = desktop + mobile;
}
function openRegReviewModal(regId){
  const r = pendingRegs.find(x=>x.reg_id===regId);
  if(!r) return;
  document.getElementById('regReviewId').value = regId;
  document.getElementById('regReviewRemarkInput').value = '';
  document.getElementById('regReviewDetailsBody').innerHTML = `
    <div class="col-6"><div class="text-soft" style="font-size:.74rem;">Name</div><div class="fw-semibold">${r.name}</div></div>
    <div class="col-6"><div class="text-soft" style="font-size:.74rem;">Role Applied For</div><div class="fw-semibold">${r.role}</div></div>
    <div class="col-6"><div class="text-soft" style="font-size:.74rem;">Mobile</div><div class="fw-semibold">${r.mobile}</div></div>
    <div class="col-6"><div class="text-soft" style="font-size:.74rem;">Email</div><div class="fw-semibold">${r.email}</div></div>
    <div class="col-12"><div class="text-soft" style="font-size:.74rem;">Shop Name</div><div class="fw-semibold">${r.shop_name}</div></div>`;
  new bootstrap.Modal(document.getElementById('regReviewModal')).show();
}
async function reviewRegistration(decision){
  const regId = document.getElementById('regReviewId').value;
  const remark = document.getElementById('regReviewRemarkInput').value;
  try{
    const r = await api('/registrations/'+regId+'/review', {method:'POST', body:{decision, remark}});
    bootstrap.Modal.getInstance(document.getElementById('regReviewModal'))?.hide();
    showToast(decision==='Approved'?'Registration Approved':'Registration Rejected', r.message, decision==='Approved'?'success':'danger');
    renderRegistrationsTable();
  }catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- PAN FORMS ---------------- */
const PAN_FORM_HOSTS = ['csf','hold-new','hold-csf'];
function initPanForms(){
  PAN_FORM_HOSTS.forEach(key=>{
    const host = document.getElementById('panFormHost-'+key);
    if(host && !host.dataset.rendered){
      host.appendChild(document.getElementById('panFormTemplate').content.cloneNode(true));
      host.dataset.rendered = 'true';
    }
  });
}
async function handlePanSubmit(e){
  e.preventDefault();
  try{ const r = await api('/pan-applications', {method:'POST', body:{type:'CSF PAN', applicant_name:'CSF Applicant', form_data:{documents:uploadedDocs}}});
    showToast('Application Submitted', r.message, 'success'); goTo('pan-status');
  }catch(err){ showToast('Submission Failed', err.message, 'danger'); }
}

let newPanFormInitialized = false;
async function initNewPanForm(){
  if(newPanFormInitialized) return;
  newPanFormInitialized = true;
  await populateStateSelect('npAddrState');
  await populateStateSelect('aoStateSelect');
  await populateStateSelect('npRepState');
  initPanStepper();
  onApplicantTypeChange();
}
let STATES_CACHE = null;
async function populateStateSelect(selectId){
  const sel = document.getElementById(selectId);
  if(!sel) return;
  if(!STATES_CACHE){ try{ STATES_CACHE = await api('/states'); }catch(e){ STATES_CACHE = []; } }
  STATES_CACHE.forEach(state=>{ const opt = document.createElement('option'); opt.value = state; opt.textContent = state; sel.appendChild(opt); });
  sel.value = '';
}
function onApplicantTypeChange(){
  const isMinor = document.querySelector('input[name="applicantType"]:checked').value === 'minor';
  document.getElementById('npSec-representative-wrap').classList.toggle('open', isMinor);
  document.getElementById('stepRepWrap').style.display = isMinor ? 'flex' : 'none';
  document.getElementById('npApplicantTypeDisplay').value = isMinor ? 'Minor Applicant' : 'Major Applicant';
  document.querySelectorAll('.rep-field[data-rep-required="1"]').forEach(f=>{ f.required = isMinor; });
}
async function onAoStateChange(){
  const state = document.getElementById('aoStateSelect').value;
  const citySel = document.getElementById('aoCitySelect');
  citySel.innerHTML = '<option value="">Select City</option>';
  document.getElementById('aoWardSection').style.display = 'none';
  clearAoFields();
  if(!state){ citySel.disabled = true; citySel.innerHTML = '<option value="">Select State First</option>'; return; }
  citySel.disabled = false;
  try{ const cities = await api('/cities?state='+encodeURIComponent(state));
    cities.forEach(c=>{ const opt = document.createElement('option'); opt.value = c; opt.textContent = c; citySel.appendChild(opt); });
  }catch(e){}
}
async function onAoCityChange(){
  const state = document.getElementById('aoStateSelect').value;
  const city = document.getElementById('aoCitySelect').value;
  clearAoFields();
  if(!city){ document.getElementById('aoWardSection').style.display = 'none'; return; }
  document.getElementById('aoWardSection').style.display = 'block';
  document.getElementById('aoWardTableBody').innerHTML = `<tr><td colspan="7" class="text-center text-soft py-3" style="font-size:.82rem;"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading AO codes for ${city}...</td></tr>`;
  try{ const wards = await api('/ao-codes?city='+encodeURIComponent(city)+'&state='+encodeURIComponent(state));
    if(!wards.length){ document.getElementById('aoWardTableBody').innerHTML = `<tr><td colspan="7" class="text-center text-soft py-3" style="font-size:.82rem;">No AO codes found for ${city}.</td></tr>`; return; }
    renderAoWardTable(wards);
  }
  catch(e){ document.getElementById('aoWardTableBody').innerHTML = `<tr><td colspan="7" class="text-center text-soft py-3">Failed to load AO codes.</td></tr>`; }
}
function renderAoWardTable(wards){
  const tbody = document.getElementById('aoWardTableBody');
  const categoryBadge = (cat) => { const m = {'Individual':'bd-active','Non-Individual':'bd-pending','Both':'bd-submitted'}; return `<span class="badge-pill ${m[cat]||'bd-pending'}">${cat||'—'}</span>`; };
  tbody.innerHTML = wards.map((w, idx) => `
    <tr class="aoward-row" onclick="selectAoWard(${idx})" id="aoRow-${idx}">
      <td><input type="radio" name="aoWard" id="aoRadio-${idx}" onclick="selectAoWard(${idx})" onchange="selectAoWard(${idx})"></td>
      <td class="fw-semibold">${w.ward}</td><td>${categoryBadge(w.category)}</td><td>${w.area_code}</td><td>${w.ao_type}</td><td>${w.range_code}</td><td>${w.ao_number}</td>
    </tr>`).join('');
  tbody.dataset.wards = JSON.stringify(wards);
}
function selectAoWard(idx){
  const tbody = document.getElementById('aoWardTableBody');
  const wards = JSON.parse(tbody.dataset.wards || '[]');
  const w = wards[idx]; if(!w) return;
  document.querySelectorAll('.aoward-row').forEach(r=>r.classList.remove('selected'));
  document.getElementById('aoRow-'+idx).classList.add('selected');
  document.getElementById('aoRadio-'+idx).checked = true;
  document.getElementById('aoAreaCode').value = w.area_code;
  document.getElementById('aoTypeField').value = w.ao_type;
  document.getElementById('aoRangeCode').value = w.range_code;
  document.getElementById('aoNumberField').value = w.ao_number;
}
function clearAoFields(){ ['aoAreaCode','aoTypeField','aoRangeCode','aoNumberField'].forEach(id=>{ const el = document.getElementById(id); if(el) el.value=''; }); }
function initPanStepper(){
  const steps = document.querySelectorAll('#panStepper .pan-step');
  steps.forEach(step=>{ step.addEventListener('click', ()=>{
    const targetId = step.dataset.target;
    const targetEl = targetId === 'npSec-representative' ? document.getElementById('npSec-representative-wrap') : document.getElementById(targetId);
    if(targetEl) targetEl.scrollIntoView({behavior:'smooth', block:'start'});
  }); });
  const mainEl = document.getElementById('appMain');
  if(mainEl && !mainEl.dataset.panScrollBound){ mainEl.dataset.panScrollBound='true'; mainEl.addEventListener('scroll', updatePanStepperHighlight, {passive:true}); }
  window.addEventListener('scroll', updatePanStepperHighlight, {passive:true});
}
function updatePanStepperHighlight(){
  if(APP.currentView !== 'pan-new') return;
  const steps = document.querySelectorAll('#panStepper .pan-step');
  if(!steps.length) return;
  let activeId = steps[0].dataset.target;
  steps.forEach(step=>{ const targetId = step.dataset.target;
    const targetEl = targetId === 'npSec-representative' ? document.getElementById('npSec-representative-wrap') : document.getElementById(targetId);
    if(targetEl && targetEl.offsetParent !== null){ const rect = targetEl.getBoundingClientRect(); if(rect.top <= 160) activeId = targetId; } });
  steps.forEach(step=>{ step.classList.toggle('active', step.dataset.target === activeId); });
}
async function handleNewPanSubmit(e){
  e.preventDefault();
  const nameEl = document.querySelector('#npSec-applicant input[placeholder*="Full name"]');
  const body = {
    type:'New PAN', applicant_name: (nameEl && nameEl.value) ? nameEl.value : 'New Applicant',
    applicant_type: document.getElementById('npApplicantTypeDisplay').value,
    state: document.getElementById('aoStateSelect').value, city: document.getElementById('aoCitySelect').value,
    area_code: document.getElementById('aoAreaCode').value, ao_type: document.getElementById('aoTypeField').value,
    range_code: document.getElementById('aoRangeCode').value, ao_number: document.getElementById('aoNumberField').value,
    form_data: { documents: uploadedDocs },
  };
  try{ const r = await api('/pan-applications', {method:'POST', body}); showToast('Application Submitted', r.message, 'success'); goTo('pan-status'); }
  catch(err){ showToast('Submission Failed', err.message, 'danger'); }
}

/* ---------------- PAN STATUS ---------------- */
let lastPanData = [];
async function renderPanStatusTable(filter=''){
  const host = document.getElementById('panStatusTableHost');
  if(!host) return;
  try{ lastPanData = await api('/pan-applications'+(filter?'?status='+filter:'')); }catch(err){ showToast('Error', err.message, 'danger'); return; }
  const data = lastPanData;
  const isAdmin = APP.role === 'superadmin';
  function actionsHtml(p){
    let btns = `<button class="row-action-btn" title="View" onclick="showToast('View Application','Viewing ${p.app_id} for ${p.applicant_name}','info')"><i class="fa-regular fa-eye"></i></button>`;
    if(isAdmin){
      btns += `<button class="row-action-btn" title="Delete" onclick="deletePanApplication('${p.app_id}')"><i class="fa-regular fa-trash-can"></i></button>`;
      if(p.status==='Processed' || p.status==='Hold') btns += `<button class="row-action-btn" title="Review" onclick="openPanReviewModal('${p.app_id}')"><i class="fa-solid fa-stamp"></i></button>`;
      if(p.receipt_name) btns += `<button class="row-action-btn" title="Download Receipt" onclick="showToast('Receipt','${p.receipt_name}','info')"><i class="fa-solid fa-download"></i></button>`;
    } else {
      if(p.status==='Hold') btns += `<button class="row-action-btn" title="Edit" onclick="goTo('pan-hold-new')"><i class="fa-regular fa-pen-to-square"></i></button>`;
      if(p.remark) btns += `<button class="row-action-btn" title="View Remark" onclick="viewPanRemark('${p.app_id}')"><i class="fa-regular fa-message"></i></button>`;
      if(p.receipt_name) btns += `<button class="row-action-btn" title="Download Receipt" onclick="showToast('Receipt','${p.receipt_name}','info')"><i class="fa-solid fa-download"></i></button>`;
    }
    return btns;
  }
  let desktop = `<div class="table-responsive d-none d-md-block"><table class="table table-modern mb-0">
    <thead><tr><th>Application ID</th><th>Applicant Name</th><th>PAN Type</th><th>Date</th><th>Status</th><th>Actions</th></tr></thead><tbody>`;
  data.forEach(p=>{ desktop += `<tr><td class="fw-semibold">${p.app_id}</td><td>${p.applicant_name}</td><td>${p.type}</td><td>${p.date}</td>
    <td><span class="badge-pill ${statusBadgeClass(p.status)}">${p.status}</span></td><td><div class="d-flex gap-1">${actionsHtml(p)}</div></td></tr>`; });
  desktop += `</tbody></table></div>`;
  let mobile = `<div class="d-md-none">`;
  data.forEach(p=>{ mobile += `<div class="table-card-mobile"><div class="d-flex justify-content-between align-items-start mb-2"><div>
    <div class="fw-semibold">${p.app_id}</div><div class="text-soft" style="font-size:.78rem;">${p.applicant_name} • ${p.type}</div></div>
    <span class="badge-pill ${statusBadgeClass(p.status)}">${p.status}</span></div>
    <div class="text-soft mb-2" style="font-size:.78rem;">${p.date}</div>
    ${p.status==='Hold' && p.remark ? `<div class="d-flex align-items-start gap-2 mb-2 p-2" style="background:var(--status-hold-bg);border-radius:8px;font-size:.74rem;color:var(--status-hold);"><i class="fa-solid fa-circle-pause mt-1"></i> ${p.remark}</div>` : ''}
    <div class="d-flex gap-2">${actionsHtml(p)}</div></div>`; });
  mobile += `</div>`;
  host.innerHTML = (data.length ? desktop + mobile : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No applications found.</div>`);
}
function filterPanStatus(val){ renderPanStatusTable(val); }
async function deletePanApplication(appId){
  if(!confirm(`Delete ${appId}?`)) return;
  try{ await api('/pan-applications/'+appId, {method:'DELETE'}); showToast('Application Deleted', `${appId} has been removed.`, 'danger'); renderPanStatusTable(); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}
function viewPanRemark(appId){
  const p = lastPanData.find(x=>x.app_id===appId); if(!p) return;
  document.getElementById('panRemarkViewTitle').textContent = `Remark — ${p.app_id}`;
  document.getElementById('panRemarkViewBody').textContent = p.remark || 'No remark provided.';
  new bootstrap.Modal(document.getElementById('panRemarkViewModal')).show();
}
let panReviewSelectedAction = 'Approved';
let panReviewReceiptFile = null;
function openPanReviewModal(appId){
  document.getElementById('panReviewAppId').value = appId;
  document.getElementById('panReviewRemarkInput').value = '';
  panReviewReceiptFile = null;
  document.getElementById('panReviewReceiptLabel').textContent = 'Tap to upload receipt';
  setPanReviewAction('Approved');
  new bootstrap.Modal(document.getElementById('panReviewModal')).show();
}
function setPanReviewAction(action){
  panReviewSelectedAction = action;
  const tabs = {Approved:'panReviewTabAccept', Rejected:'panReviewTabReject', Hold:'panReviewTabHold'};
  Object.entries(tabs).forEach(([key, id])=>{ document.getElementById(id).className = key===action ? 'btn btn-sm flex-grow-1 btn-navy' : 'btn btn-sm flex-grow-1 btn-soft'; });
  const receiptBox = document.getElementById('panReviewReceiptBox');
  const remarkLabel = document.getElementById('panReviewRemarkLabel');
  const remarkHint = document.getElementById('panReviewRemarkHint');
  const title = document.getElementById('panReviewModalTitle');
  if(action === 'Approved'){ receiptBox.style.display='block'; remarkLabel.textContent='Remark (Optional)'; remarkHint.textContent='Receipt upload is mandatory when accepting an application.'; title.textContent='Accept Application'; }
  else if(action === 'Rejected'){ receiptBox.style.display='none'; remarkLabel.innerHTML='Remark <span class="required-star">*</span>'; remarkHint.textContent='Explain why this application is being rejected.'; title.textContent='Reject Application'; }
  else { receiptBox.style.display='none'; remarkLabel.innerHTML='Remark <span class="required-star">*</span>'; remarkHint.textContent='This remark will be shown to the submitter so they can correct it.'; title.textContent='Hold Application'; }
}
function onPanReviewReceiptChosen(input){
  if(input.files && input.files[0]){ panReviewReceiptFile = input.files[0]; document.getElementById('panReviewReceiptLabel').textContent = panReviewReceiptFile.name; }
}
async function submitPanReview(){
  const appId = document.getElementById('panReviewAppId').value;
  const remark = document.getElementById('panReviewRemarkInput').value.trim();
  if(panReviewSelectedAction === 'Approved' && !panReviewReceiptFile){ showToast('Receipt Required', 'Please upload a receipt before accepting.', 'danger'); return; }
  if((panReviewSelectedAction === 'Rejected' || panReviewSelectedAction === 'Hold') && !remark){ showToast('Remark Required', 'Please add a remark.', 'danger'); return; }
  let receipt_name = '';
  try{
    if(panReviewSelectedAction === 'Approved' && panReviewReceiptFile){ const up = await apiUpload(panReviewReceiptFile); receipt_name = up.filename; }
    await api('/pan-applications/'+appId+'/review', {method:'POST', body:{action:panReviewSelectedAction, remark, receipt_name}});
    bootstrap.Modal.getInstance(document.getElementById('panReviewModal'))?.hide();
    const msg = {Approved:`${appId} accepted. Submitter notified.`, Rejected:`${appId} rejected. Submitter notified.`, Hold:`${appId} on hold. Submitter can resubmit.`};
    showToast('Application Updated', msg[panReviewSelectedAction], panReviewSelectedAction==='Approved'?'success':panReviewSelectedAction==='Rejected'?'danger':'warning');
    renderPanStatusTable();
  }catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- WALLET ---------------- */
let rechargeList = [];
async function renderRechargeTable(){
  const host = document.getElementById('rechargeTableHost');
  if(!host) return;
  const isAdmin = APP.role === 'superadmin';
  document.getElementById('rechargeFormCol').style.display = isAdmin ? 'none' : 'block';
  document.getElementById('rechargeTableCol').className = isAdmin ? 'col-12' : 'col-lg-7';
  document.getElementById('rechargeTableTitle').textContent = isAdmin ? 'Pending & Past Recharge Requests' : 'Recharge Requests';
  if(isAdmin){ const [t,s] = VIEW_TITLES['wallet-recharge-admin']; document.getElementById('desktopPageTitle').textContent=t; document.getElementById('desktopPageSub').textContent=s; }
  try{ rechargeList = await api('/wallet/recharge-requests'); }catch(err){ host.innerHTML=''; return; }
  function actionsHtml(r){ if(!isAdmin) return ''; if(r.status !== 'Pending') return `<span class="text-soft" style="font-size:.76rem;">Reviewed</span>`;
    return `<button class="row-action-btn" title="Review" onclick="openRechargeReviewModal('${r.id}')"><i class="fa-regular fa-eye"></i> Review</button>`; }
  let desktop = `<div class="table-responsive d-none d-md-block"><table class="table table-modern mb-0">
    <thead><tr>${isAdmin ? '<th>Submitted By</th>' : ''}<th>Date</th><th>Amount</th><th>UTR Number</th><th>Status</th>${isAdmin ? '<th>Actions</th>' : ''}</tr></thead><tbody>`;
  rechargeList.forEach(r=>{ desktop += `<tr>${isAdmin ? `<td>${r.submittedBy} <span class="text-soft" style="font-size:.76rem;">(${r.userCode})</span></td>` : ''}
    <td>${r.date}</td><td class="fw-semibold">${r.amount}</td><td>${r.utr}</td>
    <td><span class="badge-pill ${statusBadgeClass(r.status)}">${r.status}</span></td>${isAdmin ? `<td>${actionsHtml(r)}</td>` : ''}</tr>`; });
  desktop += `</tbody></table></div>`;
  let mobile = `<div class="d-md-none">`;
  rechargeList.forEach(r=>{ mobile += `<div class="table-card-mobile"><div class="d-flex justify-content-between align-items-start mb-1"><div>
    ${isAdmin ? `<div class="fw-semibold" style="font-size:.85rem;">${r.submittedBy} <span class="text-soft" style="font-size:.74rem;">(${r.userCode})</span></div>` : ''}
    <div class="fw-semibold">${r.amount}</div><div class="text-soft" style="font-size:.76rem;">${r.utr}</div><div class="text-soft" style="font-size:.74rem;">${r.date}</div></div>
    <span class="badge-pill ${statusBadgeClass(r.status)}">${r.status}</span></div>
    ${isAdmin && r.status === 'Pending' ? `<button class="row-action-btn w-100 mt-2" onclick="openRechargeReviewModal('${r.id}')"><i class="fa-regular fa-eye me-1"></i> Review</button>` : ''}</div>`; });
  mobile += `</div>`;
  host.innerHTML = (rechargeList.length ? desktop + mobile : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No recharge requests.</div>`);
}
let rechargeReviewTargetId = null;
function openRechargeReviewModal(id){
  const r = rechargeList.find(x=>x.id===id); if(!r) return;
  rechargeReviewTargetId = id;
  document.getElementById('rechargeReviewId').value = id;
  document.getElementById('rechargeReviewSubmitter').textContent = `${r.submittedBy} (${r.userCode})`;
  document.getElementById('rechargeReviewAmount').textContent = r.amount;
  document.getElementById('rechargeReviewUtr').textContent = r.utr;
  new bootstrap.Modal(document.getElementById('rechargeReviewModal')).show();
}
async function reviewRechargeRequest(decision){
  try{ await api('/wallet/recharge-requests/'+rechargeReviewTargetId+'/review', {method:'POST', body:{decision}});
    bootstrap.Modal.getInstance(document.getElementById('rechargeReviewModal'))?.hide();
    showToast(decision==='Approved'?'Recharge Approved':'Recharge Rejected', `Request ${decision.toLowerCase()}.${decision==='Approved'?' Wallet credited.':''}`, decision==='Approved'?'success':'danger');
    renderRechargeTable();
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function handleRechargeSubmit(e){
  e.preventDefault();
  const inputs = e.target.querySelectorAll('input');
  const amount = parseFloat(inputs[0].value); const utr = inputs[1].value;
  try{ await api('/wallet/recharge', {method:'POST', body:{amount, utr}}); showToast('Recharge Request Submitted', 'Your request has been sent for approval.', 'success'); e.target.reset(); renderRechargeTable(); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}
async function renderWalletHistoryTable(filter=''){
  const host = document.getElementById('walletHistoryTableHost');
  if(!host) return;
  let data = [];
  try{ data = await api('/wallet/transactions'+(filter?'?filter='+filter:'')); }catch(err){ host.innerHTML=''; return; }
  let desktop = `<div class="table-responsive d-none d-md-block"><table class="table table-modern mb-0">
    <thead><tr><th>Date</th><th>Transaction ID</th><th>Credit</th><th>Debit</th><th>Balance</th><th>Remarks</th></tr></thead><tbody>`;
  data.forEach(t=>{ desktop += `<tr><td>${t.date}</td><td class="fw-semibold">${t.txnId}</td>
    <td class="${t.credit!=='-'?'text-success fw-semibold':'text-soft'}">${t.credit}</td>
    <td class="${t.debit!=='-'?'text-danger fw-semibold':'text-soft'}">${t.debit}</td>
    <td class="fw-semibold">${t.balance}</td><td class="text-soft" style="font-size:.82rem;">${t.remarks}</td></tr>`; });
  desktop += `</tbody></table></div>`;
  let mobile = `<div class="d-md-none">`;
  data.forEach(t=>{ const isCredit = t.credit!=='-'; mobile += `<div class="table-card-mobile"><div class="d-flex justify-content-between align-items-start mb-1">
    <div class="fw-semibold" style="font-size:.85rem;">${t.txnId}</div><span class="badge-pill ${isCredit?'bd-credit':'bd-debit'}">${isCredit?'+'+t.credit:'-'+t.debit}</span></div>
    <div class="text-soft" style="font-size:.78rem;">${t.remarks}</div>
    <div class="d-flex justify-content-between mt-1"><span class="text-soft" style="font-size:.74rem;">${t.date}</span><span class="fw-semibold" style="font-size:.78rem;">Bal: ${t.balance}</span></div></div>`; });
  mobile += `</div>`;
  host.innerHTML = (data.length ? desktop + mobile : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No transactions yet.</div>`);
}
function filterWalletHistory(val){ renderWalletHistoryTable(val); }

/* ---------------- RATE SETUP ---------------- */
async function renderRateSetup(){
  const tbody = document.getElementById('rateSetupTableBody');
  if(!tbody) return;
  try{ const s = await api('/settings'); const pricing = s.pricing || {};
    tbody.innerHTML = Object.entries(pricing).map(([name, val]) => `<tr><td class="fw-semibold">${name}</td><td>₹${Number(val).toFixed(2)}</td>
      <td><button class="row-action-btn" onclick="editRate('${name}', ${val})"><i class="fa-regular fa-pen-to-square"></i></button></td></tr>`).join('');
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function editRate(serviceName, current){
  const val = prompt(`New charge for ${serviceName} (₹)`, current);
  if(val === null) return;
  const amount = parseFloat(val); if(isNaN(amount)){ showToast('Invalid', 'Enter a valid number.', 'danger'); return; }
  try{ const s = await api('/settings'); const pricing = {...(s.pricing||{}), [serviceName]: amount};
    await api('/settings', {method:'PUT', body:{pricing}}); showToast('Rate Updated', `${serviceName} charge set to ₹${amount.toFixed(2)}.`, 'success'); renderRateSetup();
  }catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- ADMIN SETTINGS (SMTP / FTP) ---------------- */
function _v(id){ const el = document.getElementById(id); return el ? el.value.trim() : ''; }
async function renderSettingsForms(){
  try{
    const s = await api('/settings');
    const smtp = s.smtp || {}; const ftp = s.ftp || {};
    document.getElementById('smtpHost').value = smtp.host || '';
    document.getElementById('smtpPort').value = smtp.port || '';
    document.getElementById('smtpFrom').value = smtp.from_email || '';
    document.getElementById('smtpUser').value = smtp.username || '';
    document.getElementById('smtpPass').value = smtp.password || '';
    document.getElementById('ftpHost').value = ftp.host || '';
    document.getElementById('ftpPort').value = ftp.port || '';
    document.getElementById('ftpBase').value = ftp.base_path || '';
    document.getElementById('ftpUser').value = ftp.username || '';
    document.getElementById('ftpPass').value = ftp.password || '';
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function saveSmtpSettings(e){
  e.preventDefault();
  const smtp = { host:_v('smtpHost'), port:parseInt(document.getElementById('smtpPort').value)||0, from_email:_v('smtpFrom'), username:_v('smtpUser'), password:_v('smtpPass') };
  try{ await api('/settings', {method:'PUT', body:{smtp}}); showToast('Settings Saved', 'SMTP / email settings updated.', 'success'); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}
async function saveFtpSettings(e){
  e.preventDefault();
  const ftp = { host:_v('ftpHost'), port:parseInt(document.getElementById('ftpPort').value)||0, base_path:_v('ftpBase'), username:_v('ftpUser'), password:_v('ftpPass') };
  try{ await api('/settings', {method:'PUT', body:{ftp}}); showToast('Settings Saved', 'FTP / document storage settings updated.', 'success'); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- SUPPORT TICKETS ---------------- */
let ticketList = [];
async function renderTicketList(){
  const host = document.getElementById('ticketListHost');
  if(!host) return;
  const isAdmin = APP.role === 'superadmin';
  const createCol = document.getElementById('ticketCreateCol');
  const listCol = document.getElementById('ticketListCol');
  if(createCol && listCol){
    createCol.style.display = isAdmin ? 'none' : 'block';
    listCol.className = isAdmin ? 'col-12' : 'col-lg-7';
  }
  const titleEl = document.querySelector('#ticketListCol .section-title');
  if(titleEl) titleEl.textContent = isAdmin ? 'All Support Tickets' : 'My Tickets';
  try{ ticketList = await api('/tickets'); }catch(err){ host.innerHTML=''; return; }
  host.innerHTML = ticketList.length ? ticketList.map(t => `
    <div class="table-card-mobile" style="cursor:pointer;" onclick="openTicketChat('${t.id}')">
      <div class="d-flex justify-content-between align-items-start mb-1"><div class="fw-semibold" style="font-size:.88rem;">${t.id} — ${t.subject}</div>
        <span class="badge-pill ${statusBadgeClass(t.status)}">${t.status}</span></div>
      <div class="d-flex gap-3 text-soft" style="font-size:.76rem;"><span><i class="fa-regular fa-folder me-1"></i>${t.category}</span>
        <span><i class="fa-solid fa-flag me-1"></i>${t.priority}</span><span><i class="fa-regular fa-calendar me-1"></i>${t.date}</span></div>
    </div>`).join('') : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No tickets yet.</div>`;
}
async function openTicketChat(id){
  let t = null;
  try{ t = await api('/tickets/'+id); }catch(err){ showToast('Error', err.message, 'danger'); return; }
  document.getElementById('ticketChatTitle').textContent = id + ' — ' + t.subject;
  document.getElementById('ticketChatId').value = id;
  const body = document.getElementById('ticketChatBody');
  body.innerHTML = (t.messages||[]).map(m => `<div class="chat-bubble ${m.sender_role===APP.role?'me':''}">${m.text}</div>`).join('');
  const resolveBtn = document.getElementById('ticketResolveBtn');
  resolveBtn.style.display = (APP.role === 'superadmin' && t.status !== 'Closed') ? 'inline-block' : 'none';
  new bootstrap.Modal(document.getElementById('ticketChatModal')).show();
  body.scrollTop = body.scrollHeight;
}
async function markTicketResolved(){
  const id = document.getElementById('ticketChatId').value;
  try{ await api('/tickets/'+id+'/resolve', {method:'POST'}); bootstrap.Modal.getInstance(document.getElementById('ticketChatModal'))?.hide();
    showToast('Ticket Resolved', `${id} marked as resolved.`, 'success'); renderTicketList();
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function sendTicketReply(){
  const input = document.getElementById('ticketReplyInput');
  const id = document.getElementById('ticketChatId').value;
  if(!input.value.trim()) return;
  const text = input.value;
  const body = document.getElementById('ticketChatBody');
  const bubble = document.createElement('div'); bubble.className = 'chat-bubble me'; bubble.textContent = text;
  body.appendChild(bubble); body.scrollTop = body.scrollHeight; input.value = '';
  try{ await api('/tickets/'+id+'/reply', {method:'POST', body:{text}}); }catch(err){ showToast('Error', err.message, 'danger'); }
}
async function handleTicketSubmit(e){
  e.preventDefault();
  const subject = e.target.querySelector('input').value;
  const selects = e.target.querySelectorAll('select');
  const category = selects[0].value; const priority = selects[1].value;
  const message = e.target.querySelector('textarea').value;
  try{ await api('/tickets', {method:'POST', body:{subject, category, priority, message}}); showToast('Ticket Raised', 'Your support ticket has been created.', 'success'); e.target.reset(); renderTicketList(); }
  catch(err){ showToast('Error', err.message, 'danger'); }
}

/* ---------------- NOTIFICATIONS ---------------- */
async function renderNotificationsList(){
  const host = document.getElementById('notificationsListHost');
  if(!host) return;
  let items = [];
  try{ items = await api('/notifications'); }catch(err){ host.innerHTML=''; return; }
  host.innerHTML = items.length ? items.map(n => `
    <div class="d-flex align-items-start gap-3 py-2" style="border-bottom:1px solid var(--line);">
      <div class="stat-icon" style="width:38px;height:38px;font-size:.9rem;background:${n.bg};color:${n.color};flex-shrink:0;margin-bottom:0;"><i class="fa-solid ${n.icon}"></i></div>
      <div class="flex-grow-1"><div style="font-size:.87rem;font-weight:600;">${n.title}</div><div class="text-soft" style="font-size:.78rem;">${n.detail}</div></div>
      <div class="text-soft text-end" style="font-size:.72rem;white-space:nowrap;">${n.time}</div>
    </div>`).join('') : `<div class="text-soft text-center py-4" style="font-size:.88rem;">No notifications.</div>`;
}

/* ---------------- PROFILE / CERTIFICATE ---------------- */
function renderPersonalCertificate(){
  if(!APP.user) return;
  document.getElementById('certHolderName').textContent = APP.user.name;
  document.getElementById('certHolderRole').textContent = APP.user.role_label + ' Certificate';
  document.getElementById('certHolderId').textContent = 'ID: ' + APP.user.user_code;
}
function renderPersonalProfile(){
  if(!APP.user) return;
  document.getElementById('profileNameDisplay').textContent = APP.user.name;
  document.getElementById('profileRoleDisplay').textContent = APP.user.role_label + ' • ' + APP.user.user_code;
}

/* ---------------- ROUTER (/ = homepage, anything else = web app) ---------------- */
function showLandingOnly(){
  const lp = document.getElementById('landingRoot'); if(lp) lp.style.display = 'block';
  document.getElementById('authRoot').style.display = 'none';
  document.getElementById('appShell').style.display = 'none';
  window.scrollTo({top:0});
}
function showAuthOnly(){
  const lp = document.getElementById('landingRoot'); if(lp) lp.style.display = 'none';
  document.getElementById('appShell').style.display = 'none';
  document.getElementById('authRoot').style.display = 'block';
}
async function route(){
  const path = location.pathname;
  if(path.startsWith('/dev')){ showDevOnly(); return; }
  if(path === '/' || path === ''){ showLandingOnly(); return; }
  const t = localStorage.getItem('gps_token');
  if(t){
    try{ const u = await api('/auth/me'); APP.user = u; APP.role = u.role; enterApp(); return; }
    catch(e){ localStorage.removeItem('gps_token'); }
  }
  showAuthOnly();
  showAuthView('login');
}
function navigateTo(path){ history.pushState({}, '', path); route(); }
function goToLogin(){ navigateTo('/login'); }
function goToRegister(){ history.pushState({}, '', '/login'); showAuthOnly(); showAuthView('register'); }

/* ---------------- DEVELOPER CONSOLE (hidden /developer page) ---------------- */
async function devApi(path, {method='GET', body=null}={}){
  const t = localStorage.getItem('gps_dev_token');
  const opts = { method, headers:{'Content-Type':'application/json', ...(t ? {'Authorization':'Bearer '+t} : {})} };
  if(body) opts.body = JSON.stringify(body);
  const res = await fetch('/api'+path, opts);
  let data = null; try{ data = await res.json(); }catch(e){}
  if(!res.ok){ if(res.status === 401){ localStorage.removeItem('gps_dev_token'); } throw new Error((data && data.detail) || 'Request failed'); }
  return data;
}
function showDevOnly(){
  ['landingRoot','authRoot','appShell'].forEach(id=>{ const e = document.getElementById(id); if(e) e.style.display='none'; });
  const dev = document.getElementById('devRoot'); if(dev) dev.style.display='flex';
  const t = localStorage.getItem('gps_dev_token');
  if(t){ document.getElementById('devLoginCard').style.display='none'; document.getElementById('devPanel').style.display='block'; loadDevAdmin(); }
  else { document.getElementById('devLoginCard').style.display='block'; document.getElementById('devPanel').style.display='none'; }
}
async function devLogin(e){
  e.preventDefault();
  const username = document.getElementById('devUsername').value.trim();
  const password = document.getElementById('devPassword').value;
  try{
    const data = await devApi('/dev/login', {method:'POST', body:{username, password}});
    localStorage.setItem('gps_dev_token', data.token);
    document.getElementById('devLoginCard').style.display='none';
    document.getElementById('devPanel').style.display='block';
    await loadDevAdmin();
    showToast('Console Unlocked', 'Welcome, developer.', 'success');
  }catch(err){ showToast('Access Denied', err.message, 'danger'); }
}
async function loadDevAdmin(){
  try{ const a = await devApi('/dev/admin');
    document.getElementById('devCurrentAdminId').textContent = a.user_id;
    document.getElementById('devNewUserId').value = a.user_id;
  }catch(err){ showDevOnly(); }
}
async function saveAdminCreds(e){
  e.preventDefault();
  const user_id = document.getElementById('devNewUserId').value.trim();
  const password = document.getElementById('devNewPassword').value;
  if(!user_id){ showToast('Required', 'Admin Login ID is required.', 'warning'); return; }
  const body = { user_id }; if(password) body.password = password;
  try{
    const r = await devApi('/dev/admin', {method:'POST', body});
    document.getElementById('devCurrentAdminId').textContent = r.user_id;
    document.getElementById('devNewPassword').value = '';
    showToast('Saved', r.message + ' New Login ID: ' + r.user_id, 'success');
  }catch(err){ showToast('Error', err.message, 'danger'); }
}
function devLogout(){
  localStorage.removeItem('gps_dev_token');
  document.getElementById('devLoginCard').style.display='block';
  document.getElementById('devPanel').style.display='none';
  document.getElementById('devUsername').value='';
  document.getElementById('devPassword').value='';
  showToast('Locked', 'Developer console locked.', 'info');
}

/* ---------------- BOOT ---------------- */
window.addEventListener('DOMContentLoaded', ()=>{ route(); });
window.addEventListener('popstate', ()=>{ route(); });
