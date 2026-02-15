from __future__ import annotations

import ipaddress
import json
from pathlib import Path
from typing import Optional

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()


def _mask_from_cidr(cidr: str) -> tuple[str, str]:
    iface = ipaddress.IPv4Interface(cidr)
    return str(iface.ip), str(iface.network.netmask)


async def _has_nmcli() -> bool:
    result = await _runner.run(['which', 'nmcli'])
    return result.exit_code == 0


async def current_network_info() -> dict:
    result = await _runner.run(['ip', '-j', 'addr', 'show'])
    interfaces = json.loads(result.stdout) if result.exit_code == 0 and result.stdout else []

    result_route = await _runner.run(['ip', 'route', 'show', 'default'])
    default_iface = None
    gateway = None
    if result_route.exit_code == 0 and result_route.stdout:
        parts = result_route.stdout.split()
        if 'dev' in parts:
            default_iface = parts[parts.index('dev') + 1]
        if 'via' in parts:
            gateway = parts[parts.index('via') + 1]

    ip_addr = None
    if default_iface:
        for itf in interfaces:
            if itf.get('ifname') == default_iface:
                for addr in itf.get('addr_info', []):
                    if addr.get('family') == 'inet':
                        ip_addr = f"{addr.get('local')}/{addr.get('prefixlen')}"
                        break

    dns = ''
    resolv = Path('/etc/resolv.conf')
    if resolv.exists():
        lines = [l.strip().split()[1] for l in resolv.read_text().splitlines() if l.strip().startswith('nameserver ')]
        dns = ','.join(lines)

    return {
        'interface': default_iface or 'eth0',
        'ip_address': ip_addr or '',
        'gateway': gateway or '',
        'dns': dns,
    }


async def _active_connection_for_iface(interface: str) -> Optional[str]:
    result = await _runner.run(['nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show'])
    if result.exit_code != 0:
        return None
    for line in result.stdout.splitlines():
        if not line.strip() or ':' not in line:
            continue
        name, device = line.split(':', 1)
        if device == interface:
            return name
    return interface


async def apply_network_config(interface: str, mode: str, address: Optional[str], gateway: Optional[str], dns: Optional[str]) -> tuple[bool, str]:
    if mode == 'static' and not address:
        return False, 'address is required for static mode'

    if mode == 'static' and address:
        try:
            ipaddress.IPv4Interface(address)
        except ValueError:
            return False, 'address must be CIDR format, example: 192.168.1.50/24'

    use_nmcli = await _has_nmcli()
    dns_value = (dns or '').replace(' ', '')

    if use_nmcli:
        conn = await _active_connection_for_iface(interface)
        if not conn:
            return False, f'No NetworkManager connection found for interface {interface}'

        if mode == 'dhcp':
            cmds = [
                ['nmcli', 'connection', 'modify', conn, 'ipv4.method', 'auto', 'ipv4.addresses', '', 'ipv4.gateway', '', 'ipv4.dns', ''],
                ['nmcli', 'connection', 'up', conn],
            ]
        else:
            cmds = [
                ['nmcli', 'connection', 'modify', conn, 'ipv4.method', 'manual', 'ipv4.addresses', address, 'ipv4.gateway', gateway or '', 'ipv4.dns', dns_value],
                ['nmcli', 'connection', 'up', conn],
            ]

        for cmd in cmds:
            result_cmd = await _runner.run(cmd)
            if result_cmd.exit_code != 0:
                return False, result_cmd.stderr or result_cmd.stdout
        return True, 'Network configuration applied with NetworkManager'

    cfg_path = Path(f'/etc/network/interfaces.d/cubie-nas-{interface}.cfg')
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == 'dhcp':
        content = f'auto {interface}\niface {interface} inet dhcp\n'
    else:
        ip_addr, netmask = _mask_from_cidr(address or '')
        lines = [
            f'auto {interface}',
            f'iface {interface} inet static',
            f'    address {ip_addr}',
            f'    netmask {netmask}',
        ]
        if gateway:
            lines.append(f'    gateway {gateway}')
        if dns_value:
            lines.append(f"    dns-nameservers {dns_value.replace(',', ' ')}")
        content = '\n'.join(lines) + '\n'

    cfg_path.write_text(content)

    result_restart = await _runner.run(['systemctl', 'restart', 'networking'])
    if result_restart.exit_code != 0:
        return False, (result_restart.stderr or result_restart.stdout or 'Saved configuration, but restart networking failed')

    return True, f'Network configuration saved in {cfg_path}'
