"""In-process scriptable stand-in for a Marionette peer (test fixture only).

The probe's browser-side checks are driven through the same `cmd(method, params)`
seam the real client exposes, so the probe's own control flow, assertions and
exit-code aggregation are the code under test. Responses are scriptable so a
test can make a specific check fail on purpose.
"""
import os
import re
import sys

sys.dont_write_bytecode = True

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:156.0) Gecko/20100101 Firefox/156.0"
EXT_UUID = "11111111-2222-3333-4444-555555555555"
BASE_URL = "moz-extension://" + EXT_UUID

DEFAULT_ANSWERS = {
    "useragent": UA,
    "namespaces": "dynamic",
    "storage": 42,
    "tabsi18n": "dynamic",
    "turn": {"ok": True, "turns": 1, "verdict": "mismatch", "route": "gpt-5-5-mini",
             "req": "gpt-5-6-pro", "schemaVersion": "1.9.0"},
    "auto": {"ok": True, "verdict": "auto_reasoning", "route": "gpt-5-6-auto-thinking",
             "schemaVersion": "1.9.0"},
    "contexts": {"ok": True, "count": 1, "sample": {"id": "ctx-1"}},
    "announcementMsg": {"ok": True, "newId": 999, "before": 2},
    "suspectLive": {"ok": True, "verdict": "suspected_downgrade", "tabId": 4242,
                    "turnTabId": 4242, "turnCtx": "ctx-1"},
    "navCtx": {"tabId": 4242, "pageUrl": "https://chatgpt.com/", "revision": 5, "id": "ctx-1"},
    "navFetch": {"started": True},
    "navRequested": {"captureId": "synthetic-navcheck-capture", "ctx": "ctx-1", "phase": "requested"},
    "navPush": {"pushed": True, "pathname": "/c/local-chatgpt%3Anavcheck-draft"},
    "navPushFormal": {"pushed": True, "pathname": "/c/navcheck-conv"},
    "navPushUnrelated": {"pushed": True, "pathname": "/c/navcheck-unrelated"},
    "navTempCtx": {"pageUrl": "https://chatgpt.com/c/local-chatgpt%3Anavcheck-draft",
                   "revision": 6, "id": "ctx-1", "oursCurrent": False},
    "navIdentity": {"captureId": "synthetic-navcheck-capture-2", "ctx": "ctx-1", "phase": "requested"},
    "navResponse": {"phase": "failed", "errorCode": "http_403", "ctx": "ctx-1"},
    "navFormalCtx": {"pageUrl": "https://chatgpt.com/c/navcheck-conv",
                     "revision": 7, "id": "ctx-1", "oursCurrent": False},
    "navOverlay": {"overlay": True, "pathname": "/c/navcheck-conv",
                   "text": "Route Inspector gpt-5-6-pro-navcheck gpt-5-5-mini-navcheck"},
    "navOverlayGone": {"overlay": True, "pathname": "/c/navcheck-unrelated",
                       "text": "waiting for the next message"},
    "navUnrelated": {"pageUrl": "https://chatgpt.com/c/navcheck-unrelated",
                     "revision": 8, "id": "ctx-2", "oursCurrent": False},
    "tabCtx": {"tabId": 4242, "ctx": "ctx-1"},
    "postSuspect": {"posted": True},
    "suspectVerdicts": {"completed": "suspected_downgrade", "responding": "normal",
                        "failed": "normal", "resolved": "normal"},
    "workVerdicts": {"completed": "work_unverifiable", "responding": "normal"},
    "failedTurn": {"phase": "failed", "errorCode": "stream_parse_failed",
                   "completedAt": None, "verdict": "normal"},
    # v1.1.0: the two dedicated-task verdicts, the planning/report split, the
    # hook-derived deep-research capture and the two dashboard surfaces.
    "taskKinds": {"image": {"verdict": "image_generation", "taskKind": "image_generation",
                            "route": "gpt-5-6-pro", "report": None, "schemaVersion": "1.9.0"},
                  "research": {"verdict": "deep_research", "taskKind": "deep_research",
                               "route": "gpt-5-6-pro", "report": "gpt-5-6-instant",
                               "schemaVersion": "1.9.0"}},
    "researchSplit": {"verdict": "deep_research", "planner": "gpt-5-6-thinking",
                      "report": "gpt-5-6-instant"},
    "drCapture": {"started": True, "fetchName": "routeInspectorFetch"},
    # Check 22 (hardened 2026-10-02). drLock is the pre-request background
    # snapshot the probe reads before sending: the single chatgpt.com tab, its
    # background context (id/pageUrl/revision), the state revision and the
    # capture ids that already exist (beforeIds). A test replaces one field to
    # break exactly one condition (e.g. ctxId None => missing context). drAfter
    # is the result-time state revision, which must exceed drLock.stateRevision.
    # drTurn is the capture the hook derives; the fake fills tabId/pageUrl/
    # captureContextId/requestedModel from the lock and the injected marker
    # unless a test overrides them, and {} means "no capture was produced".
    "drLock": {"tabCount": 1, "tabId": 4242, "stateRevision": 20,
               "ctxId": "ctx-1", "ctxPageUrl": "https://chatgpt.com/", "ctxRevision": 11,
               "beforeIds": ["0f1e2d3c-4b5a-4978-8967-5a4b3c2d1e0f"]},
    "drAfter": {"stateRevision": 21},
    "drTurn": {"captureId": "3f9a1c2d-5b6e-4a71-9c8d-2e4f6a8b0c1d", "taskKind": "deep_research",
               "verdict": "deep_research"},
    "uiFilters": {"filters": ["all", "normal", "auto_reasoning", "image_generation",
                              "deep_research", "suspected_downgrade"],
                  "deepSelected": True, "imageSelected": True},
    "uiSelect": {"row": True},
    "uiResearchStore": {"ok": True, "verdict": "deep_research"},
    "uiSplit": {"planner": "gpt-5-6-thinking", "report": "gpt-5-6-instant",
                "pairs": [["规划模型", "gpt-5-6-thinking"], ["报告模型", "gpt-5-6-instant"]]},
    "state": {"ok": True, "hasState": True, "schemaVersion": None},
    "popup": "Route Inspector Created by @liuqi 实时监听",
    "announcementPage": {"title": "Route Inspector · 1.0.9 版本公告",
                         "text": "1.0.9 · 版本公告 版本公告 疑似降级 历代更新日志 v1.0.9",
                         "script": True, "href": "https://x.com/liuqi"},
    "hint": {"root": True, "suspect": True, "legacy": False,
             "href": "https://rinotice.liu-qi.cn/"},
    "noticeSite": {"finalUrl": "https://rinotice.liu-qi.cn/",
                   "title": "Route Inspector 公告", "text": "版本公告"},
    "cleanup": {"after": 2},
    "page": {"fetchName": "routeInspectorFetch", "overlay": True,
             "url": "https://chatgpt.com/"},
    "dashboard": "路由诊断台 ... GPT 5.6 Pro ... GPT 5.5 mini ...",
    "clickMode": {"root": True, "btn": True},
    "disconnectedCard": {"root": True, "present": True, "refresh": True,
                         "text": "扩展连接已失效，请刷新页面后继续使用。 刷新页面"},
}

# First match wins, so the more specific fragments come first.
ROUTES = [
    ("navcheck-a-ctx", "navCtx"),
    ("navcheck-b-fetch", "navFetch"),
    ("navcheck-e2-fetch", "navFetch"),
    ("navcheck-c-requested", "navRequested"),
    ("navcheck-d-temp-push", "navPush"),
    ("navcheck-e-temp-ctx", "navTempCtx"),
    ("navcheck-f-identity", "navIdentity"),
    ("navcheck-f-response", "navResponse"),
    ("navcheck-g-formal-push", "navPushFormal"),
    ("navcheck-h-formal-ctx", "navFormalCtx"),
    ("navcheck-j-overlay", "navOverlay"),
    ("navcheck-k-unrelated-push", "navPushUnrelated"),
    ("navcheck-l-unrelated", "navUnrelated"),
    ("navcheck-m-overlay-gone", "navOverlayGone"),
    # v1.1.0 checks. The more specific fragments must precede the generic
    # ("fetchName", "page") / ("route:observation") matches further down.
    # Hardened check 22 (2026-10-02): the tab/context lock, the page-side
    # request wrapper and the new-capture lookup. These precede the generic
    # "captureContexts" / "route:get-state" / "fetchName" matches.
    ("dr22-lock", "drLock"),
    ("dr22-request", "drCapture"),
    ("dr22-poll", "drWrapped"),
    ("#rows tr", "uiSelect"),
    ("\u89c4\u5212\u6a21\u578b", "uiSplit"),
    ("x.captureId === 'ff-probe-ui-research'", "uiResearchStore"),
    ("[data-filter]", "uiFilters"),
    # Pre-hardening fragments, kept so the red run against the *unchanged*
    # probe still reaches its old check 22 (the evidence that it exited 0 when
    # it should have failed). The hardened probe uses dr22-lock/request/poll.
    ("taskkind-request", "drCapture"),
    ("gpt-6-pro-taskkind", "drTurn"),
    ("ff-probe-task-", "taskKinds"),
    ("ff-probe-research-split", "researchSplit"),
    ("beforeIds", "announcementMsg"),
    ("no capture context", "tabCtx"),
    ("'chatgpt-route-inspector',", "postSuspect"),
    ("after: after", "cleanup"),
    ("ff-probe-suspect-live", "suspectLive"),
    ("ff-probe-sus-", "suspectVerdicts"),
    ("ff-probe-wm-", "workVerdicts"),
    ("ff-probe-failed", "failedTurn"),
    ("chrome.tabs.remove", "cleanup"),
    ("finalUrl", "noticeSite"),
    (".disconnected", "disconnectedCard"),
    ("mode-live", "clickMode"),
    ("chrome.tabs.create", "tabsCreate"),
    ("navigator.userAgent", "useragent"),
    ("typeof chrome", "namespaces"),
    ("chrome.storage.local.set", "storage"),
    ("chrome.i18n.getUILanguage", "tabsi18n"),
    ("'ff-probe-auto'", "auto"),
    ("const t0 =", "turn"),
    ("captureContexts", "contexts"),
    ("route:open-announcement", "announcementMsg"),
    ("route:get-state", "state"),
    ("slice(0, 200)", "popup"),
    ("slice(0, 400)", "announcementPage"),
    ("suspect-trigger", "hint"),
    ("fetchName", "page"),
    ("document.body.textContent", "dashboard"),
]


class FakeMarionette:
    def __init__(self, profile_dir, answers=None, discover_uuid=True,
                 fail_install=False, fail_new_session=False, fail_new_window=False,
                 profile_mode="match", extra_chatgpt_pages=0):
        self.profile_dir = profile_dir
        self.answers = dict(DEFAULT_ANSWERS)
        self.answers.update(answers or {})
        self.discover_uuid = discover_uuid
        self.fail_install = fail_install
        self.fail_new_session = fail_new_session
        self.fail_new_window = fail_new_window
        # "match" | "mismatch" | "missing" | "raise" - how moz:profile comes back
        self.profile_mode = profile_mode
        self.handles = [("w0", "about:blank")]
        if discover_uuid:
            self.handles.append(("w1", BASE_URL + "/ui/onboarding/index.html"))
        # Hardened check 22 must reject ambiguity, so a test can add a second
        # chatgpt.com page beyond the one the probe itself opened.
        for index in range(extra_chatgpt_pages):
            self.handles.append(("w-chatgpt-extra-%d" % index, "https://chatgpt.com/"))
        self.current = self.handles[-1][0]
        self.calls = []
        self.closed = False

    # -- protocol seam -------------------------------------------------------
    def cmd(self, method, params=None):
        params = params or {}
        self.calls.append((method, params))
        handler = getattr(self, "_on_" + method.replace(":", "_"), None)
        if handler is None:
            raise RuntimeError("fake marionette has no handler for %s" % method)
        return handler(params)

    def close(self):
        self.closed = True

    # -- handlers ------------------------------------------------------------
    def _on_WebDriver_NewSession(self, params):
        if self.fail_new_session:
            raise RuntimeError("stub refuses WebDriver:NewSession")
        if self.profile_mode == "mismatch":
            profile = os.path.join(os.path.dirname(self.profile_dir) or self.profile_dir,
                                   "ff-ri-probe-NOT-THIS-RUN")
        elif self.profile_mode == "missing":
            profile = None
        elif self.profile_mode == "raise":
            # A peer that answers with a value the probe cannot treat as a path.
            profile = 12345
        else:
            profile = self.profile_dir
        return {"sessionId": "fake-session", "capabilities": {
            "browserName": "firefox",
            "browserVersion": "156.0",
            "platformName": "windows",
            "moz:profile": profile,
            "moz:buildID": "synthetic",
            "moz:headless": True,
        }}

    def _on_WebDriver_ExecuteScript(self, params):
        return {"value": self._answer(params["script"], params.get("args") or [])}

    def _on_WebDriver_GetWindowHandles(self, params):
        return {"value": [handle for handle, _url in self.handles]}

    def _on_WebDriver_SwitchToWindow(self, params):
        self.current = params["handle"]
        return {"value": None}

    def _on_WebDriver_GetCurrentURL(self, params):
        return {"value": dict(self.handles).get(self.current, "")}

    def _on_WebDriver_NewWindow(self, params):
        if self.fail_new_window:
            raise RuntimeError("WebDriver:NewWindow -> synthetic protocol failure")
        self.handles.append(("w-new", "about:blank"))
        return {"value": {"handle": "w-new"}}

    def _on_WebDriver_Navigate(self, params):
        url = str(params.get("url") or "")
        self.handles = [(handle, url if handle == self.current else known)
                        for handle, known in self.handles]
        return {"value": None}

    def _on_WebDriver_CloseWindow(self, params):
        self.handles = [(handle, known) for handle, known in self.handles if handle != self.current]
        self.current = self.handles[-1][0]
        return {"value": [handle for handle, _known in self.handles]}

    def _on_Addon_Install(self, params):
        if self.fail_install:
            raise RuntimeError("Addon:Install -> synthetic install failure")
        return {"value": "chatgpt-route-inspector-firefox@local"}

    def _on_Addon_Uninstall(self, params):
        # v1.0.9 probe check 20 uninstalls the addon for real; the fake allows it.
        return {"value": None}

    def _on_WebDriver_DeleteSession(self, params):
        return {"value": None}

    # -- scriptable answers --------------------------------------------------
    def _answer(self, script, script_args):
        for fragment, tag in ROUTES:
            if fragment not in script:
                continue
            if tag == "tabsCreate":
                url = script_args[0] if script_args else "about:blank"
                handle = "w-tab-%d" % len(self.handles)
                self.handles.append((handle, url))
                return None
            if tag == "namespaces":
                return {"c": "object", "b": "object",
                        "url": dict(self.handles).get(self.current, "")}
            if tag == "tabsi18n":
                return {"tabs": len(self.handles), "lang": "zh-CN",
                        "url": BASE_URL + "/ui/popup/index.html", "version": "1.0.7"}
            if tag in ("navPush", "navPushFormal", "navPushUnrelated"):
                # history.pushState really changes the tab URL, so the fake
                # must move the current handle for later GetCurrentURL probes.
                value = self.answers[tag]
                self.handles = [(handle, "https://chatgpt.com" + value["pathname"]
                                 if handle == self.current else known)
                                for handle, known in self.handles]
                return value
            if tag == "announcementMsg":
                # Check 15: the handler opened the notice site in a new tab, so
                # the fake must register a handle the probe can switch to.
                if "beforeIds" in script and not any("rinotice" in known for _h, known in self.handles):
                    self.handles.append(("w-notice", "https://rinotice.liu-qi.cn/"))
                return self.answers[tag]
            if tag == "chatgptTabQuery":
                return self.answers[tag]
            if tag == "drWrapped":
                # Hardened check 22 (2026-10-02). The probe passes
                # [marker, tabId, ctxId] and reads the result-time state. The
                # fake never filters for the probe: it fills the honest defaults
                # (marker, locked tabId, locked pageUrl, locked contextId) and a
                # test overrides one key to break exactly one condition. drTurn
                # set to {} yields no capture at all (timeout path).
                marker = script_args[0] if script_args else ""
                lock = self.answers["drLock"]
                after = self.answers.get("drAfter") or {}
                base = self.answers.get("drTurn")
                found = None
                if base:
                    found = {"requestedModel": marker, "tabId": lock.get("tabId"),
                             "pageUrl": lock.get("ctxPageUrl"),
                             "captureContextId": lock.get("ctxId")}
                    found.update(base)
                return {"found": found,
                        "ctxId": lock.get("ctxId"), "ctxPageUrl": lock.get("ctxPageUrl"),
                        "ctxRevision": lock.get("ctxRevision"),
                        "stateRevision": after.get("stateRevision")}
            if tag == "announcementPage":
                # Mirror Firefox: a URL that does not resolve inside the
                # extension renders an error page, so the page probe sees an
                # empty body and no local script.
                if "/ui/announcement/index.html" not in dict(self.handles).get(self.current, ""):
                    return {"title": "页面加载出错", "text": "", "script": False, "href": None}
            return self.answers[tag]
        raise RuntimeError("fake marionette has no answer for script: %s" % script[:120])
