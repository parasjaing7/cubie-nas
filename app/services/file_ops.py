from __future__ import annotations

import os
from pathlib import Path


def validate_path(requested_path: str, device_mountpoint: str) -> Path:
    base = Path(device_mountpoint).resolve(strict=False)
    candidate = (base / requested_path.lstrip('/')).resolve(strict=False)
    if base != candidate and base not in candidate.parents:
        raise PermissionError('Path traversal detected')
    return candidate


class FileOps:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def safe_path(self, rel: str) -> Path:
        return validate_path(rel, str(self.root))

    def list_dir(self, rel: str) -> list[dict]:
        target = self.safe_path(rel)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError('Directory not found')

        items: list[dict] = []
        for entry in target.iterdir():
            stat = entry.stat()
            items.append(
                {
                    'name': entry.name,
                    'path': str(entry.relative_to(self.root)),
                    'is_dir': entry.is_dir(),
                    'size': stat.st_size,
                    'mtime': int(stat.st_mtime),
                }
            )
        return items

    def mkdir(self, rel: str, name: str):
        (self.safe_path(rel) / name).mkdir(parents=False, exist_ok=False)

    def delete(self, rel: str):
        target = self.safe_path(rel)
        if target.is_dir():
            os.rmdir(target)
        else:
            target.unlink(missing_ok=False)

    def rename(self, rel: str, new_name: str):
        target = self.safe_path(rel)
        target.rename(target.with_name(new_name))
