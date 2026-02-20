from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine
from .deps import enforce_csrf
from .models import User
from .routers import auth, bonus, files, monitoring, network, services, storage, system, users
from .security import decode_token
from .security import hash_password

app = FastAPI(title=settings.app_name)

_SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; connect-src 'self' wss:",
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
}

_RATE_LIMIT_CAPACITY = 20.0
_RATE_LIMIT_REFILL_PER_SECOND = _RATE_LIMIT_CAPACITY / 60.0
_rate_limit_bucket: dict[str, dict[str, float]] = {}
_rate_limit_lock = asyncio.Lock()


def _parse_cors_origins(value: str) -> list[str]:
    return [origin.strip() for origin in value.split(',') if origin.strip()]


cors_origins = _parse_cors_origins(settings.cors_origins)
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'X-CSRF-Token'],
    )

app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')


def _apply_security_headers(response):
    for key, value in _SECURITY_HEADERS.items():
        response.headers[key] = value
    return response


def _client_ip(request: Request) -> str:
    xff = request.headers.get('x-forwarded-for', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


def _request_is_authenticated(request: Request) -> bool:
    auth = request.headers.get('Authorization', '')
    token = ''
    if auth.startswith('Bearer '):
        token = auth.split(' ', 1)[1].strip()
    elif request.cookies.get('access_token'):
        token = request.cookies.get('access_token', '').strip()

    if not token:
        return False

    try:
        payload = decode_token(token)
    except ValueError:
        return False

    return bool(payload.get('sub'))


async def _allow_unauthenticated_request(ip: str) -> bool:
    now = time.monotonic()
    async with _rate_limit_lock:
        bucket = _rate_limit_bucket.get(ip)
        if bucket is None:
            _rate_limit_bucket[ip] = {'tokens': _RATE_LIMIT_CAPACITY - 1.0, 'updated_at': now}
            return True

        elapsed = max(0.0, now - bucket['updated_at'])
        bucket['tokens'] = min(_RATE_LIMIT_CAPACITY, bucket['tokens'] + elapsed * _RATE_LIMIT_REFILL_PER_SECOND)
        bucket['updated_at'] = now

        if bucket['tokens'] < 1.0:
            return False

        bucket['tokens'] -= 1.0
        return True


@app.middleware('http')
async def security_middleware(request: Request, call_next):
    path = request.url.path

    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and path.startswith('/api/') and path != '/api/auth/login':
        try:
            enforce_csrf(request)
        except HTTPException as exc:
            return _apply_security_headers(JSONResponse({'detail': exc.detail}, status_code=exc.status_code))

    if path.startswith('/api/') and not _request_is_authenticated(request):
        allowed = await _allow_unauthenticated_request(_client_ip(request))
        if not allowed:
            return _apply_security_headers(JSONResponse({'detail': 'Rate limit exceeded'}, status_code=429))

    response = await call_next(request)
    return _apply_security_headers(response)


@app.on_event('startup')
def startup():
    if settings.jwt_secret == 'change-me':
        raise RuntimeError('Refusing to start with insecure default JWT secret. Set JWT_SECRET in .env')

    Path(settings.nas_root).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        if not db.query(User).first():
            admin = User(username='admin', password_hash=hash_password('admin12345'), role='admin')
            db.add(admin)
            db.commit()
    finally:
        db.close()


@app.get('/', response_class=HTMLResponse)
def root(request: Request):
    if request.cookies.get('access_token'):
        return RedirectResponse('/overview')
    return templates.TemplateResponse('login.html', {'request': request})


@app.get('/overview', response_class=HTMLResponse)
def overview_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('overview.html', {'request': request, 'page': 'overview'})


@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.cookies.get('access_token'):
        return RedirectResponse('/')
    return RedirectResponse('/overview')


@app.get('/users', response_class=HTMLResponse)
def users_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('users_page.html', {'request': request, 'page': 'users'})


@app.get('/settings', response_class=HTMLResponse)
def settings_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('settings_page.html', {'request': request, 'page': 'settings'})


def _require_login(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        return RedirectResponse('/')

    try:
        payload = decode_token(token)
    except ValueError:
        return RedirectResponse('/')

    username = payload.get('sub')
    if not username:
        return RedirectResponse('/')

    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
        if not user:
            return RedirectResponse('/')
    finally:
        db.close()

    return None


@app.get('/general', response_class=HTMLResponse)
def general_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('general.html', {'request': request, 'page': 'general'})


@app.get('/storage', response_class=HTMLResponse)
def storage_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('storage_page.html', {'request': request, 'page': 'storage'})


@app.get('/files', response_class=HTMLResponse)
def files_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('file_manager_page.html', {'request': request, 'page': 'files'})


@app.get('/services', response_class=HTMLResponse)
def services_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('services_page.html', {'request': request, 'page': 'services'})


@app.get('/network', response_class=HTMLResponse)
def network_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('network_page.html', {'request': request, 'page': 'network'})


@app.get('/nas', response_class=HTMLResponse)
def nas_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('nas_page.html', {'request': request, 'page': 'nas'})


@app.get('/healthz')
def healthz():
    return {'ok': True}


app.include_router(auth.router)
app.include_router(storage.router)
app.include_router(files.router)
app.include_router(monitoring.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(system.router)
app.include_router(system.ui_router)
app.include_router(bonus.router)
app.include_router(network.router)
