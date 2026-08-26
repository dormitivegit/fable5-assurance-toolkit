import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from software_evidence_controls.corpus import freeze, verify
from software_evidence_controls.identities import file_identity
from software_evidence_controls.io_utils import read_jsonl, sha256_bytes, sha256_file


class CorpusFixtureMixin:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir()
        self.first = self.root / "a.txt"
        self.first.write_text("alpha", encoding="utf-8")
        self.manifest = self.base / "manifest.jsonl"

    def tearDown(self):
        self.temp.cleanup()

    def write_records(self, path, records):
        path.write_text(
            "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records),
            encoding="utf-8",
        )


class CorpusFreezeTests(CorpusFixtureMixin, unittest.TestCase):
    def test_valid_freeze_and_verify(self):
        frozen = freeze([self.root], [], self.manifest).to_dict()
        self.assertEqual("PASS", frozen["result"])
        checked = verify(self.manifest).to_dict()
        self.assertEqual("PASS", checked["result"])
        self.assertEqual(1, checked["counts"]["match"])

    def test_manifest_is_one_object_per_line(self):
        freeze([self.root], [], self.manifest)
        records = read_jsonl(self.manifest)
        self.assertEqual("manifest_header", records[0]["record_type"])
        self.assertTrue(all(item["schema_version"] == "corpus-manifest/v1" for item in records))
        self.assertEqual("manifest_summary", records[-1]["record_type"])

    def test_repeated_outputs_are_byte_deterministic(self):
        second = self.base / "manifest-2.jsonl"
        freeze([self.root], [], self.manifest)
        freeze([self.root], [], second)
        self.assertEqual(self.manifest.read_bytes(), second.read_bytes())

    def test_nested_manifest_is_excluded_before_enumeration(self):
        nested = self.root / "manifest.jsonl"
        result = freeze([self.root], [], nested).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertIn("CI01_OUTPUT_WITHIN_SOURCE_EXCLUDED", [item["code"] for item in result["findings"]])
        records = read_jsonl(nested)
        paths = [item.get("relative_path") for item in records if item.get("record_type") == "source_record"]
        self.assertNotIn("manifest.jsonl", paths)

    def test_explicit_nested_output_directory_is_excluded(self):
        output = self.root / "output"
        output.mkdir()
        (output / "old.txt").write_text("old output", encoding="utf-8")
        manifest = output / "new.jsonl"
        freeze([self.root], [output], manifest)
        paths = [item.get("relative_path") for item in read_jsonl(manifest) if item.get("record_type") == "source_record"]
        self.assertNotIn("output/old.txt", paths)

    def test_physical_duplicate_records_preserved(self):
        (self.root / "b.txt").write_text("alpha", encoding="utf-8")
        result = freeze([self.root], [], self.manifest).to_dict()
        records = read_jsonl(self.manifest)
        sources = [item for item in records if item.get("record_type") == "source_record"]
        groups = [item for item in records if item.get("record_type") == "duplicate_group"]
        self.assertEqual(2, len(sources))
        self.assertEqual(1, len(groups))
        self.assertEqual(1, result["duplicate_group_count"])

    def test_hard_links_remain_separate_records(self):
        os.link(self.first, self.root / "hardlink.txt")
        freeze([self.root], [], self.manifest)
        sources = [item for item in read_jsonl(self.manifest) if item.get("source_type") == "filesystem_file"]
        self.assertEqual(2, len(sources))

    def test_in_root_symlink_recorded_not_followed(self):
        link = self.root / "link.txt"
        link.symlink_to("a.txt")
        freeze([self.root], [], self.manifest)
        records = read_jsonl(self.manifest)
        observed = [item for item in records if item.get("relative_path") == "link.txt"]
        self.assertEqual("symlink", observed[0]["source_type"])

    def test_out_of_root_symlink_recorded_not_followed(self):
        outside = self.base / "outside.txt"
        outside.write_text("private synthetic outside", encoding="utf-8")
        link = self.root / "escape.txt"
        link.symlink_to(outside)
        freeze([self.root], [], self.manifest)
        records = read_jsonl(self.manifest)
        observed = [item for item in records if item.get("relative_path") == "escape.txt"]
        self.assertEqual(1, len(observed))
        self.assertEqual("symlink", observed[0]["source_type"])
        self.assertNotEqual(sha256_file(outside), observed[0]["sha256"])

    def test_zip_members_have_separate_identities(self):
        archive = self.root / "archive.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("one.txt", "one")
            handle.writestr("two.txt", "two")
        freeze([self.root], [], self.manifest)
        members = [item for item in read_jsonl(self.manifest) if item.get("source_type") == "archive_member"]
        self.assertEqual(["one.txt", "two.txt"], [item["archive_member"] for item in members])

    def test_source_bytes_and_metadata_unchanged(self):
        before = file_identity(self.first)
        freeze([self.root], [], self.manifest)
        self.assertEqual(before, file_identity(self.first))

    def test_manifest_collision_fails_closed(self):
        self.manifest.write_bytes(b"incumbent")
        before = file_identity(self.manifest)
        result = freeze([self.root], [], self.manifest).to_dict()
        self.assertEqual("HOLD", result["result"])
        self.assertEqual(before, file_identity(self.manifest))

    def test_same_hash_manifest_is_untouched_noop(self):
        first = freeze([self.root], [], self.manifest).to_dict()
        before = file_identity(self.manifest)
        second = freeze([self.root], [], self.manifest).to_dict()
        self.assertEqual("CREATED", first["write_disposition"])
        self.assertEqual("IDEMPOTENT_NOOP", second["write_disposition"])
        self.assertEqual(before, file_identity(self.manifest))

    def test_manifest_symlink_fails_closed(self):
        incumbent = self.base / "incumbent"
        incumbent.write_bytes(b"incumbent")
        self.manifest.symlink_to(incumbent.name)
        result = freeze([self.root], [], self.manifest).to_dict()
        self.assertIn("CI08_MANIFEST_COLLISION", [item["code"] for item in result["findings"]])
        self.assertEqual(b"incumbent", incumbent.read_bytes())

    def test_symlink_root_fails_closed(self):
        link = self.base / "root-link"
        link.symlink_to(self.root.name)
        result = freeze([link], [], self.manifest).to_dict()
        self.assertIn("CI07_UNBOUNDED_ROOT", [item["code"] for item in result["findings"]])

    def test_empty_roots_fail(self):
        result = freeze([], [], self.manifest).to_dict()
        self.assertIn("CI07_UNBOUNDED_ROOT", [item["code"] for item in result["findings"]])

    def test_missing_output_parent_fails(self):
        result = freeze([self.root], [], self.base / "missing" / "manifest.jsonl").to_dict()
        self.assertIn("CI08_MANIFEST_COLLISION", [item["code"] for item in result["findings"]])


class CorpusVerifyTests(CorpusFixtureMixin, unittest.TestCase):
    def freeze(self):
        result = freeze([self.root], [], self.manifest).to_dict()
        self.assertEqual("PASS", result["result"])

    def test_source_change_detected(self):
        self.freeze()
        self.first.write_text("changed", encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI03_SOURCE_CHANGED", [item["code"] for item in result["findings"]])
        self.assertEqual(1, result["counts"]["changed"])

    def test_missing_source_detected(self):
        self.freeze()
        self.first.unlink()
        result = verify(self.manifest).to_dict()
        self.assertIn("CI02_SOURCE_MISSING", [item["code"] for item in result["findings"]])

    def test_type_change_detected(self):
        self.freeze()
        self.first.unlink()
        self.first.mkdir()
        result = verify(self.manifest).to_dict()
        self.assertIn("CI04_SOURCE_TYPE_CHANGED", [item["code"] for item in result["findings"]])

    def test_symlink_change_detected(self):
        link = self.root / "link"
        link.symlink_to("a.txt")
        self.freeze()
        link.unlink()
        link.symlink_to("other.txt")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI03_SOURCE_CHANGED", [item["code"] for item in result["findings"]])

    def test_detect_new_is_explicit_warning(self):
        self.freeze()
        (self.root / "new.txt").write_text("new", encoding="utf-8")
        without = verify(self.manifest).to_dict()
        with_new = verify(self.manifest, detect_new=True).to_dict()
        self.assertNotIn("CI10_NEW_SOURCE_DETECTED", [item["code"] for item in without["findings"]])
        self.assertIn("CI10_NEW_SOURCE_DETECTED", [item["code"] for item in with_new["findings"]])

    def test_malformed_manifest_detected(self):
        self.manifest.write_text("not-json\n", encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI09_MALFORMED_MANIFEST", [item["code"] for item in result["findings"]])

    def test_unsupported_schema_detected(self):
        self.manifest.write_text('{"schema_version":"v99","record_type":"manifest_header"}\n', encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in result["findings"]])

    def test_self_ingestion_detected(self):
        header = {"schema_version": "corpus-manifest/v1", "record_type": "manifest_header", "roots": [str(self.root)], "exclusions": []}
        record = {"schema_version": "corpus-manifest/v1", "record_type": "source_record", "source_type": "filesystem_file", "root_index": 0, "root": str(self.root), "relative_path": "../manifest.jsonl", "filesystem_path": str(self.manifest), "bytes": 0, "sha256": "0" * 64}
        self.manifest.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n", encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI05_SELF_INGESTED", [item["code"] for item in result["findings"]])

    def test_duplicate_group_inconsistency_detected(self):
        (self.root / "b.txt").write_text("alpha", encoding="utf-8")
        self.freeze()
        records = read_jsonl(self.manifest)
        group = next(item for item in records if item.get("record_type") == "duplicate_group")
        group["members"] = ["wrong"]
        self.manifest.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in records), encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI06_DUPLICATE_GROUP_INCONSISTENT", [item["code"] for item in result["findings"]])

    def test_archive_member_change_detected(self):
        archive = self.root / "archive.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("member.txt", "old")
        self.freeze()
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("member.txt", "new")
        result = verify(self.manifest).to_dict()
        self.assertIn("CI03_SOURCE_CHANGED", [item["code"] for item in result["findings"]])

    def test_accepted_manifest_option_omitted_preserves_behavior(self):
        self.freeze()
        without_option = verify(self.manifest).to_dict()
        explicit_none = verify(self.manifest, accepted_manifest_sha256=None).to_dict()
        self.assertEqual(without_option, explicit_none)

    def test_expected_root_omitted_preserves_legacy_wrong_tree_behavior(self):
        self.freeze()
        other = self.base / "other"
        other.mkdir()
        (other / "a.txt").write_text("changed elsewhere", encoding="utf-8")
        result = verify(self.manifest).to_dict()
        self.assertEqual(("PASS", 0), (result["result"], result["exit_code"]))

    def test_matching_expected_root_verifies_normally(self):
        self.freeze()
        result = verify(self.manifest, expected_roots=[self.root]).to_dict()
        self.assertEqual(("PASS", 0), (result["result"], result["exit_code"]))

    def test_wrong_expected_root_holds_before_source_verification(self):
        self.freeze()
        other = self.base / "other"
        other.mkdir()
        (other / "a.txt").write_text("changed elsewhere", encoding="utf-8")
        result = verify(self.manifest, expected_roots=[other]).to_dict()
        codes = [item["code"] for item in result["findings"]]
        self.assertEqual(("HOLD", 4), (result["result"], result["exit_code"]))
        self.assertEqual(["CI13_EXPECTED_ROOT_MISMATCH"], codes)
        self.assertEqual([], result["facts"])
        self.assertEqual(0, sum(result["counts"].values()))

    def test_recorded_root_assertion_remains_valid_from_another_location(self):
        self.freeze()
        unrelated = self.base / "unrelated"
        unrelated.mkdir()
        original = os.getcwd()
        try:
            os.chdir(unrelated)
            result = verify(self.manifest, expected_roots=[self.root]).to_dict()
        finally:
            os.chdir(original)
        self.assertEqual(("PASS", 0), (result["result"], result["exit_code"]))

    def test_expected_root_mismatch_short_circuits_missing_recorded_source(self):
        self.freeze()
        other = self.base / "other"
        other.mkdir()
        self.first.unlink()
        result = verify(self.manifest, expected_roots=[other]).to_dict()
        codes = [item["code"] for item in result["findings"]]
        self.assertEqual(["CI13_EXPECTED_ROOT_MISMATCH"], codes)
        self.assertNotIn("CI02_SOURCE_MISSING", codes)
        self.assertEqual([], result["facts"])

    def test_expected_roots_require_exact_multi_root_sequence(self):
        second = self.base / "second"
        second.mkdir()
        (second / "b.txt").write_text("beta", encoding="utf-8")
        frozen = freeze([self.root, second], [], self.manifest).to_dict()
        self.assertEqual("PASS", frozen["result"])
        controls = [
            ([self.root, second], "PASS", 0),
            ([second, self.root], "HOLD", 4),
            ([self.root], "HOLD", 4),
            ([self.root, second, self.base / "third"], "HOLD", 4),
        ]
        for expected, outcome_result, exit_code in controls:
            with self.subTest(expected=expected):
                result = verify(self.manifest, expected_roots=expected).to_dict()
                self.assertEqual((outcome_result, exit_code), (result["result"], result["exit_code"]))
                if outcome_result == "HOLD":
                    self.assertIn("CI13_EXPECTED_ROOT_MISMATCH", [item["code"] for item in result["findings"]])

    def test_expected_root_normalization_matches_but_symlink_alias_does_not(self):
        self.freeze()
        normalized = self.root / "."
        matching = verify(self.manifest, expected_roots=[normalized]).to_dict()
        self.assertEqual(("PASS", 0), (matching["result"], matching["exit_code"]))
        alias = self.base / "root-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        aliased = verify(self.manifest, expected_roots=[alias]).to_dict()
        self.assertEqual(("HOLD", 4), (aliased["result"], aliased["exit_code"]))
        evidence = aliased["findings"][0]["evidence"]
        self.assertIn("LEXICAL_MISMATCH", evidence["mismatch_classes"])

    def test_expected_root_and_accepted_manifest_sha_are_orthogonal(self):
        self.freeze()
        accepted = sha256_file(self.manifest)
        matched = verify(self.manifest, accepted_manifest_sha256=accepted, expected_roots=[self.root]).to_dict()
        wrong_sha = verify(self.manifest, accepted_manifest_sha256="0" * 64, expected_roots=[self.root]).to_dict()
        wrong_both = verify(self.manifest, accepted_manifest_sha256="0" * 64, expected_roots=[self.base / "other"]).to_dict()
        self.assertEqual(("PASS", 0), (matched["result"], matched["exit_code"]))
        self.assertIn("CI11_ACCEPTED_MANIFEST_MISMATCH", [item["code"] for item in wrong_sha["findings"]])
        self.assertEqual(["CI11_ACCEPTED_MANIFEST_MISMATCH", "CI13_EXPECTED_ROOT_MISMATCH"], [item["code"] for item in wrong_both["findings"]])

    def test_detect_new_runs_only_after_matching_expected_root(self):
        self.freeze()
        (self.root / "new.txt").write_text("new", encoding="utf-8")
        matching = verify(self.manifest, detect_new=True, expected_roots=[self.root]).to_dict()
        mismatching = verify(self.manifest, detect_new=True, expected_roots=[self.base / "other"]).to_dict()
        self.assertIn("CI10_NEW_SOURCE_DETECTED", [item["code"] for item in matching["findings"]])
        self.assertEqual(["CI13_EXPECTED_ROOT_MISMATCH"], [item["code"] for item in mismatching["findings"]])

    def test_expected_root_with_malformed_header_roots_fails_closed(self):
        self.freeze()
        records = read_jsonl(self.manifest)
        records[0]["real_roots"] = []
        self.write_records(self.manifest, records)
        result = verify(self.manifest, expected_roots=[self.root]).to_dict()
        self.assertEqual(("HOLD", 4), (result["result"], result["exit_code"]))
        self.assertIn("CI09_MALFORMED_MANIFEST", [item["code"] for item in result["findings"]])
        self.assertNotIn("CI13_EXPECTED_ROOT_MISMATCH", [item["code"] for item in result["findings"]])

    def test_same_workspace_root_remains_a_matching_assertion(self):
        self.freeze()
        result = verify(self.manifest, expected_roots=[self.root]).to_dict()
        self.assertEqual(("PASS", 0), (result["result"], result["exit_code"]))

    def test_malformed_accepted_manifest_sha_is_input_failure(self):
        self.freeze()
        result = verify(self.manifest, accepted_manifest_sha256="0" * 63).to_dict()
        self.assertEqual("FAIL", result["result"])
        self.assertEqual(2, result["exit_code"])
        self.assertIn("IN01_PARSE_ERROR", [item["code"] for item in result["findings"]])

    def test_exact_accepted_manifest_sha_verifies_normally(self):
        self.freeze()
        accepted = sha256_file(self.manifest)
        result = verify(self.manifest, accepted_manifest_sha256=accepted).to_dict()
        self.assertEqual("PASS", result["result"])
        self.assertEqual(0, result["exit_code"])

    def test_wrong_accepted_manifest_sha_is_integrity_hold(self):
        self.freeze()
        result = verify(self.manifest, accepted_manifest_sha256="0" * 64).to_dict()
        self.assertEqual("HOLD", result["result"])
        self.assertEqual(4, result["exit_code"])
        self.assertIn("CI11_ACCEPTED_MANIFEST_MISMATCH", [item["code"] for item in result["findings"]])

    def test_wrong_accepted_sha_and_malformed_jsonl_preserve_both_findings(self):
        self.manifest.write_text("not-json\n", encoding="utf-8")
        result = verify(self.manifest, accepted_manifest_sha256="0" * 64).to_dict()
        codes = [item["code"] for item in result["findings"]]
        self.assertIn("CI11_ACCEPTED_MANIFEST_MISMATCH", codes)
        self.assertIn("CI09_MALFORMED_MANIFEST", codes)
        self.assertEqual(4, result["exit_code"])

    def test_self_consistent_manifest_rewrite_is_rejected_by_accepted_sha(self):
        self.freeze()
        accepted = sha256_file(self.manifest)
        records = read_jsonl(self.manifest)
        records[0]["creation_mode"] = "SELF_CONSISTENT_REWRITE"
        self.write_records(self.manifest, records)
        semantic_only = verify(self.manifest).to_dict()
        anchored = verify(self.manifest, accepted_manifest_sha256=accepted).to_dict()
        self.assertEqual("PASS", semantic_only["result"])
        self.assertEqual(4, anchored["exit_code"])
        self.assertIn("CI11_ACCEPTED_MANIFEST_MISMATCH", [item["code"] for item in anchored["findings"]])

    def test_manifest_summary_counts_are_validated(self):
        for field in (
            "source_record_count",
            "duplicate_group_count",
            "special_file_skip_count",
        ):
            with self.subTest(field=field):
                manifest = self.base / f"{field}.jsonl"
                frozen = freeze([self.root], [], manifest).to_dict()
                self.assertEqual("PASS", frozen["result"])
                records = read_jsonl(manifest)
                records[-1][field] += 1
                self.write_records(manifest, records)
                result = verify(manifest).to_dict()
                self.assertEqual(4, result["exit_code"])
                self.assertIn("CI12_MANIFEST_SUMMARY_INCONSISTENT", [item["code"] for item in result["findings"]])

    def test_manifest_header_rule_version_mismatch_fails_closed(self):
        self.freeze()
        records = read_jsonl(self.manifest)
        records[0]["rule_version"] = "unsupported-rule-generation"
        self.write_records(self.manifest, records)
        result = verify(self.manifest).to_dict()
        self.assertEqual(4, result["exit_code"])
        self.assertIn("IN02_UNSUPPORTED_VERSION", [item["code"] for item in result["findings"]])


if __name__ == "__main__":
    unittest.main()
