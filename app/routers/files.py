from __future__ import annotations

import os
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from ..config import settings
from ..deps import get_current_user
from ..schemas import ApiResponse, BulkDownloadRequest, FileActionRequest, MkdirRequest
from ..services.file_ops import FileOps

router = APIRouter(prefix='/api/files', tags=['files'])
ops = FileOps(settings.nas_root)


@router.get('/list')
def list_files(
    path: str = Query(default=''),
    sort_by: str = Query(default='name', pattern='^(name|size|date)$'),
    order: str = Query(default='asc', pattern='^(asc|desc)$'),
    _=Depends(get_current_user),
):
    try:
        items = ops.list_dir(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    reverse = order == 'desc'
    key_map = {'name': lambda i: i['name'].lower(), 'size': lambda i: i['size'], 'date': lambda i: i['mtime']}
    items.sort(key=key_map[sort_by], reverse=reverse)
    return {'ok': True, 'data': items}


@router.post('/upload')
async def upload(path: str = Query(default=''), file: UploadFile = File(...), _=Depends(get_current_user)):
    try:
        target_dir = ops.safe_path(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    target = target_dir / file.filename
    with target.open('wb') as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)
        f.flush()
        os.fsync(f.fileno())
    return ApiResponse(ok=True, message='Uploaded')


@router.get('/download')
def download(path: str = Query(...), _=Depends(get_current_user)):
    try:
        target = ops.safe_path(path)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail='File not found')
    return FileResponse(target, filename=target.name)


@router.post('/download-bulk')
def download_bulk(payload: BulkDownloadRequest, _=Depends(get_current_user)):
    if not payload.paths:
        raise HTTPException(status_code=400, detail='No paths provided')

    archive = BytesIO()
    with zipfile.ZipFile(archive, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for raw in payload.paths:
            try:
                target = ops.safe_path(raw)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc))

            if not target.exists() or not target.is_file():
                continue

            arcname = Path(raw).name or target.name
            zf.write(target, arcname=arcname)

    archive.seek(0)
    headers = {'Content-Disposition': 'attachment; filename="files.zip"'}
    return StreamingResponse(archive, media_type='application/zip', headers=headers)


@router.post('/mkdir')
def mkdir(payload: MkdirRequest, _=Depends(get_current_user)):
    try:
        ops.mkdir(payload.path, payload.name)
        return ApiResponse(ok=True, message='Folder created')
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/rename')
def rename(payload: FileActionRequest, _=Depends(get_current_user)):
    if not payload.new_name:
        raise HTTPException(status_code=400, detail='new_name is required')
    try:
        ops.rename(payload.path, payload.new_name)
        return ApiResponse(ok=True, message='Renamed')
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post('/delete')
def delete(payload: FileActionRequest, _=Depends(get_current_user)):
    try:
        full = ops.safe_path(payload.path)
        if full.is_dir() and any(full.iterdir()):
            raise HTTPException(status_code=400, detail='Directory not empty')
        ops.delete(payload.path)
        return ApiResponse(ok=True, message='Deleted')
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
