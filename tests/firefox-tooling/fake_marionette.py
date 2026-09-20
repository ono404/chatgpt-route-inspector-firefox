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
             "req": "gpt-5-6-pro", "schemaVersion": "1.7.0"},
    "auto": {"ok": True, "verdict": "auto_reasoning", "route": "gpt-5-6-auto-thinking",
             "schemaVersion": "1.7.0"},
    "contexts": {"ok": True, "count": 1, "sample": {"id": "ctx-1"}},
    "announcementMsg": {"before": 2, "after": 2, "ok": True},
    "state": {"ok": True, "hasState": True, "schemaVersion": None},
    "popup": "Route Inspector Created by @liuqi 实时监听",
    "announcementPage": {"title": "Route Inspector · 1.0.7 公告",
                         "text": "1.0.7 · 用户公告 样本观察与反馈邀请",
                         "script": True, "href": "https://x.com/liuqi"},
    "hint": {"root": True, "notice": True, "star": True, "error": True},
    "page": {"fetchName": "routeInspectorFetch", "overlay": True,
             "url": "https://chatgpt.com/"},
    "dashboard": "路由诊断台 ... GPT 5.6 Pro ... GPT 5.5 mini ...",
}

# First match wins, so the more specific fragments come first.
ROUTES = [
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
    ("notice-star", "hint"),
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
        return {"value": None}

    def _on_Addon_Install(self, params):
        if self.fail_install:
            raise RuntimeError("Addon:Install -> synthetic install failure")
        return {"value": "chatgpt-route-inspector-firefox@local"}

    def _on_Addon_Uninstall(self, params):
        raise RuntimeError("Addon:Uninstall -> not installed")

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
            if tag == "announcementPage":
                # Mirror Firefox: a URL that does not resolve inside the
                # extension renders an error page, so the page probe sees an
                # empty body and no local script.
                if "/ui/announcement/index.html" not in dict(self.handles).get(self.current, ""):
                    return {"title": "页面加载出错", "text": "", "script": False, "href": None}
            return self.answers[tag]
        raise RuntimeError("fake marionette has no answer for script: %s" % script[:120])
