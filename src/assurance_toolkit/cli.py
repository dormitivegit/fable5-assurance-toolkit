"""Complete public CLI for the six-module recovery candidate and four pilots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .closeout import validate_closeout
from .corpus import freeze, verify
from .evaluation import prepare, score
from .governance import check
from .handoff import validate_handoff
from .io_utils import canonical_json, read_json
from .pilots import run_pilot
from .risk import classify
from .terminal import preflight
from .version import PRODUCT_VERSION, PYTHON_DISTRIBUTION_VERSION, STATUS


def _input(path: str | None, use_stdin: bool) -> Any:
    if use_stdin:
        return json.load(sys.stdin)
    if path is None:
        raise ValueError("an input path or --stdin is required")
    return read_json(path)


def _text(payload: dict[str, Any]) -> str:
    lines = []
    preferred = (
        "result", "module_id", "module_version", "rule_set_version", "profile",
        "tier", "base_reason", "plan", "allow_write", "exit_code",
    )
    emitted = set()
    for key in preferred:
        if key in payload:
            value = payload[key]
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list, bool)) else str(value)
            lines.append(f"{key}={rendered}")
            emitted.add(key)
    for key, value in payload.items():
        if key in emitted or key in {"findings", "facts"}:
            continue
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list, bool)) else str(value)
        lines.append(f"{key}={rendered}")
    for item in payload.get("findings", []):
        lines.append("FINDING " + json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def _emit(payload: dict[str, Any], output_format: str) -> None:
    sys.stdout.write(canonical_json(payload, pretty=True) if output_format == "json" else _text(payload))


def _parse_failure(command: str, exc: Exception) -> tuple[dict[str, Any], int]:
    payload = {
        "result": "FAIL",
        "module_id": command,
        "module_version": PRODUCT_VERSION,
        "rule_set_version": "recovery-1",
        "profile": "normal",
        "findings": [{
            "code": "IN01_PARSE_ERROR",
            "severity": "ERROR",
            "path": "$",
            "location": "$",
            "message": "input could not be parsed",
            "rule_version": "recovery-1",
            "evidence": exc.__class__.__name__,
        }],
        "facts": [],
        "exit_code": 2,
    }
    return payload, 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="assurance", description="FABLE5 local deterministic assurance toolkit")
    parser.add_argument("--version", action="store_true", help="show product and Python distribution versions")
    commands = parser.add_subparsers(dest="command")

    classify_parser = commands.add_parser("classify", help="classify task risk by action effect")
    classify_parser.add_argument("path", nargs="?")
    classify_parser.add_argument("--stdin", action="store_true")
    classify_parser.add_argument("--profile", choices=("normal", "strict"), default="normal")
    classify_parser.add_argument("--format", choices=("text", "json"), default="text")

    check_parser = commands.add_parser("check", help="validate a governance pack")
    check_parser.add_argument("path", nargs="?")
    check_parser.add_argument("--stdin", action="store_true")
    check_parser.add_argument("--tier", choices=("T0", "T1", "T2", "T3", "T4"))
    check_parser.add_argument("--authority-id", metavar="IDENTITY", help="caller-supplied expected authority identity")
    check_parser.add_argument("--profile", choices=("normal", "strict"), default="normal")
    check_parser.add_argument("--format", choices=("text", "json"), default="text")

    guard_parser = commands.add_parser("guard", help="read-only terminal and collision preflight")
    guard_parser.add_argument("task_state")
    guard_parser.add_argument("target")
    guard_parser.add_argument("--executor")
    guard_parser.add_argument("--reopen")
    guard_parser.add_argument("--authority-id", metavar="IDENTITY", help="caller-supplied expected authority identity")
    guard_parser.add_argument("--format", choices=("text", "json"), default="text")

    corpus_parser = commands.add_parser("corpus", help="freeze or verify a bounded corpus")
    corpus_commands = corpus_parser.add_subparsers(dest="corpus_command", required=True)
    freeze_parser = corpus_commands.add_parser("freeze", help="record exact bytes for bounded source roots")
    freeze_parser.add_argument("roots", nargs="+", help="source root path; repeat positionally for multiple roots")
    freeze_parser.add_argument("--manifest", required=True, help="write the new manifest at this explicit path")
    freeze_parser.add_argument("--exclude", action="append", default=[], help="exclude by path containment/prefix semantics; not shell-glob matching")
    freeze_parser.add_argument("--format", choices=("text", "json"), default="text", help="select human-readable text or structured JSON output")
    verify_parser = corpus_commands.add_parser("verify", help="verify current sources against an accepted manifest")
    verify_parser.add_argument("manifest", help="manifest path to verify")
    verify_parser.add_argument("--accepted-manifest-sha256", metavar="SHA256", help="bind verification to the caller-accepted exact manifest bytes")
    verify_parser.add_argument("--expected-root", action="append", default=None, metavar="ROOT", help="assert a manifest root by index")
    verify_parser.add_argument("--detect-new", action="store_true", help="report newly discovered sources as nonblocking CI10 WARN under current corpus semantics")
    verify_parser.add_argument("--format", choices=("text", "json"), default="text", help="select human-readable text or structured JSON output")

    handoff_parser = commands.add_parser("handoff", help="observe/lint a handoff against an exact carrier")
    handoff_parser.add_argument("file")
    handoff_parser.add_argument("--carrier", required=True, choices=("direct-v1-ax1-ax2", "skill-v1-candidate-ax1-ax2"))
    handoff_parser.add_argument("--profile", choices=("normal", "strict"), default="normal")
    handoff_parser.add_argument("--format", choices=("text", "json"), default="text")

    closeout_parser = commands.add_parser("closeout", help="deterministically validate a closeout")
    closeout_parser.add_argument("file")
    closeout_parser.add_argument("--profile", choices=("normal", "strict"), default="normal")
    closeout_parser.add_argument("--guard-receipt")
    closeout_parser.add_argument("--authority-id", metavar="IDENTITY", help="caller-supplied expected authority identity")
    closeout_parser.add_argument("--format", choices=("text", "json"), default="text")

    eval_parser = commands.add_parser("eval", help="prepare or score the preserved successor evaluation")
    eval_commands = eval_parser.add_subparsers(dest="eval_command", required=True)
    prepare_parser = eval_commands.add_parser("prepare")
    prepare_parser.add_argument("case_set")
    prepare_parser.add_argument("--out", required=True)
    prepare_parser.add_argument("--format", choices=("text", "json"), default="text")
    score_parser = eval_commands.add_parser("score")
    score_parser.add_argument("case_set")
    score_parser.add_argument("scores")
    score_parser.add_argument("--format", choices=("text", "json"), default="text")

    pilot_parser = commands.add_parser("pilot", help="run a synthetic disposable Batch 4 pilot")
    pilot_commands = pilot_parser.add_subparsers(dest="pilot_command", required=True)
    run_parser = pilot_commands.add_parser("run")
    run_parser.add_argument("pilot", choices=("A", "B", "C1", "C2"))
    run_parser.add_argument("--root", required=True)
    run_parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        sys.stdout.write(
            f"assurance {PRODUCT_VERSION}\n"
            f"python-distribution-version: {PYTHON_DISTRIBUTION_VERSION}\n"
            f"status: {STATUS}\n"
        )
        return 0
    if not args.command:
        parser.print_help()
        return 0
    output_format = getattr(args, "format", "text")
    try:
        if args.command == "classify":
            payload = classify(_input(args.path, args.stdin), args.profile).to_dict()
        elif args.command == "check":
            source_base = None if args.stdin or args.path is None else Path(args.path).resolve(strict=False).parent
            payload = check(
                _input(args.path, args.stdin),
                args.profile,
                authority_identity=args.authority_id,
                source_base=source_base,
            ).to_dict()
            if args.tier:
                payload["supplied_tier"] = args.tier
        elif args.command == "guard":
            state = read_json(args.task_state)
            receipt = read_json(args.reopen) if args.reopen else None
            payload = preflight(state, args.target, args.executor, receipt, authority_identity=args.authority_id).to_dict()
        elif args.command == "corpus" and args.corpus_command == "freeze":
            payload = freeze(args.roots, args.exclude, args.manifest).to_dict()
        elif args.command == "corpus" and args.corpus_command == "verify":
            payload = verify(
                args.manifest,
                args.detect_new,
                accepted_manifest_sha256=args.accepted_manifest_sha256,
                expected_roots=args.expected_root,
            ).to_dict()
        elif args.command == "handoff":
            payload = validate_handoff(args.file, args.carrier, args.profile).to_dict()
        elif args.command == "closeout":
            payload = validate_closeout(args.file, args.profile, args.guard_receipt, authority_identity=args.authority_id).to_dict()
        elif args.command == "eval" and args.eval_command == "prepare":
            payload = prepare(args.case_set, args.out).to_dict()
        elif args.command == "eval" and args.eval_command == "score":
            payload = score(args.case_set, args.scores).to_dict()
        elif args.command == "pilot" and args.pilot_command == "run":
            payload = run_pilot(args.pilot, args.root)
            payload["exit_code"] = 0 if payload.get("result") == "PASS" else 3
        else:
            parser.error("unsupported command")
            return 2
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        payload, code = _parse_failure(args.command, exc)
        _emit(payload, output_format)
        return code
    _emit(payload, output_format)
    return int(payload.get("exit_code", 0))
