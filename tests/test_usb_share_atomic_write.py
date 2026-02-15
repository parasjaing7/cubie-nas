from __future__ import annotations

import os
import stat

from app.services import usb_share


def test_atomic_write_text_updates_file(tmp_path):
    target = tmp_path / "sample.conf"
    target.write_text("old\n", encoding="utf-8")

    usb_share._atomic_write_text(target, "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_write_text_fsyncs_parent_directory(monkeypatch, tmp_path):
    target = tmp_path / "sample.conf"

    original_fsync = os.fsync
    calls = {"file": 0, "dir": 0}

    def tracking_fsync(fd: int):
        mode = os.fstat(fd).st_mode
        if stat.S_ISDIR(mode):
            calls["dir"] += 1
        else:
            calls["file"] += 1
        return original_fsync(fd)

    monkeypatch.setattr(usb_share.os, "fsync", tracking_fsync)

    usb_share._atomic_write_text(target, "value\n")

    assert calls["file"] >= 1
    assert calls["dir"] >= 1
    assert target.read_text(encoding="utf-8") == "value\n"


def test_backup_file_creates_atomic_backup(monkeypatch, tmp_path):
    source = tmp_path / "source.conf"
    source.write_text("alpha\n", encoding="utf-8")

    original_fsync = os.fsync
    calls = {"file": 0, "dir": 0}

    def tracking_fsync(fd: int):
        mode = os.fstat(fd).st_mode
        if stat.S_ISDIR(mode):
            calls["dir"] += 1
        else:
            calls["file"] += 1
        return original_fsync(fd)

    monkeypatch.setattr(usb_share.os, "fsync", tracking_fsync)

    backup = usb_share._backup_file(source)

    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "alpha\n"
    assert calls["file"] >= 1
    assert calls["dir"] >= 1


def test_restore_file_restores_from_backup_atomically(monkeypatch, tmp_path):
    target = tmp_path / "target.conf"
    backup = tmp_path / "target.conf.cubie-nas.bak"
    target.write_text("broken\n", encoding="utf-8")
    backup.write_text("restored\n", encoding="utf-8")

    original_fsync = os.fsync
    calls = {"file": 0, "dir": 0}

    def tracking_fsync(fd: int):
        mode = os.fstat(fd).st_mode
        if stat.S_ISDIR(mode):
            calls["dir"] += 1
        else:
            calls["file"] += 1
        return original_fsync(fd)

    monkeypatch.setattr(usb_share.os, "fsync", tracking_fsync)

    usb_share._restore_file(target, backup)

    assert target.read_text(encoding="utf-8") == "restored\n"
    assert calls["file"] >= 1
    assert calls["dir"] >= 1


def test_backup_file_preserves_permissions(tmp_path):
    source = tmp_path / "source.conf"
    source.write_text("alpha\n", encoding="utf-8")
    os.chmod(source, 0o640)

    backup = usb_share._backup_file(source)

    assert backup is not None
    assert stat.S_IMODE(backup.stat().st_mode) == 0o640


def test_restore_file_preserves_backup_permissions(tmp_path):
    target = tmp_path / "target.conf"
    backup = tmp_path / "target.conf.cubie-nas.bak"
    target.write_text("broken\n", encoding="utf-8")
    backup.write_text("restored\n", encoding="utf-8")
    os.chmod(target, 0o600)
    os.chmod(backup, 0o644)

    usb_share._restore_file(target, backup)

    assert target.read_text(encoding="utf-8") == "restored\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
