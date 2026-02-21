from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.routers import sharing
from app.schemas import ShareCreateRequest, ShareRemoveRequest


@dataclass
class _CmdResult:
    exit_code: int = 0
    stdout: str = 'ok'
    stderr: str = ''


class _Runner:
    async def run(self, _cmd):
        return _CmdResult()


def test_parse_shares_extracts_access_and_users():
    text = """
[global]
  workgroup = WORKGROUP

[public]
  path = /srv/nas/public
  guest ok = yes

[private]
  path = /srv/nas/private
  valid users = alice bob
"""
    rows = sharing._parse_shares(text)
    by_name = {r['name']: r for r in rows}

    assert by_name['public']['access'] == 'everyone'
    assert by_name['private']['access'] == 'specific'
    assert by_name['private']['users'] == ['alice', 'bob']


def test_upsert_share_block_replaces_existing_share():
    text = """
[global]
  workgroup = WORKGROUP

[media]
  path = /srv/nas/old
  guest ok = yes
"""
    updated = sharing._upsert_share_block(text, 'media', '/srv/nas/new', 'specific', ['alice'])

    assert '[media]' in updated
    assert 'path = /srv/nas/new' in updated
    assert 'valid users = alice' in updated
    assert '/srv/nas/old' not in updated


def test_remove_share_block_removes_only_target_section():
    text = """
[global]
  workgroup = WORKGROUP

[a]
  path = /srv/nas/a

[b]
  path = /srv/nas/b
"""
    updated = sharing._remove_share_block(text, 'a')

    assert '[a]' not in updated
    assert '/srv/nas/a' not in updated
    assert '[b]' in updated
    assert '/srv/nas/b' in updated


@pytest.mark.asyncio
async def test_add_and_remove_share_updates_smb_conf(monkeypatch, tmp_path):
    smb_path = tmp_path / 'smb.conf'
    smb_path.write_text('[global]\n  workgroup = WORKGROUP\n', encoding='utf-8')

    nas_root = tmp_path / 'nas'
    share_folder = nas_root / 'public'
    share_folder.mkdir(parents=True)

    monkeypatch.setattr(sharing, '_SMB_PATH', smb_path)
    monkeypatch.setattr(sharing, '_runner', _Runner())
    monkeypatch.setattr(sharing.settings, 'nas_root', str(nas_root))

    await sharing.add_share(
        ShareCreateRequest(name='public', folder=str(share_folder), access='everyone', users=[])
    )
    content_after_add = smb_path.read_text(encoding='utf-8')
    assert '[public]' in content_after_add
    assert f'path = {share_folder}' in content_after_add

    await sharing.remove_share(ShareRemoveRequest(name='public'))
    content_after_remove = smb_path.read_text(encoding='utf-8')
    assert '[public]' not in content_after_remove
