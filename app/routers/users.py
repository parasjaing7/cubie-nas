from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user, require_admin
from ..models import User
from ..schemas import ApiResponse, PasswordChangeRequest, SelfPasswordChangeRequest, UserCreate, UserOut, UserUpdateRequest
from ..security import hash_password, verify_password
from ..services.system_cmd import RealCommandRunner
from ..services.user_ctl import active_sessions, create_system_user, set_system_password

router = APIRouter(prefix='/api/users', tags=['users'])

_runner = RealCommandRunner()


@router.get('/app', response_model=list[UserOut])
def list_app_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post('/app', response_model=UserOut)
def create_app_user(payload: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail='User exists')
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post('/app/password')
def change_app_password(payload: PasswordChangeRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ApiResponse(ok=True, message='Password changed')


@router.post('/me/password')
def change_my_password(payload: SelfPasswordChangeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail='Current password is incorrect')

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ApiResponse(ok=True, message='Password changed')


@router.patch('/app/{username}')
def update_app_user(
    username: str,
    payload: UserUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')

    user.role = payload.role
    if payload.new_password:
        user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ApiResponse(ok=True, message='User updated')


@router.delete('/app/{username}')
def delete_app_user(
    username: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if user.username == current_user.username:
        raise HTTPException(status_code=400, detail='Cannot delete currently logged-in admin user')

    db.delete(user)
    db.commit()
    return ApiResponse(ok=True, message='User deleted')


@router.post('/system/create')
async def create_linux_user(payload: UserCreate, _: User = Depends(require_admin)):
    rc, out, err = await create_system_user(payload.username, payload.password)
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='System user created')


@router.post('/system/password')
async def set_linux_user_password(payload: PasswordChangeRequest, _: User = Depends(require_admin)):
    rc, out, err = await set_system_password(payload.username, payload.new_password)
    if rc != 0:
        raise HTTPException(status_code=400, detail=err or out)
    return ApiResponse(ok=True, message='System password changed')


@router.post('/permissions')
async def set_folder_permissions(username: str, path: str, mode: str = '770', _: User = Depends(require_admin)):
    import re
    if not re.fullmatch(r'[0-7]{3,4}', mode):
        raise HTTPException(status_code=400, detail='Invalid mode: must be 3 or 4 octal digits, e.g. 770')

    full = (Path(settings.nas_root) / path.lstrip('/')).resolve()
    if Path(settings.nas_root).resolve() not in [full, *full.parents]:
        raise HTTPException(status_code=400, detail='Invalid path')

    result_chown = await _runner.run(['chown', '-R', f'{username}:{username}', str(full)])
    if result_chown.exit_code != 0:
        raise HTTPException(status_code=400, detail=result_chown.stderr or result_chown.stdout)
    result_chmod = await _runner.run(['chmod', '-R', mode, str(full)])
    if result_chmod.exit_code != 0:
        raise HTTPException(status_code=400, detail=result_chmod.stderr or result_chmod.stdout)
    return ApiResponse(ok=True, message='Permissions updated')


@router.get('/sessions')
async def sessions(_: User = Depends(require_admin)):
    return {'ok': True, 'data': await active_sessions()}
