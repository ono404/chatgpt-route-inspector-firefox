# PROGRESS — Firefox 移植（自用）

## 现役交接（2026-09-27，neat-freak 收尾）

以下为当前答案；后续任务章节是历史记录，测试数量和结论按各轮次解读。

| 事实面 | 状态 | 当前结论 |
| --- | --- | --- |
| 代码 | verified-current | 当前交付在 `D:\LAB\sync-v109-isolated`、`codex/sync-upstream-v1.0.9`，代码验收提交 `8d01fd5`；业务目录与上游 `99f982d` 无差异。原工作区仍为 v1.0.7 / `909941e`。 |
| 本地运行与交付 | verified-current | v1.0.9 未签名 XPI / 同次 build.json / 源码 ZIP 冻结，30/30 文件复建一致；FF156.0.1 正式探针 27/27，两个语义反例退出 4。只代表受控临时 profile 场景。 |
| 发布与真实流量 | pending | 新版未上传 AMO、未签名、未日常覆盖安装；成功 SSE、真实更新事件、FF128、断线提示、Chromium E2E 等见 BLOCKED.md。未查询远端，不宣称已 push/merged。 |
| 文档 | changed-and-verified | README-FIREFOX 为交付与用法入口，BLOCKED 为未完成项；独立验收证据已归档，历史报告保留。 |
| 规则 | changed-and-verified | AGENTS 修正 327/56 项计数及覆盖边界；原工作区仅补新版位置指针。业务源码、探针和测试未修改。 |
| 记忆 | out-of-scope | Codex 生成记忆只读；旧记忆中的 v1.0.7 是历史快照，当前项目状态以此处为准。未知 .workbuddy/ 不写入。 |
| 工作区 | pending | 两个 worktree 均保留；仅在 v1.0.9 分支提交本次文档/证据。原工作区既有四文档修改与 .workbuddy/ 保留，本轮新增两个入口提示也留作未提交修改。未合并、推送或清场。 |

独立验收原始结果的脱敏副本与哈希清单见 [ACCEPTANCE](docs/upgrade-2026-09-27/independent-acceptance/ACCEPTANCE.md)。本次知识收尾只验证文档差异、链接、证据结构和产物哈希，不把此前运行的 327/56/27 项测试写成本次重新执行。

未消除警告：本轮同步安装时 npm 报 4 项依赖漏洞（3 moderate、1 high）及 esbuild 安装脚本阻止警告，构建成功；未做可达性分析或依赖升级。签名、实际安装与真实流量验收是后续任务。

清场预览：两个 worktree、release 交付物、历史证据和 .workbuddy/ 均保留。最终独立验收临时目录的 7 份文件已归档，可在用户复核后清理原临时副本；更早的 audit/rereview 临时目录含故障夹具和构建记录路径依赖，未判定可删。复核现场仍保留，等待汇报后的明确确认再清场。

规则入口为各工作区 AGENTS.md；本轮对项目文件机械枚举并核对受影响文档，未发现额外项目规则入口。上游 README/PRIVACY 与历史原始证据保留，不制造业务文档分叉。

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

## 任务 7 第三轮结果（2026-09-20，只修两处遗漏）
- 修 D1（**连接信任成为操作前置条件**）：核验 `moz:profile`（存在 + 等于本次创建并启动的目录 + 路径比较无异常）之前**只发 `WebDriver:NewSession`**；不过则记 `0e.session-profile` + `0f.untrusted-connection` 失败、立即停手、只关自己的 socket、**不发 `DeleteSession`**、仍停止本次进程并删本次 profile，**退出码 4**（沿用现有体系：这是“前置条件失败”而非“没跑”）。用户代理串读取也移到门禁之后。
- 修 D2（**早期异常也留证**）：`verify_identity` 永不抛出（解析失败 → `0b/0c/0d` 记失败 + `identity.parseError`，`0a` 仍按文件哈希判定）；`main` 把「读记录 → 解析 XPI → 身份 → 启动 → 连接 → 检查」全部纳入统一收口，任何异常落到 `meta.stage`/`meta.fatal` 并写出结果；构建记录显式校验（存在 / JSON / 字段类型），失败即身份不成立（**码 2**）。新增输出可写性前置检查（不可写 → **码 3**，且发生在启动浏览器之前）。
- 门禁（冻结后重跑，逐个退出码，原始输出 `docs/upgrade-2026-09-20/evidence/r3-*.log`）：typecheck 0 / lint 0 / test 0（33 文件 301 passed）/ **test:firefox-tooling 0（49 passed，28→49）**。业务与构建路径无变动，未重复跑三种构建与缺环境 E2E。
- 真机/命令行（FF156.0）：正向 **23/23 退出码 0**；坏公告页 4；XPI 非 ZIP / 包内缺 manifest / manifest 非 JSON / 构建记录缺失|非 JSON|数组|字段类型错误 全部 **2** 且写出结果、未启动浏览器；输出目录不可写 **3**；已有 `--out` **6** 且原文件不变。
- **D3（执行者自查发现，非管理者指出）**：本轮新增的“输出可写性检查”最初实现为在目标目录写零字节探针文件再删除，实践中有 11 个 `.ff-probe-write-probe-*` 残留（`git status` 发现）。根因未完全定位，故**不调那个探针、直接删除**：现在只做只读判断（父目录可建/是目录/可写 + 目标不是已存在目录），运行期间不在输出目录创建任何额外文件；并新增断言“输出目录除结果文件外没有别的条目”（含真实浏览器路径）。已删除那 11 个自产残留文件。
- D1 关键证据：真实探针进程 + 脚本化 peer（`tests/firefox-tooling/fake_peer.py`）谎报 `moz:profile` → 探针退出 **4**，**对端收到的命令只有 `["WebDriver:NewSession"]`**，`connectionTrusted=false`，`notes` 记录“session 未被删除”。进程内假连接侧另断言危险调用为零。
- 已知抖动（非缺陷，BLOCKED 第 11 项）：`chatgpt.com` 慢时 `9/10` 超时、`11` 未执行 → 退出 5（不重试、不静默通过）。本轮实测遇到一次并保留证据 `r3-probe-negative-badpage-attempt1-navtimeout.*`，同命令第二次恢复为 4。
- 新增 `fake_peer.py` / `test_ff_marionette_gate.py` / `test_ff_marionette_early_failure.py`，扩展 `fake_marionette.py`（`profile_mode`）与 `probe_loader.py`（真实进程助手）。**未删改任何既有测试**（原 28 项全保留）。
- 产物身份与历史证据：`ff-marionette.py=9e04541c…`（11 份结果 JSON 的 `probeSha256` 与之一致）；历史 `ff-probe-results.json=4bec56b9…`、`ff-probe-results-v1.0.7-2026-09-20.json=3da8fab7…` 未变；一/二轮证据未覆盖。本轮证据已审查（凭据类扫描零命中）+ 脱敏（`gyjxjkg`→`<user>`），按精确路径提交。**未使用 `--force`**，未清理未知文件，`.workbuddy/` 未处理。
- 新增限制（BLOCKED 第 10 项）：真实 Firefox 会如实回报自己的 profile，“连接不可信”无法在真机自然产生，只能由脚本化对端复现。
- 本轮只说明这两处遗漏的修复，不声称全部升级场景已验证，也不声称已获管理者验收。
- 提交 `ee74203`（40 文件：探针 + 3 个新测试夹具/用例 + 文档 + 29 个 `r3-*` 证据；`.log` 按精确路径 `git add -f`，未改 `.gitignore`、未强制添加目录）。收尾 `git status --porcelain -uall` 只剩 `.workbuddy/memory/*` 两条未跟踪，即**已跟踪文件干净、仍有未知未跟踪文件**；`main=182fca1e`、`git diff d5524a0 HEAD -- src schemas _locales icons manifest` 为空、两份历史结果哈希未变。

## 任务 7 第三轮开工回执（2026-09-20，只修两处遗漏）
- 起点 `HEAD=f2f53b2`（分支 `codex/sync-upstream-v1.0.7`）；`main=182fca1e` 未动；`git diff d5524a0 HEAD -- src schemas _locales icons manifest` = 空（收尾复核一次）。
- 历史哈希核对未变：`ff-probe-results.json=4bec56b9…`、`ff-probe-results-v1.0.7-2026-09-20.json=3da8fab7…`。
- 目标：① `0e.session-profile` 失败时**不得**再发任何 Addon/写存储/导航/会话清理命令，且非零退出并留证；② 损坏 XPI、缺失/非法构建记录等早期异常必须写出失败结果而非抛 traceback。
- 顺序：先读管理者证据复现 → 改 `ff-marionette.py`（profile 作为前置门禁 + 全流程统一收口）→ 新增回归测试（含真实进程）→ 真机正反向复跑 → 文档 → 提交。
- 改动范围：仅 `ff-marionette.py`、`tests/firefox-tooling/**`、4 个文档、`docs/upgrade-2026-09-20/evidence/` 新增证据。不碰业务源码/manifest/构建与打包脚本/依赖/版本/package scripts/既有业务测试阈值。
- 退出码沿用现有体系：安全中止归入 4（有检查失败），输入损坏归入 2（身份未建立），运行异常仍为 3。
- Python：`C:\Users\gyjxjkg\.workbuddy\binaries\python\versions\3.13.12\python.exe`（裸 python 是 WindowsApps 别名，退出 9009）。
- 最大风险：把 profile 门禁做过头会误伤真实浏览器 → 用真机正向复跑证明不退化。

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

## 升级开工回执（2026-09-27，v1.0.7 → v1.0.9）
- 起点：`HEAD=909941e`（分支 `codex/sync-upstream-v1.0.9`，隔离 worktree `D:\LAB\sync-v109-isolated`，从 v1.0.7 分支 HEAD 建立；原工作区四文档未提交修改已复制快照并哈希核对一致）。
- 目标：`99f982dd089b020afa85b897b07edfb340cc58dd`（upstream v1.0.9，3 提交 40 文件 +1056/-357）；顺序：merge → 最小适配（探针 schema 1.8.0/公告）→ 完整门禁 → 真机正反向 → 交付。
- 升级前基线（本机 Node v24.16.0 / npm 12.0.1，npm ci 按锁文件）：typecheck 0 / lint 0 / vitest 33 文件 301 passed 0 failed（覆盖率 97.19/91.37/100）/ test:firefox-tooling 49 passed 退出码 0。
- 环境：Firefox 156.0.1（C:\Program Files\Mozilla Firefox）；`python` 为 WindowsApps 占位符不可用，用 `py` 启动器（Python 3.14.6，工具回归实测可用）。
- 上游变化预核：schema 1.7.0→1.8.0、新会话 local-chatgpt: 临时地址、suspected_downgrade/work_unverifiable、公告改在线站点；无新增依赖与权限。
- 最大风险：探针与本地测试硬编码旧 schema 1.7.0 与旧公告入口/文案，升级后大面积红灯；只允许按上游新行为最小更新，不得弱化既有保护。

## v1.0.9 同步结果（2026-09-27）

- 提交链：`b1f06aa`（快照）→ `55d3ccf`（merge 上游 `99f982d`）→ `6f932e0`（探针/夹具适配）。分支 `codex/sync-upstream-v1.0.9`，隔离 worktree `D:\LAB\sync-v109-isolated`；原工作区未动。
- 同源：`git diff --exit-code 99f982d -- src schemas _locales icons manifest` 工作区与最终提交均为空；verify-firefox-dist 30/30、8 JS 逐字节一致。
- 门禁：typecheck/lint/test/test:firefox-tooling/build/build:firefox/build:notice/build:e2e/verify:firefox/package:firefox 全部退出码 0；vitest 34 文件 327 passed（上游净增 26），覆盖率 97.29/91.82/100；工具回归 49 passed 未变。
- 真机（FF156.0.1，临时 profile）：探针正向 27/27 退出码 0（新增检查：suspect 浮窗提示走真实 page-hook 管线、公告真实打开 `https://rinotice.liu-qi.cn/` 且历史不变、suspected_downgrade/work_unverifiable/failed 判定、local-chatgpt 会话关联）；篡改反向退出码 2（浏览器前拒绝）；输出保护退出码 6。迭代 run1–run3 红灯证据全保留。
- 止损项：断线提示卡片真机不可复现（FF156 不留孤儿内容脚本，3 轮实测），逻辑层以上游 mock 集成测试为准，详见 BLOCKED 第 12 项。
- 交付：未签名 XPI `34ca9440…da523`、同次 build.json、源码 ZIP `0cc2412f…3d0`；仓库外复建与 XPI 30/30 逐文件一致（发现并修正源码包必须含 tsconfig.json，否则 esbuild 输出缺 "use strict"）。未上传、未签名、未安装。
- e2e：仍无 extension-capable Chromium（本轮实测留证），沿用 BLOCKED 第 7 项。

## 复审修正开工回执（2026-09-27，导航验证补齐）
- 起点：HEAD `4ae924d`（分支 codex/sync-upstream-v1.0.9，工作区干净）；正式 XPI `34ca9440…da523`、源码 ZIP `0cc2412f…3d0` 哈希复核未变。
- 目标：替换探针第 19 项为真实导航检查（page-hook 生成捕获关联 + history 导航），使旧 tracker 故障包在身份通过后于第 19 项退出 4、正式包退出 0；修正第 11 项管线表述。
- 方案：在 chatgpt.com 受控页用 history.pushState/replaceState 模拟新建会话导航顺序，观测由受测 page-hook 自行生成（不预填 captureId/captureContextId、不直接发 route:observation）；响应路由断言同一当前记录 + 无关会话隔离。
- 反例材料：管理者审计目录齐全（故障 XPI `2d9b8b78…`、匹配 build.json 与 dist、tracker-comparison/positive/mutant-probe JSON），当前探针对故障包实测 27/27 退出 0（复现管理者结论）。
- 风险：受控页上 page-hook 的请求解析需要伪造 chatgpt 后端响应结构；若解析入口在 MAIN world 拦截 fetch，可用受控 Response 注入。方案失败 3 次止损改更简方案，最多 2 种。

## 复审修正结果（2026-09-27，导航验证补齐）
- 管理者验收（review-fix/REVIEW.md）两项 P2 已修：第 19 项换成真实导航检查；第 11 项表述改为 bridge→background→浮窗、不覆盖 page-hook 捕获解析。
- 新检查链路：被测 XPI 真实 page-hook 解析合成创建请求并生成 captureId、wrapped history.pushState 驱动 tracker、请求体 correlation 承担会话身份、真实 403/422 拒绝作为到达响应；不预填 ID、不发 route:observation/合成信封。跨源受控响应不可行（page-hook 只查同源，方案 A 一次失败即止损），响应先行到达会破坏创建链（时序已按真实新会话流修正并记录）。
- 红→绿（同一冻结探针 6690f89c…）：正式包 27/27 退出 0；旧 tracker 故障包身份合法通过后第 19 项失败退出 4。12 次迭代全留证（review-fix/attempt*）。
- 工具回归 53 项（原 49 保留 + 新增 4 项导航失败传播）；lint 0；对 4ae924d 与 99f982d 业务同源均为空；正式 XPI/源码 ZIP/build.json 哈希未变。
- 未覆盖仍登记：流式响应内的会话身份路径、真实账号流量；其余 BLOCKED 项不变。本轮理由记录：BLOCKED.md 与 README-FIREFOX.md 无涉及第 11/19 项的表述，故未改（导航验证已真机覆盖，无需新增阻塞项）。

## 假绿灯修正开工回执（2026-09-27，round2）
- 起点：HEAD `f1f198e`、工作区干净、探针 `6690f89c…`、正式 XPI/ZIP/build.json 哈希复核未变；管理者反例（probe-no-navigation.py 禁两次目标导航仍 27/27）已核实。
- 目标：第 19 项每阶段先确认"浏览器地址到达目标 + 后台 context.pageUrl 对应 + revision 更新"，再断言 ID 保持/切换；浮窗检查每次切回锁定句柄并核实地址，gone 阶段必须见到真实浮窗且旧记录（含 correlatedCaptureId）退出当前展示；oursCurrent 纳入断言。
- 方案：后台查询锁定单一 tabId 不再每次 query；页面操作前以完整目标 URL find_handle + location 核实；pushState 返回 pathname 必查；第 19 项 detail 走 JSON 不截断。
- 基线：lint 0、53 项工具回归通过、正式包 27/27 退 0（均为管理者实测，本轮冻结后复跑）。
- 风险：gone 阶段浮窗若真不重挂会导致正式包红灯——上次"root 不存在"实为在扩展 shell 页读取所致，正确页面上 MutationObserver 会重挂；若真机仍无浮窗则按实际行为记录。

## 假绿灯修正结果（2026-09-27，round2）
- 管理者复审两处假绿灯已修：①三阶段（临时/正式/无关）都必须证明 pushState 返回的实际 pathname、后台 context.pageUrl 到达目标、revision 严格更新，然后才断言 ID 保持/切换；②浮窗读取前以目标路径切回锁定句柄并核实 chatgpt.com origin，无关阶段必须见到真实浮窗且正式阶段实际展示的两个 captureId 都退出当前展示（oursCurrent 纳入断言），浮窗缺失不再当"已消失"。
- 真机（冻结探针 a204ae0a…）：正式包 27/27 退出 0（temp rev 0→2 / formal rev 2→4 / unrelated rev 4→5，pageUrl 逐一到达，浮窗 formal 显示 navcheck、unrelated 显示等待）；旧 tracker 故障包身份通过后第 19 项 FAIL 退出 4；禁两次目标导航的探针副本（probe-no-navigation.py）身份通过后 FAIL 退出 4——round1 假绿灯（同条件 27/27）已消除。
- 工具回归 56 项（原 49 保留 + 导航回归扩到 7 项）；lint 0；对 f1f198e 与 99f982d 业务同源为空；正式 XPI/ZIP/build.json 未变。
- 覆盖边界不变：合成请求 + 未认证拒绝响应，不验证成功流式响应的会话身份与模型路由；真实账号流量未覆盖。
- 迭代 5 次全留证（review-fix-round2/attempt*）：根因是探针自身 JS 传参缺失与 pushState 在错误窗口执行，非业务缺陷。
