from __future__ import annotations

import pytest

from app.services import user_ctl
from app.services.system_cmd import CommandResult, MockCommandRunner


@pytest.mark.asyncio
async def test_set_system_password_uses_system_cmd_runner(monkeypatch):
    runner = MockCommandRunner(CommandResult(True, 'ok', '', 0, 0.0))
    monkeypatch.setattr(user_ctl, '_runner', runner)

    rc, out, err = await user_ctl.set_system_password('alice', 's3cret')

    assert rc == 0
    assert out == 'ok'
    assert err == ''
    assert runner.calls[0]['cmd'] == ['chpasswd']
    assert runner.calls[0]['input_text'] == 'alice:s3cret\n'


@pytest.mark.asyncio
async def test_create_system_user_runs_useradd_then_chpasswd(monkeypatch):
    runner = MockCommandRunner()
    runner.queue_result(CommandResult(True, '', '', 0, 0.0))
    runner.queue_result(CommandResult(True, '', '', 0, 0.0))
    monkeypatch.setattr(user_ctl, '_runner', runner)

    rc, out, err = await user_ctl.create_system_user('bob', 'pw123456')

    assert rc == 0
    assert out == ''
    assert err == ''
    assert runner.calls[0]['cmd'] == ['useradd', '-m', 'bob']
    assert runner.calls[1]['cmd'] == ['chpasswd']
    assert runner.calls[1]['input_text'] == 'bob:pw123456\n'
