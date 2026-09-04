# PROGRESS — Firefox 移植（自用）

## 基线（任务 0，2026-09-03）
- 上游：https://github.com/Liu-Bot24/chatgpt-route-inspector，commit 4f98a66，branch main，工作树干净
- Node v24.16.0 / npm 12.0.1；上游无 LICENSE 文件（署名保留在 UI branding 中）
- 基线实测全绿：typecheck ✅ / lint ✅ / vitest 93/93 ✅ / build ✅（输出 dist/extension）
- 真实调用链：manifest(content_scripts MAIN page-hook + ISOLATED bridge) → window.postMessage → bridge(chrome.runtime.sendMessage) → background service-worker(storage+turns/assessment) → popup/dashboard/options 读取 state；page-hook 自身零 chrome.* 调用

## 任务 1–4 结论（2026-09-03）
- 任务 1：Firefox MV3 用 `background.scripts`（event page，`type:module` 需 112+）；`world:MAIN` 需 128+（MDN BCD）→ 最低版本 128.0；
  storage/runtime/tabs/action/i18n/host_permissions/options_ui 本项目用法全部支持；`minimum_chrome_version` 需剔除；gecko 块仅签名必需。
- 任务 2：新增 `scripts/firefox-manifest.mjs`（纯函数转换）+ build.mjs firefox target + `build:firefox`；业务源码零改动。
  `await chrome.*` 在 FF154 实测原生返回 Promise（之前文档说法不一，以实测为准），故无需兼容层/依赖/改调用点。
- 任务 3：typecheck ✅ / lint ✅ / test 94/94 ✅ / build ✅ / build:e2e ✅ / build:firefox ✅；Firefox manifest 权限与 Chromium 一致，
  JS 产物与 Chromium 版逐字节一致；新增 `tests/unit/manifest-firefox.test.ts` 锁定转换行为。
- 任务 4：本机 Firefox 154.0.1 真机 12/12（ff-probe-results.json）：加载零错误、后台/onboarding/popup/dashboard、
  合成观测→mismatch 管线、chatgpt.com 免登录页 hook+浮窗；需登录的真实对话与长时控制台观察列入 BLOCKED.md。
- 止损/回滚：未触发（首个完整方案一次走通，无需换路线）。

## 发布（2026-09-03）
- 私人库：https://github.com/ono404/chatgpt-route-inspector-firefox.git（origin），上游保留为 upstream
- 提交 e97db10（11 files，+454/-2），已 push，远端 HEAD 一致；分支 main 跟踪 origin/main
- 身份用仓库级 `ono404 / noreply`，未动全局 git 配置

## 任务 0 原始计划（已执行，保留备查）
- 目标：同一源码 + 独立 Firefox target（dist/firefox），Chromium 构建与测试不受影响。
- 最小改法：只做 manifest 转换，业务源码零改动；最大风险 `await chrome.*` 已由实测排除。
