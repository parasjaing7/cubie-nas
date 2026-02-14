from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import LoginAttempt, User
from ..schemas import LoginRequest, TokenResponse
from ..security import create_access_token, new_csrf_token, verify_password

router = APIRouter(prefix='/api/auth', tags=['auth'])

MAX_ATTEMPTS = 5
LOCK_MINUTES = 10


def _client_ip(request: Request) -> str:
    xff = request.headers.get('x-forwarded-for')
    if xff:
        return xff.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    attempt = db.query(LoginAttempt).filter(LoginAttempt.username == payload.username, LoginAttempt.ip_address == ip).first()
    if attempt and attempt.lock_until and attempt.lock_until > now:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail='Account temporarily locked')

    user = db.query(User).filter(User.username == payload.username, User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        if not attempt:
            attempt = LoginAttempt(username=payload.username, ip_address=ip, failed_count=0, last_attempt=now)
            db.add(attempt)
        attempt.failed_count += 1
        attempt.last_attempt = now
        if attempt.failed_count >= MAX_ATTEMPTS:
            attempt.lock_until = now + timedelta(minutes=LOCK_MINUTES)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')

    if attempt:
        attempt.failed_count = 0
        attempt.lock_until = None
        attempt.last_attempt = now
        db.commit()

    token = create_access_token(user.username, user.role)
    csrf = new_csrf_token()
    is_https = request.url.scheme == 'https'
    response.set_cookie('access_token', token, httponly=True, secure=is_https, samesite='strict', max_age=7200)
    response.set_cookie('csrf_token', csrf, httponly=False, secure=is_https, samesite='strict', max_age=7200)
    return TokenResponse(access_token=token)


@router.post('/logout')
def logout(response: Response):
    response.delete_cookie('access_token')
    response.delete_cookie('csrf_token')
    return {'ok': True, 'message': 'Logged out'}
