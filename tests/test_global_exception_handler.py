from __future__ import annotations

import asyncio

from starlette.requests import Request

from app import main


def _request(path: str) -> Request:
    scope = {
        'type': 'http',
        'http_version': '1.1',
        'method': 'GET',
        'scheme': 'http',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': [],
        'client': ('127.0.0.1', 12345),
        'server': ('testserver', 80),
    }
    return Request(scope)


def test_unhandled_exception_handler_api_response_is_safe():
    request = _request('/api/test-crash')
    response = asyncio.run(main.unhandled_exception_handler(request, RuntimeError('boom at /tmp/private/path')))

    assert response.status_code == 500
    assert response.body == b'{"detail":"Internal server error. Please try again."}'
    assert b'/tmp/private/path' not in response.body


def test_unhandled_exception_handler_html_response_is_safe():
    request = _request('/overview')
    response = asyncio.run(main.unhandled_exception_handler(request, RuntimeError('unexpected /srv/nas path')))

    assert response.status_code == 500
    assert b'Unexpected error' in response.body
    assert b'/srv/nas' not in response.body
