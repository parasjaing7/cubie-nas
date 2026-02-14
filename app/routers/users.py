from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import enforce_csrf, get_current_user, require_admin
from ..models import User
from ..schemas import ApiResponse, PasswordChangeRequest, UserCreate, UserOut
from ..security import hash_password
from ..services.system_cmd import run_cmd
from ..services.user_ctl import active_sessions, create_system_user, set_system_password

router = APIRouter(prefix='/api/users', tags=['users'])


@router.get('/app', response_model=list[UserOut])
def list_app_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post('/app', response_model=UserOut, dependencies=[Depends(enforce_csrf)])
def create_app_user(payload: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail='User exists')
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post('/app/password', dependencies=[Depends(enforce_csrf)])
def change_app_password(payload: PasswordChangeRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ApiResponse(ok=True, message='Password changed')


@router.post('/system/create', dependencies=[Depends(enforce_csrf)])
async def create_linux_user(payload: UserCreate, _: User = Depends(require_admin)):
    rc, out, err = await create_system_user(payload.username, payload.password)
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='System user created')


@router.post('/system/password', dependencies=[Depends(enforce_csrf)])
async def set_linux_user_password(payload: PasswordChangeRequest, _: User = Depends(require_admin)):
    rc, out, err = await set_system_password(payload.username, payload.new_password)
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='System password changed')


@router.post('/permissions', dependencies=[Depends(enforce_csrf)])
async def set_folder_permissions(username: str, path: str, mode: str = '770', _: User = Depends(require_admin)):
    full = (Path(settings.nas_root) / path.lstrip('/')).resolve()
    if Path(settings.nas_root).resolve() not in [full, *full.parents]:
        raise HTTPException(status_code=400, detail='Invalid path')

    rc1, _, err1 = await run_cmd(['chown', '-R', f'{username}:{username}', str(full)])
    if rc1 != 0:
        raise HTTPException(status_code=400, detail=err1)
    rc2, _, err2 = await run_cmd(['chmod', '-R', mode, str(full)])
    if rc2 != 0:
        raise HTTPException(status_code=400, detail=err2)
    return ApiResponse(ok=True, message='Permissions updated')


@router.get('/sessions')
async def sessions(_: User = Depends(require_admin)):
    return {'ok': True, 'data': await active_sessions()}
