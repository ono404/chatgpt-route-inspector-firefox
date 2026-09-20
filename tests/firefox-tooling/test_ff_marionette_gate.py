"""The connected browser must be trusted before anything else is sent.

Round-2 finding: a connection whose reported moz:profile did not match the
profile this run created still received Addon:Uninstall and Addon:Install.
These tests assert on the commands that were actually issued - a non-zero exit
code alone would not show whether a state-changing command escaped.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fake_peer import FakePeer  # noqa: E402
from probe_loader import build_record, run_probe_process, write_dist, zip_dist  # noqa: E402
from test_ff_marionette_run import PROBE, RunHarness  # noqa: E402

# Commands that change state on the other end of the socket, or that would tear
# down a browser this run does not own.
STATE_CHANGING = (
    "Addon:Install",
    "Addon:Uninstall",
    "WebDriver:Navigate",
    "WebDriver:NewWindow",
    "WebDriver:DeleteSession",
)
# Executing script in a browser of unknown provenance is also off limits.
SCRIPT_EXECUTION = ("WebDriver:ExecuteScript", "WebDriver:ExecuteAsyncScript")
FORBIDDEN_BEFORE_TRUST = STATE_CHANGING + SCRIPT_EXECUTION


class TestUntrustedConnectionHarness(RunHarness):
    """In-process: the probe's own calls, recorded at the client seam."""

    def _gate_result(self, profile_mode):
        code = self.run_probe(fake_kwargs={"profile_mode": profile_mode})
        return code, self.saved(), [method for method, _params in self.fake.calls]

    def assert_no_state_change(self, sent, payload):
        forbidden = [method for method in sent if method in FORBIDDEN_BEFORE_TRUST]
        self.assertEqual(forbidden, [], "state-changing commands were sent: %s" % (sent,))
        self.assertEqual(payload["meta"]["connectionTrusted"], False)
        self.assertTrue(self.fake.closed, "only the socket should be closed")
        self.assertIn("session was not deleted", " ".join(payload["meta"]["notes"]))

    def test_mismatched_profile_blocks_every_later_command(self):
        code, payload, sent = self._gate_result("mismatch")
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        checks = {c["check"]: c for c in payload["results"]}
        self.assertFalse(checks["0e.session-profile"]["ok"])
        self.assertIn("0f.untrusted-connection", checks)
        self.assertFalse(checks["0f.untrusted-connection"]["ok"])
        # nothing beyond the session handshake may have been sent
        self.assertEqual(sent, ["WebDriver:NewSession"], sent)
        self.assert_no_state_change(sent, payload)
        # and nothing that follows the gate was attempted
        self.assertIn("1.install-no-manifest-error", payload["meta"]["summary"]["missingChecks"])
        self.assertIsNotNone(payload["meta"]["summary"]["aborted"])
        self.assertIn("aborted for safety", payload["meta"]["exitReason"])
        self.assert_cleanup()

    def test_missing_profile_blocks_every_later_command(self):
        code, payload, sent = self._gate_result("missing")
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        checks = {c["check"]: c for c in payload["results"]}
        self.assertFalse(checks["0e.session-profile"]["ok"])
        self.assertEqual(sent, ["WebDriver:NewSession"], sent)
        self.assert_no_state_change(sent, payload)
        self.assert_cleanup()

    def test_profile_check_that_raises_blocks_every_later_command(self):
        # The peer answers with a value the probe cannot treat as a path, so the
        # check itself raises. That must stop the run, not be swallowed.
        code, payload, sent = self._gate_result("raise")
        self.assertEqual(code, PROBE.EXIT_CHECKS_FAILED)
        checks = {c["check"]: c for c in payload["results"]}
        self.assertFalse(checks["0e.session-profile"]["ok"])
        self.assertIn("profile check raised", checks["0e.session-profile"]["detail"])
        self.assertEqual(sent, ["WebDriver:NewSession"], sent)
        self.assert_no_state_change(sent, payload)
        self.assert_cleanup()

    def test_matching_profile_still_continues(self):
        code, payload, sent = self._gate_result("match")
        self.assertEqual(code, PROBE.EXIT_OK)
        self.assertIn("Addon:Install", sent)
        self.assertIn("WebDriver:DeleteSession", sent)
        self.assertEqual(payload["meta"]["connectionTrusted"], True)


class TestUntrustedPeerRealProcess(unittest.TestCase):
    """Real process, real socket: what actually crossed the wire."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ff-probe-peer-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dist = write_dist(os.path.join(self.tmp, "dist"))
        self.xpi = zip_dist(self.dist, os.path.join(self.tmp, "good.xpi"))
        self.record_path = os.path.join(self.tmp, "good.build.json")
        with open(self.record_path, "w", encoding="utf-8") as handle:
            json.dump(build_record(PROBE, self.dist, self.xpi), handle)
        self.out = os.path.join(self.tmp, "peer-results.json")

    @unittest.skipUnless(os.path.isfile(PROBE.DEFAULT_FIREFOX),
                         "no Firefox executable available")
    def test_real_probe_process_sends_nothing_state_changing_to_an_untrusted_peer(self):
        wrong_profile = os.path.join(self.tmp, "not-the-profile-this-run-created")
        peer = FakePeer({"browserName": "firefox", "browserVersion": "156.0",
                         "platformName": "windows", "moz:profile": wrong_profile,
                         "moz:buildID": "peer", "moz:headless": True})
        self.addCleanup(peer.close)

        code, stdout, stderr = run_probe_process([
            "--xpi", self.xpi, "--expect-build-record", self.record_path,
            "--dist", self.dist, "--out", self.out, "--label", "peer-gate",
            "--port", str(peer.port), "--startup-timeout", "60",
            "--firefox", PROBE.DEFAULT_FIREFOX,
        ])

        # The claim under test is the traffic, not the exit code.
        self.assertTrue(peer.connected >= 1,
                        "the probe never reached the peer:\n%s\n%s" % (stdout, stderr))
        sent = peer.methods()
        forbidden = [method for method in sent if method in FORBIDDEN_BEFORE_TRUST]
        self.assertEqual(forbidden, [], "state-changing commands crossed the wire: %s" % (sent,))
        self.assertEqual(sent, ["WebDriver:NewSession"], sent)

        self.assertNotIn(code, (0, PROBE.EXIT_OUTPUT_EXISTS), "exit=%s\n%s" % (code, stdout))
        self.assertTrue(os.path.isfile(self.out), "no result file was written")
        with open(self.out, encoding="utf-8") as handle:
            payload = json.load(handle)
        checks = {c["check"]: c for c in payload["results"]}
        if code == PROBE.EXIT_CHECKS_FAILED:
            self.assertFalse(checks["0e.session-profile"]["ok"])
            self.assertIn("0f.untrusted-connection", checks)
            self.assertNotIn("1.install-no-manifest-error", checks)
        self.assertNotIn("Addon:Install", sent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
