import ast
import json
import tempfile
import unittest
from pathlib import Path

from software_evidence_controls.findings import finding, outcome, sort_findings
from software_evidence_controls.models import PredicateResult
from software_evidence_controls.terminal import preflight


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "src" / "software_evidence_controls"
PRODUCT_FILES = {
    "PM-01": ("risk.py",),
    "PM-02": ("governance.py",),
    "PM-03": ("terminal.py",),
    "PM-04": ("corpus.py",),
    "PM-05": ("handoff.py", "closeout.py"),
    "PM-06": ("evaluation.py",),
}
PRODUCT_MODULE_NAMES = {Path(name).stem for names in PRODUCT_FILES.values() for name in names}


class ArchitectureRegressionTests(unittest.TestCase):
    def test_exactly_six_product_modules_declared(self):
        value = json.loads((REPOSITORY / "contracts" / "schemas" / "MODULE_CONTRACTS.json").read_text(encoding="utf-8"))
        self.assertEqual(6, value["top_level_product_module_count"])
        self.assertEqual([f"PM-{index:02d}" for index in range(1, 7)], [item["module_id"] for item in value["modules"]])

    def test_standard_library_only_distribution(self):
        text = (REPOSITORY / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("dependencies = []", text)

    def test_no_source_level_network_imports(self):
        forbidden = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "websockets", "aiohttp"}
        observed = set()
        for path in SOURCE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    observed.update(item.name.split(".")[0] for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    observed.add(node.module.split(".")[0])
        self.assertFalse(observed & forbidden)

    def test_no_automatic_model_call_symbols(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
        for symbol in ("openai", "anthropic", "model.generate", "chat.completions", "invoke_model"):
            self.assertNotIn(symbol, text.lower())

    def test_no_daemon_database_or_web_framework(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in SOURCE.glob("*.py"))
        for symbol in ("sqlite3", "flask", "django", "fastapi", "daemoncontext"):
            self.assertNotIn(symbol, text.lower())

    def test_status_semantics_do_not_overclaim_later_gates(self):
        text = (REPOSITORY / "docs" / "STATUS_SEMANTICS.md").read_text(encoding="utf-8")
        for marker in ("INDEPENDENTLY_REVIEWED=NO", "USER_ACCEPTED=NO", "VALIDATED=NO", "CANONICAL=NO", "INSTALLED=NO", "PRODUCTION_READY=NO"):
            self.assertIn(marker, text)

    def test_finding_sort_is_deterministic_and_safety_first(self):
        items = [
            finding("RR02", "WARN", "b", "2", "warn", 2),
            finding("TG01", "HOLD", "a", "1", "hold", 1),
            finding("GP01", "ERROR", "c", "3", "error", 3),
        ]
        first = sort_findings(items)
        second = sort_findings(reversed(items))
        self.assertEqual(first, second)
        self.assertEqual(["TG01", "GP01", "RR02"], [item.code for item in first])

    def test_exit_code_precedence_terminal_over_integrity(self):
        items = [finding("CI03", "ERROR", "x", "x", "integrity", 1), finding("TG03", "HOLD", "x", "x", "terminal", 2)]
        self.assertEqual(("HOLD", 5), outcome(items, "normal"))

    def test_strict_only_promotes_existing_warning(self):
        items = [finding("RR01", "WARN", "x", "x", "warning", 1)]
        self.assertEqual(("PASS", 0), outcome(items, "normal"))
        self.assertEqual(("FAIL", 1), outcome(items, "strict"))

    def test_finding_schema_has_required_fields(self):
        value = json.loads((REPOSITORY / "contracts" / "schemas" / "FINDING_SCHEMA.json").read_text(encoding="utf-8"))
        self.assertEqual(["code", "severity", "path", "location", "message", "rule_version", "evidence"], value["required"])

    def test_contract_identity_records_are_not_carrier_copies(self):
        review = json.loads((REPOSITORY / "contracts" / "review-kernel" / "IDENTITY.json").read_text(encoding="utf-8"))
        handoff = json.loads((REPOSITORY / "contracts" / "session-handoff" / "IDENTITIES.json").read_text(encoding="utf-8"))
        self.assertFalse(review["content_copied"])
        self.assertFalse(handoff["carrier_content_copied"])
        self.assertFalse(handoff["semantic_fork_created"])

    def test_pilot_product_dependencies_are_lazy(self):
        tree = ast.parse((SOURCE / "pilots.py").read_text(encoding="utf-8"))
        top_level_dependencies = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                top_level_dependencies.add(node.module.split(".")[0])
        self.assertFalse(top_level_dependencies & PRODUCT_MODULE_NAMES)


class RemovabilityTests(unittest.TestCase):
    def assert_independently_removable(self, module_id):
        own_names = {Path(name).stem for name in PRODUCT_FILES[module_id]}
        for filename in PRODUCT_FILES[module_id]:
            tree = ast.parse((SOURCE / filename).read_text(encoding="utf-8"))
            dependencies = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
                    dependencies.add(node.module.split(".")[0])
            self.assertFalse((dependencies & PRODUCT_MODULE_NAMES) - own_names)


def make_removability_test(module_id):
    def test(self):
        self.assert_independently_removable(module_id)
    return test


for module_id in PRODUCT_FILES:
    setattr(RemovabilityTests, f"test_{module_id.lower().replace('-', '_')}_has_no_cross_product_dependency", make_removability_test(module_id))


class PositivePredicateMutationTests(unittest.TestCase):
    def state(self, prerequisites):
        return {
            "schema_version": "task-state/v1", "task_id": "predicate", "terminal_state": "OPEN",
            "terminal_hash": "a" * 64, "new_attempt_identity": "attempt", "authorized_executor": "executor",
            "single_writer": True, "prerequisites": prerequisites, "target": {"proposed_sha256": "b" * 64},
        }

    def test_all_positive_predicates_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = preflight(self.state({"source_unchanged": True, "authorization_scope_matches": True}), Path(temporary) / "target", "executor").to_dict()
        self.assertEqual("CREATE_NEW_ATOMICALLY", result["plan"])

    def test_source_unchanged_false_denies(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = preflight(self.state({"source_unchanged": False, "authorization_scope_matches": True}), Path(temporary) / "target", "executor").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_authorization_scope_matches_false_denies(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = preflight(self.state({"source_unchanged": True, "authorization_scope_matches": False}), Path(temporary) / "target", "executor").to_dict()
        self.assertEqual("DENY_PRECONDITION", result["plan"])

    def test_predicate_result_requires_positive_name_and_passed_value(self):
        predicate = PredicateResult("target_absent", True, {"exists": False})
        self.assertEqual("target_absent", predicate.name)
        self.assertTrue(predicate.passed)

    def test_no_inverted_predicate_names_in_terminal_source(self):
        tree = ast.parse((SOURCE / "terminal.py").read_text(encoding="utf-8"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "PredicateResult" and node.args and isinstance(node.args[0], ast.Constant):
                names.append(node.args[0].value)
        self.assertTrue(names)
        self.assertTrue(all(not str(name).startswith(("not_", "no_", "failed_")) for name in names))


if __name__ == "__main__":
    unittest.main()
