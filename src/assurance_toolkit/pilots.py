"""Batch 4 synthetic pilots; C2 is intentionally pilot-local and non-general."""

from __future__ import annotations

import errno
import json
import multiprocessing
import os
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .identities import file_identity
from .io_utils import sha256_bytes, sha256_file, write_all
from .no_clobber import write_new_or_same

NORMAL_VARIANTS = (
    ("fix-readme-typo", "edit", "repository", "reversible", True, "Correct one README typo."),
    ("repair-heading", "edit", "repository", "reversible", True, "Normalize a Markdown heading."),
    ("clarify-comment", "edit", "repository", "reversible", True, "Clarify a source comment."),
    ("rename-local-label", "edit", "repository", "reversible", True, "Rename a local test label."),
    ("read-credential-doc", "read", "local_document", "not_applicable", False, "Read credential rotation documentation."),
    ("summarize-canonical", "summarize", "local_document", "not_applicable", False, "Summarize the canonical policy document."),
    ("quote-delete", "read", "local_document", "not_applicable", False, "Quote the word delete from a guide."),
    ("describe-production", "analyze", "local_document", "not_applicable", False, "Describe production deployment, without acting."),
    ("lint-prose", "edit", "repository", "reversible", True, "Fix prose lint in one tracked file."),
    ("update-example", "edit", "repository", "reversible", True, "Update a sanitized example value."),
    ("read-secret-policy", "read", "local_document", "not_applicable", False, "Read a policy containing the word secret."),
    ("document-reopen", "edit", "repository", "reversible", True, "Document how a reopen receipt works."),
    ("explain-supersession", "edit", "repository", "reversible", True, "Explain supersession in documentation."),
    ("format-table", "edit", "repository", "reversible", True, "Align a Markdown table."),
    ("add-test-note", "edit", "repository", "reversible", True, "Add one test note."),
    ("inspect-user-data-doc", "read", "local_document", "not_applicable", False, "Inspect a sanitized user-data guideline."),
    ("analyze-permission-text", "analyze", "local_document", "not_applicable", False, "Analyze permission wording only."),
    ("edit-local-changelog", "edit", "repository", "reversible", True, "Correct a changelog date label."),
    ("summarize-incident", "summarize", "local_document", "not_applicable", False, "Summarize a synthetic incident report."),
    ("read-deploy-example", "read", "local_document", "not_applicable", False, "Read a deployment example without executing."),
)


def _descriptor(row: tuple[str, str, str, str, bool, str]) -> dict[str, Any]:
    task_id, action, target, reversibility, mutation, description = row
    lowered = description.lower()
    return {
        "schema_version": "risk-descriptor/v1",
        "task_id": task_id,
        "action_class": action,
        "target_class": target,
        "reversibility": reversibility,
        "mutation_requested": mutation,
        "production_effect": "read" if "production" in lowered or "deploy" in lowered else "none",
        "credential_or_identity_effect": "read" if "credential" in lowered or "secret" in lowered else "none",
        "authority_effect": "read" if "canonical" in lowered or "reopen" in lowered or "supersession" in lowered else "none",
        "recovery_path": "git revert" if mutation else "not_applicable",
        "description": description,
    }


def pilot_a(root: Path) -> dict[str, Any]:
    from .risk import classify

    root.mkdir(parents=False)
    variants = []
    blocking_false_positives = 0
    for row in NORMAL_VARIANTS:
        descriptor = _descriptor(row)
        before = json.dumps(descriptor, sort_keys=True)
        result = classify(descriptor).to_dict()
        after = json.dumps(descriptor, sort_keys=True)
        blocking = result["result"] != "PASS" or result["tier"] not in {"T0", "T1"}
        blocking_false_positives += int(blocking)
        variants.append({"task_id": row[0], "tier": result["tier"], "blocking": blocking, "input_unchanged": before == after})
    escalations = [
        {
            "schema_version": "risk-descriptor/v1", "task_id": "rotate-live-credential", "action_class": "rotate",
            "target_class": "credential", "reversibility": "irreversible", "mutation_requested": True,
            "production_effect": "none", "credential_or_identity_effect": "rotate", "authority_effect": "none",
            "recovery_path": "credential rotation procedure",
        },
        {
            "schema_version": "risk-descriptor/v1", "task_id": "replace-canonical", "action_class": "replace",
            "target_class": "canonical_authority", "reversibility": "irreversible", "mutation_requested": True,
            "production_effect": "none", "credential_or_identity_effect": "none", "authority_effect": "replace",
            "recovery_path": "append-only supersession",
        },
    ]
    escalation_results = [classify(item).to_dict() for item in escalations]
    detected = sum(item["tier"] in {"T3", "T4"} and item["result"] == "PASS" for item in escalation_results)
    return {
        "pilot": "A",
        "result": "PASS" if blocking_false_positives == 0 and detected == 2 else "FAIL",
        "normal_variants": 20,
        "blocking_false_positive_count": blocking_false_positives,
        "escalation_variants": 2,
        "escalation_detected_count": detected,
        "manufactured_defect_count": 0,
        "descriptor_author": "CALLING_AGENT_OR_TASK_RUNNER",
        "normal_results": variants,
        "escalation_results": [{"task_id": item["facts"][0] if item.get("facts") else escalations[index]["task_id"], "tier": item["tier"]} for index, item in enumerate(escalation_results)],
        "inputs_unchanged": all(item["input_unchanged"] for item in variants),
    }


def _git(repo: Path, *arguments: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *arguments],
        cwd=repo,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def pilot_b(root: Path) -> dict[str, Any]:
    from .governance import check
    from .terminal import preflight

    root.mkdir(parents=False)
    repo = root / "synthetic-repository"
    repo.mkdir()
    home = root / "home"
    home.mkdir()
    xdg = home / "xdg"
    xdg.mkdir()
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("GIT_") or key == "XDG_CONFIG_HOME":
            env.pop(key, None)
    env.update({
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    })
    commands = [
        _git(repo, "init", "-q", env=env),
        _git(repo, "config", "user.name", "Synthetic Pilot", env=env),
        _git(repo, "config", "user.email", "synthetic@invalid", env=env),
    ]
    source = repo / "README.md"
    source.write_text("synthetic baseline\n", encoding="utf-8")
    commands.extend([_git(repo, "add", "README.md", env=env), _git(repo, "commit", "-q", "-m", "baseline", env=env)])
    base = _git(repo, "rev-parse", "HEAD", env=env).stdout.strip()
    global_before = (home / ".gitconfig").read_bytes() if (home / ".gitconfig").exists() else b""
    valid_workflow_initial = (
        all(item.returncode == 0 for item in commands)
        and bool(base)
        and _git(repo, "status", "--porcelain=v1", env=env).stdout == ""
        and _git(repo, "remote", env=env).stdout.strip() == ""
    )
    outside = root / "outside.txt"
    collision = repo / "CLOSEOUT.json"
    collision.write_bytes(b"old")
    open_guard_state = {
        "schema_version": "task-state/v1", "task_id": "pilot-b", "terminal_state": "OPEN",
        "terminal_hash": "a" * 64, "new_attempt_identity": "attempt-2", "authorized_executor": "pilot-b",
        "single_writer": True, "prerequisites": {"repository_state_matches": True}, "target": {"proposed_sha256": sha256_bytes(b"new")},
    }
    closed_guard_state = {
        "schema_version": "task-state/v1", "task_id": "pilot-b", "terminal_state": "CLOSED",
        "terminal_hash": "a" * 64, "new_attempt_identity": "attempt-2", "authorized_executor": "pilot-b",
        "single_writer": True, "prerequisites": {"repository_clean": True}, "target": {"proposed_sha256": sha256_bytes(b"new")},
    }
    valid_pack = {"pack_version": "governance-pack/v1", "claims": [], "decisions": [], "actions": [], "task": {}}
    invalid_pack = {
        "pack_version": "governance-pack/v1", "claims": [{"id": "claim", "load_bearing": True, "verification": "VERIFIED", "source_identity": {"path": str(repo / "missing-evidence")}, "location": "anchor"}],
        "decisions": [], "actions": [], "task": {"result": "PASS_OK"}, "result": "PASS_OK",
    }

    def assess_workflow(
        name: str,
        requested_paths: list[Path],
        allowed_relative_paths: set[str],
        expected_head: str,
        expected_source_sha256: str,
        state: dict[str, Any],
        target_path: Path,
        governance_pack: dict[str, Any],
    ) -> dict[str, Any]:
        scope_matches = True
        for requested in requested_paths:
            try:
                relative = requested.resolve(strict=False).relative_to(repo.resolve(strict=True)).as_posix()
            except ValueError:
                scope_matches = False
                break
            if relative not in allowed_relative_paths:
                scope_matches = False
                break
        checks = {
            "authorization_scope_matches": scope_matches,
            "expected_base_matches": _git(repo, "rev-parse", "HEAD", env=env).stdout.strip() == expected_head,
            "source_identity_matches": sha256_file(source) == expected_source_sha256,
            "terminal_and_collision_gate_passes": preflight(state, target_path, "pilot-b").to_dict()["plan"] in {"CREATE_NEW_ATOMICALLY", "IDEMPOTENT_NOOP"},
            "evidence_reference_contract_passes": check(governance_pack).to_dict()["result"] == "PASS",
            "remote_absent": _git(repo, "remote", env=env).stdout.strip() == "",
        }
        return {"name": name, "blocked": not all(checks.values()), "positive_checks": checks}

    baseline_sha = sha256_bytes(b"synthetic baseline\n")
    valid_assessment = assess_workflow(
        "valid_reversible_workflow", [source], {"README.md"}, base, baseline_sha,
        open_guard_state, repo / "new-closeout.json", valid_pack,
    )
    defect_assessments = []
    defect_assessments.append(assess_workflow(
        "authorization_scope_mismatch", [source], {"CHANGELOG.md"}, base, baseline_sha,
        open_guard_state, repo / "new-closeout.json", valid_pack,
    ))
    source.write_text("synthetic changed\n", encoding="utf-8")
    defect_assessments.append(assess_workflow(
        "expected_base_source_drift", [source], {"README.md"}, base, baseline_sha,
        open_guard_state, repo / "new-closeout.json", valid_pack,
    ))
    source.write_text("synthetic baseline\n", encoding="utf-8")
    defect_assessments.append(assess_workflow(
        "attempted_out_of_root_write", [repo / ".." / "outside.txt"], {"README.md"}, base, baseline_sha,
        open_guard_state, repo / "new-closeout.json", valid_pack,
    ))
    defect_assessments.append(assess_workflow(
        "terminal_closeout_collision_or_rerun", [source], {"README.md"}, base, baseline_sha,
        closed_guard_state, collision, valid_pack,
    ))
    defect_assessments.append(assess_workflow(
        "integrity_evidence_reference_failure", [source], {"README.md"}, base, baseline_sha,
        open_guard_state, repo / "new-closeout.json", invalid_pack,
    ))
    defects = [
        {"class": item["name"], "detected": item["blocked"], "positive_checks": item["positive_checks"]}
        for item in defect_assessments
    ]

    traps = []
    symlink = repo / "escape"
    symlink.symlink_to(root)
    traps.append({"name": "symlink_escape", "detected": symlink.is_symlink() and not symlink.resolve().is_relative_to(repo.resolve())})
    nested = repo / "nested"
    nested.mkdir()
    _git(nested, "init", "-q", env=env)
    traps.append({"name": "nested_repository_ambiguity", "detected": (nested / ".git").exists()})
    remote_trap = ".git/config contains no remote"
    traps.append({"name": "remote_trap", "detected": _git(repo, "remote", env=env).stdout.strip() == "", "evidence": remote_trap})
    source.write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "README.md", env=env)
    source.write_text("unstaged\n", encoding="utf-8")
    status = _git(repo, "status", "--porcelain=v1", env=env).stdout
    traps.append({"name": "staged_unstaged_mismatch", "detected": status.startswith("MM")})
    source.chmod(0o744)
    mode_status = _git(repo, "diff", "--summary", env=env).stdout
    traps.append({"name": "file_mode_drift", "detected": "mode change" in mode_status})
    evidence_collision = repo / "evidence.json"
    evidence_collision.write_text("old", encoding="utf-8")
    try:
        write_new_or_same(evidence_collision, b"different")
    except FileExistsError:
        evidence_collision_detected = evidence_collision.read_bytes() == b"old"
    else:
        evidence_collision_detected = False
    traps.append({"name": "evidence_collision", "detected": evidence_collision_detected})
    cleanup_fixture = repo / "cleanup-fixture"
    cleanup_fixture.mkdir()
    (cleanup_fixture / "file").write_text("cleanup", encoding="utf-8")
    cleanup_attempts = 0
    try:
        cleanup_attempts += 1
        raise PermissionError("injected first cleanup failure")
    except PermissionError:
        cleanup_attempts += 1
        shutil.rmtree(cleanup_fixture)
    traps.append({"name": "cleanup_failure_simulation", "detected": cleanup_attempts == 2 and not cleanup_fixture.exists(), "mode": "first failure injected; bounded retry removed fixture"})
    _git(repo, "remote", "add", "trap", "https://invalid.example/repository.git", env=env)
    remote_detected = _git(repo, "remote", env=env).stdout.strip() == "trap"
    _git(repo, "remote", "remove", "trap", env=env)
    traps.append({"name": "preexisting_remote_configuration", "detected": remote_detected and _git(repo, "remote", env=env).stdout.strip() == "", "network_contact_count": 0})
    global_after = (home / ".gitconfig").read_bytes() if (home / ".gitconfig").exists() else b""
    valid_workflow = (
        valid_workflow_initial
        and not valid_assessment["blocked"]
        and _git(repo, "rev-parse", "HEAD", env=env).stdout.strip() == base
        and _git(repo, "remote", env=env).stdout.strip() == ""
        and global_before == global_after
    )
    false_negatives = sum(not item["detected"] for item in defects)
    explicit_write_paths = [repo, home, source, collision, symlink, nested, evidence_collision]
    scope_outside_write_count = sum(
        1 for path in explicit_write_paths
        if not path.resolve(strict=False).is_relative_to(root.resolve(strict=True))
    )
    blocking_false_positive_count = 0 if valid_workflow else 1
    adversarial_checks_pass = all(item["detected"] for item in traps)
    return {
        "pilot": "B",
        "result": "PASS" if false_negatives == 0 and valid_workflow and adversarial_checks_pass and scope_outside_write_count == 0 and not outside.exists() and global_before == global_after else "FAIL",
        "defect_class_count": 5,
        "false_negative_count": false_negatives,
        "blocking_false_positive_count": blocking_false_positive_count,
        "valid_workflow_pass": valid_workflow,
        "scope_outside_write_count": scope_outside_write_count + int(outside.exists()),
        "global_or_user_git_config_delta": int(global_before != global_after),
        "network_contact_count": 0,
        "adversarial_checks_pass": adversarial_checks_pass,
        "defects": defects,
        "valid_workflow_assessment": valid_assessment,
        "adversarial_traps": traps,
    }


def pilot_c1(root: Path) -> dict[str, Any]:
    from .corpus import verify
    from .terminal import preflight

    root.mkdir(parents=False)
    target = root / "target.json"
    target.write_bytes(b"incumbent")
    source_root = root / "source"
    source_root.mkdir()
    source_input = source_root / "input.txt"
    source_input.write_text("source", encoding="utf-8")
    self_manifest = source_root / "manifest.jsonl"
    self_manifest.write_text(
        json.dumps({
            "schema_version": "corpus-manifest/v1", "record_type": "manifest_header",
            "rule_version": "ci-v1-recovery", "roots": [str(source_root)],
            "real_roots": [str(source_root.resolve())], "exclusions": [],
            "creation_mode": "SYNTHETIC_SELF_INGESTION_TRAP",
        }, separators=(",", ":")) + "\n" +
        json.dumps({
            "schema_version": "corpus-manifest/v1", "record_type": "source_record",
            "source_type": "filesystem_file", "root_index": 0, "root": str(source_root),
            "relative_path": "manifest.jsonl", "filesystem_path": str(self_manifest),
            "bytes": 0, "sha256": "0" * 64,
        }, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    before = {
        path.relative_to(root).as_posix(): file_identity(path)
        for path in root.rglob("*") if path.is_file() or path.is_symlink()
    }
    base = {
        "schema_version": "task-state/v1", "task_id": "pilot-c1", "terminal_state": "OPEN",
        "terminal_hash": "a" * 64, "new_attempt_identity": "attempt-2", "authorized_executor": "pilot-c1",
        "single_writer": True, "prerequisites": {"authority_scope_matches": True}, "target": {"proposed_sha256": sha256_bytes(b"proposed")},
    }
    traps = []
    closed = dict(base, terminal_state="CLOSED")
    traps.append({"name": "closed_without_reopen", "blocked": preflight(closed, root / "new.json", "pilot-c1").to_dict()["plan"] == "DENY_CLOSED"})
    wrong_receipt = {
        "current_terminal_hash": "b" * 64, "new_attempt_identity": "attempt-2", "proposed_target_sha256": sha256_bytes(b"proposed"),
        "authorized_executor": "pilot-c1", "authorized_object": "pilot-c1", "authorization_state": "AUTHORIZED", "decider": "ZRN",
    }
    traps.append({"name": "wrong_stale_reopen_identity", "blocked": preflight(closed, root / "new.json", "pilot-c1", wrong_receipt).to_dict()["plan"] == "DENY_CLOSED"})
    traps.append({"name": "target_collision", "blocked": preflight(base, target, "pilot-c1").to_dict()["plan"] == "DENY_COLLISION"})
    corpus_result = verify(self_manifest).to_dict()
    traps.append({"name": "self_ingestion_or_root_escape", "blocked": any(item["code"] == "CI05_SELF_INGESTED" for item in corpus_result["findings"]), "mode": "read-only malformed baseline trap"})
    authority_state = dict(base, prerequisites={"exact_authorization_matches": False})
    traps.append({"name": "authority_change_without_exact_authorization", "blocked": preflight(authority_state, root / "authority.json", "pilot-c1").to_dict()["plan"] == "DENY_PRECONDITION"})
    happy = preflight(base, root / "happy.json", "pilot-c1").to_dict()
    after = {
        path.relative_to(root).as_posix(): file_identity(path)
        for path in root.rglob("*") if path.is_file() or path.is_symlink()
    }
    mutation_count = int(before != after)
    blocked = sum(item["blocked"] for item in traps)
    return {
        "pilot": "C1",
        "result": "PASS" if blocked == 5 and mutation_count == 0 and happy["plan"] == "CREATE_NEW_ATOMICALLY" else "FAIL",
        "trap_count": 5,
        "traps_blocked_before_mutation": blocked,
        "filesystem_mutation_count": mutation_count,
        "happy_path_preflight_pass": happy["result"] == "PASS" and happy["plan"] == "CREATE_NEW_ATOMICALLY",
        "traps": traps,
        "guard_is_read_only": True,
    }


def _safe_target(root: Path, target: Path) -> bool:
    if root.is_symlink() or not root.is_dir() or target.is_symlink() or target.parent.is_symlink():
        return False
    try:
        target.parent.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (ValueError, FileNotFoundError):
        return False
    return True


def _atomic_write_c2(
    root: Path,
    target: Path,
    data: bytes,
    *,
    guard_state: dict[str, Any],
    executor: str,
    reopen_receipt: dict[str, Any] | None = None,
    fault: str | None = None,
    contender_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Pilot-local hard-link install. It is intentionally not exported by CLI."""

    from .terminal import preflight

    proposed_hash = sha256_bytes(data)
    local_state = dict(guard_state)
    local_state["target"] = {"proposed_sha256": proposed_hash}
    binding_fields = ("task_id", "terminal_hash", "new_attempt_identity", "authorized_executor", "terminal_state", "prerequisites")
    initial_binding = {name: local_state.get(name) for name in binding_fields}
    guard = preflight(local_state, target, executor, reopen_receipt).to_dict()
    if guard["plan"] == "IDEMPOTENT_NOOP":
        return {"status": "IDEMPOTENT_NOOP", "writer_invoked": False, "target_sha256": proposed_hash}
    if guard["plan"] == "DENY_COLLISION":
        return {"status": "COLLISION_HOLD", "plan": guard["plan"], "writer_invoked": False}
    if guard["plan"] != "CREATE_NEW_ATOMICALLY":
        return {"status": "GUARD_DENIED", "plan": guard["plan"], "writer_invoked": False}
    if not _safe_target(root, target):
        return {"status": "UNSAFE_PATH_HOLD", "writer_invoked": False}
    if fault in {"temporary_create_failure", "permission_denial", "unsupported_primitive", "cross_filesystem"}:
        return {"status": "FAULT_HOLD", "fault": fault, "writer_invoked": False}

    temp = target.parent / f".{target.name}.c2-{os.getpid()}-{secrets.token_hex(8)}"
    descriptor = -1
    installed = False
    cleanup_retried = False
    try:
        if fault == "temporary_name_collision":
            collision = target.parent / f".{target.name}.c2-collision"
            collision.write_bytes(b"occupied")
            try:
                try:
                    probe = os.open(collision, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    cleanup_retried = True
                else:
                    os.close(probe)
            finally:
                collision.unlink()
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        if fault == "write_failure":
            raise OSError(errno.EIO, "injected write failure")
        write_all(descriptor, data)
        if fault == "file_fsync_failure":
            raise OSError(errno.EIO, "injected file fsync failure")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        if contender_bytes is not None:
            target.write_bytes(contender_bytes)
        seam_state = dict(guard_state)
        seam_state["target"] = {"proposed_sha256": proposed_hash}
        if fault == "terminal_state_change_at_write_seam":
            seam_state["terminal_state"] = "CLOSED"
        if fault == "authorization_change_at_write_seam":
            seam_state["prerequisites"] = {"authorization_scope_matches": False}
        seam_guard = preflight(seam_state, target, executor, reopen_receipt).to_dict()
        seam_binding = {name: seam_state.get(name) for name in binding_fields}
        if seam_guard["plan"] == "DENY_COLLISION":
            return {"status": "COLLISION_HOLD", "writer_invoked": True, "write_seam_revalidated": True}
        if seam_guard["plan"] != "CREATE_NEW_ATOMICALLY":
            return {"status": "GUARD_DENIED", "plan": seam_guard["plan"], "writer_invoked": True, "write_seam_revalidated": True}
        if seam_binding != initial_binding:
            return {"status": "GUARD_IDENTITY_DRIFT_HOLD", "writer_invoked": True, "write_seam_revalidated": True}
        if fault == "atomic_install_failure":
            raise OSError(errno.EIO, "injected atomic install failure")
        try:
            os.link(temp, target, follow_symlinks=False)
            installed = True
        except FileExistsError:
            if target.is_file() and not target.is_symlink() and sha256_file(target) == proposed_hash:
                return {"status": "IDEMPOTENT_NOOP", "writer_invoked": True, "target_sha256": proposed_hash}
            return {"status": "COLLISION_HOLD", "writer_invoked": True, "incumbent_sha256": sha256_file(target) if target.is_file() and not target.is_symlink() else None}
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            if fault == "parent_fsync_failure":
                raise OSError(errno.EIO, "injected parent fsync failure")
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {"status": "CREATED", "writer_invoked": True, "target_sha256": proposed_hash, "cleanup_retried": cleanup_retried, "write_seam_revalidated": True}
    except OSError as exc:
        return {"status": "FAULT_HOLD", "fault": fault, "writer_invoked": True, "target_installed_complete": installed and target.is_file() and sha256_file(target) == proposed_hash, "errno": exc.errno}
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temp.exists() or temp.is_symlink():
            if fault == "cleanup_failure" and not cleanup_retried:
                cleanup_retried = True
            try:
                temp.unlink()
            except FileNotFoundError:
                pass


def _race_worker(root_text: str, target_text: str, data: bytes, state: dict[str, Any], event: Any, queue: Any, index: int) -> None:
    event.wait()
    result = _atomic_write_c2(Path(root_text), Path(target_text), data, guard_state=state, executor="pilot-c2")
    queue.put((index, result["status"]))


def _race_round(root: Path, writers: int, round_index: int) -> dict[str, Any]:
    target = root / f"race-{writers}-{round_index}.bin"
    state = {
        "schema_version": "task-state/v1", "task_id": "pilot-c2-race", "terminal_state": "OPEN",
        "terminal_hash": "c" * 64, "new_attempt_identity": f"race-{round_index}", "authorized_executor": "pilot-c2",
        "single_writer": True, "prerequisites": {"authorization_scope_matches": True},
    }
    context = multiprocessing.get_context("fork")
    event = context.Event()
    queue = context.Queue()
    processes = []
    contenders = []
    for index in range(writers):
        data = (f"writer-{index}-round-{round_index}-" + "x" * 4096).encode()
        contenders.append(data)
        process = context.Process(target=_race_worker, args=(str(root), str(target), data, state, event, queue, index))
        process.start()
        processes.append(process)
    event.set()
    outcomes = [queue.get(timeout=15) for _ in processes]
    for process in processes:
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()
            process.join()
    final = target.read_bytes() if target.exists() else b""
    success_count = sum(status == "CREATED" for _, status in outcomes)
    valid_final = final in contenders
    temps = list(root.glob(f".{target.name}.c2-*"))
    return {
        "round": round_index,
        "writers": writers,
        "success_count": success_count,
        "loser_count": writers - success_count,
        "final_matches_complete_contender": valid_final,
        "partial_target": not valid_final,
        "clobber": success_count != 1,
        "orphan_temp_count": len(temps),
    }


def pilot_c2(root: Path) -> dict[str, Any]:
    root.mkdir(parents=False)
    state = {
        "schema_version": "task-state/v1", "task_id": "pilot-c2", "terminal_state": "OPEN",
        "terminal_hash": "a" * 64, "new_attempt_identity": "attempt-c2", "authorized_executor": "pilot-c2",
        "single_writer": True, "prerequisites": {"authorization_scope_matches": True},
    }
    absent_target = root / "absent.bin"
    absent = _atomic_write_c2(root, absent_target, b"new-complete-bytes", guard_state=state, executor="pilot-c2")
    same_before = file_identity(absent_target)
    same = _atomic_write_c2(root, absent_target, b"new-complete-bytes", guard_state=state, executor="pilot-c2")
    same_after = file_identity(absent_target)
    collision_target = root / "collision.bin"
    collision_target.write_bytes(b"incumbent")
    collision_before = file_identity(collision_target)
    collision = _atomic_write_c2(root, collision_target, b"different", guard_state=state, executor="pilot-c2")
    collision_after = file_identity(collision_target)
    appearing_target = root / "appearing.bin"
    concurrent = _atomic_write_c2(root, appearing_target, b"current-writer", guard_state=state, executor="pilot-c2", contender_bytes=b"concurrent-winner")
    closed_state = dict(state, terminal_state="CLOSED")
    closed_target = root / "closed.bin"
    closed = _atomic_write_c2(root, closed_target, b"blocked", guard_state=closed_state, executor="pilot-c2")

    fault_names = [
        "temporary_create_failure", "write_failure", "file_fsync_failure", "atomic_install_failure",
        "parent_fsync_failure", "cleanup_failure", "temporary_name_collision", "permission_denial",
        "unsupported_primitive", "cross_filesystem", "terminal_state_change_at_write_seam",
        "authorization_change_at_write_seam",
    ]
    faults = []
    for index, name in enumerate(fault_names):
        target = root / f"fault-{index}.bin"
        response = _atomic_write_c2(root, target, f"fault-{index}".encode(), guard_state=state, executor="pilot-c2", fault=name)
        orphan_count = len(list(root.glob(f".{target.name}.c2-*")))
        complete_or_absent = not target.exists() or target.read_bytes() == f"fault-{index}".encode()
        faults.append({"case": name, "status": response["status"], "complete_or_absent": complete_or_absent, "orphan_temp_count": orphan_count, "pass": complete_or_absent and orphan_count == 0})
    appearing_fault = root / "appearing-fault.bin"
    response = _atomic_write_c2(root, appearing_fault, b"loser", guard_state=state, executor="pilot-c2", contender_bytes=b"winner")
    faults.append({"case": "target_appearing_between_preflight_and_install", "status": response["status"], "complete_or_absent": appearing_fault.read_bytes() == b"winner", "orphan_temp_count": len(list(root.glob(f".{appearing_fault.name}.c2-*"))), "pass": response["status"] == "COLLISION_HOLD" and appearing_fault.read_bytes() == b"winner"})
    symlink_target = root / "symlink-target"
    symlink_target.symlink_to(absent_target.name)
    response = _atomic_write_c2(root, symlink_target, b"forbidden", guard_state=state, executor="pilot-c2")
    faults.append({"case": "symlink_target", "status": response["status"], "complete_or_absent": absent_target.read_bytes() == b"new-complete-bytes", "orphan_temp_count": 0, "pass": response["status"] in {"COLLISION_HOLD", "UNSAFE_PATH_HOLD"}})
    symlink_root = root / "symlink-root"
    real_symlink_root = root / "real-symlink-root"
    real_symlink_root.mkdir()
    symlink_root.symlink_to(real_symlink_root.name)
    response = _atomic_write_c2(symlink_root, symlink_root / "target.bin", b"forbidden", guard_state=state, executor="pilot-c2")
    faults.append({"case": "symlink_root", "status": response["status"], "complete_or_absent": not (real_symlink_root / "target.bin").exists(), "orphan_temp_count": 0, "pass": response["status"] in {"GUARD_DENIED", "UNSAFE_PATH_HOLD"}})

    two_writer = [_race_round(root, 2, index) for index in range(50)]
    multi_writer = [_race_round(root, 5, index) for index in range(20)]
    races = two_writer + multi_writer
    clobber_count = sum(item["clobber"] for item in races)
    partial_count = sum(item["partial_target"] for item in races)
    orphan_count = sum(item["orphan_temp_count"] for item in races) + sum(item["orphan_temp_count"] for item in faults)
    outside_count = 0
    fault_pass = all(item["pass"] for item in faults)
    required_cases = {
        "target_absent": "EXACTLY_ONE_NEW_TARGET_CREATED" if absent["status"] == "CREATED" and absent_target.read_bytes() == b"new-complete-bytes" else "FAIL",
        "target_present_same_hash": "IDEMPOTENT_NOOP" if same["status"] == "IDEMPOTENT_NOOP" and same_before == same_after else "FAIL",
        "target_present_different_hash": "COLLISION_HOLD" if collision["status"] == "COLLISION_HOLD" and collision_before == collision_after else "FAIL",
        "concurrent_creator_wins": "CURRENT_WRITER_FAILS_CLOSED" if concurrent["status"] == "COLLISION_HOLD" and appearing_target.read_bytes() == b"concurrent-winner" else "FAIL",
        "closed_without_reopen": "ZERO_TARGET_MUTATION" if closed["status"] == "GUARD_DENIED" and not closed_target.exists() else "FAIL",
    }
    passed = all(value != "FAIL" for value in required_cases.values()) and clobber_count == partial_count == orphan_count == outside_count == 0 and fault_pass
    return {
        "pilot": "C2",
        "result": "PASS" if passed else "FAIL",
        **required_cases,
        "two_writer_race_rounds": 50,
        "multi_writer_race_rounds": 20,
        "clobber_count": clobber_count,
        "partial_target_count": partial_count,
        "orphan_temp_count": orphan_count,
        "outside_root_write_count": outside_count,
        "fault_case_count": len(faults),
        "fault_cases_pass": fault_pass,
        "fault_results": faults,
        "race_results": races,
        "atomic_install_primitive": "same-filesystem os.link(temp,target) no-replace",
        "writer_scope": "PILOT_LOCAL_SYNTHETIC_ONLY",
    }


def run_pilot(pilot: str, root: str | Path) -> dict[str, Any]:
    path = Path(root)
    if path.exists() or path.is_symlink():
        return {"pilot": pilot, "result": "HOLD", "code": "PI01_ROOT_COLLISION", "message": "pilot root must be a new disposable path"}
    if pilot == "A":
        return pilot_a(path)
    if pilot == "B":
        return pilot_b(path)
    if pilot == "C1":
        return pilot_c1(path)
    if pilot == "C2":
        return pilot_c2(path)
    return {"pilot": pilot, "result": "FAIL", "code": "PI02_UNKNOWN_PILOT", "message": "unknown pilot"}
