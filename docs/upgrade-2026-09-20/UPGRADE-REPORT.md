# 升级交付报告：Firefox Route Inspector v1.0.5 → v1.0.7

- 执行者：Agent（本次升级）；独立验收：管理者
- 日期：2026-09-20（**第二轮修订**：验证工具与交付证据修正，见 §9；**第三轮修订**：连接信任前置门禁与早期失败留证，见 §10）
- 工作目录：`D:\LAB\火狐浏览器插件制作2`
- 状态：**本地完成，未 push、未发 PR、未发布 Release、未提交 AMO、未替换日常 Firefox 扩展**（按交付范围约定）

## 1. 起点 / 目标 / 结果

| 项 | 值 |
| --- | --- |
| 起点（main，冻结不动） | `182fca1e8b6e7b4f73e5ae01f634d286209980f4` |
| 共同祖先 | `4f98a663c4fb111f582f6a4d1aaefd190a5d9b7a` |
| 目标 | `d5524a00d2721f1d022350a2589cac1dddccaaca`（`upstream/main`，解引用 == tag `v1.0.7`） |
| 工作分支 | `codex/sync-upstream-v1.0.7` |
| 开工记录提交 | `8affe8f`（PROGRESS 开工回执 + 分析） |
| 结果（合并提交） | `33f0879`（双亲 `8affe8f` + `d5524a0`） |
| 构建目录 | `dist/extension`、`dist/firefox`、`dist/e2e`（均为忽略目录） |
| 回退方法 | `git switch main`（main 未被触碰）；或 `git revert -m 1 33f0879` |

上游 `main` 未超前稳定版：`upstream/main` 即 v1.0.7 的发布提交，无“未纳入的已发布改动”。

## 2. 原来落后哪些重要更新

上游区间 `4f98a66..d5524a0` 共 **3 个提交**（`6a853eb` v1.0.6、`727568a` feat、`d5524a0` v1.0.7），**62 文件 +4950/−415**。
**依赖零变化**（`package-lock.json` 仅版本号 4 行），非业务文件仅版本号。

按源码核实（不凭文件名宣称修复）：

1. **采集生命周期重构**：新增 `core/capture-context.ts`，把 live（实时请求）与 reload（会话重载）拆成独立生命周期，
   引入文档级 `CaptureContext`（`documentId`/`visitStartedAt`/`revision`/`reloadEligible`/`invalidated` 墓碑）；
   `page-hook.ts`（+607 行）与 `bridge.ts`（+252 行）随之重写，新增 `route:context` 消息与握手。
   行为影响：切标签不必再提前切换；离开站点会退役显示上下文但保留历史。
2. **流式解析重写**：新增 `core/sse-decoder.ts`（220 行），支持 `delta` / `delta_encoding` v1 增量协议、通道继承、`add/replace/append/remove/truncate/patch` 操作与多层限额。
3. **额度采集**：新增 `core/usage-quota.ts`，从 `limits_progress` 投影 `deep_research` / `image_gen` 剩余额度与重置时间（`quotaObservedAt` 标注快照时间）。
4. **schema 1.4.0 → 1.7.0**：新增 `captureContextId` 与 4 个额度字段；verdict 新增 `auto_reasoning`；`routeModelSources` 新增 `assistant.metadata.model_slug`、`assistant[data-message-model-slug]`。
5. **判定规则**：`assessment.ts` 对 `gpt-5-6-auto-thinking` / `gpt-5-5-auto-thinking` 单列 `auto_reasoning`（非通用豁免，冲突字段仍走原路径）。
6. **端点识别**：新增 `conversation_init`（额度入口），并把带 `cursor/offset/before/after` 的历史分页排除出 `conversation_record`。
7. **存储层**：缓存 + 单调 `revision` + `clearedAt` 清空边界 + `captureContexts`；`storeObservation` 新增 stale 判定与失败计数只在真正失败时累加。
8. **1.0.7 升级公告**：新增 `ui/announcement/`（页面 + 脚本）、`background/upgrade-notice.ts`、`ui/shared/notice-hint.ts`（浮窗星标入口）、`shared/upgrade-notice.ts`；
   仅在 `onInstalled.reason==='update'` 且旧版本 < 1.0.7 时打开一次，标记键 `routeInspectorNotice107Shown` 独立于可清空历史。
9. **隐私**：导出时额外脱敏 `captureId`（改为 `capture-<序号>`）与 `captureContextId`。
10. **测试**：新增 11 个测试文件（bridge/page-hook/tab 生命周期、upgrade-notice、sse-decoder、usage-quota、capture-context、page-scope、state、notice-hint、audit-regressions 等）。

### 历史 `stream_parse_failed` 的核实结论（不沿用旧推断）

- 上游**未做定点修复**：`failed()` 分支仍不特判页面侧 abort（无 `AbortError`/`signal` 处理），catch 映射后仍落 `stream_parse_failed`。
- 但有真实相关增强：单事件 >1MB 改为具名 `stream_event_too_large`；新增「无 SSE 分隔符的拼接 data 行」回退解析；错误码新增 `record_too_large` / `http_*` / `unexpected_content_type` / `response_clone_failed`。
- **判定：保持未确认**（见 `BLOCKED.md` 第 4 项）。下次真实出现时，新错误码将比 1.0.5 更能定位原因。

## 3. 实际改了哪些文件及原因

### 3.1 随上游同步（来源 = `d5524a0`，共 62 个文件）
`src/**`、`schemas/route-turn.v1.schema.json`、`tests/**`、`manifest/manifest.json`（仅 version）、`package.json`（仅 version）、`package-lock.json`、`README.md`、`README-en.md`、`scripts/build.mjs`（`uiEntries` 加 `announcement`）。
**`git diff d5524a0 HEAD -- src schemas _locales icons` 为空 → 业务源码与上游逐字节一致，无 Firefox 专属业务分叉。**

### 3.2 本次新增（Firefox 专有，4 个）
| 文件 | 原因 |
| --- | --- |
| `scripts/verify-firefox-dist.mjs` | 产物完整性/同源校验脚本：路径集合双向比对、JS 逐字节一致、manifest+HTML 引用存在性、gecko 声明、announcement 资源。每次同步必跑，可复现 |
| `scripts/package-firefox.mjs` | 打包 `dist/firefox` → XPI 并输出 manifest/逐文件 sha256，供探针核对身份，杜绝误测旧包 |
| `tests/integration/firefox-upgrade-migration.test.ts` | 合成旧数据（schema 1.4.0，1.0.5 形态存储）→ schema 1.7.0 迁移验证；纯合成数据，不碰用户真实数据 |
| `docs/upgrade-2026-09-20/**` | 本次升级的交付报告、原始命令输出、红→绿证据、探针结果 |

### 3.3 本次修改（Firefox 专有 / 文档）
| 文件 | 原因 |
| --- | --- |
| `package.json` | 新增 `verify:firefox`、`package:firefox` 两个 script（与既有 `build:firefox` 对称） |
| `ff-marionette.py` | 参数化路径（原先写死旧 XPI/profile/端口/输出）；新增 XPI 内 manifest 哈希前置校验（不匹配退出码 2）；补充 v1.0.7 专项检查；结果结构改为 `{meta, results}` |
| `README-FIREFOX.md` | 同步基线、新命令、探针用法、FF156 必需启动参数、限制 |
| `AGENTS.md` | 仅更新事实：测试数 94→301、新增命令、当前状态 |
| `PROGRESS.md` / `BLOCKED.md` | 保留历史并追加本次记录 / 更新未决项 |

**未做**：无关重构、顺手修 bug、工具安装、自创依赖升级；未改全局 Git/网络/浏览器配置；未删用户文件或真实导出；旧 `ff-probe-results.json` 未覆盖。

## 4. 兼容性风险

| # | 风险 | 评估与处置 |
| --- | --- | --- |
| 1 | `build.mjs` 双向改动：上游加 `announcement` 入口、本地有 firefox target | **已自动合并为双侧保留**；`verify:firefox` 路径集合比对通过。下次同步的重点检查对象 |
| 2 | Firefox ≥156 禁止对扩展页执行 Marionette 脚本 | 本次实测发现；必须 `-remote-allow-system-access` 启动。**已写入 README**。该限制不影响扩展自身运行，只影响探针工具 |
| 3 | 新增 use of `chrome.runtime.getManifest`、`tabs.get/onUpdated/onRemoved` | Firefox 长期支持，无新权限，无需抬低下限。`getManifest?.()` 已做可选调用兜底 |
| 4 | `notice-hint` CSS 使用 `:has()` | Firefox 121+ 支持，**低于既有 `strict_min_version 128`**，不抬下限 |
| 5 | 旧存储迁移（1.4.0→1.7.0） | 合成数据实测通过；该测试断言的是 **`readState()` 在这条测试路径上不写存储**——不构成“整个升级过程或运行期间用户数据绝不改写”的普遍结论（存储写入由 `storeObservation` 等显式路径负责）。旧记录会被重算 verdict（含 auto_reasoning 重判），符合上游设计 |
| 6 | 权限/上网行为 | `permissions:["storage"]`、`host_permissions`、`content_scripts` 均未变；无新增扩展自身联网点；`data_collection_permissions {required:["none"]}` 仍真实成立，**未虚填** |
| 7 | `dist/extension` 与 `dist/firefox` 产物漂移 | 30 个文件路径集合一致、8 个 JS 逐字节一致、仅 manifest 不同；脚本每次强制校验 |
| 8 | 最低版本 128 未在本机实测 | 本机只有 Firefox 156。**不得宣称已在 128 验证通过**（BLOCKED 第 6 项） |

## 5. 各项测试结果（2026-09-20，冻结代码后重跑）

| 命令 | 升级前基线 | 升级后 | 退出码 |
| --- | --- | --- | --- |
| `npm run typecheck` | 通过 | 通过 | 0 |
| `npm run lint` | 通过 | 通过 | 0 |
| `npm test`（vitest + coverage） | 21 文件 / **94 passed** / 0 failed / 0 skipped | 33 文件 / **301 passed** / 0 failed / 0 skipped | 0 |
| `npm run build` | 通过 | 通过 | 0 |
| `npm run build:firefox` | 通过 | 通过 | 0 |
| `npm run build:e2e` | — | 通过 | 0 |
| `npm run verify:firefox` | — | `extension=30 firefox=30 identical=true`，OK | 0 |
| `npm run test:e2e` | — | **未执行：本机无 extension-capable Chromium** | 1（环境错误） |

- 覆盖率（升级后）：All files 97.19% stmts / 91.35% branch / 100% funcs（阈值 80/80/80/70 全过）。
- 测试数量 94 → 301，未删测试、未用 skip/todo、未放松断言、未修改阈值。

### 反向验证（红 → 绿）
在**仓库外**临时副本中移走 `ui/announcement/index.js`：

- 红：4 项失败 → `missing in firefox: ui/announcement/index.js`、`JS missing on firefox side`、`index.html references missing file index.js`、`announcement asset missing`，**退出码 1**。
- 绿：还原 → `OK`，**退出码 0**。
- 证据：`evidence/verify-dist-red.log`、`evidence/verify-dist-green.log`。正式源码与旧证据未受损伤。

### Firefox 真机实测（第一轮）
- 环境：**Firefox 156.0**（本机实测版本），headless，`-no-remote`，**全新专用临时 profile**，未触碰日常 profile，未发送真实 ChatGPT 消息。
- 被测产物：`chatgpt-route-inspector-firefox-1.0.7.xpi`
  - `manifest.json sha256 = c43c9104de4a6b00bbb9bb6317d88da4570113066c2235b4ceaed793f327d16a`
  - `xpi sha256 = 7c49d39d9fd35601a896aee23a8e7dbbe8d941340734858b0f9c9ca24b11e1e6`
  - 冻结后重构建的 `dist/firefox/manifest.json` 哈希与包内**一致** → 测的确实是本次构建（探针内置前置校验，不匹配即退出码 2）。
- 结果：**18/18 PASS**（第一轮 15 项 + 3 项判定拆分口径，逐项见结果文件）。覆盖：XPI 身份、加载零 manifest 错误、后台命名空间与 `await chrome.*`、Popup/诊断台渲染、
  合成观测经真实管线、chatgpt.com MAIN hook（`routeInspectorFetch`）、ISOLATED 浮窗、
  **1.0.7 公告浮窗入口**、**capture context 注册**、**`auto_reasoning` 判定**、**公告页渲染与外链**、**`route:open-announcement` 消息链路**。
- 结果文件：`docs/upgrade-2026-09-20/ff-probe-results-v1.0.7-2026-09-20.json`（含 date / commit `33f0879` / XPI 与 manifest 哈希 / Firefox 版本 / profile 路径）。
- **第一轮探针的已知不足**（第二轮已修，见 §9）：检查失败仍退出 0；身份只比对 manifest 哈希；`--out` 默认写死会覆盖旧结果；`meta.profile` 取自环境变量而非浏览器实测。
  上表 18/18 与本节其余结论据第一轮原始 JSON 仍然成立，但退出码与身份强度不得再引用第一轮工具的行为。

## 6. 是否建议现在使用新版

**建议：可以先在临时加载下自用，但不建议直接替换日常 Firefox 里的扩展。**

理由：
- 支持升级的：业务源码与上游 v1.0.7 逐字节同源；五项必需检查全绿；301 项测试通过；产物同源与完整性有脚本化证据；FF156 真机 22/22（含产物四级身份核对与四类反向验证）。
- 仍需用户补验的（不宜宣称“全部完成”）：
  1. **真实登录对话捕获**（历史未决项，需人工肉眼确认）；
  2. **真实 1.0.5→1.0.7 更新事件**——临时加载在 Firefox 中只会产生 `reason=install`，`onInstalled.reason==='update'` 路径**无法用临时加载验证**，需签名安装才能确认公告页恰好开一次；
  3. **Firefox 128 下限未实测**（本机仅 156）；
  4. `test:e2e` 未执行（缺 Chromium）；
  5. **额度字段（`deep_research` / `image_gen`）无真机专项检查**——真机探针项目里没有额度断言，只有上游单元/集成测试结论，**不得描述为“真机已走通”**（第一轮的该表述见 §9 勘误）。

## 7. BLOCKED.md 未决项

1. 真实登录对话捕获链路 —— 待人工
2. 长时控制台错误观察 —— 待人工
3. （历史）真实导出核验结论 —— 针对 1.0.5 的历史结论，保留
4. `phase=failed/stream_parse_failed` —— **本次复核后仍为未确认**（上游未定点修复）
5. **真实更新事件 1.0.5→1.0.7** —— 本次新增，未验证
6. **Firefox 128 下限** —— 本次新增，未验证
7. **`test:e2e`** —— 本次新增，缺环境未执行

8. **额度字段（`deep_research` / `image_gen`）无真机专项检查** —— 新增（见 §9.1 E1）

## 8. 证据索引

### 第一轮（原始，未改动；哈希见 §9.7）

| 路径 | 内容 |
| --- | --- |
| `evidence/cmd00-baseline-*.log` | 升级前基线五条命令输出 |
| `evidence/cmd01..cmd07-post-*.log` | 升级后 typecheck / lint / test / build / build:firefox / build:e2e / verify:firefox |
| `evidence/cmd08-post-test-e2e-NOTRUN.log` | `test:e2e` 环境错误原文（无 Chromium） |
| `evidence/verify-dist-red.log` / `-green.log` / `verify-dist.log` | 反向验证红→绿与正式校验 |
| `evidence/ff-probe-run-2026-09-20.log` | Firefox 真机探针逐项 PASS/FAIL 输出 |
| `ff-probe-results-v1.0.7-2026-09-20.json` | 真机结果（含 meta 元数据） |

### 第二轮（本轮新增，已脱敏）

| 路径 | 内容 |
| --- | --- |
| `evidence/r2-typecheck.log` … `r2-package-firefox.log` | 门禁命令逐个输出（typecheck / lint / test / build / build:firefox / build:e2e / verify:firefox / package:firefox） |
| `evidence/r2-tooling-tests.log` | `npm run test:firefox-tooling`（28 项验证工具回归测试） |
| `evidence/r2-tampered-fixture.log` | 篡改副本夹具生成记录（同 manifest、异 JS） |
| `evidence/r2-probe-positive.log` / `.json` | 正向真机：22/22、退出码 0 |
| `evidence/r2-probe-negative-badpage.{log,json}` | 反向：不存在的公告页 → 退出码 4 |
| `evidence/r2-probe-negative-tampered.{log,json}` | 反向：同 manifest 异 JS → 退出码 2（未连接浏览器） |
| `evidence/r2-probe-negative-browser-exits.{log,json}` | 反向：浏览器启动即退出 → 退出码 3 |
| `evidence/r2-probe-negative-startup-timeout.{log,json}` | 反向：启动超时 → 退出码 3 |
| `evidence/r2-probe-negative-existing-out.log` | 反向：`--out` 指向已有文件 → 退出码 6，原文件哈希不变 |
| `evidence/r2-probe-defaultout.{log,json}` | 省略 `--out`：生成新文件、不写历史结果 |

> 本报告是**执行者交付**，不代替管理者的独立验收。

### 第三轮（本轮新增，已脱敏）

| 路径 | 内容 |
| --- | --- |
| `evidence/r3-typecheck.log` / `r3-lint.log` / `r3-test.log` / `r3-tooling-tests.log` | 门禁逐个输出（业务 301 passed；工具 **48 passed**） |
| `evidence/r3-fixtures.log` | 损坏输入夹具的生成记录与各自 sha256 |
| `evidence/r3-probe-positive.{log,json}` | 真机正向：23/23、退出码 0（含会话 profile == 本次启动目录） |
| `evidence/r3-probe-untrusted-peer.{log,json}` | 真实进程 + 脚本化 peer 谎报 `moz:profile`：退出码 4，对端只收到 `WebDriver:NewSession` |
| `evidence/r3-probe-negative-badpage.{log,json}` | 反向：坏公告页 → 退出码 4 |
| `evidence/r3-probe-negative-broken-xpi.{log,json}` | 反向：XPI 非 ZIP → 退出码 2，留证 |
| `evidence/r3-probe-negative-no-manifest.{log,json}` | 反向：包内缺 `manifest.json` → 退出码 2，留证 |
| `evidence/r3-probe-negative-manifest-not-json.{log,json}` | 反向：包内 manifest 非法 JSON → 退出码 2，留证 |
| `evidence/r3-probe-negative-record-{missing,not-json,is-list,wrong-type}.{log,json}` | 反向：构建记录缺失 / 非法 JSON / 结构类型错误 → 退出码 2，留证 |
| `evidence/r3-probe-negative-unwritable-out.log` | 反向：输出目录不可写 → 退出码 3，未启动浏览器 |
| `evidence/r3-probe-negative-existing-out.log` | 反向：`--out` 指向已有文件 → 退出码 6，原文件不变 |

## 9. 第二轮修订：验证工具与交付证据修正（2026-09-20）

范围：**只修验证工具与交付证据**。未改 `src/`、`schemas/`、`_locales/`、`icons/`、`manifest/`、`scripts/build.mjs`、Firefox manifest 转换、`package-lock.json`、既有业务测试与覆盖率阈值。
冻结核对（开工与收尾各做一次）：`git diff d5524a0 HEAD -- src schemas _locales icons manifest` 为空；`HEAD:src=cd7a4860`、`HEAD:schemas=687e37b2`、`HEAD:_locales=bdeb3070`、`HEAD:icons=6d968481`、`HEAD:manifest=a45b9798`、`HEAD:scripts/build.mjs=5a508e8d`、`HEAD:tests=f0ea7108`；`main=182fca1e`（未触碰）。

### 9.1 勘误（第一轮的失实或过强表述）

| # | 第一轮表述 | 更正 |
| --- | --- | --- |
| E1 | “新增功能（公告、上下文生命周期、**额度**、auto_reasoning）均在真机走通” | **额度不成立**：真机探针项目里没有额度专项检查，只有上游单元/集成测试。已改为“额度未做真机专项验证”（BLOCKED 第 8 项） |
| E2 | “`readState()` 全程不写存储，**用户数据零改写**” | 收窄为：该合成迁移测试路径上 `readState()` 不写存储。不构成“整个升级过程或运行期间用户数据绝不改写”的普遍结论 |
| E3 | README 称冲突“**只会**出现在 `scripts/build.mjs` 与 `package.json`” | 无法保证，已删除；改为“可能出现在任何被双方同时修改的文件上” |
| E4 | 未说明 `verify:firefox` 的检查边界 | 已补：仅凭两 target 路径互比，无法发现“两边同时漏掉”的新增页面。本轮新增 `src/ui/**/index.html` 锚点检查把盲区收窄，但仍看不到“`uiEntries` 有条目而对应 HTML/TS 文件不存在”的情况 |
| E5 | 同步步骤把 `verify:firefox` 排在 `build:firefox` 之前 | 顺序改为先 `build` + `build:firefox`，再 `verify:firefox` |
| E6 | 第一轮探针的退出码/“身份通过”被当作可用结论 | 见 §9.2：第一轮工具的**逐项 PASS/FAIL 结果仍然有效**，但退出码与身份强度不可引用 |

### 9.2 第一轮工具的实际缺陷（管理者独立验收发现，本轮全部修正）

1. 检查失败、关键检查未执行、连接/运行异常时，进程**仍然退出 0**——成败只能靠人工在终端里搜 `FAIL`。
2. 身份只比对 XPI 内 `manifest.json` 的哈希：**同一 manifest 配不同 JS 的包照样“通过”**。
3. `--out` 默认写死 `ff-probe-results.json`：默认运行会**覆盖历史结果文件**。
4. `meta.profile` 取自环境变量 `FF_PROFILE`，属调用方自述，不是浏览器实测。

### 9.3 本轮改动

| 文件 | 改了什么 | 为什么 |
| --- | --- | --- |
| `ff-marionette.py` | 重构为“自启动浏览器 + 分级退出码 + 完整产物身份 + 输出保护” | 修正 9.2 的四项缺陷；恢复 `--expect-manifest-sha256` 之外的完整内容身份 |
| `scripts/package-firefox.mjs` | 打包后**回读压缩包**与 `dist/firefox` 逐文件比对，不一致则不写构建记录；记录新增 `createdAt` / `xpiEntriesVerified` / 重打包语义说明 | 让探针的“预期值”来源本身可信 |
| `scripts/verify-firefox-dist.mjs` | 新增 `src/ui/**/index.html` 锚点完整性检查；输出检查边界说明 | 收窄“两 target 同时漏页”的盲区，并如实声明残余边界 |
| `scripts/run-firefox-tooling-tests.mjs`（新） | 解析可用的 Python 3 解释器并运行工具回归测试 | 本机裸 `python` 是 WindowsApps 别名（退出 9009），不能当成“测试失败” |
| `tests/firefox-tooling/**`（新，6 文件） | 28 项回归测试 + 合成分发夹具（含假 Marionette 与篡改包生成器） | 让失败条件可复现，不依赖真实浏览器 |
| `package.json` | 新增 `test:firefox-tooling` 脚本 | 仅新增验证命令，未改依赖或版本 |
| `README-FIREFOX.md` / `AGENTS.md` / `PROGRESS.md` / `BLOCKED.md` | 同步流程、退出码、输出保护、检查边界、额度未验证、清理局限 | 让文档与实测一致 |
| `docs/upgrade-2026-09-20/**` | 本报告 + 本轮证据 | 交付物 |

**未做**：重同步上游、push、发布、签名、替换日常 Firefox 扩展、安装 Chromium/Firefox 128、发送真实账号消息、删除或改写任何历史证据、处理 `.workbuddy/`。

### 9.4 正向结果（冻结代码后重跑）

- 被测产物：`release/chatgpt-route-inspector-firefox-1.0.7.xpi`
  - `xpi sha256 = 2b3044146252c76e8816496e26e4a0d09b86090e592578df5c876a95e1933993`
  - `manifest.json sha256 = c43c9104de4a6b00bbb9bb6317d88da4570113066c2235b4ceaed793f327d16a`（与第一轮一致，内容未变）
  - 构建记录 `sha256 = 0208c1e2b7a8d1d7379992b5e93e917172243a7782ed47cbeb9f06be4e7dc1d1`
- 探针自身：`probeSha256 = f46f9d36e56409cdfa6aa303ab9c8f531dae4394224d248f3220cd1bc683615c`（六个结果 JSON 中的该值一致 → 确实跑的是同一份冻结代码）
- 环境：Firefox **156.0**，`moz:buildID=20260909172920`，headless；探针自建全新专用临时 profile；会话回报的 `moz:profile` 与本次启动的临时目录**完全相同**（检查 `0e.session-profile` PASS）；运行结束后无遗留探针 profile、无残留进程。
- 结果：**22 项全部执行、22 PASS、0 FAIL、0 缺失 → 退出码 0**。
  四类身份检查同时通过：`0a` XPI 整体哈希、`0b` XPI 与 `dist/firefox` 逐文件一致（30 文件）、`0c` `dist` 与构建记录一致（30 文件）、`0d` manifest 哈希（与记录一致）。
- 证据：`evidence/r2-probe-positive.log` / `.json`；省略 `--out` 的同内容复跑见 `r2-probe-defaultout.*`（同样 22/22、退出码 0）。

### 9.5 反向验证（同一轮实测，逐项退出码）

| 场景 | 关键参数 | 期望 | 实测退出码 | 观察到的失败项 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 不存在的公告页 | `--announcement-ui ui/announcement/missing-manager-test.html` | 非零 | **4** | `14.announcement-page`（`{'title':'页面加载出错','text':'','script':False,'href':None}`） | `r2-probe-negative-badpage.*` |
| 同 manifest 异 JS | 临时副本（仅改 `content/page-hook.js`） | 非零且**不连接浏览器** | **2** | `0a/0b/0c`；`0d.manifest-sha256` **PASS**（证明只比 manifest 会放过它） | `r2-probe-negative-tampered.*`、`r2-tampered-fixture.log` |
| 浏览器启动即退出 | `--firefox C:\Windows\System32\where.exe` | 非零 | **3** | `FATAL RuntimeError: Firefox exited during startup`，18 项未执行 | `r2-probe-negative-browser-exits.*` |
| 启动超时 | `--startup-timeout 0.05` | 非零 | **3** | `FATAL TimeoutError`，18 项未执行，结果文件仍写出 | `r2-probe-negative-startup-timeout.*` |
| 已有输出文件 | `--out` 指向 `r2-probe-positive.json` | 非零且文件不变 | **6** | 拒绝覆盖 | `r2-probe-negative-existing-out.log` |
| 省略 `--out` | 不给 `--out` | 生成新文件、不写历史 | **0** | — | `r2-probe-defaultout.*` |

反向用例的三项关键性质均已实测：
- “身份被拒”发生在**连接/卸载/安装之前**——该用例的 `--firefox` 指向不存在路径，若探针尝试启动会变成退出码 3，实测为 2，且结果 JSON 里 `launch` 为 `null`、`notes` 记录“identity rejected; browser was not launched”；
- 篡改包场景里 `0d`（manifest 哈希）仍 PASS，只有完整内容身份拦住它；
- 拒绝覆盖后 `r2-probe-positive.json` 的 sha256 前后均为 `7305521b062f474d4ca2737b91e940ee805e5326765b6463391174f0a5d9d8f3`（脱敏后为 `1c634965…`），字节未变。

### 9.6 独立回归测试（不依赖真实浏览器）

`npm run test:firefox-tooling` → **28 passed，退出码 0**（`evidence/r2-tooling-tests.log`）。覆盖任务要求的四类失败条件，且断言的是探针自身的判断而非恒定返回值：

- 检查失败退出非零：伪造一项检查失败 → 退出码 4，且失败项被写进结果 JSON 的 `summary.failedChecks` 与 `exitReason`；
- 运行异常留证：启动超时 / 连接被拒 / 单组检查内协议异常 → 退出码 3 或 4，`meta.fatal` 或 `failedChecks` 有记录，后续检查仍继续执行；
- 同 manifest 不同 JS 拒绝：合成 XPI 夹具，断言 `0a/0b/0c` 失败、`main()` 返回 2，并用“若调用启动函数即抛断言异常”的方式证明**没有启动浏览器**；
- 历史输出不覆盖：已有 `--out` → 退出码 6 且字节不变；省略 `--out` → 生成带时间戳的新文件，并断言仓库历史 `ff-probe-results.json` 的 sha256 前后一致。
- 另有退出码聚合矩阵、默认输出路径不碰撞、XPI 多余文件/缺文件、构建记录与 dist 不符等用例。

浏览器侧用进程内可编程假实现（`tests/firefox-tooling/fake_marionette.py`）替代，只压缩了墙钟等待（`time.sleep`），未改任何控制流或断言。真实浏览器路径另由 §9.4/§9.5 覆盖。

### 9.7 证据保护与脱敏

- 历史证据**逐个哈希核对，全部未变**：`ff-probe-results.json = 4bec56b9…`、`ff-probe-results-v1.0.7-2026-09-20.json = 3da8fab7…`、`evidence/` 下第一轮 17 个 `.log` 与本轮开工前记录逐一相同。
- 本轮证据按“审查 → 脱敏 → 精确路径纳入版本控制”处理：脱敏规则为把本机 Windows 账户名 `gyjxjkg` 替换为 `<user>`（仅出现于绝对路径），脱敏前原件留在仓库外临时目录以备核对。脱敏后逐文件 `sha256` 见 §9.9。
- 审查结论：对全部证据文件（含被 `.gitignore` 忽略的 `.log`）做了凭据类模式扫描（`sk-` / `Bearer` / `password=` / `api_key=` / `session_token` / `refresh_token` / `authorization:` / JWT / `@gmail|qq|163|outlook|hotmail` / 真实会话 URL），**无任何命中**；未包含真实账号会话、Cookie、令牌或导出附件。
- **残留（需管理者决定）**：`docs/upgrade-2026-09-20/ff-probe-results-v1.0.7-2026-09-20.json` 属于第一轮冻结证据，含 2 处同一类绝对路径（账户名），按“不得修改历史证据”的要求**未做脱敏**。
- 提交方式：`.gitignore` 的全局 `*.log` 规则不改（不扩大日志跟踪范围），改用**精确路径** `git add -f` 逐个添加已审查的日志；未对目录做 `git add -f`。
- 第一轮遗留问题一并修正：第一轮那 17 个 `evidence/*.log` 当时**根本没有进入版本控制**（被全局 `*.log` 规则忽略，只在工作区），与本轮日志在同一个跟进提交里按精确路径补入。
- 未跟踪的 `.workbuddy/` 未被处理、未被提交、未被删除，其存在已在 §9.8 明确列出。
- 哈希口径：§9.9 列出的是**工作区文件**的 sha256。仓库 `core.autocrlf=true`，新克隆检出的行尾可能变为 CRLF，届时 sha256 会不同；可用 `git rev-parse HEAD:<路径>` 核对提交内容本身。

### 9.8 最终 Git 状态

分支 `codex/sync-upstream-v1.0.7`，起点 `HEAD = 7dd7a86`，`main = 182fca1e`（未动）。本轮**未 push、未发布**。

提交：本报告与工具修正为 `f55c1ed`（38 文件，+3738/−246）；其后一个跟进提交把第一轮 17 个 `evidence/*.log` 按精确路径补入版本控制。收尾时的 `git status --porcelain -uall` 只剩两条未跟踪项（`.workbuddy/memory/2026-09-20.md`、`.workbuddy/memory/MEMORY.md`）——即**已跟踪文件干净，仍有未知未跟踪文件**，不写“工作树干净”。

修改（已跟踪）：`AGENTS.md`、`BLOCKED.md`、`PROGRESS.md`、`README-FIREFOX.md`、`docs/upgrade-2026-09-20/UPGRADE-REPORT.md`、`ff-marionette.py`、`package.json`、`scripts/package-firefox.mjs`、`scripts/verify-firefox-dist.mjs`。
新增（未跟踪 → 已纳入本次提交）：`scripts/run-firefox-tooling-tests.mjs`、`tests/firefox-tooling/{probe_loader.py, fake_marionette.py, make_tampered_copy.py, test_ff_marionette_identity.py, test_ff_marionette_run.py}`、`docs/upgrade-2026-09-20/evidence/r2-*`。
**仍然未跟踪且未处理**：`.workbuddy/memory/2026-09-20.md`、`.workbuddy/memory/MEMORY.md`（未知目录的 Agent 记忆，按约定不处理）。

### 9.9 本轮证据哈希（脱敏后）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `evidence/r2-typecheck.log` | 63 | `22c70c07ca223b374d93d40d32c4a490417c641dd2b473fac761fcd89a4a0e9c` |
| `evidence/r2-lint.log` | 54 | `f90f3abc0a909d5686824cbc267002d41d6ed375f34fe259ed3d4f2972f67e94` |
| `evidence/r2-test.log` | 6591 | `aba067beb5b3b0a010d7eb8f901b5ccfe32115d13f156c2e6d85ecbc6b7b9c06` |
| `evidence/r2-build.log` | 820 | `a021d384016aa9e99aaca5b6eabbf181eb122930526d1778d88cbbbce5653732` |
| `evidence/r2-build-firefox.log` | 820 | `13113fa8a86fcecaaf731f909d1c5ef9cd1ad5697fd6ebdb321f3e6743f1fcb7` |
| `evidence/r2-build-e2e.log` | 779 | `b8184b4b834d63562944c971842634e2b0accce0daf1222fd86e9a474a599acd` |
| `evidence/r2-verify-firefox.log` | 413 | `f62909307c86b93946fbdff77ce13d7c6d21bf0700ed9d644610dc34f6a3a569` |
| `evidence/r2-package-firefox.log` | 507 | `00c363b2601f9c17dd20ab782bbea1011f2198ecbd9651567c43f356fb130ef6` |
| `evidence/r2-tooling-tests.log` | 32132 | `690be2e86dc3ef07bf522dad5d1f63b77b59578c4600a7dbdc18d9a3336b713d` |
| `evidence/r2-tampered-fixture.log` | 495 | `01f4ae77d7b4acd7e83c5e0b3c1521f7c9adb06ef76bf276f8921132bb8d1d6a` |
| `evidence/r2-probe-positive.log` | 4126 | `a4ec598841c2a907dc70ee53d84d3e6aed025d320af07e31c4bd1cc41c48df8f` |
| `evidence/r2-probe-positive.json` | 10161 | `1c634965bd3ce391c89278f68f8b82a2f1dfa717c01ecfb2b22645ba5ea5431e` |
| `evidence/r2-probe-defaultout.log` | 4158 | `2e25cd1ecdbfba5235a1019381298a4db1c178240e76ef1e600b26ec3e17bd29` |
| `evidence/r2-probe-defaultout.json` | 10510 | `28fe7dff7902a430cc54c8c6de5dc4ac6fc6787f362c807a4f59cb3d2ad808a6` |
| `evidence/r2-probe-negative-badpage.log` | 3773 | `6bdadfc92f8c4b375374c64fd5f37d3a83096df244b933c54990f119d0303232` |
| `evidence/r2-probe-negative-badpage.json` | 9361 | `ac8bbcc7ec03f4af6f28e4ede2f564f6ceef6025e7a5c8570c4b5d7f26eb7c7e` |
| `evidence/r2-probe-negative-tampered.log` | 906 | `6b317bc573ef73f21129b3fad17d07d186778f8811f1bee58c8393ab47d85a66` |
| `evidence/r2-probe-negative-tampered.json` | 5246 | `e603713de47f9916967e790ac5a58b1bd9da5083867f25b99843f101430c2360` |
| `evidence/r2-probe-negative-browser-exits.log` | 883 | `81e9f4a59e97526e6099d8b34b5d671c85a6c686e23169ee19e46aa96c67579f` |
| `evidence/r2-probe-negative-browser-exits.json` | 5654 | `489ddc02036f96f0b5d02610fa4fc92549bff1563f1adc00cca8063975f6b7ca` |
| `evidence/r2-probe-negative-startup-timeout.log` | 967 | `9c6fb65f3061beb0fad0659844b2615eae54cb4d0c6d81526c67ea48dfd6dac6` |
| `evidence/r2-probe-negative-startup-timeout.json` | 5842 | `647895cefee7f1132f39d5d2b5b2a0158c03d1364ed50e4c406982b7941b3c88` |
| `evidence/r2-probe-negative-existing-out.log` | 450 | `6148caef20d7ca46d3eb318050a7276b573520cdc563cf418f233dbfb3914ae8` |

### 9.10 本轮结束时的实际观测（不代表管理者验收）

- 本轮结论：验证工具的第一轮缺陷已修正，四类失败条件与输出保护均有实测失败证据与非零退出；文档与实测一致。
- **本轮不声称全部升级场景已验证**，也不声称已获管理者验收；额度真机、真实登录对话、真实更新事件、Firefox 128 下限、`test:e2e` 仍为未验证项（BLOCKED 第 1/2/4/5/6/7/8 项）。

## 10. 第三轮修订：连接信任前置门禁与早期失败留证（2026-09-20）

范围：**只修管理者第二轮指出的两处遗漏**。未改业务源码、`manifest/`、构建与打包脚本、依赖、版本、`package.json` 脚本、既有业务测试与覆盖率阈值。
冻结核对（开工与收尾各一次）：`git diff d5524a0 HEAD -- src schemas _locales icons manifest` 为空；`HEAD:src=cd7a4860`、`HEAD:scripts/build.mjs=5a508e8d`；`main=182fca1e`（未动）；`ff-marionette.py` 在本轮所有证据生成前后均为 `9e04541c33f52fc5b1100586c042776f0b9d7e0111cc4ce0cb2cffc7e2f243c9`（每份结果 JSON 的 `meta.probeSha256` 与之一致）。

### 10.1 两处遗漏与修法

| # | 第二轮实测遗漏 | 修法 |
| --- | --- | --- |
| D1 | 给探针一个模拟连接、其回报的 `moz:profile` 与本次创建目录不符时，`0e.session-profile=False` 但仍继续调用 `Addon:Uninstall` + `Addon:Install`（含全部后续检查） | 把该检查升级为**操作前置条件**：核验通过前只发 `WebDriver:NewSession`（身份由它返回），核验不过则记 `0e.session-profile`+`0f.untrusted-connection` 失败、**立即停止**、只关自己的 socket、**不发 `DeleteSession`**、仍停止本次进程并删本次 profile，按码 4 退出。用户代理串的读取也从 `main` 移到门禁之后 |
| D2 | 内容为 “broken zip” 的 XPI 让 `verify_identity` 抛 `zipfile.BadZipFile`：退出 1、无 traceback 之外的记录、指定结果 JSON 未生成 | `verify_identity` 改为**永不抛出**（解析失败 → `0b/0c/0d` 记失败 + `identity.parseError`，`0a` 仍按文件哈希判定）；`main` 把“读构建记录 → 解析 XPI → 身份 → 启动 → 连接 → 检查”全部纳入统一收口，任何异常都落到 `meta.fatal` / `meta.stage` 并写出结果；构建记录改为显式校验（存在性 / JSON / 字段类型），失败即身份不成立（码 2） |

附带：新增输出可写性前置检查（输出目录不可创建/不可写时**在启动浏览器之前**报错并以码 3 退出，不创建也不改动任何文件）；`--out` 指向已存在目录时给出明确 stderr 并同样拒绝（码 6）。

**本轮自发现并修掉的第三个问题（D3，由执行者自查，非管理者指出）**：可写性检查最初实现为“在目标目录写一个零字节探针文件再删掉”，实践中有 11 个 `.ff-probe-write-probe-<pid>` 零字节文件残留在证据目录里（`git status` 发现）。根因未完全定位（同一代码在单次运行与单测中均能正确删除，疑似与并发/杀软有关），因此**没有去调那个探针，而是把它整个删除**：现在的检查只做「父目录可建/是目录/可写 + 目标不是已存在目录」的只读判断，运行期间不会在输出目录创建任何额外文件。新增两项回归测试断言“运行结束后输出目录里除结果文件外没有别的条目”（含真实浏览器路径），已通过。

### 10.2 改动文件

`ff-marionette.py`（门禁 + 统一收口 + 记录校验 + 只读的输出可写前置检查 + `stage`/`reachedStages`/`browserLaunched`/`browserConnected`/`connectionTrusted`/`aborted` 记录）；
`tests/firefox-tooling/`：新增 `fake_peer.py`、`test_ff_marionette_gate.py`、`test_ff_marionette_early_failure.py`，扩展 `fake_marionette.py`（`profile_mode` 支持 match/mismatch/missing/raise）、`probe_loader.py`（真实进程运行助手）；
`README-FIREFOX.md`、`AGENTS.md`、`PROGRESS.md`、`BLOCKED.md`、本报告；`docs/upgrade-2026-09-20/evidence/r3-*`。

### 10.3 回归测试（先红后绿）

新增 21 项，工具测试总数 **28 → 49**，全部通过（`evidence/r3-tooling-tests.log`，`Ran 49 tests` / `OK`；仅“真实进程对脚本化 peer”“真实浏览器”两项会在缺 Firefox 时跳过，本机未跳过）：

- **门禁（进程内假连接，断言的是探针真实发出的调用列表）**：`moz:profile` 不一致 / 缺失 / 检查抛异常三种情形下，`fake.calls` 只含 `WebDriver:NewSession`，且 `Addon:*`、`WebDriver:ExecuteScript`、`WebDriver:Navigate`、`WebDriver:NewWindow`、`WebDriver:DeleteSession` 全部为零；退出码 4；`connectionTrusted=false`；结果里 `1.install-no-manifest-error` 属于 `missingChecks`；进程被停止、临时 profile 被删除。另有 `match` 情形反向确认门禁不会误伤（仍会 `Addon:Install` 与 `DeleteSession`）。
- **门禁（真实进程 + 真实 socket）**：`fake_peer.py` 占用探针端口并谎报 `moz:profile`，用真实 `ff-marionette.py` 进程跑一次，断言对端收到的命令**只有** `WebDriver:NewSession`。
- **早期失败（真实进程）**：非 ZIP、包内缺 `manifest.json`、包内 manifest 非法 JSON、构建记录缺失 / 非法 JSON / 是 JSON 数组 / 字段类型错误 → 均退出码 2、结果 JSON 存在且可解析、`browserLaunched=false`、`launch=null`，且 stderr 不含 traceback。
- **输出路径**：父路径是文件 → 退出码 3 + stderr，不创建/不改动任何文件；输出指向已存在目录 → 码 6 且目录保持为空；参数错误 → 码 64；已有 `--out` → 码 6 且原字节不变；运行结束后输出目录里除结果文件外没有别的条目（含真实浏览器路径）。
- 原有的 28 项（身份拒绝、输出保护、退出码聚合、运行异常留证等）全部保留，未删减、未跳过、未放松。

### 10.4 真机与命令行实测（本次核验过的产物）

被测产物：`release/chatgpt-route-inspector-firefox-1.0.7.xpi`
`xpi sha256=2b3044146252c76e8816496e26e4a0d09b86090e592578df5c876a95e1933993`、
manifest `c43c9104de4a6b00bbb9bb6317d88da4570113066c2235b4ceaed793f327d16a`、构建记录 `0208c1e2…d1d1`。
环境：Firefox **156.0**，`moz:buildID=20260909172920`，headless；探针自建专用临时 profile，结束后无残留 profile、无残留进程。

| 场景 | 期望 | 实测退出码 | 结果文件 | 证据 |
| --- | --- | --- | --- | --- |
| 正向完整通过 | 0 | **0** | 23/23 全通过，`moz:profile` == 本次启动目录 | `r3-probe-positive.{log,json}` |
| 坏公告页 | 非零、有结果 | **4** | 22 passed / `14.announcement-page` failed | `r3-probe-negative-badpage.*` |
| 坏公告页（同命令第一次，站点慢） | 非零、有结果 | 5 | `9/10` timed out、`11` 未执行 → 探针如实报 FAIL，未静默通过 | `r3-probe-negative-badpage-attempt1-navtimeout.*` |
| XPI 非 ZIP | 非零、有结果 | **2** | stage=identity，`parseError=BadZipFile`，未启动浏览器 | `r3-probe-negative-broken-xpi.*` |
| 包内缺 manifest | 非零、有结果 | **2** | 同上，`parseError` 含 `no manifest.json` | `r3-probe-negative-no-manifest.*` |
| 包内 manifest 非法 JSON | 非零、有结果 | **2** | 同上，`parseError` 含 `JSONDecodeError` | `r3-probe-negative-manifest-not-json.*` |
| 构建记录缺失 | 非零、有结果 | **2** | `0f.build-record` failed，未启动浏览器 | `r3-probe-negative-record-missing.*` |
| 构建记录非法 JSON | 非零、有结果 | **2** | 同上 | `r3-probe-negative-record-not-json.*` |
| 构建记录是 JSON 数组 | 非零、有结果 | **2** | `expected an object` | `r3-probe-negative-record-is-list.*` |
| 构建记录字段类型错误 | 非零、有结果 | **2** | `field fileHashes has type list, expected dict` | `r3-probe-negative-record-wrong-type.*` |
| 对端谎报 `moz:profile`（真实进程 + 脚本化 peer） | 非零、留证、**危险调用为零** | **4** | 对端收到的命令 = `["WebDriver:NewSession"]`，`connectionTrusted=false`，`notes` 记录“session 未被删除” | `r3-probe-untrusted-peer.{log,json}` |
| 输出目录不可写 | 非零、明确 stderr | **3** | 启动浏览器之前退出，`blocker.txt` 哈希与内容不变 | `r3-probe-negative-unwritable-out.log` |
| `--out` 指向已有文件 | 6、原文件不变 | **6** | `r3-probe-positive.json` 未被改动 | `r3-probe-negative-existing-out.log` |

> 站点慢导致的 `5` 已单独记为 BLOCKED 第 11 项已知抖动：探针**不重试、不静默通过**，判定以完整正向运行（`r3-probe-positive`）为准。

**对端收到的命令列表（D1 的关键证据，取自 `r3-probe-untrusted-peer.log`）**
`peer lie: moz:profile = C:\Users\<user>\AppData\Local\Temp\ff-ri-probe-NOT-THIS-RUN`
`commands the peer received: ["WebDriver:NewSession"]`
`browserLaunched=True browserConnected=True connectionTrusted=False`
`notes=["session was not deleted: this connection was never verified as the browser this run created"]`
该用例里 `0e.session-profile` / `0f.untrusted-connection` 记失败，`1.install-no-manifest-error` 等 16 项未执行（`missingChecks`），退出码 4。

### 10.5 门禁复跑（逐个退出码）

`typecheck 0` / `lint 0` / `npm test 0`（33 文件 **301 passed**，覆盖率 97.19% stmts / 91.34% branch / 100% funcs，阈值未动）/ `test:firefox-tooling 0`（**49 passed**）。业务与构建路径冻结且无相关变动，故本轮未重复跑三种构建与缺环境的 E2E（沿用第二轮的构建结论），`build:e2e` 环境限制仍记于 BLOCKED 第 7 项。

### 10.6 历史证据与未知文件

- 历史证据未变：`ff-probe-results.json=4bec56b9…`、`ff-probe-results-v1.0.7-2026-09-20.json=3da8fab7…`，第一、二轮 `evidence/*.log|json` 未被覆盖（本轮只新增 `r3-*`）。
- 本轮证据同样做了凭据类模式扫描（无命中）与脱敏（本机账户名 → `<user>`），按精确路径提交，未改 `.gitignore`。
- D3 相关：本轮由执行者自己发现并删除了 **11 个零字节 `.ff-probe-write-probe-<pid>` 文件**——它们是本轮新增的可写性探针在证据目录里留下的**自产痕迹**（不是用户的未知文件，也不是历史证据）；修复后同一测试与全部重跑均不再产生此类文件，并有回归测试守住。
- 本轮**未使用 `--force`** 绕过历史保护，也未清理任何未知文件；`.workbuddy/` 未处理、未提交、未删除。
- 限制（新增 BLOCKED 第 10、11 项）：真实 Firefox 会如实回报自己的 profile，**“连接不可信”无法在真机自然产生**，只能由脚本化对端复现；真机探针受 `chatgpt.com` 响应速度影响，站点慢时 `9/10` 会超时并退出 5（不重试、不静默通过）。

### 10.7 本轮证据哈希（脱敏后）

| 文件 | 字节 | sha256 |
| --- | --- | --- |
| `evidence/r3-typecheck.log` | 63 | `22c70c07ca223b374d93d40d32c4a490417c641dd2b473fac761fcd89a4a0e9c` |
| `evidence/r3-lint.log` | 54 | `f90f3abc0a909d5686824cbc267002d41d6ed375f34fe259ed3d4f2972f67e94` |
| `evidence/r3-test.log` | 6331 | `d527e80e4555058321603ccbbf8d298c691be308b9c6d67b628ae84b25ea58c1` |
| `evidence/r3-tooling-tests.log` | 44819 | `8593ca0959320e979c33b9d50079fdb70a2051827b9fa0a03df28648d10c56e4` |
| `evidence/r3-fixtures.log` | 833 | `28e82e7d59b6c7edc00c4187ab8bf0308bdceead5a39fcc43766ffde8b8b1388` |
| `evidence/r3-probe-positive.log` | 4180 | `68c61ab171f662161bf796605eb1d6d4ce687454070c1449a71e6f96510dbc28` |
| `evidence/r3-probe-positive.json` | 10750 | `d5fd0c7b9b1bb4d6bf53942bb5c7c92a0219891301c7791a759b40efb81a0eb3` |
| `evidence/r3-probe-untrusted-peer.log` | 2013 | `11caf0a8e2d2c76dba2ade9d0d5b29245eb1f2bdf54402949b96ac2a098c68f9` |
| `evidence/r3-probe-untrusted-peer.json` | 7852 | `b36bba62f11fbb905cdc0db4edf62fdc1066d689370950579e72541db8613dec` |
| `evidence/r3-probe-negative-badpage.log` | 3827 | `d29ee7faf0b17b8847e8cd180b37e72877abd301d059b03a9325f9f564ab2c11` |
| `evidence/r3-probe-negative-badpage.json` | 10637 | `bc43e746a09bd8d30cc58c798984368ab8e9025bc206fc54c8d30d124d37e4a2` |
| `evidence/r3-probe-negative-badpage-attempt1-navtimeout.log` | 3362 | `343d5a6870437275c135b37db4671e08bfcc7f1a382489c047aef10862ce6f4d` |
| `evidence/r3-probe-negative-badpage-attempt1-navtimeout.json` | 9582 | `e84b5ba3672f1e7c5ce3a9b48203bcf003c641a913faf705ecec745e5fb7ffca` |
| `evidence/r3-probe-negative-broken-xpi.log` | 673 | `a991abd0899c7de72843267b5af3a593b38e9b4db4eed105c39a99d682d32552` |
| `evidence/r3-probe-negative-broken-xpi.json` | 5509 | `65bf729c6909d2cf5ed53d9cfcfaa1c4d4d5de2d48cde7b9facd4b332c1ab23d` |
| `evidence/r3-probe-negative-no-manifest.log` | 740 | `645e288e28f842fabfd3c74c5773f32c3cb1dfbafad7e3e2c4748ce91d1d4ead` |
| `evidence/r3-probe-negative-no-manifest.json` | 5675 | `e426588c7f030f4ad085e83e69f1cbefaf617b7f2c447026d443e469d438611d` |
| `evidence/r3-probe-negative-manifest-not-json.log` | 854 | `d574d01b5c83c75d88c659a0d528b6478e43581deae2e909e53dd0ded47f0b50` |
| `evidence/r3-probe-negative-manifest-not-json.json` | 5909 | `a8c03a59d13b0b061a00160bfc9d42cf09962b53d1ba73eca5deccee56ab9698` |
| `evidence/r3-probe-negative-record-missing.log` | 671 | `c8543625f065ef2b6118149ad87ee2ae202313cd0812fd0e4ab955a32d2e3419` |
| `evidence/r3-probe-negative-record-missing.json` | 5579 | `c4975191b49af968a0566a6fcb6991bfa511fecde05b8de6424febfee4eed096` |
| `evidence/r3-probe-negative-record-not-json.log` | 698 | `cdea5e65dbc5c2722a48103c70951eb472c8867c4f6b202c17848fa1be9f7292` |
| `evidence/r3-probe-negative-record-not-json.json` | 5682 | `b0d5ff0eada74e1c29b45569bd4daa67048fa77a34d0323138138158564668e3` |
| `evidence/r3-probe-negative-record-is-list.log` | 616 | `406d54c51c26300833637a2db52787d934aa535e01a4a340458db4580e4e5721` |
| `evidence/r3-probe-negative-record-is-list.json` | 5592 | `06ef16017f840b0ab2e542c0c3e596468d8844df00ff060ba9d4bffef6cac747` |
| `evidence/r3-probe-negative-record-wrong-type.log` | 630 | `4a1d982cad8899b38df5a8fb5d12036cb5dfeef70c6528fe7ccb58482453e017` |
| `evidence/r3-probe-negative-record-wrong-type.json` | 5701 | `8dcd203ab3f161ec162926ea2ebba6c475fd01a9707d5be98e93700d6470c9a9` |
| `evidence/r3-probe-negative-unwritable-out.log` | 680 | `ecdbab0362d3f2d39353a83d6e8f08b61325ca6a9ef32de48678e327a2fcc91b` |
| `evidence/r3-probe-negative-existing-out.log` | 477 | `5c20a06a9dd3abc977ae55c3aaefc5a708c6574e6f57ecd1c1302609deb7ea70` |

> 哈希口径同 §9.7：工作区文件哈希；`core.autocrlf=true`，核对提交内容用 `git rev-parse HEAD:<路径>`。

### 10.8 本轮结束时的实际观测（不代表管理者验收）

- 连接不可信时**状态修改协议调用为零**已有两类证据（进程内调用列表 + 真实进程对脚本化 peer 的 wire 记录）；损坏输入全部在启动浏览器前以码 2 失败并留下有效 JSON；正常真机与既有反向验证未退化。
- 本轮**只说明这两处遗漏的修复**；额度真机、真实登录对话、真实更新事件、FF128 下限、`test:e2e` 仍未验证，也不声称已获管理者验收。
