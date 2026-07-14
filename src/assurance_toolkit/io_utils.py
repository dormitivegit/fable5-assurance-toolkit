"""Bounded parsing, hashing, and deterministic serialization."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Iterable


def canonical_json(value: Any, *, pretty: bool = False) -> str:
    separators = None if pretty else (",", ":")
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=separators,
        sort_keys=False,
    ) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: os.PathLike[str] | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_all(descriptor: int, data: bytes) -> None:
    """Write all bytes or fail; shared by bounded no-clobber seams."""

    view = memoryview(data)
    offset = 0
    while offset < len(view):
        count = os.write(descriptor, view[offset:])
        if count <= 0:
            raise OSError("short write")
        offset += count


def parse_json_bytes(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def read_json(path: os.PathLike[str] | str) -> Any:
    with open(path, "rb") as handle:
        return parse_json_bytes(handle.read())


def read_jsonl(path: os.PathLike[str] | str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, "rb") as handle:
        for line_number, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            value = parse_json_bytes(raw)
            if not isinstance(value, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            records.append(value)
    return records


def json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must start with '/'")
    current = value
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    return current


def exact_source_resolves(identity: Any, location: Any) -> tuple[bool, str]:
    """Resolve only an explicitly named file or ZIP member and exact anchor."""

    if isinstance(identity, str):
        spec = {"path": identity}
    elif isinstance(identity, dict):
        spec = identity
    else:
        return False, "source identity is not a path/object"
    path_text = spec.get("path") or spec.get("source_path")
    if not path_text:
        return False, "source path missing"
    path = Path(path_text)
    if not path.is_file() or path.is_symlink():
        return False, "exact source is absent, non-regular, or a symlink"
    expected_hash = spec.get("sha256") or spec.get("source_sha256")
    member = spec.get("archive_member")
    try:
        if member:
            with zipfile.ZipFile(path) as archive:
                info = archive.getinfo(member)
                if info.is_dir():
                    return False, "archive member is a directory"
                data = archive.read(info)
        else:
            data = path.read_bytes()
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        return False, f"exact source resolution failed: {exc.__class__.__name__}"
    actual_hash = sha256_bytes(data)
    if expected_hash and expected_hash != actual_hash:
        return False, "source SHA-256 mismatch"
    if not location:
        return False, "location missing"
    try:
        if isinstance(location, str):
            if location not in data.decode("utf-8"):
                return False, "text anchor not found"
        elif isinstance(location, dict) and "json_pointer" in location:
            pointed = json_pointer(json.loads(data.decode("utf-8")), location["json_pointer"])
            if "expected" in location and pointed != location["expected"]:
                return False, "JSON Pointer expected value mismatch"
        elif isinstance(location, dict) and "anchor" in location:
            text = data.decode("utf-8")
            lines = text.splitlines()
            start = int(location.get("line_start", 1))
            end = int(location.get("line_end", len(lines)))
            if start < 1 or end < start or end > len(lines):
                return False, "line range out of bounds"
            if str(location["anchor"]) not in "\n".join(lines[start - 1 : end]):
                return False, "bounded text anchor not found"
        else:
            return False, "unsupported location form"
    except (IndexError, KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return False, "location resolution failed"
    return True, actual_hash


def paths_within(root: Path, paths: Iterable[Path]) -> bool:
    root_real = root.resolve(strict=False)
    for path in paths:
        try:
            path.resolve(strict=False).relative_to(root_real)
        except ValueError:
            return False
    return True
