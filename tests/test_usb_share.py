from __future__ import annotations

from pathlib import PosixPath

import pytest

from app.services import usb_share
from app.services.system_cmd import CommandResult, MockCommandRunner


def _result(exit_code: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(exit_code == 0, stdout, stderr, exit_code, 0.0)


def _queue_success_common(runner: MockCommandRunner):
    runner.queue_result(_result(stdout="part usb 64G TestDisk"))  # preflight lsblk
    runner.queue_result(_result(stdout=""))  # findmnt SOURCE /
    runner.queue_result(_result(stdout="part"))  # lsblk TYPE
    runner.queue_result(_result(stdout=""))  # findmnt current mount
    runner.queue_result(_result(stdout="ext4"))  # blkid TYPE
    runner.queue_result(_result(stdout="UUID-123"))  # blkid UUID
    runner.queue_result(_result())  # chown mountpoint
    runner.queue_result(_result())  # chmod mountpoint


@pytest.fixture
def mapped_paths(monkeypatch, tmp_path):
    class MappedPath(PosixPath):
        _mapped_root = tmp_path

        def __new__(cls, *args, **kwargs):
            path = PosixPath(*args, **kwargs)
            path_str = str(path)
            if path_str == "/srv/nas":
                path = tmp_path
            elif path_str.startswith("/srv/nas/"):
                path = tmp_path / path.relative_to("/srv/nas")
            return PosixPath.__new__(cls, path)

    monkeypatch.setattr(usb_share, "Path", MappedPath)
    monkeypatch.setattr(usb_share, "_upsert_fstab", lambda *args, **kwargs: None)
    monkeypatch.setattr(usb_share, "_upsert_samba_share", lambda *args, **kwargs: None)
    monkeypatch.setattr(usb_share, "_backup_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(usb_share, "_restore_file", lambda *args, **kwargs: None)


@pytest.mark.asyncio
async def test_successful_storage_provisioning(mapped_paths):
    runner = MockCommandRunner()
    _queue_success_common(runner)
    runner.queue_result(_result())  # mount
    runner.queue_result(_result(stdout="/srv/nas/testshare"))  # verify mount target
    runner.queue_result(_result(stdout="/dev/sda1"))  # verify mount source
    runner.queue_result(_result(stdout="UUID-123"))  # verify source UUID
    runner.queue_result(_result())  # chown -R
    runner.queue_result(_result())  # chmod -R
    runner.queue_result(_result())  # testparm
    runner.queue_result(_result())  # systemctl enable
    runner.queue_result(_result())  # systemctl restart

    ok, message, data = await usb_share.provision_usb_share(
        device="/dev/sda1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is True
    assert "mounted" in message
    assert data["share_name"] == "testshare"
    assert data["filesystem"] == "ext4"


@pytest.mark.asyncio
async def test_command_failure_rollback(mapped_paths):
    runner = MockCommandRunner()
    _queue_success_common(runner)
    runner.queue_result(_result())  # mount
    runner.queue_result(_result(stdout="/srv/nas/testshare"))  # verify mount target
    runner.queue_result(_result(stdout="/dev/sda1"))  # verify mount source
    runner.queue_result(_result(stdout="UUID-123"))  # verify source UUID
    runner.queue_result(_result(exit_code=1, stderr="chown failed"))  # chown -R
    runner.queue_result(_result())  # umount after failure

    ok, message, _ = await usb_share.provision_usb_share(
        device="/dev/sda1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert "chown failed" in message.lower() or "ownership update failed" in message
    assert any(call["cmd"][0] == "umount" for call in runner.calls)


@pytest.mark.asyncio
async def test_invalid_device_input(mapped_paths):
    runner = MockCommandRunner()

    ok, message, _ = await usb_share.provision_usb_share(
        device="sda1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert message == "Invalid device path"
    assert runner.calls == []


@pytest.mark.asyncio
async def test_mount_failure_scenario(mapped_paths):
    runner = MockCommandRunner()
    _queue_success_common(runner)
    runner.queue_result(_result(exit_code=32, stderr="mount failed"))  # mount

    ok, message, _ = await usb_share.provision_usb_share(
        device="/dev/sda1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert "mount failed" in message.lower()
    assert not any(call["cmd"][0] == "chown" and "-R" in call["cmd"] for call in runner.calls)
