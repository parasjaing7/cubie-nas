from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import get_current_user, require_admin
from ..schemas import ApiResponse, ShareCreateRequest, ShareRemoveRequest
from ..services.system_cmd import RealCommandRunner

router = APIRouter(prefix='/api/sharing', tags=['sharing'])

_runner = RealCommandRunner()
_SMB_PATH = Path('/etc/samba/smb.conf')


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + '.cubie-nas.bak')
    _atomic_write_text(backup, path.read_text(encoding='utf-8'))
    return backup


def _restore_file(path: Path, backup: Path | None) -> None:
    if backup and backup.exists():
        _atomic_write_text(path, backup.read_text(encoding='utf-8'))


def _parse_shares(text: str) -> list[dict]:
    shares: list[dict] = []
    current_name: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            if current_name and current_name.lower() not in {'global', 'printers', 'print$'}:
                shares.append({'name': current_name, 'lines': current_lines})
            current_name = stripped[1:-1].strip()
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)

    if current_name and current_name.lower() not in {'global', 'printers', 'print$'}:
        shares.append({'name': current_name, 'lines': current_lines})

    out = []
    for share in shares:
        options: dict[str, str] = {}
        for raw in share['lines']:
            stripped = raw.strip()
            if not stripped or stripped.startswith('#') or stripped.startswith(';') or '=' not in stripped:
                continue
            key, value = stripped.split('=', 1)
            options[key.strip().lower()] = value.strip()

        users = [u for u in options.get('valid users', '').split() if u]
        guest_ok = options.get('guest ok', '').lower() in {'yes', 'true', '1'}
        access = 'everyone' if guest_ok or not users else 'specific'
        out.append(
            {
                'name': share['name'],
                'path': options.get('path', ''),
                'access': access,
                'users': users,
            }
        )
    return out


def _remove_share_block(text: str, name: str) -> str:
    target = name.strip().lower()
    out: list[str] = []
    skip = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            sec = stripped[1:-1].strip().lower()
            skip = sec == target
            if skip:
                continue
        if not skip:
            out.append(line)
    return '\n'.join(out).rstrip() + '\n'


def _upsert_share_block(text: str, name: str, folder: str, access: str, users: list[str]) -> str:
    cleaned = _remove_share_block(text, name)
    block = [
        f'[{name}]',
        f'   path = {folder}',
        '   browseable = yes',
        '   writable = yes',
        '   read only = no',
    ]
    if access == 'everyone':
        block.extend(['   guest ok = yes', '   guest only = yes'])
    else:
        block.extend(['   guest ok = no', f"   valid users = {' '.join(users)}"])

    merged = cleaned.rstrip() + '\n\n' + '\n'.join(block) + '\n'
    return merged


async def _share_connection_counts() -> dict[str, int]:
    result = await _runner.run(['smbstatus', '-j'])
    if result.exit_code != 0 or not result.stdout:
        return {}
    try:
        payload = json.loads(result.stdout)
    except Exception:
        return {}

    counts: dict[str, int] = {}

    shares = payload.get('shares')
    if isinstance(shares, dict):
        share_iter = shares.values()
    elif isinstance(shares, list):
        share_iter = shares
    else:
        share_iter = []

    for row in share_iter:
        if not isinstance(row, dict):
            continue
        name = str(row.get('service') or row.get('name') or row.get('share_name') or '').strip()
        if not name:
            continue
        raw_count = row.get('num_connections')
        count = int(raw_count) if isinstance(raw_count, int) else 1
        key = name.lower()
        counts[key] = counts.get(key, 0) + max(1, count)

    return counts


def _resolve_share_folder(folder: str) -> Path:
    base = Path(settings.nas_root).resolve(strict=False)
    raw = Path(folder)
    resolved = raw.resolve(strict=False) if raw.is_absolute() else (base / folder).resolve(strict=False)
    if base != resolved and base not in resolved.parents:
        raise HTTPException(status_code=400, detail='Folder must be under NAS root')
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=400, detail='Folder does not exist')
    return resolved


@router.get('/list')
async def list_shares(_: object = Depends(get_current_user)):
    if not _SMB_PATH.exists():
        return {'ok': True, 'data': []}

    shares = _parse_shares(_SMB_PATH.read_text(encoding='utf-8'))
    counts = await _share_connection_counts()
    for share in shares:
        share['connections'] = counts.get(share['name'].lower(), 0)
    return {'ok': True, 'data': shares}


@router.post('/add')
async def add_share(payload: ShareCreateRequest, _: object = Depends(require_admin)):
    if payload.access == 'specific' and not payload.users:
        raise HTTPException(status_code=400, detail='Select at least one user for specific access')

    if not _SMB_PATH.exists():
        raise HTTPException(status_code=400, detail='/etc/samba/smb.conf not found')

    resolved_folder = _resolve_share_folder(payload.folder)
    original = _SMB_PATH.read_text(encoding='utf-8')
    backup = _backup_file(_SMB_PATH)

    try:
        updated = _upsert_share_block(
            original,
            payload.name,
            str(resolved_folder),
            payload.access,
            payload.users,
        )
        _atomic_write_text(_SMB_PATH, updated)

        result_testparm = await _runner.run(['testparm', '-s'])
        if result_testparm.exit_code != 0:
            _restore_file(_SMB_PATH, backup)
            raise HTTPException(status_code=400, detail=result_testparm.stderr or result_testparm.stdout)

        result_reload = await _runner.run(['smbcontrol', 'smbd', 'reload-config'])
        if result_reload.exit_code != 0:
            _restore_file(_SMB_PATH, backup)
            raise HTTPException(status_code=400, detail=result_reload.stderr or result_reload.stdout)
    except HTTPException:
        raise
    except Exception as exc:
        _restore_file(_SMB_PATH, backup)
        raise HTTPException(status_code=400, detail=str(exc))

    return ApiResponse(ok=True, message='Share added')


@router.post('/remove')
async def remove_share(payload: ShareRemoveRequest, _: object = Depends(require_admin)):
    if not _SMB_PATH.exists():
        raise HTTPException(status_code=400, detail='/etc/samba/smb.conf not found')

    original = _SMB_PATH.read_text(encoding='utf-8')
    shares = _parse_shares(original)
    if payload.name.lower() not in {s['name'].lower() for s in shares}:
        raise HTTPException(status_code=404, detail='Share not found')

    backup = _backup_file(_SMB_PATH)

    try:
        updated = _remove_share_block(original, payload.name)
        _atomic_write_text(_SMB_PATH, updated)

        result_testparm = await _runner.run(['testparm', '-s'])
        if result_testparm.exit_code != 0:
            _restore_file(_SMB_PATH, backup)
            raise HTTPException(status_code=400, detail=result_testparm.stderr or result_testparm.stdout)

        result_reload = await _runner.run(['smbcontrol', 'smbd', 'reload-config'])
        if result_reload.exit_code != 0:
            _restore_file(_SMB_PATH, backup)
            raise HTTPException(status_code=400, detail=result_reload.stderr or result_reload.stdout)
    except HTTPException:
        raise
    except Exception as exc:
        _restore_file(_SMB_PATH, backup)
        raise HTTPException(status_code=400, detail=str(exc))

    return ApiResponse(ok=True, message='Share removed')


@router.get('/connections')
async def smb_connections(_: object = Depends(get_current_user)):
    result = await _runner.run(['smbstatus', '-j'])
    if result.exit_code != 0 or not result.stdout:
        return {'ok': True, 'data': []}

    try:
        payload = json.loads(result.stdout)
    except Exception:
        return {'ok': True, 'data': []}

    rows = []

    sessions = payload.get('sessions')
    if isinstance(sessions, dict):
        sessions_iter = sessions.values()
    elif isinstance(sessions, list):
        sessions_iter = sessions
    else:
        sessions_iter = []

    for sess in sessions_iter:
        if not isinstance(sess, dict):
            continue
        rows.append(
            {
                'user': sess.get('username') or sess.get('uid') or 'unknown',
                'ip_address': sess.get('remote_machine') or sess.get('hostname') or '-',
                'connected_since': str(sess.get('start') or sess.get('connect_time') or '-'),
            }
        )

    return {'ok': True, 'data': rows}
