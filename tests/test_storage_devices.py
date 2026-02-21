from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services import storage
from app.services.system_cmd import CommandResult


@dataclass
class _Usage:
    total: int
    used: int
    free: int


class _Runner:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.calls = 0

    async def run(self, cmd: list[str]):
        self.calls += 1
        return CommandResult(True, self.stdout, '', 0, 0.01)


@pytest.mark.asyncio
async def test_list_storage_devices_filters_mounted_and_maps_types(tmp_path, monkeypatch):
    mounted_sd = tmp_path / 'sdroot'
    mounted_usb = tmp_path / 'usbroot'
    mounted_sd.mkdir()
    mounted_usb.mkdir()

    payload = f'''{{
      "blockdevices": [
        {{"name":"mmcblk0p1","mountpoint":"{mounted_sd}","tran":null,"type":"part","label":"System SD","fstype":"ext4"}},
        {{"name":"sda1","mountpoint":"{mounted_usb}","tran":"usb","type":"part","label":"USB Drive","fstype":"ext4"}},
        {{"name":"nvme0n1p1","mountpoint":null,"tran":"nvme","type":"part","label":"NVMe","fstype":"ext4"}}
      ]
    }}'''

    runner = _Runner(payload)
    monkeypatch.setattr(storage, '_runner', runner)
    monkeypatch.setattr(storage, 'disk_usage', lambda _: _Usage(total=64 * 1024**3, used=20 * 1024**3, free=44 * 1024**3))
    storage._DEVICE_CACHE['ts'] = 0.0
    storage._DEVICE_CACHE['data'] = []

    data = await storage.list_storage_devices()

    assert len(data) == 2
    assert data[0]['label'] == 'System SD'
    assert data[0]['type'] == 'sd'
    assert data[1]['label'] == 'USB Drive'
    assert data[1]['type'] == 'usb'
    assert data[0]['total_gb'] == 64.0
    assert data[0]['used_gb'] == 20.0
    assert data[0]['free_gb'] == 44.0


@pytest.mark.asyncio
async def test_list_storage_devices_uses_10_second_cache(monkeypatch, tmp_path):
    mount_dir = tmp_path / 'mnt'
    mount_dir.mkdir()
    payload = f'{{"blockdevices":[{{"name":"sda1","mountpoint":"{mount_dir}","tran":"usb","type":"part","label":"USB","fstype":"ext4"}}]}}'

    runner = _Runner(payload)
    monkeypatch.setattr(storage, '_runner', runner)
    monkeypatch.setattr(storage, 'disk_usage', lambda _: _Usage(total=10 * 1024**3, used=1 * 1024**3, free=9 * 1024**3))

    times = iter([1000.0, 1001.0])
    monkeypatch.setattr(storage.time, 'time', lambda: next(times))

    storage._DEVICE_CACHE['ts'] = 0.0
    storage._DEVICE_CACHE['data'] = []

    first = await storage.list_storage_devices()
    second = await storage.list_storage_devices()

    assert runner.calls == 1
    assert first == second


@pytest.mark.asyncio
async def test_list_storage_devices_returns_empty_on_bad_json(monkeypatch):
    runner = _Runner('not-json')
    monkeypatch.setattr(storage, '_runner', runner)
    storage._DEVICE_CACHE['ts'] = 0.0
    storage._DEVICE_CACHE['data'] = []

    data = await storage.list_storage_devices()

    assert data == []
