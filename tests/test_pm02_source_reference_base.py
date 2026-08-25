import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
ENV = os.environ | {
    "PYTHONPATH": str(REPOSITORY / "src"),
    "PYTHONDONTWRITEBYTECODE": "1",
}
CONTRACT = REPOSITORY / "contracts" / "schemas" / "PM02_SOURCE_REFERENCE_CONTRACT.json"


def cli(*args, cwd, input_text=None):
    return subprocess.run(
        [sys.executable, "-m", "assurance_toolkit", *args],
        cwd=cwd,
        env=ENV,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def pack_for(path, content):
    return {
        "pack_version": "governance-pack/v1",
        "claims": [{
            "id": "C1",
            "text": "synthetic claim",
            "load_bearing": True,
            "verification": "VERIFIED",
            "source_identity": {
                "path": str(path),
                "sha256": hashlib.sha256(content).hexdigest(),
            },
            "location": "load-bearing anchor",
            "conflict": "NONE",
        }],
        "decisions": [],
        "actions": [],
        "task": {},
        "result": "PASS_SYNTHETIC",
    }


class Pm02SourceReferenceBaseTests(unittest.TestCase):
    def test_public_contract_freezes_file_and_stdin_reference_bases(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual("PM-02", contract["module_id"])
        self.assertIn("filesystem parent", contract["file_backed_pack"]["relative_source_identity_path"])
        self.assertIn("fail closed", contract["stdin_pack"]["relative_source_identity_path"])

    def test_file_backed_relative_source_is_pack_parent_based_across_three_cwds(self):
        content = b"alpha\nload-bearing anchor\nomega\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack_dir = root / "pack"
            pack_dir.mkdir()
            (pack_dir / "source.txt").write_bytes(content)
            pack_path = pack_dir / "pack.json"
            pack_path.write_text(json.dumps(pack_for("source.txt", content)), encoding="utf-8")
            unrelated = root / "unrelated"
            unrelated.mkdir()

            observed = []
            for position, cwd in (
                ("repo-root", REPOSITORY),
                ("repo-subdirectory", REPOSITORY / "tests"),
                ("unrelated-temporary-directory", unrelated),
            ):
                with self.subTest(position=position):
                    completed = cli("check", str(pack_path), "--format", "json", cwd=cwd)
                    payload = json.loads(completed.stdout)
                    self.assertEqual("", completed.stderr)
                    self.assertEqual(0, completed.returncode)
                    self.assertEqual("PASS", payload["result"])
                    self.assertEqual([], payload["findings"])
                    observed.append((payload["result"], payload["findings"], completed.returncode))
            self.assertEqual([observed[0]] * 3, observed)

    def test_missing_pack_adjacent_source_fails_exact_reference(self):
        content = b"alpha\nload-bearing anchor\nomega\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pack_path = root / "pack.json"
            pack_path.write_text(json.dumps(pack_for("source.txt", content)), encoding="utf-8")
            completed = cli("check", str(pack_path), "--format", "json", cwd=REPOSITORY)
        payload = json.loads(completed.stdout)
        self.assertEqual(1, completed.returncode)
        self.assertIn("GP05_BROKEN_EVIDENCE_REFERENCE", [item["code"] for item in payload["findings"]])

    def test_tampered_pack_adjacent_source_fails_exact_sha(self):
        expected = b"alpha\nload-bearing anchor\nomega\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.txt").write_bytes(b"tampered\nload-bearing anchor\n")
            pack_path = root / "pack.json"
            pack_path.write_text(json.dumps(pack_for("source.txt", expected)), encoding="utf-8")
            completed = cli("check", str(pack_path), "--format", "json", cwd=REPOSITORY)
        payload = json.loads(completed.stdout)
        gp05 = next(item for item in payload["findings"] if item["code"] == "GP05_BROKEN_EVIDENCE_REFERENCE")
        self.assertEqual(1, completed.returncode)
        self.assertEqual("source SHA-256 mismatch", gp05["evidence"])

    def test_stdin_relative_source_fails_closed_without_cwd_fallback(self):
        content = b"alpha\nload-bearing anchor\nomega\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.txt").write_bytes(content)
            completed = cli(
                "check",
                "--stdin",
                "--format",
                "json",
                cwd=root,
                input_text=json.dumps(pack_for("source.txt", content)),
            )
        payload = json.loads(completed.stdout)
        gp05 = next(item for item in payload["findings"] if item["code"] == "GP05_BROKEN_EVIDENCE_REFERENCE")
        self.assertEqual(1, completed.returncode)
        self.assertIn("file-backed pack parent", gp05["evidence"])

    def test_stdin_absolute_source_remains_available(self):
        content = b"alpha\nload-bearing anchor\nomega\n"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.txt"
            source.write_bytes(content)
            completed = cli(
                "check",
                "--stdin",
                "--format",
                "json",
                cwd=REPOSITORY,
                input_text=json.dumps(pack_for(source, content)),
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode)
        self.assertEqual("PASS", payload["result"])
        self.assertEqual([], payload["findings"])


if __name__ == "__main__":
    unittest.main()
