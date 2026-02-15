from __future__ import annotations

from pathlib import Path

from .system_cmd import RealCommandRunner

_runner = RealCommandRunner()


async def ensure_self_signed(cert_file: str, key_file: str, cn: str = 'cubie-nas.local') -> tuple[int, str]:
    cert = Path(cert_file)
    key = Path(key_file)
    cert.parent.mkdir(parents=True, exist_ok=True)

    if cert.exists() and key.exists():
        return 0, 'TLS certificate already exists'

    result = await _runner.run(
        [
            'openssl',
            'req',
            '-x509',
            '-nodes',
            '-days',
            '825',
            '-newkey',
            'rsa:2048',
            '-subj',
            f'/CN={cn}',
            '-keyout',
            key_file,
            '-out',
            cert_file,
        ]
    )
    if result.exit_code != 0:
        return result.exit_code, result.stderr or result.stdout
    return 0, 'TLS certificate generated'
