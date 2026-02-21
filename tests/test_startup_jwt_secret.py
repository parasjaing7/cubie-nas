from __future__ import annotations

import pytest

from app import main


def _run_lifespan_startup(monkeypatch_obj):
    """Execute lifespan startup logic synchronously for testing."""
    import asyncio
    gen = main.lifespan(main.app)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(gen.__aenter__())
    finally:
        try:
            loop.run_until_complete(gen.__aexit__(None, None, None))
        except Exception:
            pass
        loop.close()


def test_startup_rejects_default_jwt_secret(monkeypatch):
    create_all_calls = {'count': 0}

    def _track_create_all(*args, **kwargs):
        create_all_calls['count'] += 1

    monkeypatch.setattr(main.settings, 'jwt_secret', 'change-me')
    monkeypatch.setattr(main.Base.metadata, 'create_all', _track_create_all)

    with pytest.raises(RuntimeError, match='JWT secret|JWT_SECRET|default'):
        _run_lifespan_startup(monkeypatch)

    assert create_all_calls['count'] == 0


def test_startup_allows_non_default_jwt_secret(monkeypatch, tmp_path):
    create_all_calls = {'count': 0}

    class _DummyQuery:
        def first(self):
            return True

    class _DummySession:
        def __init__(self):
            self.closed = False

        def query(self, _model):
            return _DummyQuery()

        def close(self):
            self.closed = True

    dummy_session = _DummySession()

    def _track_create_all(*args, **kwargs):
        create_all_calls['count'] += 1

    monkeypatch.setattr(main.settings, 'jwt_secret', 'super-long-random-secret')
    monkeypatch.setattr(main.settings, 'nas_root', str(tmp_path / 'nas'))
    monkeypatch.setattr(main.Base.metadata, 'create_all', _track_create_all)
    monkeypatch.setattr(main, 'SessionLocal', lambda: dummy_session)

    _run_lifespan_startup(monkeypatch)

    assert create_all_calls['count'] == 1
    assert dummy_session.closed is True
