from __future__ import annotations

import os
import stat
from pathlib import PosixPath

import pytest

from app.services import network
from app.services.system_cmd import CommandResult, MockCommandRunner


def _result(exit_code: int = 0, stdout: str = '', stderr: str = '') -> CommandResult:
    return CommandResult(exit_code == 0, stdout, stderr, exit_code, 0.0)


@pytest.mark.asyncio
async def test_apply_network_config_writes_dhcp_config_atomically(monkeypatch, tmp_path):
    etc_root = tmp_path / 'etc'
    interfaces_dir = etc_root / 'network' / 'interfaces.d'
    interfaces_dir.mkdir(parents=True, exist_ok=True)

    class MappedPath(PosixPath):
        def __new__(cls, *args, **kwargs):
            path = PosixPath(*args, **kwargs)
            path_str = str(path)
            if path_str == '/etc':
                path = etc_root
            elif path_str.startswith('/etc/'):
                path = etc_root / path.relative_to('/etc')
            return PosixPath.__new__(cls, path)

    async def _no_nmcli() -> bool:
        return False

    runner = MockCommandRunner()
    runner.queue_result(_result())  # systemctl restart networking

    monkeypatch.setattr(network, 'Path', MappedPath)
    monkeypatch.setattr(network, '_has_nmcli', _no_nmcli)
    monkeypatch.setattr(network, '_runner', runner)

    ok, message = await network.apply_network_config(
        interface='eth0',
        mode='dhcp',
        address=None,
        gateway=None,
        dns=None,
    )

    cfg_path = interfaces_dir / 'cubie-nas-eth0.cfg'
    assert ok is True
    assert 'saved' in message.lower()
    assert cfg_path.read_text(encoding='utf-8') == 'auto eth0\niface eth0 inet dhcp\n'
    assert any(call['cmd'] == ['systemctl', 'restart', 'networking'] for call in runner.calls)


def test_atomic_write_text_updates_file(tmp_path):
    target = tmp_path / 'network.cfg'
    target.write_text('old\n', encoding='utf-8')

    network._atomic_write_text(target, 'new\n')

    assert target.read_text(encoding='utf-8') == 'new\n'


def test_atomic_write_text_fsyncs_parent_directory(monkeypatch, tmp_path):
    target = tmp_path / 'network.cfg'

    original_fsync = os.fsync
    calls = {'file': 0, 'dir': 0}

    def tracking_fsync(fd: int):
        mode = os.fstat(fd).st_mode
        if stat.S_ISDIR(mode):
            calls['dir'] += 1
        else:
            calls['file'] += 1
        return original_fsync(fd)

    monkeypatch.setattr(network.os, 'fsync', tracking_fsync)

    network._atomic_write_text(target, 'value\n')

    assert calls['file'] >= 1
    assert calls['dir'] >= 1
    assert target.read_text(encoding='utf-8') == 'value\n'
