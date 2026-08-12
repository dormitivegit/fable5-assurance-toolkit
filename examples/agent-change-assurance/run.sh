#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PYTHON_BIN=python3
TEMP_BASE=${TMPDIR:-/tmp}
TEMP_BASE=${TEMP_BASE%/}
WORK_DIR=""
LAST_EXIT=0

fail() {
  printf 'EXAMPLE_ERROR=%s\n' "$1" >&2
  exit 1
}

cleanup() {
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" && "$WORK_DIR" == "$TEMP_BASE"/fable5-agent-change-assurance.* ]]; then
    rm -rf -- "$WORK_DIR"
  fi
}

trap cleanup EXIT

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 is required"
if ! PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" - <<'PY'
import sys

raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
then
  fail "Python 3.11 or newer is required"
fi

WORK_DIR=$(mktemp -d "$TEMP_BASE/fable5-agent-change-assurance.XXXXXX")
SOURCE_DIR="$WORK_DIR/source"
BASELINE_MANIFEST="$WORK_DIR/baseline.jsonl"
POST_CHANGE_MANIFEST="$WORK_DIR/post-change.jsonl"
mkdir -p "$SOURCE_DIR"

run_cli() {
  local output_file=$1
  shift
  set +e
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$REPOSITORY_ROOT/src" \
    "$PYTHON_BIN" -m assurance_toolkit "$@" --format json >"$output_file"
  LAST_EXIT=$?
  set -e
  PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" -m json.tool "$output_file"
}

assert_output() {
  local assertion=$1
  local output_file=$2
  PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" - "$assertion" "$output_file" <<'PY'
import json
import sys

assertion, output_file = sys.argv[1:]
with open(output_file, encoding="utf-8") as handle:
    payload = json.load(handle)

def require(condition, message):
    if not condition:
        raise AssertionError(message)

if assertion == "risk":
    require(payload["result"] == "PASS", "risk result")
    require(payload["module_id"] == "PM-01", "risk module")
    require(payload["tier"] == "T1", "risk tier")
    require(payload["classification_is_authorization"] is False, "authorization boundary")
elif assertion == "freeze":
    require(payload["result"] == "PASS", "freeze result")
    require(payload["module_id"] == "PM-04", "freeze module")
    require(payload["source_record_count"] == 1, "freeze source count")
elif assertion == "baseline":
    require(payload["result"] == "PASS", "baseline result")
    require(payload["counts"] == {
        "match": 1,
        "missing": 0,
        "changed": 0,
        "type_changed": 0,
        "self_ingested": 0,
    }, "baseline counts")
elif assertion == "changed":
    require(payload["result"] == "HOLD", "changed result")
    require(payload["exit_code"] == 4, "changed exit code")
    require(payload["counts"]["changed"] == 1, "changed count")
    require("CI03_SOURCE_CHANGED" in {item["code"] for item in payload["findings"]}, "changed finding")
elif assertion == "post-change":
    require(payload["result"] == "PASS", "post-change result")
    require(payload["counts"] == {
        "match": 1,
        "missing": 0,
        "changed": 0,
        "type_changed": 0,
        "self_ingested": 0,
    }, "post-change counts")
elif assertion == "handoff":
    require(payload["result"] == "PASS", "handoff result")
    require(payload["module_id"] == "PM-05", "handoff module")
    require(payload["findings"] == [], "handoff evidence reference")
    require(payload["mode"] == "OBSERVATION_AND_STRUCTURAL_LINT_ONLY", "handoff mode")
    require(payload["receiver_ready"] == "NOT_MACHINE_DETERMINED", "receiver boundary")
    require(payload["semantically_complete"] == "NOT_MACHINE_DETERMINED", "semantic boundary")
else:
    raise AssertionError(f"unknown assertion: {assertion}")
PY
}

printf '== 1/6 Classify the bounded change ==\n'
run_cli "$WORK_DIR/risk.json" classify "$SCRIPT_DIR/task.json"
[[ $LAST_EXIT -eq 0 ]] || fail "risk classification returned exit $LAST_EXIT"
assert_output risk "$WORK_DIR/risk.json" || fail "risk assertions did not match"

printf '\n== 2/6 Freeze and verify a one-file baseline ==\n'
printf '%s\n' \
  'def greeting() -> str:' \
  '    return "Hello"' >"$SOURCE_DIR/greeting.py"
run_cli "$WORK_DIR/baseline-freeze.json" corpus freeze "$SOURCE_DIR" --manifest "$BASELINE_MANIFEST"
[[ $LAST_EXIT -eq 0 ]] || fail "baseline freeze returned exit $LAST_EXIT"
assert_output freeze "$WORK_DIR/baseline-freeze.json" || fail "baseline freeze assertions did not match"
run_cli "$WORK_DIR/baseline-verify.json" corpus verify "$BASELINE_MANIFEST"
[[ $LAST_EXIT -eq 0 ]] || fail "baseline verification returned exit $LAST_EXIT"
assert_output baseline "$WORK_DIR/baseline-verify.json" || fail "baseline verification assertions did not match"

printf '\n== 3/6 Simulate an upstream agent-produced change ==\n'
printf '%s\n' \
  'def greeting(name: str) -> str:' \
  '    return f"Hello, {name}!"' >"$SOURCE_DIR/greeting.py"
printf '%s\n' 'SIMULATION=upstream agent output replaced greeting.py; no AI model was invoked'

printf '\n== 4/6 Assert deterministic detection against the baseline ==\n'
run_cli "$WORK_DIR/change-detection.json" corpus verify "$BASELINE_MANIFEST"
[[ $LAST_EXIT -eq 4 ]] || fail "expected integrity exit 4, observed $LAST_EXIT"
assert_output changed "$WORK_DIR/change-detection.json" || fail "change detection assertions did not match"
printf '%s\n' 'EXPECTED_NONZERO=confirmed exit 4 with CI03_SOURCE_CHANGED'

printf '\n== 5/6 Freeze and verify post-change evidence ==\n'
run_cli "$WORK_DIR/post-change-freeze.json" corpus freeze "$SOURCE_DIR" --manifest "$POST_CHANGE_MANIFEST"
[[ $LAST_EXIT -eq 0 ]] || fail "post-change freeze returned exit $LAST_EXIT"
assert_output freeze "$WORK_DIR/post-change-freeze.json" || fail "post-change freeze assertions did not match"
run_cli "$WORK_DIR/post-change-verify.json" corpus verify "$POST_CHANGE_MANIFEST"
[[ $LAST_EXIT -eq 0 ]] || fail "post-change verification returned exit $LAST_EXIT"
assert_output post-change "$WORK_DIR/post-change-verify.json" || fail "post-change verification assertions did not match"

printf '\n== 6/6 Validate a self-contained handoff observation ==\n'
PYTHONDONTWRITEBYTECODE=1 "$PYTHON_BIN" - \
  "$SCRIPT_DIR/handoff-template.json" \
  "$POST_CHANGE_MANIFEST" \
  "$WORK_DIR/handoff-input.json" <<'PY'
import hashlib
import json
import sys

template_file, manifest_file, output_file = sys.argv[1:]
with open(template_file, encoding="utf-8") as handle:
    handoff = json.load(handle)
with open(manifest_file, "rb") as handle:
    manifest_sha256 = hashlib.sha256(handle.read()).hexdigest()
handoff["source_references"] = [{
    "load_bearing": True,
    "identity": {"path": manifest_file, "sha256": manifest_sha256},
    "location": "manifest_summary",
}]
with open(output_file, "w", encoding="utf-8") as handle:
    json.dump(handoff, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY
printf '%s\n' 'HANDOFF_EVIDENCE=post-change manifest bound by SHA-256 and manifest_summary anchor'
run_cli "$WORK_DIR/handoff-result.json" handoff "$WORK_DIR/handoff-input.json" --carrier direct-v1-ax1-ax2
[[ $LAST_EXIT -eq 0 ]] || fail "handoff validation returned exit $LAST_EXIT"
assert_output handoff "$WORK_DIR/handoff-result.json" || fail "handoff assertions did not match"

printf '\nDEMO_SUMMARY\n'
printf '%s\n' \
  'DEMO_RESULT=PASS' \
  'MODULES_EXERCISED=PM-01,PM-04,PM-05' \
  'RISK_TIER=T1' \
  'CLASSIFICATION_IS_AUTHORIZATION=false' \
  'BASELINE_VERIFY=PASS' \
  'EXPECTED_NEGATIVE_EXIT=4' \
  'EXPECTED_NEGATIVE_FINDING=CI03_SOURCE_CHANGED' \
  'POST_CHANGE_VERIFY=PASS' \
  'HANDOFF_EVIDENCE_REFERENCE=RESOLVED' \
  'HANDOFF_MODE=OBSERVATION_AND_STRUCTURAL_LINT_ONLY' \
  'RECEIVER_READY=NOT_MACHINE_DETERMINED' \
  'HUMAN_REVIEW_REQUIRED=YES' \
  'RUNTIME_NETWORK_DEPENDENCY=NONE' \
  'EXTERNAL_AI_DEPENDENCY=NONE' \
  'TEMP_WORKSPACE_CLEANUP=automatic'
