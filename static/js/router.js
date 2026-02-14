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

const provisionState = {
  steps: [],
  statuses: [],
  current: -1,
  startedAt: null,
  elapsedTimer: null,
  progressTimer: null,
};

function renderProvisionSteps() {
  const list = document.getElementById('provision-steps');
  if (!list) return;
  list.innerHTML = '';
  provisionState.steps.forEach((step, i) => {
    const st = provisionState.statuses[i] || 'pending';
    const label = st === 'done' ? '[DONE]' : st === 'running' ? '[WAIT]' : st === 'error' ? '[ERR]' : '[PEND]';
    const li = document.createElement('li');
    li.textContent = `${label} ${step}`;
    list.appendChild(li);
  });
}

function setProvisionElapsed() {
  const el = document.getElementById('provision-elapsed');
  if (!el || !provisionState.startedAt) return;
  const sec = Math.max(0, Math.floor((Date.now() - provisionState.startedAt) / 1000));
  el.textContent = `${sec}s`;
}

function setProvisionCurrent(index) {
  provisionState.current = index;
  provisionState.statuses = provisionState.statuses.map((s, i) => {
    if (i < index) return s === 'error' ? 'error' : 'done';
    if (i === index) return 'running';
    return s === 'error' ? 'error' : 'pending';
  });
  renderProvisionSteps();
}

function startProvisionProgress(operation, steps) {
  const op = document.getElementById('provision-op');
  const summary = document.getElementById('provision-summary');
  if (op) op.textContent = operation;
  if (summary) summary.textContent = 'Operation started. Waiting for server-side steps to complete.';

  provisionState.steps = steps.slice();
  provisionState.statuses = steps.map(() => 'pending');
  provisionState.current = 0;
  provisionState.startedAt = Date.now();

  if (provisionState.elapsedTimer) clearInterval(provisionState.elapsedTimer);
  if (provisionState.progressTimer) clearInterval(provisionState.progressTimer);

  setProvisionCurrent(0);
  setProvisionElapsed();

  provisionState.elapsedTimer = setInterval(setProvisionElapsed, 1000);
  provisionState.progressTimer = setInterval(() => {
    if (provisionState.current < 0) return;
    if (provisionState.current < provisionState.steps.length - 1) {
      setProvisionCurrent(provisionState.current + 1);
    }
  }, 6000);
}

function completeProvisionSuccess(message) {
  const op = document.getElementById('provision-op');
  const summary = document.getElementById('provision-summary');
  provisionState.statuses = provisionState.statuses.map(() => 'done');
  provisionState.current = provisionState.steps.length - 1;
  renderProvisionSteps();
  if (summary) summary.textContent = message || 'Completed successfully.';
  if (op) op.textContent = 'Completed';
  if (provisionState.elapsedTimer) clearInterval(provisionState.elapsedTimer);
  if (provisionState.progressTimer) clearInterval(provisionState.progressTimer);
}

function completeProvisionError(message) {
  const op = document.getElementById('provision-op');
  const summary = document.getElementById('provision-summary');
  if (provisionState.current >= 0 && provisionState.current < provisionState.statuses.length) {
    provisionState.statuses[provisionState.current] = 'error';
  }
  renderProvisionSteps();
  if (summary) summary.textContent = message || 'Operation failed.';
  if (op) op.textContent = 'Failed';
  if (provisionState.elapsedTimer) clearInterval(provisionState.elapsedTimer);
  if (provisionState.progressTimer) clearInterval(provisionState.progressTimer);
}

function buildProvisionSteps(payload) {
  const steps = ['Validate request'];
  if (payload.wipe_repartition) {
    steps.push('Wipe existing partitions');
    steps.push('Create GPT + one partition');
  }
  if (payload.format_before_mount || payload.wipe_repartition) {
    steps.push(`Format filesystem (${payload.fs_type || 'ext4'})`);
  }
  steps.push('Mount filesystem');
  steps.push('Publish SMB share');
  steps.push('Refresh NAS view');
  return steps;
}

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms)),
  ]);
}

async function refreshNasUiAfterProvision(type) {
  const tasks = [withTimeout(loadNasPage(), 8000, 'NAS service refresh')];
  if (type === 'usb') {
    tasks.push(withTimeout(loadUsbDevices(), 8000, 'USB device refresh'));
  }
  if (type === 'nvme') {
    tasks.push(withTimeout(loadNvmeDevices(), 8000, 'NVMe device refresh'));
  }

  const results = await Promise.allSettled(tasks);
  const errors = results
    .filter((r) => r.status === 'rejected')
    .map((r) => r.reason && r.reason.message ? r.reason.message : String(r.reason));

  return {
    ok: errors.length === 0,
    warning: errors.length > 0 ? `Operation completed, but UI refresh had issues: ${errors.join(' | ')}` : '',
  };
}

function updateWipeUi(prefix) {
  const wipe = document.getElementById(`${prefix}-wipe`);
  const wrap = document.getElementById(`${prefix}-wipe-confirm-wrap`);
  const dev = document.getElementById(`${prefix}-device`);
  const confirm = document.getElementById(`${prefix}-wipe-confirm`);
  if (!wipe || !wrap || !dev || !confirm) return;

  wrap.style.display = wipe.checked ? 'block' : 'none';
  confirm.placeholder = `WIPE ${dev.value || '/dev/...'} `;
}

function initWipeUi(prefix) {
  const wipe = document.getElementById(`${prefix}-wipe`);
  const dev = document.getElementById(`${prefix}-device`);
  if (!wipe || !dev) return;
  wipe.addEventListener('change', () => updateWipeUi(prefix));
  dev.addEventListener('change', () => updateWipeUi(prefix));
  updateWipeUi(prefix);
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
  const [curRes, stateRes] = await Promise.all([
    api('/api/network/current'),
    api('/api/network/state').catch(() => ({ data: null })),
  ]);

  const d = curRes.data || {};
  const st = stateRes.data || {};

  const curIface = document.getElementById('n-current-iface');
  const curIp = document.getElementById('n-current-ip');
  const curGw = document.getElementById('n-current-gw');
  const curDns = document.getElementById('n-current-dns');
  if (curIface) curIface.textContent = d.interface || '-';
  if (curIp) curIp.textContent = d.ip_address || '-';
  if (curGw) curGw.textContent = d.gateway || '-';
  if (curDns) curDns.textContent = d.dns || '-';

  const iface = document.getElementById('n-iface');
  const addr = document.getElementById('n-address');
  const gw = document.getElementById('n-gateway');
  const dns = document.getElementById('n-dns');
  if (iface) iface.value = d.interface || '';
  if (addr) addr.value = d.ip_address || '';
  if (gw) gw.value = d.gateway || '';
  if (dns) dns.value = d.dns || '';

  const ethChip = document.getElementById('eth-chip');
  const ethBody = document.getElementById('eth-scan-body');
  if (ethChip) {
    const ethUp = !!(st.ethernet && st.ethernet.enabled);
    ethChip.textContent = ethUp ? 'UP' : 'DOWN';
    ethChip.className = `status-chip ${ethUp ? 'up' : 'down'}`;
  }
  if (ethBody) {
    ethBody.innerHTML = '';
    const ports = (st.ethernet && Array.isArray(st.ethernet.ports)) ? st.ethernet.ports : [];
    if (ports.length === 0) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="4" class="muted">No ethernet ports detected.</td>';
      ethBody.appendChild(tr);
    } else {
      ports.forEach((p) => {
        const tr = document.createElement('tr');
        const up = !!p.up;
        tr.innerHTML = `<td>${p.name || '-'}</td><td><span class="dot ${up ? 'up' : 'down'}"></span>${p.state || '-'}</td><td>${p.mac || '-'}</td><td>${p.mtu || '-'}</td>`;
        ethBody.appendChild(tr);
      });
    }
  }

  const wifiChip = document.getElementById('wifi-chip');
  if (wifiChip) {
    const wifiUp = !!(st.wifi && st.wifi.enabled);
    wifiChip.textContent = wifiUp ? 'UP' : 'DOWN';
    wifiChip.className = `status-chip ${wifiUp ? 'up' : 'down'}`;
  }

  const btChip = document.getElementById('bt-chip');
  if (btChip) {
    const btUp = !!(st.bluetooth && st.bluetooth.enabled);
    btChip.textContent = btUp ? 'UP' : 'DOWN';
    btChip.className = `status-chip ${btUp ? 'up' : 'down'}`;
  }

  const hotspotChip = document.getElementById('hotspot-chip');
  if (hotspotChip) {
    const hsUp = !!(st.hotspot && st.hotspot.enabled);
    hotspotChip.textContent = hsUp ? 'ON' : 'OFF';
    hotspotChip.className = `status-chip ${hsUp ? 'up' : 'down'}`;
  }

  const hsSsid = document.getElementById('hotspot-ssid');
  const hsPass = document.getElementById('hotspot-password');
  if (hsSsid && st.hotspot) hsSsid.value = st.hotspot.ssid || '';
  if (hsPass && st.hotspot) hsPass.value = st.hotspot.password || '';
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
    updateWipeUi('usb');
  } catch (err) {
    msg.textContent = err.message;
  }
}

async function loadNvmeDevices() {
  const msg = document.getElementById('nvme-msg');
  const body = document.getElementById('nvme-body');
  const sel = document.getElementById('nvme-device');
  body.innerHTML = '';
  sel.innerHTML = '';

  try {
    const res = await api('/api/storage/drives');
    const nvmeAll = (res.data || []).filter((d) => {
      const transport = String(d.transport || '').trim().toLowerCase();
      const device = String(d.device || '').trim().toLowerCase();
      return transport === 'nvme' || device.startsWith('/dev/nvme');
    });

    const nvmeParts = nvmeAll.filter((d) => /\/dev\/nvme\d+n\d+p\d+$/i.test(String(d.device || '')));
    const nvmeDisks = nvmeAll.filter((d) => /\/dev\/nvme\d+n\d+$/i.test(String(d.device || '')));
    const other = nvmeAll.filter((d) => !nvmeParts.includes(d) && !nvmeDisks.includes(d));
    const ordered = [...nvmeParts, ...nvmeDisks, ...other];

    if (ordered.length === 0) {
      msg.textContent = 'No NVMe drives detected.';
      return;
    }

    ordered.forEach((d) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${d.device}</td><td>${d.model || '-'}</td><td>${d.fstype || '-'}</td><td>${d.size || '-'}</td><td>${d.mountpoint || '-'}</td>`;
      body.appendChild(tr);

      const op = document.createElement('option');
      op.value = d.device;
      const suffix = /\/dev\/nvme\d+n\d+p\d+$/i.test(String(d.device || '')) ? 'partition' : 'disk';
      op.textContent = `${d.device} (${d.size || '-'}, ${suffix})`;
      sel.appendChild(op);
    });

    msg.textContent = `${ordered.length} NVMe candidate device(s) detected.`;
    updateWipeUi('nvme');
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
  const wipe = document.getElementById('usb-wipe').checked;
  const wipeConfirm = document.getElementById('usb-wipe-confirm').value.trim();

  if (!device || !shareName) {
    msg.textContent = 'Device and share name are required.';
    return;
  }

  if (wipe) {
    const expected = `WIPE ${device}`;
    if (wipeConfirm !== expected) {
      msg.textContent = `Confirmation mismatch. Type exactly: ${expected}`;
      return;
    }
    const ok = confirm(`This will DELETE all partitions on ${device}, recreate one partition, and format it as ${fsType}. Continue?`);
    if (!ok) {
      return;
    }
  } else if (format) {
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
    fs_type: (format || wipe) ? fsType : null,
    wipe_repartition: wipe,
    wipe_confirmation: wipe ? wipeConfirm : null,
  };

  const steps = buildProvisionSteps(payload);
  startProvisionProgress(`USB Provision (${device})`, steps);

  try {
    const res = await api('/api/storage/usb/provision-smb', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    setProvisionCurrent(Math.max(steps.length - 1, 0));
    const refresh = await refreshNasUiAfterProvision('usb');

    const baseMsg = res.message;
    if (refresh.ok) {
      msg.textContent = baseMsg;
      completeProvisionSuccess(res.message);
    } else {
      msg.textContent = `${baseMsg} | ${refresh.warning}`;
      completeProvisionSuccess(`${res.message} (${refresh.warning})`);
    }
  } catch (err) {
    msg.textContent = err.message;
    completeProvisionError(err.message);
  }
}

async function provisionNvmeShare(ev) {
  ev.preventDefault();
  const msg = document.getElementById('nvme-msg');
  const format = document.getElementById('nvme-format').checked;
  const device = document.getElementById('nvme-device').value;
  const shareName = document.getElementById('nvme-share-name').value.trim();
  const mountpoint = document.getElementById('nvme-mountpoint').value.trim();
  const fsType = document.getElementById('nvme-fstype').value;
  const wipe = document.getElementById('nvme-wipe').checked;
  const wipeConfirm = document.getElementById('nvme-wipe-confirm').value.trim();

  if (!device || !shareName) {
    msg.textContent = 'Device and share name are required.';
    return;
  }

  if (wipe) {
    const expected = `WIPE ${device}`;
    if (wipeConfirm !== expected) {
      msg.textContent = `Confirmation mismatch. Type exactly: ${expected}`;
      return;
    }
    const ok = confirm(`This will DELETE all partitions on ${device}, recreate one partition, and format it as ${fsType}. Continue?`);
    if (!ok) {
      return;
    }
  } else if (format) {
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
    fs_type: (format || wipe) ? fsType : null,
    wipe_repartition: wipe,
    wipe_confirmation: wipe ? wipeConfirm : null,
  };

  const steps = buildProvisionSteps(payload);
  startProvisionProgress(`NVMe Provision (${device})`, steps);

  try {
    const res = await api('/api/storage/nvme/provision-smb', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    setProvisionCurrent(Math.max(steps.length - 1, 0));
    const refresh = await refreshNasUiAfterProvision('nvme');

    const baseMsg = res.message;
    if (refresh.ok) {
      msg.textContent = baseMsg;
      completeProvisionSuccess(res.message);
    } else {
      msg.textContent = `${baseMsg} | ${refresh.warning}`;
      completeProvisionSuccess(`${res.message} (${refresh.warning})`);
    }
  } catch (err) {
    msg.textContent = err.message;
    completeProvisionError(err.message);
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
  loadNvmeDevices();
  initWipeUi('usb');
  initWipeUi('nvme');
  document.getElementById('usb-share-form').addEventListener('submit', provisionUsbShare);
  document.getElementById('nvme-share-form').addEventListener('submit', provisionNvmeShare);
}
