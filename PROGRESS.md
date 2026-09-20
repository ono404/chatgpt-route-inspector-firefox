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
- 分支 `codex/sync-upstream-v1.0.7`（main 冻结在 `182fca1`，未重写历史）。
- 开工记录提交 `8affe8f` → `git merge --no-ff d5524a0` → 合并提交 `33f0879`（双亲：8affe8f + d5524a0）。
- **零冲突**：`scripts/build.mjs` 自动三方合并为双侧同时保留（`uiEntries` 含 `announcement` + `validTargets` 含 `firefox` + `toFirefoxManifest` 出口）；
  `package.json` 版本 1.0.7 与 `build:firefox` 并存。
- 选择 merge 而非 rebase/cherry-pick 的理由：上游提交哈希可追溯（合并提交单亲即上游 SHA），后续同步只需再次 merge 上游，无重写风险。
- 合并后 `git diff d5524a0 HEAD -- src schemas _locales icons tests` 仅剩新增的 `tests/unit/manifest-firefox.test.ts` → **业务源码与上游逐字节一致，无 Firefox 专属业务分叉**。
- 版本/权限核实：manifest 与 package.json 均 1.0.7；`permissions:[storage]`、`host_permissions`、`content_scripts` 均未变（上游只改 version 字段）。
- 新增 API 审计：`chrome.runtime.getManifest`（扩展页/后台，FF 长期支持）、`tabs.get/onUpdated/onRemoved`（FF 长期支持，无新权限）；
  新增唯一 CSS 特性 `:has()`（FF 121+，低于既有下限 128）。**最低版本维持 128.0，未改动。**
- `required:['none']` 仍真实成立：上游未新增权限、未新增扩展自身联网点；公告页外链为 `target="_blank"` 的用户主动跳转（上游单测断言 `not.toMatch(/(script|iframe|img)[^>]+(https?:)/)`）。**未虚填 AMO 声明。**
- storage 迁移：`core/migration.ts` 未变，仍通用再归一；补齐合成旧数据验证（见任务 3）。

## 任务 3 验证结果（2026-09-20）
命令与退出码（原始输出：`docs/upgrade-2026-09-20/evidence/`）：

| 命令 | 升级前基线 | 升级后 | 退出码 |
| --- | --- | --- | --- |
| typecheck | 0 | 0 | 0 |
| lint | 0 | 0 | 0 |
| test (`vitest run --coverage`) | 21 文件 / 94 passed / 0 failed / 0 skipped | 33 文件 / 301 passed / 0 failed / 0 skipped | 0 |
| build | ✅ | ✅ | 0 |
| build:firefox | ✅ | ✅ | 0 |
| build:e2e | — | ✅ | 0 |
| verify:firefox | — | ✅ | 0 |
| test:e2e | — | **未执行（缺 Chromium）** | 1（环境错误） |

- 覆盖率：All files 97.19% stmts / 91.35% branch / 100% funcs（阈值 80/80/80/70 全过）。
- 测试数量不低于基线：94 → 301（上游新增 + 本任务新增 `tests/integration/firefox-upgrade-migration.test.ts` 5 项），未删测试、未放松断言。
- 新增 `scripts/verify-firefox-dist.mjs`：两 target **路径集合双向比对**（非交集）+ 逐文件同源（JS 强制 30 个文件中的 8 个 JS 逐字节一致）+ manifest/HTML 本地引用存在性 + gecko 声明 + announcement 资源完整性。
  实测：`extension=30 firefox=30 identical=true`，`OK`，退出码 0。
- **反向验证（红→绿）**：在仓库外临时副本移除 `ui/announcement/index.js` → 4 项失败、退出码 1；还原 → `OK`、退出码 0。
  证据：`evidence/verify-dist-red.log`、`evidence/verify-dist-green.log`。（首次误将副本放在仓库内 `.tmp/`，被 ESLint 扫描导致 lint 556 错，已移出仓库并复跑 lint=0。）
- 合成旧数据迁移验证（新文件 `tests/integration/firefox-upgrade-migration.test.ts`，5 项全过，全部合成数据、不碰真实数据）：
  1.0.5 形态快照（schema 1.4.0、无 `revision`/`captureContexts`/`clearedAt`）读取后：`revision=0`、无 `clearedAt`、turns 全部升到 1.7.0、
  `auto_reasoning` 重判生效、额度字段补 null、旧字段 confidence/effectiveModel 清除、退役 source 记录丢弃、
  设置与 parserHealth 保留、畸形 captureContext 丢弃而合法保留、**`readState()` 全程未写存储（用户数据零改写）**。

## 任务 4 Firefox 真机结果（2026-09-20）
- 产物：`dist/firefox` → XPI `chatgpt-route-inspector-firefox-1.0.7.xpi`，
  `manifest.json sha256=c43c9104…d327d16a`、`xpi sha256=7c49d39d…4b11e1e6`；冻结后重构建的 `dist/firefox/manifest.json` 哈希与包内一致 → 测的确是本次构建。
- 环境：Firefox **156.0**（headless，专用全新临时 profile，未触碰日常 profile，未发生真实 ChatGPT 消息发送）。
- **结果 18/18 PASS**：`docs/upgrade-2026-09-20/ff-probe-results-v1.0.7-2026-09-20.json`（含 date/commit/XPI+manifest 哈希/Firefox 版本）。
  覆盖：XPI 身份校验、加载零错误、`await chrome.*`(storage/tabs/runtime/i18n)、Popup/诊断台渲染、合成观测真实管线、MAIN hook、ISOLATED 浮窗、
  **1.0.7 公告浮窗入口**、**capture context 注册**、**auto_reasoning 判定**、**公告页渲染与外链**、**route:open-announcement 链路**。
- **关键环境发现（已写入 README）**：Firefox ≥156 对特权上下文（扩展页）拒绝 `WebDriver:ExecuteScript`
  （`unsupported operation`），必须加 `-remote-allow-system-access` 启动才能恢复；FF154 无此限制，历史 12/12 是 FF154 结果。
- 探针改造：`ff-marionette.py` 参数化（`--xpi/--expect-manifest-sha256/--port/--out/--label/--commit`）、新增 XPI 内 manifest 哈希前置校验（不匹配即退出码 2，杜绝误测旧包）、
  输出改为 `{meta, results}` 并记录版本与哈希。旧 `ff-probe-results.json` 未覆盖。
- 未测：真实 1.0.5→1.0.7 更新事件（临时加载无法产生 `reason=update`）、FF128 下限 —— 均记入 BLOCKED.md 第 5/6 项。

## 任务 6 验证工具修正开工回执（2026-09-20，第二轮）
- 起点 `HEAD=7dd7a86ed3df12ea5f9fdc4d8551316b371041b4`，分支 `codex/sync-upstream-v1.0.7`；main 仍为 `182fca1`（未动）。
- 冻结核对：`git diff d5524a00… HEAD -- src schemas _locales icons manifest` = 空；`HEAD:scripts/build.mjs=5a508e8d`；`git status -uall` 仅 `.workbuddy/memory/*` 两条未跟踪。
- 旧证据哈希已录（不得覆盖）：`ff-probe-results.json=4bec56b9…`、`UPGRADE-REPORT.md=881c3fda…`、`ff-probe-results-v1.0.7-2026-09-20.json=3da8fab7…`，17 个 `evidence/*.log` 逐个记录于 `docs/upgrade-2026-09-20/evidence/`。
- 本轮范围：只修 `ff-marionette.py` / `package-firefox.mjs` / `verify-firefox-dist.mjs` / 新增验证工具回归测试 / 必要 npm script / 文档；不碰业务源码与构建脚本。
- 已确认缺陷（管理者实测）：`ff-marionette.py` 检查失败仍退出 0；仅核对 manifest 哈希；`--out` 默认写死旧结果文件；meta 用环境变量冒充 profile；README 顺序倒置。
- Python 解释器：裸 `python` 是 WindowsApps 别名（退出 9009），一律用 `C:\Users\gyjxjkg\.workbuddy\binaries\python\versions\3.13.12\python.exe`。
- 方案：探针自行以全新专用临时 profile 启动 Firefox（隐藏窗口）并连接；身份改为「构建记录 → XPI 全量哈希 + 逐文件比对」；退出码按检查聚合；`--out` 缺省生成不碰撞新路径且拒绝覆盖。
- 最大风险：`ff-marionette.py` 重构后真机行为变化 → 用真机正/反向各跑一遍，且回归测试用本地 stub Marionette 夹具固定。

## 任务 6 验证工具修正结果（2026-09-20，第二轮）
- 范围：只修 `ff-marionette.py` / `scripts/package-firefox.mjs` / `scripts/verify-firefox-dist.mjs` / 新增验证工具回归测试 / 必要 npm script / 文档。**业务路径与 main 未变**（`git diff d5524a0 HEAD -- src schemas _locales icons manifest` 为空；`main=182fca1e`）。
- 修掉的第一轮缺陷：① 检查失败仍退出 0；② 身份只比 manifest 哈希（同 manifest 异 JS 可混过）；③ `--out` 默认覆盖旧结果；④ `meta.profile` 取自环境变量而非浏览器实测。
- 探针改为**自启动浏览器**（全新专用临时 profile + 自选端口 + 隐藏窗口 + 只停自己启动的实例 + 删除自己建的 profile）。
- 退出码：0 全通过 / 2 身份被拒（连接前）/ 3 运行异常 / 4 有检查失败 / 5 检查没跑全 / 6 拒绝覆盖已有输出 / 64 参数错。
- 门禁（最终冻结代码后重跑，逐个记录退出码，原始输出 `docs/upgrade-2026-09-20/evidence/r2-*.log`）：typecheck 0 / lint 0 / test 0（33 文件 301 passed）/ build 0 / build:firefox 0 / build:e2e 0 / verify:firefox 0 / package:firefox 0 / **test:firefox-tooling 0（28 passed）**。
- 真机正向（FF156.0，`moz:buildID=20260909172920`，会话回报 `moz:profile` == 本次启动的临时目录）：**22 项全执行 / 22 PASS / 0 FAIL / 0 缺失 → 退出码 0**；XPI `sha256=2b304414…3993`、manifest `c43c9104…d16a`、构建记录 `0208c1e2…d1d1`、`probeSha256=f46f9d36…615c`。
- 真机反向：坏公告页 → 4（`14.announcement-page` FAIL）；同 manifest 异 JS → 2（`0a/0b/0c` FAIL 而 `0d` PASS，且未连接浏览器）；浏览器启动即退出 → 3；启动超时 → 3；`--out` 指向已有文件 → 6 且原文件哈希不变；省略 `--out` → 0 且生成新时间戳文件、历史 `ff-probe-results.json` 哈希不变。
- 新增 `scripts/run-firefox-tooling-tests.mjs`（本机裸 `python` 是 WindowsApps 别名会退出 9009；另：本沙箱内 Node 的 `spawnSync` 一律 EBUSY，必须用异步 `spawn`）与 `tests/firefox-tooling/**` 6 文件。
- 历史证据零改动（逐个哈希核对）：`ff-probe-results.json=4bec56b9…`、`ff-probe-results-v1.0.7-2026-09-20.json=3da8fab7…`、第一轮 17 个 `evidence/*.log` 全部原值。
- 本轮证据已审查 + 脱敏（`gyjxjkg` → `<user>`，仅出现在绝对路径；凭据类模式扫描零命中），按精确路径 `git add -f` 纳入提交，未改 `.gitignore`、未把整个目录强制添加。
- 仍未处理：未跟踪的 `.workbuddy/`（其存在已在报告 §9.8 与最终 Git 状态中明确列出）。
- 提交：`f55c1ed`（工具 + 文档 + 本轮证据，38 文件）；其后一个提交把**第一轮那 17 个被全局 `*.log` 规则漏掉的 `evidence/*.log`** 按精确路径补入版本控制（此前它们只存在于工作区，正是第一轮“证据未进入提交”的成因）。
- 本轮**只说明验证修正结果**，不声称全部升级场景已验证，也不声称已获管理者验收；额度真机等未验证项见 BLOCKED.md 第 8 项。

## 任务 5 交付（2026-09-20）
- 新增 `docs/upgrade-2026-09-20/`：`UPGRADE-REPORT.md`（交付报告）+ `evidence/`（原始命令输出、红→绿证据、探针日志）+ 探针结果 JSON。
- 新增脚本：`scripts/verify-firefox-dist.mjs`、`scripts/package-firefox.mjs`（+ npm script `verify:firefox`、`package:firefox`）。
- 文档：README-FIREFOX.md 重写（同步基线/新命令/探针用法/FF156 参数/限制）、AGENTS.md 事实更新、BLOCKED.md 更新未决项、本文件。
- 回退方法：`git switch main`（main 仍为 `182fca1`，未被触碰）；或 `git revert -m 1 33f0879` 撤回本次合并。
