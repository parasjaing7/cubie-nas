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
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${u[i]}`;
}

function fmtUptime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

async function loadGeneralPage() {
  const g = await api('/api/system/general-info');
  const d = g.data;
  document.getElementById('g-model').textContent = d.model || '-';
  document.getElementById('g-hostname').textContent = d.hostname || '-';
  document.getElementById('g-os').textContent = d.os || '-';
  document.getElementById('g-arch').textContent = d.arch || '-';
  document.getElementById('g-cpu-model').textContent = d.cpu_model || '-';
  document.getElementById('g-cpu-cores').textContent = `${d.cpu_cores_physical} physical / ${d.cpu_cores_logical} logical`;
  document.getElementById('g-ram-total').textContent = `${d.ram_total_mb} MB`;
  document.getElementById('g-temp').textContent = d.temperature_c ? `${d.temperature_c.toFixed(1)} C` : 'N/A';

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${proto}://${location.host}/api/monitor/ws`);
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    document.getElementById('live-cpu').textContent = `${m.cpu_percent}%`;
    document.getElementById('live-ram').textContent = `${m.ram_used_mb}/${m.ram_total_mb} MB`;
    document.getElementById('live-rx').textContent = `${fmtBytes(m.net_rx_bps)}/s`;
    document.getElementById('live-tx').textContent = `${fmtBytes(m.net_tx_bps)}/s`;
    document.getElementById('live-up').textContent = fmtUptime(m.uptime_seconds);
  };
  ws.onclose = () => {
    document.getElementById('top-status').textContent = 'Reconnecting...';
    setTimeout(loadGeneralPage, 2000);
  };
}

async function loadStoragePage() {
  const res = await api('/api/storage/drives');
  const body = document.getElementById('storage-body');
  body.innerHTML = '';
  res.data.forEach((d) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${d.name || '-'}</td><td>${d.device}</td><td>${d.fstype || '-'}</td><td>${d.mountpoint || '-'}</td><td>${fmtBytes(d.used_bytes)}</td><td>${fmtBytes(d.free_bytes)}</td><td>${d.smart_status || '-'}</td>`;
    body.appendChild(tr);
  });
}

async function loadNetworkPage() {
  const res = await api('/api/network/current');
  const d = res.data;
  document.getElementById('n-current-iface').textContent = d.interface || '-';
  document.getElementById('n-current-ip').textContent = d.ip_address || '-';
  document.getElementById('n-current-gw').textContent = d.gateway || '-';
  document.getElementById('n-current-dns').textContent = d.dns || '-';

  document.getElementById('n-iface').value = d.interface || '';
  document.getElementById('n-address').value = d.ip_address || '';
  document.getElementById('n-gateway').value = d.gateway || '';
  document.getElementById('n-dns').value = d.dns || '';
}

async function saveNetworkSettings(ev) {
  ev.preventDefault();
  const payload = {
    interface: document.getElementById('n-iface').value,
    mode: document.getElementById('n-mode').value,
    address: document.getElementById('n-address').value || null,
    gateway: document.getElementById('n-gateway').value || null,
    dns: document.getElementById('n-dns').value || null,
  };
  const msg = document.getElementById('network-msg');
  try {
    const res = await api('/api/network/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    msg.textContent = res.message;
    await loadNetworkPage();
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function loadNasPage() {
  const res = await api('/api/services/list');
  const smb = (res.data || []).find((s) => s.service === 'samba');
  document.getElementById('smb-enabled').textContent = smb ? (smb.enabled ? 'Yes' : 'No') : 'Unavailable';
  document.getElementById('smb-active').textContent = smb ? (smb.active ? 'Running' : 'Stopped') : 'Unavailable';
}

async function smbAction(action) {
  const msg = document.getElementById('smb-msg');
  msg.textContent = '';
  try {
    const res = await api(`/api/services/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'samba' }),
    });
    msg.textContent = res.message;
    await loadNasPage();
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function loadUsbDevices() {
  const msg = document.getElementById('usb-msg');
  const body = document.getElementById('usb-body');
  const sel = document.getElementById('usb-device');
  body.innerHTML = '';
  sel.innerHTML = '';

  try {
    const res = await api('/api/storage/drives');
    const usb = (res.data || []).filter((d) => d.is_usb || d.transport === 'usb');
    if (usb.length === 0) {
      msg.textContent = 'No USB drives detected.';
      return;
    }

    usb.forEach((d) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.device}</td><td>${d.model || '-'}</td><td>${d.fstype || '-'}</td><td>${d.size || '-'}</td><td>${d.mountpoint || '-'}</td>`;
      body.appendChild(tr);

      const op = document.createElement('option');
      op.value = d.device;
      op.textContent = `${d.device} (${d.size || '-'})`;
      sel.appendChild(op);
    });
    msg.textContent = `${usb.length} USB device(s) detected.`;
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function provisionUsbShare(ev) {
  ev.preventDefault();
  const msg = document.getElementById('usb-msg');
  const format = document.getElementById('usb-format').checked;
  const device = document.getElementById('usb-device').value;
  const shareName = document.getElementById('usb-share-name').value.trim();
  const mountpoint = document.getElementById('usb-mountpoint').value.trim();
  const fsType = document.getElementById('usb-fstype').value;

  if (!device || !shareName) {
    msg.textContent = 'Device and share name are required.';
    return;
  }

  if (format) {
    const ok = confirm(`This will ERASE all data on ${device}. Continue?`);
    if (!ok) {
      return;
    }
  }

  const payload = {
    device: device,
    share_name: shareName,
    mountpoint: mountpoint || null,
    format_before_mount: format,
    fs_type: format ? fsType : null,
  };

  try {
    const res = await api('/api/storage/usb/provision-smb', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    msg.textContent = `${res.message} | Share path: \\\\${location.hostname}\\\\${payload.share_name}`;
    await loadUsbDevices();
    await loadNasPage();
  } catch (err) {
    msg.textContent = err.message;
  }
}

document.getElementById('theme-toggle').addEventListener('click', () => {
  document.body.classList.toggle('dark');
  localStorage.setItem('theme-dark', document.body.classList.contains('dark') ? '1' : '0');
});

document.getElementById('logout-btn').addEventListener('click', async () => {
  await api('/api/auth/logout', { method: 'POST' });
  location.href = '/';
});

if (localStorage.getItem('theme-dark') === '1') {
  document.body.classList.add('dark');
}

const page = document.body.getAttribute('data-page');
if (page === 'general') {
  loadGeneralPage();
}
if (page === 'storage') {
  loadStoragePage();
}
if (page === 'network') {
  loadNetworkPage();
  document.getElementById('network-form').addEventListener('submit', saveNetworkSettings);
}
if (page === 'nas') {
  loadNasPage();
  loadUsbDevices();
  document.getElementById('usb-share-form').addEventListener('submit', provisionUsbShare);
}
