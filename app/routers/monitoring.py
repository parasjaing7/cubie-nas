from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..deps import get_current_user
from ..security import decode_token
from ..services.monitor import RateSampler, read_stats

router = APIRouter(prefix='/api/monitor', tags=['monitor'])


@router.get('/snapshot')
def snapshot(_=Depends(get_current_user)):
    sampler = RateSampler()
    return {'ok': True, 'data': read_stats(sampler)}


def _token_from_cookie_header(cookie_header: str | None) -> str | None:
    if not cookie_header:
        return None
    parts = [p.strip() for p in cookie_header.split(';')]
    for part in parts:
        if part.startswith('access_token='):
            return part.split('=', 1)[1]
    return None


@router.websocket('/ws')
async def monitor_ws(ws: WebSocket):
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
