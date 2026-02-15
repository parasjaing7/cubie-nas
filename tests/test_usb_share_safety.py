from __future__ import annotations

from pathlib import PosixPath

import pytest

from app.services import usb_share
from app.services.system_cmd import CommandResult, MockCommandRunner


def _result(exit_code: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(exit_code == 0, stdout, stderr, exit_code, 0.0)


@pytest.fixture
def mapped_paths(monkeypatch, tmp_path):
    class MappedPath(PosixPath):
        def __new__(cls, *args, **kwargs):
            path = PosixPath(*args, **kwargs)
            path_str = str(path)
            if path_str == "/srv/nas":
                path = tmp_path
            elif path_str.startswith("/srv/nas/"):
                path = tmp_path / path.relative_to("/srv/nas")
            elif path_str == "/etc":
                path = tmp_path / "etc"
            elif path_str.startswith("/etc/"):
                path = tmp_path / path.relative_to("/etc")
            return PosixPath.__new__(cls, path)

    monkeypatch.setattr(usb_share, "Path", MappedPath)


@pytest.mark.asyncio
async def test_preflight_rejects_os_disk(mapped_paths):
    runner = MockCommandRunner()
    runner.queue_result(_result(stdout="disk usb 100G RootDisk"))  # preflight lsblk
    runner.queue_result(_result(stdout="/dev/sda2"))  # findmnt SOURCE /
    runner.queue_result(_result(stdout="sda"))  # lsblk PKNAME for root source

    ok, message, _ = await usb_share.provision_usb_share(
        device="/dev/sda",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert "OS disk" in message


@pytest.mark.asyncio
async def test_concurrency_lock_rejects_parallel_request(mapped_paths):
    runner = MockCommandRunner()

    await usb_share._PROVISION_LOCK.acquire()
    try:
        ok, message, _ = await usb_share.provision_usb_share(
            device="/dev/sdb1",
            share_name="testshare",
            mountpoint="/srv/nas/testshare",
            format_before_mount=False,
            fs_type=None,
            runner=runner,
        )
    finally:
        usb_share._PROVISION_LOCK.release()

    assert ok is False
    assert "already in progress" in message


def test_filesystem_provision_lock_is_exclusive(monkeypatch, tmp_path):
    lock_path = tmp_path / "provision.lock"
    monkeypatch.setattr(usb_share, "_PROVISION_FILE_LOCK_PATH", lock_path)

    first_fd = usb_share._acquire_provision_file_lock()
    assert first_fd is not None

    try:
        second_fd = usb_share._acquire_provision_file_lock()
        assert second_fd is None
    finally:
        usb_share._release_provision_file_lock(first_fd)

    third_fd = usb_share._acquire_provision_file_lock()
    assert third_fd is not None
    usb_share._release_provision_file_lock(third_fd)


@pytest.mark.asyncio
async def test_filesystem_lock_failure_rejects_request(mapped_paths, monkeypatch):
    runner = MockCommandRunner()

    monkeypatch.setattr(usb_share, "_acquire_provision_file_lock", lambda: None)

    ok, message, _ = await usb_share.provision_usb_share(
        device="/dev/sdb1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert "already in progress" in message
    assert runner.calls == []


@pytest.mark.asyncio
async def test_filesystem_lock_released_after_attempt(mapped_paths, monkeypatch):
    released = {"value": False}

    monkeypatch.setattr(usb_share, "_acquire_provision_file_lock", lambda: 123)

    def _release(fd: int):
        assert fd == 123
        released["value"] = True

    async def _fake_impl(**kwargs):
        return True, "ok", {}

    monkeypatch.setattr(usb_share, "_release_provision_file_lock", _release)
    monkeypatch.setattr(usb_share, "_provision_block_share_impl", _fake_impl)

    ok, _, _ = await usb_share.provision_usb_share(
        device="/dev/sdb1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=MockCommandRunner(),
    )

    assert ok is True
    assert released["value"] is True
