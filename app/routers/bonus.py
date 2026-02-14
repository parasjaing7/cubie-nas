from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..deps import enforce_csrf, require_admin
from ..schemas import ApiResponse
from ..services.system_cmd import run_cmd

router = APIRouter(prefix='/api/bonus', tags=['bonus'])


@router.get('/docker/containers')
async def docker_list(_: object = Depends(require_admin)):
    rc, out, err = await run_cmd(['docker', 'ps', '-a', '--format', '{{.ID}} {{.Names}} {{.Status}}'])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    rows = []
    for line in out.splitlines():
        parts = line.split(' ', 2)
        if len(parts) == 3:
            rows.append({'id': parts[0], 'name': parts[1], 'status': parts[2]})
    return {'ok': True, 'data': rows}


@router.post('/docker/start', dependencies=[Depends(enforce_csrf)])
async def docker_start(container: str, _: object = Depends(require_admin)):
    rc, out, err = await run_cmd(['docker', 'start', container])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Container started')


@router.post('/docker/stop', dependencies=[Depends(enforce_csrf)])
async def docker_stop(container: str, _: object = Depends(require_admin)):
    rc, out, err = await run_cmd(['docker', 'stop', container])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Container stopped')


@router.post('/backup/run', dependencies=[Depends(enforce_csrf)])
async def backup_run(src: str, dst: str, _: object = Depends(require_admin)):
    src_path = (Path(settings.nas_root) / src.lstrip('/')).resolve()
    dst_path = (Path(settings.nas_root) / dst.lstrip('/')).resolve()
    root = Path(settings.nas_root).resolve()
    if root not in [src_path, *src_path.parents] or root not in [dst_path, *dst_path.parents]:
        raise HTTPException(status_code=400, detail='Path outside NAS root')

    rc, out, err = await run_cmd(['rsync', '-aH', '--delete', f'{src_path}/', f'{dst_path}/'])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Backup completed')


@router.get('/plugins')
def plugins(_: object = Depends(require_admin)):
    plugin_dir = Path('plugins')
    plugin_dir.mkdir(exist_ok=True)
    return {'ok': True, 'data': [p.name for p in plugin_dir.glob('*.py')]}
