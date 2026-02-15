from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, SessionLocal, engine
from .models import User
from .routers import auth, bonus, files, monitoring, network, services, storage, system, users
from .security import decode_token
from .security import hash_password

app = FastAPI(title=settings.app_name)


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


@app.get('/logs', response_class=HTMLResponse)
def logs_page(request: Request):
    redirect = _require_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse('logs_page.html', {'request': request, 'page': 'logs'})


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
app.include_router(bonus.router)
app.include_router(network.router)
