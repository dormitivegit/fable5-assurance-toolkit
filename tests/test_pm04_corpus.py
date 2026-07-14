import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from assurance_toolkit.corpus import freeze, verify
from assurance_toolkit.identities import file_identity
from assurance_toolkit.io_utils import read_jsonl, sha256_bytes, sha256_file


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


if __name__ == "__main__":
    unittest.main()
