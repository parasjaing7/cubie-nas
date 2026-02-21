from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user, require_admin
from ..schemas import ApiResponse, ServiceActionRequest
from ..services.service_ctl import SERVICE_MAP, service_action, service_status

router = APIRouter(prefix='/api/services', tags=['services'])


@router.get('/list')
async def list_services(_=Depends(get_current_user)):
    data = []
    for name in SERVICE_MAP:
        data.append(await service_status(name))
    return {'ok': True, 'data': data}


@router.get('/status')
async def status(_=Depends(get_current_user)):
    ordered = ['samba', 'ssh', 'nfs', 'ftp']
    data = []
    for name in ordered:
        data.append(await service_status(name))
    return {'ok': True, 'data': data}


@router.post('/restart')
async def restart(payload: ServiceActionRequest, _=Depends(require_admin)):
    rc, out, err = await service_action(payload.service, 'restart')
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Restarted')


@router.post('/enable')
async def enable(payload: ServiceActionRequest, _=Depends(require_admin)):
    rc, out, err = await service_action(payload.service, 'enable')
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Enabled')


@router.post('/disable')
async def disable(payload: ServiceActionRequest, _=Depends(require_admin)):
    rc, out, err = await service_action(payload.service, 'disable')
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Disabled')


@router.post('/start')
async def start(payload: ServiceActionRequest, _=Depends(require_admin)):
    rc, out, err = await service_action(payload.service, 'start')
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Started')


@router.post('/stop')
async def stop(payload: ServiceActionRequest, _=Depends(require_admin)):
    rc, out, err = await service_action(payload.service, 'stop')
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Stopped')
