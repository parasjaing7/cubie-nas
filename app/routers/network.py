from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_current_user, require_admin
from ..schemas import ApiResponse, NetworkConfigRequest
from ..services.network import apply_network_config, current_network_info

router = APIRouter(prefix='/api/network', tags=['network'])


@router.get('/current')
async def current(_: object = Depends(get_current_user)):
    return {'ok': True, 'data': await current_network_info()}


@router.post('/save')
async def save(payload: NetworkConfigRequest, _: object = Depends(require_admin)):
    ok, message = await apply_network_config(
        interface=payload.interface,
        mode=payload.mode,
        address=payload.address,
        gateway=payload.gateway,
        dns=payload.dns,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return ApiResponse(ok=True, message=message)
