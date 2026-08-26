"""Explicit no-clobber file output for bounded product outputs."""

from __future__ import annotations

import errno
import os
import secrets
from pathlib import Path

from .io_utils import sha256_bytes, sha256_file, write_all


def write_new_or_same(path: Path, data: bytes) -> str:
    """Create new bytes exclusively or return an untouched same-hash no-op."""

    if path.is_symlink():
        raise FileExistsError("output path is a symlink")
    if path.exists():
        if path.is_file() and sha256_file(path) == sha256_bytes(data):
            return "IDEMPOTENT_NOOP"
        raise FileExistsError("output collision")
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise NotADirectoryError("output parent must be an existing regular directory")
    temp = parent / f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
    descriptor = -1
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        write_all(descriptor, data)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temp, path, follow_symlinks=False)
        except OSError as exc:
            if exc.errno == errno.EEXIST and path.is_file() and not path.is_symlink():
                if sha256_file(path) == sha256_bytes(data):
                    return "IDEMPOTENT_NOOP"
            raise FileExistsError("output collision during atomic install") from exc
        directory_fd = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return "CREATED"
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
