from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import enforce_csrf, get_current_user, require_admin
from ..schemas import ApiResponse
from ..services.system_info import get_general_info
from ..services.ssl import ensure_self_signed
from ..services.system_cmd import run_cmd

router = APIRouter(prefix='/api/system', tags=['system'])


@router.get('/general-info')
def general_info(_: object = Depends(get_current_user)):
    return {'ok': True, 'data': get_general_info()}


@router.post('/tls/generate', dependencies=[Depends(enforce_csrf)])
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


@router.post('/firewall/apply', dependencies=[Depends(enforce_csrf)])
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
        rc, out, err = await run_cmd(cmd)
        if rc != 0:
            raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Firewall configured')
