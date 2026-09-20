# 升级交付报告：Firefox Route Inspector v1.0.5 → v1.0.7

- 执行者：Agent（本次升级）；独立验收：管理者
- 日期：2026-09-20
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
| 5 | 旧存储迁移（1.4.0→1.7.0） | 合成数据实测通过；`readState()` 全程**不写存储**，用户数据零改写。旧记录会被重算 verdict（含 auto_reasoning 重判），符合上游设计 |
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

### Firefox 真机实测
- 环境：**Firefox 156.0**（本机实测版本），headless，`-no-remote`，**全新专用临时 profile**，未触碰日常 profile，未发送真实 ChatGPT 消息。
- 被测产物：`chatgpt-route-inspector-firefox-1.0.7.xpi`
  - `manifest.json sha256 = c43c9104de4a6b00bbb9bb6317d88da4570113066c2235b4ceaed793f327d16a`
  - `xpi sha256 = 7c49d39d9fd35601a896aee23a8e7dbbe8d941340734858b0f9c9ca24b11e1e6`
  - 冻结后重构建的 `dist/firefox/manifest.json` 哈希与包内**一致** → 测的确实是本次构建（探针内置前置校验，不匹配即退出码 2）。
- 结果：**18/18 PASS**。覆盖：XPI 身份、加载零 manifest 错误、后台命名空间与 `await chrome.*`、Popup/诊断台渲染、
  合成观测经真实管线、chatgpt.com MAIN hook（`routeInspectorFetch`）、ISOLATED 浮窗、
  **1.0.7 公告浮窗入口**、**capture context 注册**、**`auto_reasoning` 判定**、**公告页渲染与外链**、**`route:open-announcement` 消息链路**。
- 结果文件：`docs/upgrade-2026-09-20/ff-probe-results-v1.0.7-2026-09-20.json`（含 date / commit `33f0879` / XPI 与 manifest 哈希 / Firefox 版本 / profile 路径）。

## 6. 是否建议现在使用新版

**建议：可以先在临时加载下自用，但不建议直接替换日常 Firefox 里的扩展。**

理由：
- 支持升级的：业务源码与上游 v1.0.7 逐字节同源；五项必需检查全绿；301 项测试通过；产物同源与完整性有脚本化证据；FF156 真机 18/18，新增功能（公告、上下文生命周期、额度、auto_reasoning）均在真机走通。
- 仍需用户补验的（不宜宣称“全部完成”）：
  1. **真实登录对话捕获**（历史未决项，需人工肉眼确认）；
  2. **真实 1.0.5→1.0.7 更新事件**——临时加载在 Firefox 中只会产生 `reason=install`，`onInstalled.reason==='update'` 路径**无法用临时加载验证**，需签名安装才能确认公告页恰好开一次；
  3. **Firefox 128 下限未实测**（本机仅 156）；
  4. `test:e2e` 未执行（缺 Chromium）。

## 7. BLOCKED.md 未决项

1. 真实登录对话捕获链路 —— 待人工
2. 长时控制台错误观察 —— 待人工
3. （历史）真实导出核验结论 —— 针对 1.0.5 的历史结论，保留
4. `phase=failed/stream_parse_failed` —— **本次复核后仍为未确认**（上游未定点修复）
5. **真实更新事件 1.0.5→1.0.7** —— 本次新增，未验证
6. **Firefox 128 下限** —— 本次新增，未验证
7. **`test:e2e`** —— 本次新增，缺环境未执行

## 8. 证据索引

| 路径 | 内容 |
| --- | --- |
| `evidence/cmd00-baseline-*.log` | 升级前基线五条命令输出 |
| `evidence/cmd01..cmd07-post-*.log` | 升级后 typecheck / lint / test / build / build:firefox / build:e2e / verify:firefox |
| `evidence/cmd08-post-test-e2e-NOTRUN.log` | `test:e2e` 环境错误原文（无 Chromium） |
| `evidence/verify-dist-red.log` / `-green.log` / `verify-dist.log` | 反向验证红→绿与正式校验 |
| `evidence/ff-probe-run-2026-09-20.log` | Firefox 真机探针逐项 PASS/FAIL 输出 |
| `ff-probe-results-v1.0.7-2026-09-20.json` | 真机结果（含 meta 元数据） |

> 本报告是**执行者交付**，不代替管理者的独立验收。
