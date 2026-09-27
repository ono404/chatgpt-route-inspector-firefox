"""In-process scriptable stand-in for a Marionette peer (test fixture only).

The probe's browser-side checks are driven through the same `cmd(method, params)`
seam the real client exposes, so the probe's own control flow, assertions and
exit-code aggregation are the code under test. Responses are scriptable so a
test can make a specific check fail on purpose.
"""
import os
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
             "req": "gpt-5-6-pro", "schemaVersion": "1.8.0"},
    "auto": {"ok": True, "verdict": "auto_reasoning", "route": "gpt-5-6-auto-thinking",
             "schemaVersion": "1.8.0"},
    "contexts": {"ok": True, "count": 1, "sample": {"id": "ctx-1"}},
    "announcementMsg": {"ok": True, "newId": 999, "before": 2},
    "suspectLive": {"ok": True, "verdict": "suspected_downgrade", "tabId": 4242,
                    "turnTabId": 4242, "turnCtx": "ctx-1"},
    "navCtx": {"tabId": 4242, "ctx": "ctx-1"},
    "navFetch": {"started": True},
    "navRequested": {"captureId": "synthetic-navcheck-capture", "ctx": "ctx-1", "phase": "requested"},
    "navPush": {"pushed": True},
    "navTempCtx": {"ctxId": "ctx-1", "turnCtx": "ctx-1",
                   "pageUrl": "https://chatgpt.com/c/local-chatgpt%3Anavcheck-draft"},
    "navIdentity": {"captureId": "synthetic-navcheck-capture-2", "ctx": "ctx-1", "phase": "requested"},
    "navResponse": {"phase": "failed", "errorCode": "http_403", "ctx": "ctx-1"},
    "navFormalCtx": {"ctxId": "ctx-1", "turnCtx": "ctx-1"},
    "navOverlay": {"overlay": True,
                   "text": "Route Inspector gpt-5-6-pro-navcheck gpt-5-5-mini-navcheck"},
    "navOverlayGone": {"overlay": True, "text": "waiting for the next message"},
    "navUnrelated": {"ctxId": "ctx-2", "oursCurrent": False},
    "tabCtx": {"tabId": 4242, "ctx": "ctx-1"},
    "postSuspect": {"posted": True},
    "suspectVerdicts": {"completed": "suspected_downgrade", "responding": "normal",
                        "failed": "normal", "resolved": "normal"},
    "workVerdicts": {"completed": "work_unverifiable", "responding": "normal"},
    "failedTurn": {"phase": "failed", "errorCode": "stream_parse_failed",
                   "completedAt": None, "verdict": "normal"},
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
    ("navcheck-g-formal-push", "navPush"),
    ("navcheck-h-formal-ctx", "navFormalCtx"),
    ("navcheck-j-overlay", "navOverlay"),
    ("navcheck-k-unrelated-push", "navPush"),
    ("navcheck-l-unrelated", "navUnrelated"),
    ("navcheck-m-overlay-gone", "navOverlayGone"),
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
                 profile_mode="match"):
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
            if tag == "announcementMsg":
                # Check 15: the handler opened the notice site in a new tab, so
                # the fake must register a handle the probe can switch to.
                if "beforeIds" in script and not any("rinotice" in known for _h, known in self.handles):
                    self.handles.append(("w-notice", "https://rinotice.liu-qi.cn/"))
                return self.answers[tag]
            if tag == "chatgptTabQuery":
                return self.answers[tag]
            if tag == "announcementPage":
                # Mirror Firefox: a URL that does not resolve inside the
                # extension renders an error page, so the page probe sees an
                # empty body and no local script.
                if "/ui/announcement/index.html" not in dict(self.handles).get(self.current, ""):
                    return {"title": "页面加载出错", "text": "", "script": False, "href": None}
            return self.answers[tag]
        raise RuntimeError("fake marionette has no answer for script: %s" % script[:120])
