from __future__ import annotations

import pytest

from app.services import syncthing


@pytest.mark.asyncio
async def test_syncthing_status_not_running(monkeypatch):
    monkeypatch.setattr(syncthing, '_port_open', lambda *args, **kwargs: False)

    data = await syncthing.syncthing_status()

    assert data['running'] is False
    assert data['available'] is False
    assert data['folders_syncing'] == 0
    assert 'not installed' in data['message'].lower()


@pytest.mark.asyncio
async def test_syncthing_status_running_with_payload(monkeypatch):
    payload = {
        'myID': 'ABCDEFGH1234567890ZYXWVU',
        'foldersSyncing': 2,
        'lastSyncTime': '2026-02-21T10:22:33Z',
    }
    monkeypatch.setattr(syncthing, '_port_open', lambda *args, **kwargs: True)
    monkeypatch.setattr(syncthing, '_fetch_status_json', lambda *args, **kwargs: payload)

    data = await syncthing.syncthing_status()

    assert data['running'] is True
    assert data['available'] is True
    assert data['device_id'] == payload['myID']
    assert data['device_id_short'] == 'ABCDEFGH...ZYXWVU'
    assert data['folders_syncing'] == 2
    assert data['last_sync_time'] == '2026-02-21T10:22:33Z'


@pytest.mark.asyncio
async def test_syncthing_status_running_but_api_unavailable(monkeypatch):
    def _boom(*args, **kwargs):
        raise OSError('connection reset')

    monkeypatch.setattr(syncthing, '_port_open', lambda *args, **kwargs: True)
    monkeypatch.setattr(syncthing, '_fetch_status_json', _boom)

    data = await syncthing.syncthing_status()

    assert data['running'] is True
    assert data['available'] is False
    assert data['folders_syncing'] == 0
    assert 'unavailable' in data['message'].lower()
