from __future__ import annotations

from pathlib import Path


def test_systemd_unit_has_filesystem_sandboxing():
    unit_path = Path("systemd/cubie-nas.service")
    content = unit_path.read_text(encoding="utf-8")

    assert "ProtectSystem=strict" in content
    assert "ProtectHome=true" in content

    expected_rw_paths = (
        "/opt/cubie-nas",
        "/var/lib/cubie-nas",
        "/srv/nas",
        "/etc/samba",
        "/etc/fstab",
        "/etc/cubie-nas",
        "/etc/network/interfaces.d",
    )

    for path in expected_rw_paths:
        assert path in content
