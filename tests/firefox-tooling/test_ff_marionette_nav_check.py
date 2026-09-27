"""Regression for the v1.0.9 new-chat navigation check (review-fix 2026-09-27).

The navigation check (19.new-chat-navigation-association) must aggregate its
step assertions into the run results and make the probe exit non-zero when a
navigation-semantic assertion fails, so a tracker regression can never pass
the probe silently. Uses the in-process fake peer; the real-browser red/green
evidence lives in docs/upgrade-2026-09-27/review-fix/.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import probe_loader  # noqa: E402
from fake_marionette import FakeMarionette  # noqa: E402
from probe_loader import build_record, write_dist, zip_dist  # noqa: E402

PROBE = probe_loader.load_probe()

NAV_CHECK = "19.new-chat-navigation-association"


class FakeProcess:
    def __init__(self):
        self.pid = 4242
        self._alive = True
        self.terminated = False

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def kill(self):
        self.terminated = True
        self._alive = False

    def wait(self, timeout=None):
        return 0


class NavCheckHarness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-navcheck-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = write_dist(os.path.join(self.tmp, "dist"))
        self.xpi = zip_dist(self.dist, os.path.join(self.tmp, "good.xpi"))
        self.record_path = os.path.join(self.tmp, "good.build.json")
        with open(self.record_path, "w", encoding="utf-8") as handle:
            json.dump(build_record(PROBE, self.dist, self.xpi), handle)
        self.out = os.path.join(self.tmp, "results.json")
        self.fake = None

    def run_probe(self, answers=None):
        process = FakeProcess()
        launched = []

        def fake_launch(firefox_exe, profile_dir, port):
            launched.append({"firefox": firefox_exe, "profile": profile_dir, "port": port})
            return process, ["fake-firefox", "-profile", profile_dir]

        def fake_wait(host, port, timeout, proc):
            return None

        def fake_marionette(host, port):
            self.fake = FakeMarionette(launched[-1]["profile"], answers=answers)
            return self.fake

        argv = ["--xpi", self.xpi, "--expect-build-record", self.record_path,
                "--dist", self.dist, "--label", "navcheck-regression",
                "--firefox", os.path.join(self.tmp, "fake-firefox.exe"),
                "--out", self.out]
        originals = (PROBE.launch_firefox, PROBE.wait_for_port, PROBE.Marionette)
        PROBE.launch_firefox = fake_launch
        PROBE.wait_for_port = fake_wait
        PROBE.Marionette = fake_marionette
        try:
            with mock.patch("time.sleep", lambda _seconds: None):
                code = PROBE.main(argv)
        finally:
            PROBE.launch_firefox, PROBE.wait_for_port, PROBE.Marionette = originals
        self.process = process
        return code

    def saved(self):
        with open(self.out, encoding="utf-8") as handle:
            return json.load(handle)

    def nav_check(self, payload):
        for check in payload["results"]:
            if check["check"] == NAV_CHECK:
                return check
        raise AssertionError("%s missing from results" % NAV_CHECK)


class TestNavCheckPropagation(NavCheckHarness):
    def test_green_run_includes_the_navigation_check(self):
        code = self.run_probe()
        self.assertEqual(code, PROBE.EXIT_OK)
        payload = self.saved()
        check = self.nav_check(payload)
        self.assertTrue(check["ok"], check)
        self.assertEqual(payload["meta"]["summary"]["failed"], 0)
        self.assertEqual(payload["meta"]["summary"]["missingChecks"], [])
        self.assertTrue(self.process.terminated)

    def test_temporary_navigation_context_change_fails_into_results(self):
        # The v1.0.9 fix semantic: navigating to the local-chatgpt: draft URL
        # must keep the creation context id. Simulate a tracker that changes it.
        code = self.run_probe(answers={"navTempCtx": {"ctxId": "ctx-CHANGED",
                                                      "turnCtx": "ctx-1",
                                                      "pageUrl": "changed"}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        check = self.nav_check(payload)
        self.assertFalse(check["ok"], check)
        self.assertIn("ctx-CHANGED", check["detail"])
        self.assertIn(NAV_CHECK, payload["meta"]["summary"]["failedChecks"])
        self.assertTrue(self.process.terminated)

    def test_lost_promotion_at_the_formal_url_fails_into_results(self):
        # After the server identity is correlated, navigating to the formal
        # conversation URL must promote the same context id.
        code = self.run_probe(answers={"navFormalCtx": {"ctxId": "ctx-OTHER",
                                                        "turnCtx": "ctx-1"}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        check = self.nav_check(payload)
        self.assertFalse(check["ok"], check)
        self.assertIn(NAV_CHECK, payload["meta"]["summary"]["failedChecks"])

    def test_unrelated_conversation_must_retire_the_record(self):
        # Switching to an unrelated conversation must not keep the record current.
        code = self.run_probe(answers={"navUnrelated": {"ctxId": "ctx-1", "oursCurrent": True}})
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        payload = self.saved()
        check = self.nav_check(payload)
        self.assertFalse(check["ok"], check)
        self.assertIn(NAV_CHECK, payload["meta"]["summary"]["failedChecks"])


if __name__ == "__main__":
    unittest.main()
