function cookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]+)');
  return m ? m.pop() : '';
}

async function api(url, options = {}) {
  options.headers = options.headers || {};
  if (options.method && options.method !== 'GET') {
    options.headers['X-CSRF-Token'] = cookie('csrf_token');
  }
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

function fmtBytes(v) {
  if (v == null) return '-';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${u[i]}`;
}

function fmtUptime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

function wsMonitor() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/api/monitor/ws`);
  ws.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    document.getElementById('cpu').textContent = `${d.cpu_percent}%`;
    document.getElementById('ram').textContent = `${d.ram_used_mb}/${d.ram_total_mb} MB`;
    document.getElementById('temp').textContent = d.temp_c ? `${d.temp_c.toFixed(1)} C` : 'N/A';
    document.getElementById('rx').textContent = `${fmtBytes(d.net_rx_bps)}/s`;
    document.getElementById('tx').textContent = `${fmtBytes(d.net_tx_bps)}/s`;
    document.getElementById('disk-r').textContent = `${fmtBytes(d.disk_read_bps)}/s`;
    document.getElementById('disk-w').textContent = `${fmtBytes(d.disk_write_bps)}/s`;
    document.getElementById('uptime').textContent = fmtUptime(d.uptime_seconds);
  };
  ws.onclose = () => setTimeout(wsMonitor, 2000);
}

async function loadDrives() {
  const data = await api('/api/storage/drives');
  const tbody = document.querySelector('#drives-table tbody');
  tbody.innerHTML = '';
  data.data.forEach((d) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${d.device}</td><td>${d.fstype || '-'}</td><td>${d.size || '-'}</td><td>${d.mountpoint || '-'}</td><td>${fmtBytes(d.used_bytes)}</td><td>${fmtBytes(d.free_bytes)}</td><td>${d.smart_status || '-'}</td>`;
    tbody.appendChild(tr);
  });
}

async function loadFiles() {
  const path = document.getElementById('path').value;
  const sortBy = document.getElementById('sortBy').value;
  const sortOrder = document.getElementById('sortOrder').value;
  const data = await api(`/api/files/list?path=${encodeURIComponent(path)}&sort_by=${sortBy}&order=${sortOrder}`);
  const tbody = document.querySelector('#files-table tbody');
  tbody.innerHTML = '';
  data.data.forEach((f) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${f.is_dir ? '[DIR]' : '[FILE]'} ${f.name}</td><td>${fmtBytes(f.size)}</td><td>${new Date(f.mtime * 1000).toLocaleString()}</td><td>${
      f.is_dir ? `<button onclick="setPath('${f.path}')">Open</button>` : `<button onclick="window.open('/api/files/download?path=${encodeURIComponent(f.path)}')">Download</button>`
    } <button onclick="renameItem('${f.path}')">Rename</button> <button onclick="deleteItem('${f.path}')">Delete</button></td>`;
    tbody.appendChild(tr);
  });
}

function setPath(p) {
  document.getElementById('path').value = p;
  loadFiles();
}

async function deleteItem(path) {
  if (!confirm(`Delete ${path}?`)) return;
  await api('/api/files/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
  await loadFiles();
}

async function renameItem(path) {
  const newName = prompt('New name:');
  if (!newName) return;
  await api('/api/files/rename', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, new_name: newName })
  });
  await loadFiles();
}

async function createFolder() {
  const path = document.getElementById('path').value;
  const name = document.getElementById('mkdir-name').value;
  await api('/api/files/mkdir', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, name })
  });
  document.getElementById('mkdir-name').value = '';
  await loadFiles();
}

async function uploadFiles(files) {
  const path = document.getElementById('path').value;
  for (const file of files) {
    const fd = new FormData();
    fd.append('file', file);
    await api(`/api/files/upload?path=${encodeURIComponent(path)}`, { method: 'POST', body: fd });
  }
  await loadFiles();
}

async function loadServices() {
  const data = await api('/api/services/list');
  const tbody = document.querySelector('#services-table tbody');
  tbody.innerHTML = '';
  data.data.forEach((s) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${s.service}</td><td>${s.enabled}</td><td>${s.active}</td><td><button onclick="serviceAction('${s.service}','enable')">Enable</button> <button onclick="serviceAction('${s.service}','disable')">Disable</button> <button onclick="serviceAction('${s.service}','restart')">Restart</button></td>`;
    tbody.appendChild(tr);
  });
}

async function serviceAction(service, action) {
  await api(`/api/services/${action}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ service })
  });
  await loadServices();
}

async function createAppUser() {
  await api('/api/users/app', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: document.getElementById('new-user').value,
      password: document.getElementById('new-pass').value,
      role: document.getElementById('new-role').value
    })
  });
  alert('App user created');
}

async function createSystemUser() {
  await api('/api/users/system/create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: document.getElementById('sys-user').value,
      password: document.getElementById('sys-pass').value,
      role: 'user'
    })
  });
  alert('System user created');
}

async function loadSessions() {
  const data = await api('/api/users/sessions');
  document.getElementById('sessions-box').textContent = JSON.stringify(data.data, null, 2);
}

async function generateTLS() {
  const data = await api('/api/system/tls/generate', { method: 'POST' });
  document.getElementById('security-box').textContent = data.message;
}

async function showFirewallCmds() {
  const data = await api('/api/system/firewall/commands');
  document.getElementById('security-box').textContent = data.data.join('\n');
}

async function applyFirewall() {
  const data = await api('/api/system/firewall/apply', { method: 'POST' });
  document.getElementById('security-box').textContent = data.message;
}

async function listDocker() {
  const data = await api('/api/bonus/docker/containers');
  document.getElementById('bonus-box').textContent = JSON.stringify(data.data, null, 2);
}

async function runBackup() {
  const src = document.getElementById('backup-src').value;
  const dst = document.getElementById('backup-dst').value;
  const data = await api(`/api/bonus/backup/run?src=${encodeURIComponent(src)}&dst=${encodeURIComponent(dst)}`, { method: 'POST' });
  document.getElementById('bonus-box').textContent = data.message;
}

async function listPlugins() {
  const data = await api('/api/bonus/plugins');
  document.getElementById('bonus-box').textContent = JSON.stringify(data.data, null, 2);
}

document.getElementById('logout-btn').addEventListener('click', async () => {
  await api('/api/auth/logout', { method: 'POST' });
  location.href = '/';
});

document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('dark');
  localStorage.setItem('theme-dark', document.body.classList.contains('dark') ? '1' : '0');
});

if (localStorage.getItem('theme-dark') === '1') {
  document.body.classList.add('dark');
}

const dz = document.getElementById('drop-zone');
dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.style.opacity = 0.7; });
dz.addEventListener('dragleave', () => { dz.style.opacity = 1; });
dz.addEventListener('drop', async (e) => {
  e.preventDefault();
  dz.style.opacity = 1;
  await uploadFiles(e.dataTransfer.files);
});

wsMonitor();
loadDrives();
loadFiles();
loadServices();
