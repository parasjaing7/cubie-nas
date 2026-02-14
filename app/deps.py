from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token


def _extract_token(request: Request) -> str:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth.split(' ', 1)[1]
    token = request.cookies.get('access_token')
    if token:
        return token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing token')


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_token(request)
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')

    username = payload.get('sub')
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token payload')

    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin role required')
    return current_user


def enforce_csrf(request: Request):
    if request.method in {'GET', 'HEAD', 'OPTIONS'}:
        return

    if request.url.path.startswith('/api/auth/login'):
        return

    cookie = request.cookies.get('csrf_token')
    header = request.headers.get('X-CSRF-Token')
    if not cookie or not header or cookie != header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF validation failed')
