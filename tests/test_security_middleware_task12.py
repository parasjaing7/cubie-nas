from __future__ import annotations

import json

import pytest
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app import main


def _make_request(
    method: str,
    path: str,
    *,
    ip: str = '127.0.0.1',
    cookie: str | None = None,
    csrf_header: str | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b'cookie', cookie.encode()))
    if csrf_header:
        headers.append((b'x-csrf-token', csrf_header.encode()))

    scope = {
        'type': 'http',
        'http_version': '1.1',
        'method': method,
        'scheme': 'http',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': headers,
        'client': (ip, 12345),
        'server': ('testserver', 80),
    }

    async def _receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    return Request(scope, _receive)


@pytest.mark.asyncio
async def test_security_headers_added_on_success_response(monkeypatch):
    main._rate_limit_bucket.clear()
    monkeypatch.setattr(main, '_request_is_authenticated', lambda _request: True)

    request = _make_request('GET', '/healthz')

    async def _next(_request: Request):
        return JSONResponse({'ok': True})

    response = await main.security_middleware(request, _next)

    assert response.status_code == 200
    assert response.headers['Content-Security-Policy'].startswith("default-src 'self'")
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert response.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'


@pytest.mark.asyncio
async def test_csrf_enforced_globally_for_api_mutations(monkeypatch):
    main._rate_limit_bucket.clear()
    monkeypatch.setattr(main, '_request_is_authenticated', lambda _request: True)

    request = _make_request('POST', '/api/system/tls/generate')

    async def _next(_request: Request):
        return JSONResponse({'ok': True})

    response = await main.security_middleware(request, _next)

    assert response.status_code == 403
    assert json.loads(response.body)['detail'] == 'CSRF validation failed'


@pytest.mark.asyncio
async def test_csrf_login_endpoint_exempt(monkeypatch):
    main._rate_limit_bucket.clear()
    monkeypatch.setattr(main, '_request_is_authenticated', lambda _request: False)

    request = _make_request('POST', '/api/auth/login')

    async def _next(_request: Request):
        return JSONResponse({'ok': True})

    response = await main.security_middleware(request, _next)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_blocks_after_20_unauthenticated_api_requests():
    main._rate_limit_bucket.clear()
    ip = '10.10.10.10'

    allowed = [await main._allow_unauthenticated_request(ip) for _ in range(20)]
    blocked = await main._allow_unauthenticated_request(ip)

    assert all(allowed)
    assert blocked is False
