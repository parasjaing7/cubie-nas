from __future__ import annotations

import asyncio
import os
import re
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..deps import get_current_user, require_admin
from ..models import User
from ..schemas import ApiResponse
from ..security import decode_token
from ..services.system_info import get_general_info
from ..services.ssl import ensure_self_signed
from ..services.system_cmd import RealCommandRunner, spawn_bash_pty, spawn_stream_process

router = APIRouter(prefix='/api/system', tags=['system'])
ui_router = APIRouter(tags=['system-ui'])

_runner = RealCommandRunner()
_templates = Jinja2Templates(directory='templates')
_active_terminal_sessions: dict[str, bool] = {}
_terminal_sessions_lock = asyncio.Lock()
_JOURNAL_UNITS = ['cubie-nas', 'smbd', 'nmbd', 'nfs-kernel-server', 'ssh', 'vsftpd']
_LOG_LINE_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:[\.,]\d+)?)\s+'
    r'(?P<host>\S+)\s+(?P<unit>[\w@.-]+)(?:\[\d+\])?:\s*(?P<msg>.*)$'
)


def _log_level(message: str) -> str:
    upper = message.upper()
    if 'CRIT' in upper or 'FATAL' in upper or 'PANIC' in upper or 'ERROR' in upper:
        return 'ERROR'
    if 'WARN' in upper:
        return 'WARN'
    if 'DEBUG' in upper or 'TRACE' in upper:
        return 'DEBUG'
    return 'INFO'


def _parse_journal_line(line: str) -> dict[str, str]:
    match = _LOG_LINE_RE.match(line.strip())
    if not match:
        msg = line.strip()
        return {'ts': '', 'unit': 'journalctl', 'level': _log_level(msg), 'msg': msg}

    unit = match.group('unit')
    msg = match.group('msg').strip()
    return {
        'ts': match.group('ts'),
        'unit': unit,
        'level': _log_level(msg),
        'msg': msg,
    }


def _get_ws_token(websocket: WebSocket) -> str | None:
    auth = websocket.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1].strip()
        if token:
            return token
    token = websocket.cookies.get('access_token')
    if token:
        return token
    return None


def _authenticate_ws_user(websocket: WebSocket) -> str | None:
    token = _get_ws_token(websocket)
    if not token:
        return None

    try:
        payload = decode_token(token)
    except ValueError:
        return None

    username = payload.get('sub')
    if not username:
        return None

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
        if not user:
            return None
    finally:
        db.close()

    return username


@ui_router.get('/terminal', response_class=HTMLResponse)
def terminal_page(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        return RedirectResponse('/')

    try:
        payload = decode_token(token)
    except ValueError:
        return RedirectResponse('/')

    username = payload.get('sub')
    if not username:
        return RedirectResponse('/')

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
        if not user:
            return RedirectResponse('/')
    finally:
        db.close()

    return _templates.TemplateResponse('terminal.html', {'request': request, 'page': 'terminal'})


@ui_router.get('/logs', response_class=HTMLResponse)
def logs_page(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        return RedirectResponse('/')

    try:
        payload = decode_token(token)
    except ValueError:
        return RedirectResponse('/')

    username = payload.get('sub')
    if not username:
        return RedirectResponse('/')

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
        if not user:
            return RedirectResponse('/')
    finally:
        db.close()

    return _templates.TemplateResponse('logs.html', {'request': request, 'page': 'logs'})


@ui_router.websocket('/ws/terminal')
async def terminal_ws(websocket: WebSocket):
    username = _authenticate_ws_user(websocket)
    if not username:
        await websocket.close(code=1008)
        return

    async with _terminal_sessions_lock:
        if _active_terminal_sessions.get(username):
            await websocket.close(code=1008)
            return
        _active_terminal_sessions[username] = True

    master_fd = None
    shell_proc = None

    try:
        await websocket.accept()

        master_fd, slave_fd = os.openpty()
        shell_proc = await spawn_bash_pty(slave_fd)
        os.close(slave_fd)

        async def pty_to_ws():
            while True:
                chunk = await asyncio.to_thread(os.read, master_fd, 1024)
                if not chunk:
                    break
                await websocket.send_text(chunk.decode(errors='ignore'))

        async def ws_to_pty():
            while True:
                message = await websocket.receive_text()
                os.write(master_fd, message.encode())

        sender = asyncio.create_task(pty_to_ws())
        receiver = asyncio.create_task(ws_to_pty())

        done, pending = await asyncio.wait(
            [sender, receiver],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        for task in done:
            try:
                task.result()
            except Exception:
                pass
    finally:
        if shell_proc and shell_proc.returncode is None:
            shell_proc.terminate()
            try:
                await asyncio.wait_for(shell_proc.wait(), timeout=2)
            except Exception:
                shell_proc.kill()
                await shell_proc.wait()

        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

        async with _terminal_sessions_lock:
            _active_terminal_sessions.pop(username, None)


@ui_router.websocket('/ws/logs')
async def logs_ws(websocket: WebSocket):
    username = _authenticate_ws_user(websocket)
    if not username:
        await websocket.close(code=1008, reason='forbidden')
        return

    process = None
    line_buffer: deque[dict[str, str]] = deque(maxlen=500)

    try:
        await websocket.accept()
        cmd = ['journalctl', '-f']
        for unit in _JOURNAL_UNITS:
            cmd.extend(['-u', unit])
        cmd.extend(['--output=short-iso', '--no-pager'])

        process = await spawn_stream_process(cmd)

        while True:
            if process.stdout is None:
                break

            raw = await process.stdout.readline()
            if not raw:
                break

            payload = _parse_journal_line(raw.decode(errors='ignore'))
            line_buffer.append(payload)
            await websocket.send_json(payload)
    except Exception:
        pass
    finally:
        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except Exception:
                process.kill()
                await process.wait()


@router.get('/general-info')
def general_info(_: object = Depends(get_current_user)):
    return {'ok': True, 'data': get_general_info()}


@router.post('/tls/generate')
async def generate_tls(_: object = Depends(require_admin)):
    rc, msg = await ensure_self_signed(settings.tls_cert_file, settings.tls_key_file)
    if rc != 0:
        raise HTTPException(status_code=400, detail=msg)
    return ApiResponse(ok=True, message=msg)


@router.get('/firewall/commands')
def firewall_commands(_: object = Depends(require_admin)):
    cmds = [
        'ufw default deny incoming',
        'ufw default allow outgoing',
        'ufw allow 22/tcp',
        'ufw allow 445/tcp',
        'ufw allow 2049/tcp',
        'ufw allow 8443/tcp',
        'ufw enable',
    ]
    return {'ok': True, 'data': cmds}


@router.post('/firewall/apply')
async def firewall_apply(_: object = Depends(require_admin)):
    for cmd in [
        ['ufw', 'default', 'deny', 'incoming'],
        ['ufw', 'default', 'allow', 'outgoing'],
        ['ufw', 'allow', '22/tcp'],
        ['ufw', 'allow', '445/tcp'],
        ['ufw', 'allow', '2049/tcp'],
        ['ufw', 'allow', '8443/tcp'],
        ['ufw', '--force', 'enable'],
    ]:
        result = await _runner.run(cmd)
        if result.exit_code != 0:
            raise HTTPException(status_code=400, detail=result.stderr or result.stdout)
    return ApiResponse(ok=True, message='Firewall configured')


@router.get('/logs')
async def system_logs(lines: int = Query(default=200, ge=50, le=2000), _: object = Depends(require_admin)):
    result = await _runner.run(['journalctl', '-u', 'cubie-nas', '-n', str(lines), '--no-pager'])
    if result.exit_code != 0:
        raise HTTPException(status_code=400, detail=result.stderr or result.stdout)
    entries = result.stdout.splitlines() if result.stdout else []
    return {'ok': True, 'data': entries}
