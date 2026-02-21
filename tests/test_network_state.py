from __future__ import annotations

import json

import pytest

from app.services import network
from app.services.system_cmd import CommandResult


class _Runner:
    async def run(self, cmd: list[str]):
        if cmd[:4] == ['ip', '-j', 'link', 'show']:
            payload = [
                {'ifname': 'lo', 'operstate': 'UNKNOWN', 'link_type': 'loopback'},
                {'ifname': 'eth0', 'operstate': 'UP', 'link_type': 'ether', 'address': '00:11:22:33:44:55', 'mtu': 1500},
                {'ifname': 'wlan0', 'operstate': 'DOWN', 'link_type': 'ether', 'address': '00:11:22:33:44:66', 'mtu': 1500},
            ]
            return CommandResult(True, json.dumps(payload), '', 0, 0.01)
        if cmd[:3] == ['rfkill', 'list', 'bluetooth']:
            return CommandResult(True, 'Soft blocked: no\nHard blocked: no\n', '', 0, 0.01)
        if cmd[:6] == ['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show']:
            return CommandResult(True, 'hotspot:wifi:wlan0\n', '', 0, 0.01)
        return CommandResult(False, '', 'unsupported', 1, 0.01)


@pytest.mark.asyncio
async def test_network_state_parses_interfaces(monkeypatch):
    monkeypatch.setattr(network, '_runner', _Runner())

    state = await network.network_state()

    assert state['ethernet']['enabled'] is True
    assert len(state['ethernet']['ports']) == 1
    assert state['ethernet']['ports'][0]['name'] == 'eth0'
    assert state['bluetooth']['enabled'] is True
    assert state['hotspot']['enabled'] is True
