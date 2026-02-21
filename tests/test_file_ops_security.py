from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers import files
from app.services import file_ops
from app.schemas import BulkDownloadRequest


def test_validate_path_blocks_traversal(tmp_path):
    with pytest.raises(PermissionError):
        file_ops.validate_path('../../etc/passwd', str(tmp_path))


def test_list_files_returns_403_on_path_traversal(monkeypatch):
    def _deny(_path: str):
        raise PermissionError('Path traversal detected')

    monkeypatch.setattr(files.ops, 'list_dir', _deny)

    with pytest.raises(HTTPException) as exc:
        files.list_files(path='../../etc', sort_by='name', order='asc')

    assert exc.value.status_code == 403


def test_bulk_download_returns_403_on_path_traversal(monkeypatch):
    def _deny(_path: str):
        raise PermissionError('Path traversal detected')

    monkeypatch.setattr(files.ops, 'safe_path', _deny)

    with pytest.raises(HTTPException) as exc:
        files.download_bulk(BulkDownloadRequest(paths=['../../etc/passwd']))

    assert exc.value.status_code == 403
