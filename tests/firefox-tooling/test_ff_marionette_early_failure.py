"""Damaged input must still produce a usable, non-fabricated failure record.

Round-2 finding: a non-zip XPI raised zipfile.BadZipFile out of main(), so the
run exited 1 with a traceback and wrote no result file at all.

Every case here is run through the real command line, because "the process must
exit non-zero and still write JSON" cannot be shown by a unit test alone.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe_loader  # noqa: E402
from probe_loader import build_record, run_probe_process, write_dist, zip_dist  # noqa: E402

PROBE = probe_loader.load_probe()


class EarlyFailureBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-early-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = write_dist(os.path.join(self.tmp, "dist"))
        self.xpi = zip_dist(self.dist, os.path.join(self.tmp, "good.xpi"))
        self.record_path = os.path.join(self.tmp, "good.build.json")
        with open(self.record_path, "w", encoding="utf-8") as handle:
            json.dump(build_record(PROBE, self.dist, self.xpi), handle)
        self.out = os.path.join(self.tmp, "results.json")

    def path(self, name):
        return os.path.join(self.tmp, name)

    def probe_argv(self, xpi=None, record=None, out=None, extra=None):
        return [
            "--xpi", xpi or self.xpi,
            "--expect-build-record", record if record is not None else self.record_path,
            "--dist", self.dist,
            "--out", out or self.out,
            "--label", "early-failure",
        ] + (extra or [])

    def run_and_load(self, **kwargs):
        code, stdout, stderr = run_probe_process(self.probe_argv(**kwargs))
        self.assertNotIn("Traceback (most recent call last)", stderr,
                         "a traceback escaped instead of a failure record:\n%s" % stderr)
        self.assertTrue(os.path.isfile(self.out),
                        "no result file was written (exit=%s)\n%s\n%s" % (code, stdout, stderr))
        with open(self.out, encoding="utf-8") as handle:
            payload = json.load(handle)
        return code, payload, stdout, stderr

    def assert_early_failure(self, payload, checks_expect_failed):
        """Shared expectations for anything that fails before the browser."""
        checks = {c["check"]: c for c in payload["results"]}
        for name in checks_expect_failed:
            self.assertIn(name, checks, "missing check %s" % name)
            self.assertFalse(checks[name]["ok"], name)
        meta = payload["meta"]
        for key in ("stage", "startedAt", "finishedAt", "exitCode", "exitReason", "summary"):
            self.assertIsNotNone(meta[key], key)
        self.assertIsInstance(meta["summary"]["executed"], int)
        self.assertTrue(meta["exitReason"])
        self.assertFalse(meta["browserLaunched"], "a browser must not be started for damaged input")
        self.assertFalse(meta["browserConnected"])
        self.assertIsNone(meta["launch"])
        return checks


class TestDamagedPackage(EarlyFailureBase):
    def broken_zip(self):
        path = self.path("broken.xpi")
        with open(path, "wb") as handle:
            handle.write(b"this is not a zip archive\n")
        return path

    def test_not_a_zip_exits_2_and_writes_a_result(self):
        code, payload, stdout, _stderr = self.run_and_load(xpi=self.broken_zip())
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        checks = self.assert_early_failure(payload, ["0a.xpi-sha256", "0b.xpi-contents",
                                                     "0d.manifest-sha256"])
        self.assertIn("package could not be parsed", checks["0b.xpi-contents"]["detail"])
        self.assertIn("BadZipFile", payload["meta"]["identity"]["parseError"])
        # unknown fields stay unknown rather than being invented
        self.assertIsNone(payload["meta"]["identity"]["manifestSha256"])
        self.assertIsNone(payload["meta"]["identity"]["packagedFiles"])
        self.assertNotIn("launched firefox", stdout)
        self.assertEqual(payload["meta"]["stage"], "identity")

    def test_zip_without_manifest_json_exits_2_and_writes_a_result(self):
        path = self.path("no-manifest.xpi")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("readme.txt", "nothing to see")
        code, payload, _stdout, _stderr = self.run_and_load(xpi=path)
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        self.assert_early_failure(payload, ["0b.xpi-contents", "0d.manifest-sha256"])
        self.assertIn("no manifest.json", payload["meta"]["identity"]["parseError"])

    def test_packaged_manifest_with_invalid_json_exits_2_and_writes_a_result(self):
        path = self.path("bad-manifest.xpi")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", "{ this is not json")
        code, payload, _stdout, _stderr = self.run_and_load(xpi=path)
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        self.assert_early_failure(payload, ["0b.xpi-contents", "0d.manifest-sha256"])
        self.assertIn("JSONDecodeError", payload["meta"]["identity"]["parseError"])


class TestDamagedBuildRecord(EarlyFailureBase):
    def write_record(self, name, text):
        path = self.path(name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def assert_record_failure(self, record_path, expected_fragment):
        code, payload, _stdout, _stderr = self.run_and_load(record=record_path)
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        checks = self.assert_early_failure(payload, ["0f.build-record"])
        self.assertIn(expected_fragment, checks["0f.build-record"]["detail"])
        self.assertIsNotNone(payload["meta"]["expectation"]["buildRecordError"])
        self.assertFalse(payload["meta"]["summary"]["identityOk"])
        return payload

    def test_missing_record_file(self):
        self.assert_record_failure(self.path("does-not-exist.json"), "build record not found")

    def test_record_with_invalid_json(self):
        self.assert_record_failure(self.write_record("bad.json", "{ not json"),
                                   "not readable JSON")

    def test_record_that_is_not_an_object(self):
        self.assert_record_failure(self.write_record("list.json", "[1, 2, 3]"),
                                   "expected an object")

    def test_record_missing_the_xpi_hash(self):
        self.assert_record_failure(self.write_record("nohash.json", '{"fileHashes": {"a": "b"}}'),
                                   "xpiSha256")

    def test_record_with_wrongly_typed_fields(self):
        self.assert_record_failure(
            self.write_record("typed.json", json.dumps({"xpiSha256": "abc", "fileHashes": []})),
            "expected dict")

    def test_record_with_empty_file_hashes(self):
        self.assert_record_failure(
            self.write_record("empty.json", json.dumps({"xpiSha256": "a" * 64, "fileHashes": {}})),
            "fileHashes")


class TestOutputPathFailures(EarlyFailureBase):
    def test_unwritable_output_parent_fails_early_without_touching_files(self):
        blocker = self.path("blocker")
        with open(blocker, "w", encoding="utf-8") as handle:
            handle.write("i am a file, not a directory\n")
        before = open(blocker, "rb").read()
        target = os.path.join(blocker, "results.json")

        code, stdout, stderr = run_probe_process(self.probe_argv(out=target))
        self.assertNotEqual(code, 0)
        self.assertEqual(code, PROBE.EXIT_FATAL)
        self.assertIn("cannot write results", stderr)
        self.assertNotIn("launched firefox", stdout)
        self.assertFalse(os.path.exists(target))
        self.assertEqual(open(blocker, "rb").read(), before)
        # nothing else was created next to the blocker either
        self.assertEqual(sorted(os.listdir(self.tmp)), sorted(["dist", "good.xpi",
                                                              "good.build.json", "blocker"]))

    def test_existing_output_is_refused_and_never_rewritten(self):
        with open(self.out, "wb") as handle:
            handle.write(b'{"historical": "keep me"}\n')
        before = open(self.out, "rb").read()
        # deliberately no --force: history must survive a test run
        code, _stdout, stderr = run_probe_process(self.probe_argv())
        self.assertEqual(code, PROBE.EXIT_OUTPUT_EXISTS)
        self.assertIn("refusing to overwrite", stderr)
        self.assertEqual(open(self.out, "rb").read(), before)

    def test_no_extra_file_is_created_next_to_the_results(self):
        # Guards the output-protection step itself: a run may leave the results
        # file and nothing else in the destination directory.
        code, _stdout, _stderr = run_probe_process(self.probe_argv(xpi=self.path("missing.xpi")))
        self.assertNotEqual(code, 0)
        self.assertTrue(os.path.isfile(self.out))
        leftovers = sorted(name for name in os.listdir(self.tmp)
                           if name not in ("dist", "good.xpi", "good.build.json", "results.json"))
        self.assertEqual(leftovers, [], "unexpected files next to the results")

    @unittest.skipUnless(os.path.isfile(PROBE.DEFAULT_FIREFOX),
                         "no Firefox executable available")
    def test_real_run_also_leaves_nothing_else_next_to_the_results(self):
        # The heaviest path (real identity + real browser) must be just as tidy.
        # The exit code is not asserted here: the network-dependent checks may
        # fail, and what this test guards is the destination directory.
        code, _stdout, _stderr = run_probe_process(self.probe_argv(), timeout=420)
        self.assertNotEqual(code, PROBE.EXIT_OUTPUT_EXISTS)
        with open(self.out, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(payload["meta"]["stage"], "checks")
        leftovers = sorted(name for name in os.listdir(self.tmp)
                           if name not in ("dist", "good.xpi", "good.build.json", "results.json"))
        self.assertEqual(leftovers, [], "unexpected files next to the results")

    def test_existing_directory_as_output_is_refused(self):
        directory = self.path("out-dir")
        os.makedirs(directory)
        code, _stdout, stderr = run_probe_process(self.probe_argv(out=directory))
        self.assertEqual(code, PROBE.EXIT_OUTPUT_EXISTS)
        self.assertIn("existing directory", stderr)
        self.assertEqual(os.listdir(directory), [])

    def test_bad_command_line_is_rejected_before_anything_else(self):
        code, _stdout, stderr = run_probe_process(["--dist", self.dist])
        self.assertEqual(code, PROBE.EXIT_USAGE)
        self.assertIn("error", stderr)
        self.assertFalse(os.path.exists(self.out))


class TestVerifyIdentityNeverRaises(unittest.TestCase):
    """The identity step must never escape as an exception."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-noraise-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_identity_reports_instead_of_raising(self):
        dist = write_dist(os.path.join(self.tmp, "dist"))
        broken = os.path.join(self.tmp, "broken.xpi")
        with open(broken, "wb") as handle:
            handle.write(b"not a zip")
        checks, meta = PROBE.verify_identity(broken, dist, "a" * 64, None, "")
        names = {check["check"] for check in checks}
        self.assertIn("0b.xpi-contents", names)
        self.assertTrue(any(not check["ok"] for check in checks))
        self.assertIsNotNone(meta["parseError"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
