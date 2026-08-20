"""PM-04: bounded, versioned corpus freeze and integrity verification."""

from __future__ import annotations

import os
import re
import stat
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

from .findings import finding, outcome, sort_findings
from .io_utils import canonical_json, parse_json_bytes, sha256_bytes, sha256_file
from .models import ModuleResult
from .no_clobber import write_new_or_same

MODULE_ID = "PM-04"
RULE_VERSION = "ci-v1-recovery"
SCHEMA_VERSION = "corpus-manifest/v1"
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")


def _under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _path_forms(path: Path) -> tuple[Path, Path]:
    return Path(os.path.abspath(os.path.normpath(path))), path.resolve(strict=False)


def _excluded(lexical: Path, real: Path, exclusions: list[tuple[Path, Path]]) -> bool:
    return any(_under(lexical, left) or _under(real, right) for left, right in exclusions)


def _parse_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(data.splitlines(), 1):
        if not raw.strip():
            continue
        value = parse_json_bytes(raw)
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number} is not a JSON object")
        records.append(value)
    return records


def _current_special_file_skip_count(header: dict[str, Any], manifest: Path) -> int | None:
    roots = header.get("roots")
    raw_exclusions = header.get("exclusions")
    if not isinstance(roots, list) or not all(isinstance(item, str) for item in roots):
        return None
    if not isinstance(raw_exclusions, list) or not all(isinstance(item, str) for item in raw_exclusions):
        return None
    root_forms = [_path_forms(Path(item)) for item in roots]
    if any(not lexical.exists() or lexical.is_symlink() or not lexical.is_dir() for lexical, _ in root_forms):
        return None
    exclusion_forms = [_path_forms(Path(item)) for item in raw_exclusions]
    exclusion_forms.append(_path_forms(manifest))
    skipped_special = 0
    for root_lex, _ in root_forms:
        for current, dirs, files in os.walk(root_lex, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_dirs = []
            for name in sorted(dirs):
                path = current_path / name
                lexical, real = _path_forms(path)
                if _excluded(lexical, real, exclusion_forms) or path.is_symlink():
                    continue
                kept_dirs.append(name)
            dirs[:] = kept_dirs
            for name in sorted(files):
                path = current_path / name
                lexical, real = _path_forms(path)
                if _excluded(lexical, real, exclusion_forms):
                    continue
                if not path.is_symlink() and not path.is_file():
                    skipped_special += 1
    return skipped_special


def _archive_records(root_index: int, root: Path, file_path: Path, relative: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if file_path.suffix.lower() != ".zip":
        return records
    try:
        with zipfile.ZipFile(file_path) as archive:
            for info in sorted(archive.infolist(), key=lambda item: item.filename):
                member = PurePosixPath(info.filename)
                if info.is_dir() or member.is_absolute() or ".." in member.parts or "\\" in info.filename:
                    continue
                data = archive.read(info)
                records.append({
                    "schema_version": SCHEMA_VERSION,
                    "record_type": "source_record",
                    "source_type": "archive_member",
                    "root_index": root_index,
                    "root": str(root),
                    "relative_path": f"{relative}!{info.filename}",
                    "filesystem_path": str(file_path),
                    "archive_member": info.filename,
                    "bytes": len(data),
                    "sha256": sha256_bytes(data),
                })
    except (OSError, zipfile.BadZipFile):
        return []
    return records


def _symlink_record(root_index: int, root: Path, path: Path, relative: str) -> dict[str, Any]:
    target = os.readlink(path)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "source_record",
        "source_type": "symlink",
        "root_index": root_index,
        "root": str(root),
        "relative_path": relative,
        "filesystem_path": str(path),
        "link_target": target,
        "bytes": len(target.encode()),
        "sha256": sha256_bytes(target.encode()),
    }


def freeze(
    roots: list[str | Path],
    exclusions: list[str | Path],
    new_manifest_path: str | Path,
    options: dict[str, Any] | None = None,
) -> ModuleResult:
    findings = []
    options = options or {}
    manifest = Path(new_manifest_path)
    if not roots:
        findings.append(finding("CI07_UNBOUNDED_ROOT", "ERROR", "$", "roots", "at least one explicit bounded root is required", []))
    if manifest.is_symlink() or (manifest.exists() and not manifest.is_file()):
        findings.append(finding("CI08_MANIFEST_COLLISION", "HOLD", str(manifest), "manifest", "manifest output is a symlink or non-file collision", "EXISTS"))
    root_forms: list[tuple[Path, Path]] = []
    for raw in roots:
        lexical, real = _path_forms(Path(raw))
        if not lexical.exists() or lexical.is_symlink() or not lexical.is_dir():
            findings.append(finding("CI07_UNBOUNDED_ROOT", "HOLD", str(lexical), "root", "root must be an existing non-symlink directory", "INVALID_ROOT"))
        else:
            root_forms.append((lexical, real))
    user_exclusion_forms = [_path_forms(Path(raw)) for raw in exclusions]
    manifest_forms = _path_forms(manifest)
    exclusion_forms = list(user_exclusion_forms)
    exclusion_forms.append(manifest_forms)
    for root_lex, root_real in root_forms:
        if _under(manifest_forms[0], root_lex) or _under(manifest_forms[1], root_real):
            findings.append(finding("CI01_OUTPUT_WITHIN_SOURCE_EXCLUDED", "INFO", str(manifest), "manifest", "nested manifest output is excluded before source enumeration", str(root_lex)))
    if any(item.severity in {"ERROR", "HOLD"} for item in findings):
        sorted_items = sort_findings(findings)
        result, exit_code = outcome(sorted_items, "normal", family="integrity")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code)

    records: list[dict[str, Any]] = []
    skipped_special = 0
    for root_index, (root_lex, root_real) in enumerate(root_forms):
        for current, dirs, files in os.walk(root_lex, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_dirs = []
            for name in sorted(dirs):
                path = current_path / name
                lexical, real = _path_forms(path)
                if _excluded(lexical, real, exclusion_forms):
                    continue
                if path.is_symlink():
                    records.append(_symlink_record(root_index, root_lex, path, path.relative_to(root_lex).as_posix()))
                else:
                    kept_dirs.append(name)
            dirs[:] = kept_dirs
            for name in sorted(files):
                path = current_path / name
                lexical, real = _path_forms(path)
                if _excluded(lexical, real, exclusion_forms):
                    continue
                relative = path.relative_to(root_lex).as_posix()
                if path.is_symlink():
                    records.append(_symlink_record(root_index, root_lex, path, relative))
                elif path.is_file():
                    record = {
                        "schema_version": SCHEMA_VERSION,
                        "record_type": "source_record",
                        "source_type": "filesystem_file",
                        "root_index": root_index,
                        "root": str(root_lex),
                        "relative_path": relative,
                        "filesystem_path": str(path),
                        "bytes": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                    records.append(record)
                    if options.get("expand_archives", True):
                        records.extend(_archive_records(root_index, root_lex, path, relative))
                else:
                    skipped_special += 1
    records.sort(key=lambda item: (item["root_index"], item["relative_path"], item["source_type"]))
    by_hash: dict[str, list[str]] = defaultdict(list)
    for record in records:
        by_hash[record["sha256"]].append(f"{record['root_index']}:{record['relative_path']}:{record['source_type']}")
    duplicate_groups = [
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "duplicate_group",
            "sha256": digest,
            "members": sorted(members),
        }
        for digest, members in sorted(by_hash.items())
        if len(members) > 1
    ]
    header = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "manifest_header",
        "rule_version": RULE_VERSION,
        "roots": [str(item[0]) for item in root_forms],
        "real_roots": [str(item[1]) for item in root_forms],
        "exclusions": sorted({str(item[0]) for item in user_exclusion_forms}),
        "creation_mode": "EXPLICIT_NEW_FILE_NO_CLOBBER",
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "manifest_summary",
        "source_record_count": len(records),
        "duplicate_group_count": len(duplicate_groups),
        "special_file_skip_count": skipped_special,
    }
    lines = [header, *records, *duplicate_groups, summary]
    data = "".join(canonical_json(item) for item in lines).encode("utf-8")
    try:
        disposition = write_new_or_same(manifest, data)
    except (FileExistsError, NotADirectoryError, OSError) as exc:
        findings.append(finding("CI08_MANIFEST_COLLISION", "HOLD", str(manifest), "manifest", "manifest output could not be created without clobber", exc.__class__.__name__))
        sorted_items = sort_findings(findings)
        result, exit_code = outcome(sorted_items, "normal", family="integrity")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, exit_code=exit_code)
    return ModuleResult("PASS", MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), facts=[{"manifest_sha256": sha256_bytes(data)}, {"source_record_count": len(records)}], exit_code=0, data={"manifest": str(manifest), "write_disposition": disposition, "source_record_count": len(records), "duplicate_group_count": len(duplicate_groups), "special_file_skip_count": skipped_special})


def verify(
    manifest_path: str | Path,
    detect_new: bool = False,
    accepted_manifest_sha256: str | None = None,
) -> ModuleResult:
    findings = []
    manifest = Path(manifest_path)
    if accepted_manifest_sha256 is not None and (
        not isinstance(accepted_manifest_sha256, str)
        or SHA256_PATTERN.fullmatch(accepted_manifest_sha256) is None
    ):
        findings.append(finding(
            "IN01_PARSE_ERROR",
            "ERROR",
            str(manifest),
            "accepted_manifest_sha256",
            "accepted manifest SHA-256 must be exactly 64 hexadecimal characters",
            accepted_manifest_sha256,
        ))
        result, exit_code = outcome(findings, "normal")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), exit_code=exit_code)
    try:
        manifest_bytes = manifest.read_bytes()
    except OSError as exc:
        findings.append(finding("CI09_MALFORMED_MANIFEST", "ERROR", str(manifest), "manifest", "manifest cannot be read as object-per-line JSONL", exc.__class__.__name__))
        result, exit_code = outcome(findings, "normal", family="integrity")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), exit_code=exit_code)
    actual_manifest_sha256 = sha256_bytes(manifest_bytes)
    if (
        accepted_manifest_sha256 is not None
        and accepted_manifest_sha256.lower() != actual_manifest_sha256
    ):
        findings.append(finding(
            "CI11_ACCEPTED_MANIFEST_MISMATCH",
            "HOLD",
            str(manifest),
            "manifest",
            "manifest raw-byte SHA-256 differs from the caller-supplied accepted identity",
            {"expected": accepted_manifest_sha256.lower(), "actual": actual_manifest_sha256},
        ))
    try:
        records = _parse_jsonl_bytes(manifest_bytes)
    except (UnicodeError, ValueError) as exc:
        findings.append(finding("CI09_MALFORMED_MANIFEST", "ERROR", str(manifest), "manifest", "manifest cannot be parsed as object-per-line JSONL", exc.__class__.__name__))
        result, exit_code = outcome(findings, "normal", family="integrity")
        return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sort_findings(findings), exit_code=exit_code)
    if not records or records[0].get("record_type") != "manifest_header":
        findings.append(finding("CI09_MALFORMED_MANIFEST", "ERROR", str(manifest), "line 1", "line 1 must be manifest_header", records[0].get("record_type") if records else "EMPTY"))
        header = {}
    else:
        header = records[0]
    if header and header.get("rule_version") != RULE_VERSION:
        findings.append(finding(
            "IN02_UNSUPPORTED_VERSION",
            "ERROR",
            str(manifest),
            "line 1 rule_version",
            "unsupported PM-04 manifest rule version",
            header.get("rule_version"),
        ))
    for index, record in enumerate(records, 1):
        if record.get("schema_version") != SCHEMA_VERSION:
            findings.append(finding("IN02_UNSUPPORTED_VERSION", "ERROR", str(manifest), f"line {index}", "unsupported manifest schema version", record.get("schema_version")))
        if record.get("record_type") not in {"manifest_header", "source_record", "duplicate_group", "manifest_summary"}:
            findings.append(finding("CI09_MALFORMED_MANIFEST", "ERROR", str(manifest), f"line {index}", "unknown manifest record type", record.get("record_type")))

    exclusions = [Path(value) for value in header.get("exclusions", []) if isinstance(value, str)]
    states: list[dict[str, Any]] = []
    source_records = [item for item in records if item.get("record_type") == "source_record"]
    duplicate_groups = [item for item in records if item.get("record_type") == "duplicate_group"]
    summaries = [item for item in records if item.get("record_type") == "manifest_summary"]
    observed_summary = summaries[0] if len(summaries) == 1 else None
    actual_summary = {
        "source_record_count": len(source_records),
        "duplicate_group_count": len(duplicate_groups),
        "special_file_skip_count": _current_special_file_skip_count(header, manifest) if header else None,
    }
    summary_consistent = observed_summary is not None and records[-1] is observed_summary
    if summary_consistent:
        for name, actual in actual_summary.items():
            observed = observed_summary.get(name)
            if isinstance(observed, bool) or not isinstance(observed, int) or observed < 0:
                summary_consistent = False
                break
            if actual is not None and observed != actual:
                summary_consistent = False
                break
    if not summary_consistent:
        findings.append(finding(
            "CI12_MANIFEST_SUMMARY_INCONSISTENT",
            "ERROR",
            str(manifest),
            "manifest_summary",
            "manifest summary counts or placement do not match the manifest records and current special-file skips",
            {"observed": observed_summary, "actual": actual_summary, "summary_record_count": len(summaries)},
        ))
    observed_members: dict[str, set[str]] = defaultdict(set)
    for record in source_records:
        path = Path(str(record.get("filesystem_path", "")))
        source_type = record.get("source_type")
        state = "MATCH"
        if any(_under(path.resolve(strict=False), exclusion.resolve(strict=False)) for exclusion in exclusions) or path.resolve(strict=False) == manifest.resolve(strict=False):
            state = "SELF_INGESTED"
            findings.append(finding("CI05_SELF_INGESTED", "HOLD", str(path), "source_record", "manifest record points into an excluded/output path", record.get("relative_path")))
        elif not path.exists() and not path.is_symlink():
            state = "MISSING"
            findings.append(finding("CI02_SOURCE_MISSING", "ERROR", str(path), "source_record", "accepted source is missing", record.get("relative_path")))
        elif source_type == "filesystem_file":
            if not path.is_file() or path.is_symlink():
                state = "TYPE_CHANGED"
                findings.append(finding("CI04_SOURCE_TYPE_CHANGED", "ERROR", str(path), "source_record", "filesystem source type changed", source_type))
            elif path.stat().st_size != record.get("bytes") or sha256_file(path) != record.get("sha256"):
                state = "CHANGED"
                findings.append(finding("CI03_SOURCE_CHANGED", "ERROR", str(path), "source_record", "filesystem source bytes changed", record.get("relative_path")))
        elif source_type == "symlink":
            if not path.is_symlink():
                state = "TYPE_CHANGED"
                findings.append(finding("CI04_SOURCE_TYPE_CHANGED", "ERROR", str(path), "source_record", "symlink source type changed", source_type))
            else:
                target = os.readlink(path)
                if sha256_bytes(target.encode()) != record.get("sha256"):
                    state = "CHANGED"
                    findings.append(finding("CI03_SOURCE_CHANGED", "ERROR", str(path), "source_record", "symlink identity changed", target))
        elif source_type == "archive_member":
            member = str(record.get("archive_member", ""))
            try:
                with zipfile.ZipFile(path) as archive:
                    data = archive.read(member)
                if len(data) != record.get("bytes") or sha256_bytes(data) != record.get("sha256"):
                    state = "CHANGED"
                    findings.append(finding("CI03_SOURCE_CHANGED", "ERROR", str(path), member, "archive member bytes changed", member))
                observed_members[str(path)].add(member)
            except (OSError, KeyError, zipfile.BadZipFile):
                state = "MISSING"
                findings.append(finding("CI02_SOURCE_MISSING", "ERROR", str(path), member, "archive member is missing", member))
        else:
            state = "TYPE_CHANGED"
            findings.append(finding("CI04_SOURCE_TYPE_CHANGED", "ERROR", str(path), "source_record", "unsupported recorded source type", source_type))
        states.append({"path": str(path), "relative_path": record.get("relative_path"), "state": state})

    for group in duplicate_groups:
        expected = sorted(group.get("members", []))
        actual = sorted(
            f"{record['root_index']}:{record['relative_path']}:{record['source_type']}"
            for record in source_records
            if record.get("sha256") == group.get("sha256")
        )
        if expected != actual or len(expected) < 2:
            findings.append(finding("CI06_DUPLICATE_GROUP_INCONSISTENT", "ERROR", str(manifest), "duplicate_group", "duplicate group does not match physical source records", {"expected": expected, "actual": actual}))

    if detect_new and header:
        known = {(item.get("root_index"), item.get("relative_path")) for item in source_records if item.get("source_type") == "filesystem_file"}
        for root_index, root_text in enumerate(header.get("roots", [])):
            root = Path(root_text)
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = path.relative_to(root).as_posix()
                if (root_index, relative) not in known and not any(_under(path.resolve(strict=False), exclusion.resolve(strict=False)) for exclusion in exclusions):
                    findings.append(finding("CI10_NEW_SOURCE_DETECTED", "WARN", str(path), "detect_new", "new bounded source is not in the frozen manifest", relative))

    sorted_items = sort_findings(findings)
    result, exit_code = outcome(sorted_items, "normal", family="integrity")
    counts = {name.lower(): sum(item["state"] == name for item in states) for name in ("MATCH", "MISSING", "CHANGED", "TYPE_CHANGED", "SELF_INGESTED")}
    return ModuleResult(result, MODULE_ID, rule_set_version=RULE_VERSION, findings=sorted_items, facts=states, exit_code=exit_code, data={"counts": counts, "detect_new": detect_new})
