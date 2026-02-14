from __future__ import annotations

import time

import psutil


class RateSampler:
    def __init__(self):
        self.prev_net = psutil.net_io_counters()
        self.prev_disk = psutil.disk_io_counters()
        self.prev_t = time.time()

    def sample(self) -> dict:
        now = time.time()
        dt = max(now - self.prev_t, 0.001)

        net = psutil.net_io_counters()
        disk = psutil.disk_io_counters()

        rx = (net.bytes_recv - self.prev_net.bytes_recv) / dt
        tx = (net.bytes_sent - self.prev_net.bytes_sent) / dt
        dr = (disk.read_bytes - self.prev_disk.read_bytes) / dt
        dw = (disk.write_bytes - self.prev_disk.write_bytes) / dt

        self.prev_net = net
        self.prev_disk = disk
        self.prev_t = now

        return {
            'net_rx_bps': round(rx, 1),
            'net_tx_bps': round(tx, 1),
            'disk_read_bps': round(dr, 1),
            'disk_write_bps': round(dw, 1),
        }


def read_temp_c() -> float | None:
    try:
        temps = psutil.sensors_temperatures()
    except Exception:
        return None

    for _, values in temps.items():
        if values:
            return values[0].current
    return None


def read_stats(sampler: RateSampler) -> dict:
    vm = psutil.virtual_memory()
    rates = sampler.sample()
    return {
        'cpu_percent': psutil.cpu_percent(interval=None),
        'ram_used_mb': round(vm.used / (1024 * 1024), 1),
        'ram_total_mb': round(vm.total / (1024 * 1024), 1),
        'temp_c': read_temp_c(),
        'net_rx_bps': rates['net_rx_bps'],
        'net_tx_bps': rates['net_tx_bps'],
        'disk_read_bps': rates['disk_read_bps'],
        'disk_write_bps': rates['disk_write_bps'],
        'uptime_seconds': int(time.time() - psutil.boot_time()),
    }
