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
- 2026-09-03 加 `data_collection_permissions {required:["none"]}`（AMO 新提交强制要求），门禁全绿并 push（456a7aa）

## 任务 0 原始计划（已执行，保留备查）
- 目标：同一源码 + 独立 Firefox target（dist/firefox），Chromium 构建与测试不受影响。
- 最小改法：只做 manifest 转换，业务源码零改动；最大风险 `await chrome.*` 已由实测排除。

## 升级开工回执（2026-09-20，v1.0.5 → v1.0.7）
- 起点：`HEAD=182fca1e8b6e7b4f73e5ae01f634d286209980f4`（main，工作树干净）；共同祖先 `4f98a663c4fb111f582f6a4d1aaefd190a5d9b7a`。
- 目标：`d5524a00d2721f1d022350a2589cac1dddccaaca`（upstream/main，解引用 == tag `v1.0.7`）；上游仅领先 3 个提交，main 未超前稳定版。
- 升级前基线（本机 Node v22.22.2 / npm 10.9.7）：typecheck 0 / lint 0 / vitest 21 文件 94 passed 0 failed 0 skipped / build 0 / build:firefox 0。
- 主要更新：capture-context、sse-decoder、usage-quota、upgrade-notice、announcement 新页面；page-hook/bridge 生命周期重构；schema 1.4.0→1.7.0。
- 合并方案：新建 `codex/sync-upstream-v1.0.7`，以 merge 纳入上游（保留可追溯性），保留 Firefox target 与 ID。
- 最大风险：`scripts/build.mjs` 双向改动（本地 firefox target ↔ 上游 announcement 入口）；page-hook/bridge 大改用例变化可能影响 Firefox MAIN-world 适配。

## 任务 1 升级范围分析（2026-09-20）
上游区间 `4f98a66..d5524a0` 共 3 个提交（6a853eb v1.0.6、727568a feat、d5524a0 v1.0.7），62 文件 +4950/-415。**依赖零变化**（package-lock 仅版本号 4 行）。逐项核实（读源码，不凭文件名）：
- 新增模块：`core/capture-context.ts`（文档级 CaptureContext 生命周期，live/reload 独立）、`core/usage-quota.ts`（deep_research/image_gen 额度投影）、`core/page-scope.ts`（tab 显示归属校验）、`core/sse-decoder.ts`（**SSE delta 解码器重写**）、`background/upgrade-notice.ts` + `shared/upgrade-notice.ts`（1.0.7 升级公告）、`ui/shared/notice-hint.ts`。
- 新增 UI：`ui/announcement/`（index.html + index.ts），经 `build.mjs` 的 `uiEntries` 新增入口产出；i18n 词条内联在 `ui/shared/i18n.ts`（`notice.*`），`_locales/` 未变。
- 语义变更：schemaVersion `1.4.0→1.7.0`，新增 `captureContextId` 与 4 个额度字段、verdict 新增 `auto_reasoning`、routeModelSources 新增 DOM 来源；`assessment.ts` 对 `gpt-5-6/5-5-auto-thinking` 单独归类；`endpoints.ts` 新增 `conversation_init` 并排除历史分页（cursor/offset/before/after）；`storage.ts` 引入状态缓存+`revision`+`clearedAt`+`captureContexts`；`privacy.ts` 导出时额外脱敏 captureId/captureContextId。
- 迁移：`core/migration.ts` 本身未改，仍走 `normalizeObservation→createTurn` 通用再归一，故旧 1.4.0 记录会被重算为 1.7.0（含 auto_reasoning 重判）。已有上游测试覆盖。
- **历史 `stream_parse_failed` 核实结论**：上游有相关改动但**非定点修复**——(a) 单事件 >1MB 现抛具名 `stream_event_too_large`（SDK 层限额 1MB）；(b) 新增「无 SSE 分隔符的拼接 data 行」回退解析；(c) 解码器新增 delta/patch/truncate 限额与 `reset`。但 `failed()` 分支仍未特判页面侧 abort（无 AbortError/signal 处理），catch 映射后仍落 `stream_parse_failed`。**判定：未确认根因已消除**，BLOCKED.md 保留该未知项。
- Firefox 接缝（3 处）：① `build.mjs` `uiEntries` 必须并入 `announcement`，否则 dist/firefox 缺页面；② 新增 `chrome.runtime.getManifest`（content 侧，代码已用 `?.` 兜底）、`tabs.get/onUpdated/onRemoved`（FF 长期支持，无新权限）；③ `notice-hint` CSS 用 `:has()`，Firefox 121+ 支持，低于既有 `strict_min_version 128`，不抬高下限。
- 冲突风险：`scripts/build.mjs` 双向改动（本地 firefox target ↔ 上游 uiEntries）；其余（package.json/README/manifest）改动位置互不相邻。无计划新增依赖。

## 任务 2 合并记录（2026-09-20）
（见下方「任务 2 执行结果」）
