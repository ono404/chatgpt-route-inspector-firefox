"""Offline regression tests: artifact identity, output protection, exit codes.

These tests never start a browser. They prove the failure conditions directly:
a tampered package with an unchanged manifest must be rejected before any
browser interaction, an existing evidence file must survive, and exit code 0
must be reachable only by a complete, fully green run.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe_loader  # noqa: E402
from probe_loader import DIST_FILES, build_record, write_dist, zip_dist  # noqa: E402

PROBE = probe_loader.load_probe()
TAMPERED_JS = b"// page hook v1 TAMPERED: same manifest, different code\n"


class IdentityTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = write_dist(os.path.join(self.tmp, "dist"))
        self.xpi = zip_dist(self.dist, os.path.join(self.tmp, "good.xpi"))
        self.record = build_record(PROBE, self.dist, self.xpi)
        self.record_path = os.path.join(self.tmp, "good.build.json")
        with open(self.record_path, "w", encoding="utf-8") as handle:
            json.dump(self.record, handle)

    def checks(self, xpi=None, dist=None, expected=None, record=None):
        found, _meta = PROBE.verify_identity(
            xpi or self.xpi, dist or self.dist,
            self.record["xpiSha256"] if expected is None else expected,
            self.record if record is None else record, self.record_path)
        return {check["check"]: check for check in found}


class TestTruePositive(IdentityTestBase):
    def test_matching_build_passes_every_identity_check(self):
        checks = self.checks()
        self.assertTrue(all(c["ok"] for c in checks.values()),
                        {k: v["detail"] for k, v in checks.items() if not v["ok"]})
        self.assertIn("0a.xpi-sha256", checks)
        self.assertIn("0b.xpi-contents", checks)
        self.assertIn("0c.dist-matches-record", checks)
        self.assertIn("0d.manifest-sha256", checks)


class TestTamperedPackageRejected(IdentityTestBase):
    def _tampered_xpi(self, name):
        src = os.path.join(self.tmp, name + "-src")
        write_dist(src)
        return zip_dist(src, os.path.join(self.tmp, name + ".xpi"),
                        overrides={"content/page-hook.js": TAMPERED_JS})

    def test_same_manifest_different_js_is_rejected(self):
        # Only one JS file differs, so manifest.json is byte-identical: a
        # manifest-hash-only identity check would have passed this package.
        xpi = self._tampered_xpi("tampered")
        with open(self.xpi, "rb") as good, open(xpi, "rb") as bad:
            self.assertNotEqual(good.read(), bad.read())
        self.assertEqual(PROBE.read_xpi_manifest(self.xpi)[0],
                         PROBE.read_xpi_manifest(xpi)[0],
                         "fixture must keep the manifest hash identical")
        checks = self.checks(xpi=xpi)
        self.assertFalse(checks["0a.xpi-sha256"]["ok"], checks["0a.xpi-sha256"])
        self.assertFalse(checks["0b.xpi-contents"]["ok"], checks["0b.xpi-contents"])
        self.assertFalse(checks["0c.dist-matches-record"]["ok"], checks["0c.dist-matches-record"])

    def test_tampered_package_is_rejected_before_any_browser_interaction(self):
        xpi = self._tampered_xpi("tampered-before-connect")
        out = os.path.join(self.tmp, "out.json")
        launches = []

        def forbidden_launch(*args, **kwargs):  # pragma: no cover - must not run
            launches.append(args)
            raise AssertionError("the probe must not launch a browser for a rejected package")

        original = PROBE.launch_firefox
        PROBE.launch_firefox = forbidden_launch
        try:
            code = PROBE.main(["--xpi", xpi, "--expect-build-record", self.record_path,
                               "--dist", self.dist, "--out", out, "--label", "tampered",
                               "--firefox", os.path.join(self.tmp, "no-such-firefox.exe")])
        finally:
            PROBE.launch_firefox = original
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        self.assertEqual(launches, [], "no browser may be launched")
        with open(out, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["meta"]["exitCode"], PROBE.EXIT_IDENTITY)
        self.assertFalse(saved["meta"]["summary"]["identityOk"])
        self.assertIsNone(saved["meta"]["launch"])
        self.assertIn("identity rejected", " ".join(saved["meta"]["notes"]))

    def test_extra_file_inside_xpi_is_rejected(self):
        src = os.path.join(self.tmp, "extra-src")
        write_dist(src)
        xpi = zip_dist(src, os.path.join(self.tmp, "extra.xpi"),
                       extra={"ui/announcement/evil.js": b"// not in dist\n"})
        checks = self.checks(xpi=xpi)
        self.assertFalse(checks["0b.xpi-contents"]["ok"], checks["0b.xpi-contents"])
        self.assertIn("not in dist", checks["0b.xpi-contents"]["detail"])

    def test_file_missing_from_xpi_is_rejected(self):
        src = os.path.join(self.tmp, "missing-src")
        write_dist(src, {k: v for k, v in DIST_FILES.items()
                         if k != "ui/announcement/index.html"})
        xpi = zip_dist(src, os.path.join(self.tmp, "missing.xpi"))
        checks = self.checks(xpi=xpi)
        self.assertFalse(checks["0b.xpi-contents"]["ok"], checks["0b.xpi-contents"])
        self.assertIn("missing from XPI", checks["0b.xpi-contents"]["detail"])

    def test_record_describing_another_dist_is_rejected(self):
        other = write_dist(os.path.join(self.tmp, "other-dist"),
                           dict(DIST_FILES, **{"agent-notes.txt": b"other build\n"}))
        other_xpi = zip_dist(other, os.path.join(self.tmp, "other.xpi"))
        other_record = build_record(PROBE, other, other_xpi)
        checks = self.checks(expected=other_record["xpiSha256"], record=other_record)
        self.assertFalse(checks["0a.xpi-sha256"]["ok"])
        self.assertFalse(checks["0c.dist-matches-record"]["ok"], checks["0c.dist-matches-record"])

    def test_missing_expectation_is_rejected(self):
        checks = self.checks(expected="")
        self.assertFalse(checks["0a.xpi-sha256"]["ok"], checks["0a.xpi-sha256"])
        self.assertIn("no expected XPI sha256", checks["0a.xpi-sha256"]["detail"])


class TestOutputProtection(IdentityTestBase):
    def test_default_out_is_dated_and_never_the_historical_file(self):
        path = PROBE.default_out_path(self.tmp, "positive")
        self.assertNotEqual(os.path.basename(path), "ff-probe-results.json")
        self.assertTrue(re.search(r"^ff-probe-results-positive-\d{8}-\d{6}\.json$",
                                  os.path.basename(path)), path)
        self.assertNotEqual(os.path.abspath(path), os.path.abspath(probe_loader.HISTORICAL_RESULTS))

    def test_default_out_never_collides(self):
        first = PROBE.default_out_path(self.tmp, "probe")
        with open(first, "w", encoding="utf-8") as handle:
            handle.write("{}")
        second = PROBE.default_out_path(self.tmp, "probe")
        self.assertNotEqual(first, second)
        self.assertFalse(os.path.exists(second))

    def test_existing_out_is_refused_and_left_untouched(self):
        out = os.path.join(self.tmp, "existing.json")
        sentinel = b'{"historical": "must survive"}\n'
        with open(out, "wb") as handle:
            handle.write(sentinel)
        code = PROBE.main(["--xpi", os.path.join(self.tmp, "does-not-exist.xpi"),
                           "--out", out, "--label", "refuse"])
        self.assertEqual(code, PROBE.EXIT_OUTPUT_EXISTS)
        with open(out, "rb") as handle:
            self.assertEqual(handle.read(), sentinel)

    def test_force_allows_overwrite(self):
        out = os.path.join(self.tmp, "existing.json")
        with open(out, "wb") as handle:
            handle.write(b"old\n")
        code = PROBE.main(["--xpi", os.path.join(self.tmp, "does-not-exist.xpi"),
                           "--out", out, "--label", "force", "--force"])
        self.assertEqual(code, PROBE.EXIT_IDENTITY)
        with open(out, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["meta"]["exitCode"], PROBE.EXIT_IDENTITY)

    def test_historical_evidence_file_is_never_the_default_target(self):
        self.assertTrue(os.path.isfile(probe_loader.HISTORICAL_RESULTS))
        tmp_script_dir = os.path.join(self.tmp, "script-dir")
        os.makedirs(tmp_script_dir, exist_ok=True)
        self.assertFalse(
            os.path.abspath(PROBE.default_out_path(tmp_script_dir, "probe"))
            == os.path.abspath(probe_loader.HISTORICAL_RESULTS))


class TestExitCodeAggregation(unittest.TestCase):
    def test_zero_requires_complete_and_green(self):
        self.assertEqual(PROBE.decide_exit_code(True, None, [], []), PROBE.EXIT_OK)

    def test_identity_failure_wins_over_everything(self):
        self.assertEqual(PROBE.decide_exit_code(False, RuntimeError("boom"), ["a"], ["b"]),
                         PROBE.EXIT_IDENTITY)

    def test_runtime_anomaly_is_non_zero(self):
        self.assertEqual(PROBE.decide_exit_code(True, RuntimeError("boom"), [], []),
                         PROBE.EXIT_FATAL)

    def test_single_failed_check_is_non_zero(self):
        code = PROBE.decide_exit_code(True, None, ["14.announcement-page"], [])
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        self.assertNotEqual(code, 0)

    def test_unexecuted_required_check_is_non_zero(self):
        code = PROBE.decide_exit_code(True, None, [], ["9.page-hook-MAIN-world"])
        self.assertEqual(code, PROBE.EXIT_INCOMPLETE)
        self.assertNotEqual(code, 0)

    def test_every_non_green_combination_is_non_zero(self):
        for identity_ok in (True, False):
            for fatal in (None, RuntimeError("boom")):
                for failed in ([], ["x"]):
                    for missing in ([], ["y"]):
                        green = identity_ok and fatal is None and not failed and not missing
                        code = PROBE.decide_exit_code(identity_ok, fatal, failed, missing)
                        self.assertEqual(code == 0, green,
                                         (identity_ok, fatal, failed, missing, code))


if __name__ == "__main__":
    unittest.main(verbosity=2)
