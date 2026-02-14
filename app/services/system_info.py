from __future__ import annotations

import platform
from pathlib import Path

import psutil

from .monitor import read_temp_c


def _read_model() -> str:
    model_file = Path('/proc/device-tree/model')
    if model_file.exists():
        raw = model_file.read_bytes()
        return raw.decode(errors='ignore').replace('\x00', '').strip()
    return 'Unknown SBC Model'


def _read_cpu_model() -> str:
    cpuinfo = Path('/proc/cpuinfo')
    if not cpuinfo.exists():
        return platform.processor() or 'Unknown CPU'

    for line in cpuinfo.read_text(errors='ignore').splitlines():
        if line.lower().startswith('model name') or line.lower().startswith('hardware'):
            return line.split(':', 1)[1].strip()
    return platform.processor() or 'Unknown CPU'


def get_general_info() -> dict:
    vm = psutil.virtual_memory()
    return {
        'model': _read_model(),
        'hostname': platform.node(),
        'os': f"{platform.system()} {platform.release()}",
        'arch': platform.machine(),
        'cpu_model': _read_cpu_model(),
        'cpu_cores_logical': psutil.cpu_count(logical=True) or 0,
        'cpu_cores_physical': psutil.cpu_count(logical=False) or 0,
        'ram_total_mb': round(vm.total / (1024 * 1024), 1),
        'temperature_c': read_temp_c(),
    }
