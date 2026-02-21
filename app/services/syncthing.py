from __future__ import annotations

import asyncio
import json
import socket
from urllib import request

SYNCTHING_PORT = 8384
SYNCTHING_STATUS_URL = f'http://127.0.0.1:{SYNCTHING_PORT}/rest/system/status'
LEARN_MORE_URL = 'https://syncthing.net/'


def _port_open(host: str = '127.0.0.1', port: int = SYNCTHING_PORT, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _fetch_status_json(url: str = SYNCTHING_STATUS_URL, timeout: float = 1.5) -> dict:
    req = request.Request(url, method='GET')
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8', errors='ignore')
    return json.loads(body) if body else {}


def _truncate_device_id(value: str) -> str:
    raw = (value or '').strip()
    if len(raw) <= 16:
        return raw or '-'
    return f'{raw[:8]}...{raw[-6:]}'


def _first_nonempty(payload: dict, keys: tuple[str, ...], default: str = '-') -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ''):
            return str(value)
    return default


def _folders_syncing(payload: dict) -> int:
    for key in ('foldersSyncing', 'numPendingFolders', 'syncingFolders'):
        value = payload.get(key)
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, str) and value.isdigit():
            return max(0, int(value))
    return 0


async def syncthing_status() -> dict:
    running = await asyncio.to_thread(_port_open)
    if not running:
        return {
            'running': False,
            'available': False,
            'device_id': '-',
            'device_id_short': '-',
            'folders_syncing': 0,
            'last_sync_time': '-',
            'message': 'Syncthing not installed — enables automatic phone backup.',
            'learn_more_url': LEARN_MORE_URL,
        }

    try:
        payload = await asyncio.to_thread(_fetch_status_json)
    except Exception:
        return {
            'running': True,
            'available': False,
            'device_id': '-',
            'device_id_short': '-',
            'folders_syncing': 0,
            'last_sync_time': '-',
            'message': 'Syncthing is running, but status API is unavailable.',
            'learn_more_url': LEARN_MORE_URL,
        }

    device_id = str(payload.get('myID') or '').strip()
    return {
        'running': True,
        'available': True,
        'device_id': device_id or '-',
        'device_id_short': _truncate_device_id(device_id),
        'folders_syncing': _folders_syncing(payload),
        'last_sync_time': _first_nonempty(payload, ('lastSyncTime', 'lastSync', 'startTime')),
        'message': 'Syncthing status available.',
        'learn_more_url': LEARN_MORE_URL,
    }
