from __future__ import annotations

from pathlib import PosixPath

import pytest

from app.services import usb_share
from app.services.system_cmd import CommandResult, MockCommandRunner


def _result(exit_code: int = 0, stdout: str = "", stderr: str = "") -> CommandResult:
    return CommandResult(exit_code == 0, stdout, stderr, exit_code, 0.0)


@pytest.fixture
def mapped_paths(monkeypatch, tmp_path):
    etc_root = tmp_path / "etc"
    samba_root = etc_root / "samba"
    samba_root.mkdir(parents=True, exist_ok=True)

    fstab = etc_root / "fstab"
    smb = samba_root / "smb.conf"

    fstab_content = "# fstab base\n"
    smb_content = "[global]\nworkgroup = WORKGROUP\n"
    fstab.write_text(fstab_content)
    smb.write_text(smb_content)

    class MappedPath(PosixPath):
        def __new__(cls, *args, **kwargs):
            path = PosixPath(*args, **kwargs)
            if str(path).startswith("/srv/nas/"):
                path = tmp_path / path.relative_to("/srv/nas")
            elif str(path).startswith("/etc/"):
                path = tmp_path / path.relative_to("/etc")
            return PosixPath.__new__(cls, path)

    monkeypatch.setattr(usb_share, "Path", MappedPath)

    return {
        "fstab": fstab,
        "smb": smb,
        "fstab_content": fstab_content,
        "smb_content": smb_content,
    }


@pytest.mark.asyncio
async def test_config_rollback_on_testparm_failure(mapped_paths):
    runner = MockCommandRunner()
    runner.queue_result(_result(stdout="usb"))  # lsblk TRAN
    runner.queue_result(_result(stdout="part"))  # lsblk TYPE
    runner.queue_result(_result(stdout=""))  # findmnt
    runner.queue_result(_result(stdout="ext4"))  # blkid TYPE
    runner.queue_result(_result(stdout="UUID-123"))  # blkid UUID
    runner.queue_result(_result())  # chown mountpoint
    runner.queue_result(_result())  # chmod mountpoint
    runner.queue_result(_result())  # mount
    runner.queue_result(_result())  # chown -R
    runner.queue_result(_result())  # chmod -R
    runner.queue_result(_result(exit_code=1, stderr="testparm failed"))  # testparm
    runner.queue_result(_result())  # umount rollback

    ok, message, _ = await usb_share.provision_usb_share(
        device="/dev/sda1",
        share_name="testshare",
        mountpoint="/srv/nas/testshare",
        format_before_mount=False,
        fs_type=None,
        runner=runner,
    )

    assert ok is False
    assert "Samba config test failed" in message
    assert mapped_paths["fstab"].read_text() == mapped_paths["fstab_content"]
    assert mapped_paths["smb"].read_text() == mapped_paths["smb_content"]
    assert any(call["cmd"][0] == "umount" for call in runner.calls)
