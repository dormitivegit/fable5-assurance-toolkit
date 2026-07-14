"""Identity helpers kept independent from product module policy."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from .io_utils import sha256_bytes, sha256_file


def file_identity(path: os.PathLike[str] | str) -> dict[str, Any]:
    item = Path(path)
    st = item.lstat()
    identity: dict[str, Any] = {
        "mode": stat.S_IMODE(st.st_mode),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "inode": st.st_ino,
        "device": st.st_dev,
        "uid": st.st_uid,
        "gid": st.st_gid,
    }
    if item.is_symlink():
        target = os.readlink(item)
        identity.update({"type": "symlink", "sha256": sha256_bytes(target.encode())})
    elif item.is_file():
        identity.update({"type": "file", "sha256": sha256_file(item)})
    elif item.is_dir():
        identity.update({"type": "directory"})
    else:
        identity.update({"type": "special"})
    if hasattr(os, "listxattr"):
        try:
            identity["xattrs"] = {
                name: os.getxattr(item, name).hex() for name in sorted(os.listxattr(item))
            }
        except OSError:
            identity["xattrs"] = "UNAVAILABLE"
    return identity
