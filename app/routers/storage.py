from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import enforce_csrf, get_current_user, require_admin
from ..schemas import ApiResponse, DriveFormatRequest, MountRequest, UsbShareRequest
from ..services.storage import list_drives, smart_status
from ..services.system_cmd import run_cmd
from ..services.usb_share import provision_nvme_share, provision_usb_share

router = APIRouter(prefix='/api/storage', tags=['storage'])


@router.get('/drives')
async def drives(include_smart: bool = Query(default=False), _=Depends(get_current_user)):
    data = await list_drives()
    if include_smart:
        for d in data:
            d['smart_status'] = await smart_status(d['device'])
    return {'ok': True, 'data': data}


@router.post('/mount', dependencies=[Depends(enforce_csrf)])
async def mount_drive(payload: MountRequest, _=Depends(require_admin)):
    rc, out, err = await run_cmd(['mount', payload.device, payload.mountpoint])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Mounted')


@router.post('/unmount', dependencies=[Depends(enforce_csrf)])
async def unmount_drive(payload: MountRequest, _=Depends(require_admin)):
    rc, out, err = await run_cmd(['umount', payload.device])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='Unmounted')


@router.post('/format', dependencies=[Depends(enforce_csrf)])
async def format_drive(payload: DriveFormatRequest, _=Depends(require_admin)):
    if payload.confirmation != f'FORMAT {payload.device}':
        raise HTTPException(status_code=400, detail='Confirmation text mismatch')

    if payload.fs_type != 'ext4':
        raise HTTPException(status_code=400, detail='Only ext4 is supported for NAS usage')

    rc, out, err = await run_cmd(['mkfs.ext4', '-F', payload.device])
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message=f'Formatted {payload.device} as ext4')


@router.post('/usb/provision-smb', dependencies=[Depends(enforce_csrf)])
async def provision_usb_as_smb(payload: UsbShareRequest, _=Depends(require_admin)):
    ok, message, data = await provision_usb_share(
        device=payload.device,
        share_name=payload.share_name,
        mountpoint=payload.mountpoint,
        format_before_mount=payload.format_before_mount,
        fs_type=payload.fs_type,
        wipe_repartition=payload.wipe_repartition,
        wipe_confirmation=payload.wipe_confirmation,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return ApiResponse(ok=True, message=message, data=data)


@router.post('/nvme/provision-smb', dependencies=[Depends(enforce_csrf)])
async def provision_nvme_as_smb(payload: UsbShareRequest, _=Depends(require_admin)):
    ok, message, data = await provision_nvme_share(
        device=payload.device,
        share_name=payload.share_name,
        mountpoint=payload.mountpoint,
        format_before_mount=payload.format_before_mount,
        fs_type=payload.fs_type,
        wipe_repartition=payload.wipe_repartition,
        wipe_confirmation=payload.wipe_confirmation,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return ApiResponse(ok=True, message=message, data=data)
