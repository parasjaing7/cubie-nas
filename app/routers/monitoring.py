from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..deps import get_current_user
from ..security import decode_token
from ..services.monitor import RateSampler, read_stats
from ..services.syncthing import syncthing_status

router = APIRouter(prefix='/api/monitor', tags=['monitor'])
ws_router = APIRouter(tags=['monitor-ws'])


@router.get('/snapshot')
def snapshot(_=Depends(get_current_user)):
    sampler = RateSampler()
    return {'ok': True, 'data': read_stats(sampler)}


@router.get('/syncthing/status')
async def backup_status(_=Depends(get_current_user)):
    return {'ok': True, 'data': await syncthing_status()}


def _token_from_cookie_header(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    parts = [p.strip() for p in cookie_header.split(';')]
    for part in parts:
        if part.startswith('access_token='):
            return part.split('=', 1)[1]
    return None


async def _monitor_ws_impl(ws: WebSocket):
    token = _token_from_cookie_header(ws.headers.get('cookie'))
    if not token:
        await ws.close(code=4401)
        return

    try:
        decode_token(token)
    except ValueError:
        await ws.close(code=4401)
        return

    await ws.accept()
    sampler = RateSampler()
    try:
        while True:
            await ws.send_json(read_stats(sampler))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


@router.websocket('/ws')
async def monitor_ws(ws: WebSocket):
    await _monitor_ws_impl(ws)


@ws_router.websocket('/ws/monitor')
async def monitor_ws_alias(ws: WebSocket):
    await _monitor_ws_impl(ws)
