# 升级报告：v1.0.9 → v1.1.0（Firefox 自用移植）

日期：2026-10-01 ｜ 分支 `codex/sync-upstream-v1.1.0` ｜ 工作区 `D:\LAB\sync-v109-isolated`

## 1. 结论摘要

- 源码与上游 **v1.1.0（`dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552`）同源**：合并后
  `git diff --exit-code dd5ea33 -- src schemas _locales icons manifest` 为空。
- 门禁全绿（逐条退出码见 §4）；Firefox **真机探针 32/32、退出码 0**（Firefox 157.0）。
- 交付：未签名 XPI + 同次 build.json + 源码 ZIP；**仓库外复建与 XPI 30/30 逐文件一致**。
- 未提交补强已作保全提交 `73696a7`；旧交付物与历史证据哈希未变。
- **未签名、未上传 AMO、未日常安装**。真实成功 SSE、真实更新事件、FF128 仍未验证（§7）。

## 2. 起点与目标（核对结果）

| 项 | 任务书预期 | 实测 | 结论 |
| --- | --- | --- | --- |
| 起点 HEAD | `2470d15` | `2470d157`，分支 `codex/sync-upstream-v1.0.9` | 一致 |
| 未提交改动 | 四文档 + 校验器 + 未跟踪测试/证据 | `M AGENTS/BLOCKED/PROGRESS/README-FIREFOX`、`M scripts/verify-firefox-dist.mjs`、`?? tests/integration/firefox-dist-verifier.test.ts`、`?? docs/verify-hardening-2026-09-27/` | 一致 |
| 业务目录 vs `99f982d` | 无差异 | `git diff 99f982d -- src schemas _locales icons manifest` 空 | 一致 |
| 目标标签 | `dd5ea336…` | `git rev-parse v1.1.0` = `dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552` | 一致 |
| 上游差异 | 1 提交 / 40 文件 / +1431 / −45 | `git diff --stat 99f982d v1.1.0`：1 提交，40 文件，+1431 / −45 | 一致 |
| 依赖 | 不变 | `package-lock.json` 仅版本号 4 行 | 一致 |

## 3. 执行顺序与产物

1. **备份**（进任何修改之前）：`D:\LAB\sync-v110-backup-2026-10-01\`
   —— preserve 19 文件 + `dist/`(94) + `release/`(3) = **117 文件**，附 `HASHES.sha256`。
2. **保全提交** `73696a7`（19 文件，精确路径 `git add`，未用 `git add .`；未提交任何生成物或备份）。
3. **建分支** `codex/sync-upstream-v1.1.0`。
4. **开工回执** `0c46668`（≤10 行，写入 PROGRESS 顶部）。
5. **合并** `git merge --no-ff dd5ea33…` → 合并提交 **`770095f`**，双亲
   `0c46668` + `dd5ea336…`。**零冲突**：本次没有触发任何三方冲突（`scripts/build.mjs`、
   `package.json` 的历史冲突点本次未同时改动；上游 v1.1.0 未改这两个文件的内容部分，
   只改了 `package.json` 的 version 行）。
6. **最小适配**（见 §5）→ **门禁** → **真机正反向** → **源码包与复建** → 本轮文档与提交。

## 4. 门禁：命令、退出码、计数

原始输出全部在 `docs/upgrade-2026-10-01/evidence/`。

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm ci` | 0 | 5 项依赖漏洞（3 moderate、2 high），esbuild 安装脚本阻止警告；构建不受影响 |
| `npm run build` | 0 | `dist/extension` |
| `npm run build:firefox` | 0 | `dist/firefox`（30 文件） |
| `npm run typecheck` | 0 | — |
| `npm run lint` | 0 | — |
| `npm test`（vitest run --coverage） | 0 | **38 文件 / 442 passed / 0 failed / 0 skipped**；覆盖率 98.1 / 91.8 / 100 |
| `npm run test:firefox-tooling` | 0 | **66 passed**（基线 56，新增 10 项反例） |
| `npm run build:notice` | 0 | — |
| `npm run build:e2e` | 0 | — |
| `npm run verify:firefox` | 0 | extension=30 firefox=30 identical=true；8 个 JS 逐字节一致 |
| `npm run package:firefox` | 0 | XPI 30 文件与 dist 一致 |
| `npm run test:e2e` | **1** | 缺 extension-capable Chromium（环境阻塞，未安装），1 failed / 12 did not run |

对照基线：单测 336 → **442**（上游净增 106）；工具 56 → **66**；两项均只增不减，未删/未 skip。
覆盖率阈值（80/80/80/70）未改，实测值高于阈值且高于基线（97.29 → 98.1）。

### 红→绿证据

| 阶段 | 证据 | 结果 |
| --- | --- | --- |
| 适配前（未改探针，v1.1.0 包） | `b-probe-red.txt` / `b-probe-red.json` | **26 passed / 1 failed**，失败项 `7.synthetic-observation-pipeline`（schema 1.8.0 vs 实际 1.9.0）→ 退出 4 |
| 适配后（同一包） | `d-probe-positive.txt` | **32 passed / 0 failed / 0 missing** → 退出 0 |
| 工具回归（新增反例） | `b-tooling-green.txt` | 66 passed；其中 10 项为**故意制造失败**的反例 |

## 5. 最小适配（仅动白名单文件）

| 文件 | 改动 | 理由 |
| --- | --- | --- |
| `ff-marionette.py` | 新增 `ROUTE_SCHEMA_VERSION = "1.9.0"` 常量，检查 7 与之比较 | 原为字面量 `"1.8.0"`；改为常量后仍是**等值断言**（不接受别的版本），并把这行写进 `detail` 便于失败时定位 |
| `ff-marionette.py` | 新增检查 20–24 并注册进 `REQUIRED_CHECKS` | v1.1.0 新功能的真机断言（§6） |
| `tests/firefox-tooling/fake_marionette.py` | `turn` / `auto` 夹具改 `1.9.0`；新增 8 个 answer 与 9 条路由片段 | 夹具与探针的明确预期同步；**保留错误 schema 拒绝**（见下） |
| `tests/firefox-tooling/test_ff_marionette_run.py` | 新增 `TestV110TaskKindChecks`（10 项） | 5 个新检查各有对应**失败反例** |
| `tests/integration/firefox-upgrade-migration.test.ts` | 标题与 `EMPTY_QUOTA_FIELDS` 断言附近增加 4 个 v1.1.0 字段的 null 默认断言 | 迁移目标 schema 更新；继续验证「合成旧数据归一且读取不写存储」 |

**未**全局替换版本字符串：`tests/integration/upgrade-notice.test.ts`、`src/ui/announcement/`、
`background/upgrade-notice.ts`、`fake_marionette.py` 的 `announcementPage` 夹具仍保留 **1.0.9 公告页**语义，
因为 v1.1.0 上游**仍然保留**该公告页与去重逻辑（真机检查 14/15 实测通过：包内 1.0.9 公告页渲染、
外链可达并返回 **1.1.0** 公告正文）。

### 「错误 schema 被拒绝」仍然成立

- 探针检查 7 是 `== ROUTE_SCHEMA_VERSION` 的等值断言，不是「存在即可」。
- 反例：把夹具改回 `1.8.0`（`test_stale_schema_version_fails_the_pipeline_check`）
  与改成 `2.0.0`（`test_future_schema_version_is_also_rejected`）都**必须**让检查 7 失败、退出 4，二者均实测通过。
- 真机红证据 `b-probe-red.json` 就是「1.8.0 期望 vs 1.9.0 实际」被拒绝的实拍。

## 6. 新功能断言（标明输入来源与注入层级）

| 检查 | 断言内容 | 输入 | 注入层级 |
| --- | --- | --- | --- |
| 20 `task-kind-verdicts` | `image_generation` / `deep_research` 两种 verdict 生效，且**不**被降级为 `suspected_downgrade`；schemaVersion == 1.9.0 | 合成 observation | 扩展上下文 `route:observation`（后台管线） |
| 21 `research-planning-report-split` | 规划模型与报告模型**分列且不同** | 合成 observation | 同上 |
| 22 `deep-research-capture-taskkind` | 被测 **page-hook 自己**发出的请求被识别为 `deep_research`；`captureId` 由 hook 的 `crypto.randomUUID()` 生成 | 合成 Deep Research 创建请求（仅结构化 metadata，无提示词正文） | **真实 page-hook → bridge → background**；响应为 chatgpt.com 真实未认证拒绝 |
| 23 `ui-task-filters` | 诊断台结论筛选含「图片生成」「深度研究」两个新标签 | 合成 observation + 真实扩展页 | 扩展页 DOM（`moz-extension://…/ui/dashboard/index.html`） |
| 24 `ui-research-model-split` | 选中深研记录后，「规划模型」「报告模型」为**两行**且值不同 | 同上 | 同上 |

检查 22 的真机实测拿到了 hook 生成的真实 UUID
（`27fa7338-89fc-4732-9fd2-96d237422f31`，非 `ff-probe-` 前缀 → 探针未预填），
证明这条链路不是靠预填 ID 或缺失 DOM 冒充的。

**覆盖边界（重要）**：检查 22 与 19 走的都是合成请求 + **未认证拒绝响应**，
因此**不覆盖成功 SSE 内的会话身份、研究任务关联或模型路由**。

## 7. 真机探针（Firefox 157.0）

- 命令：
  ```
  py -B ff-marionette.py --xpi release/chatgpt-route-inspector-firefox-1.1.0.xpi \
    --expect-build-record release/chatgpt-route-inspector-firefox-1.1.0.build.json \
    --dist dist/firefox --out docs/upgrade-2026-10-01/ff-probe-positive-v1.1.0-2026-10-01.json \
    --label v1.1.0-positive --commit 770095f
  ```
- 结果：**32 executed / 32 passed / 0 failed / 0 missing → 退出码 0**。
  `browserVersion=157.0`、`moz:buildID=20260924084938`、`connectionTrusted=true`、
  临时 profile 回报值与本次启动目录一致、运行后临时 profile 已删除。
- 产物身份（连接浏览器之前完成）：XPI `04af228b…65ae` == 记录；包内 30 文件 == `dist/firefox`；
  `manifestVersion=1.1.0`、`geckoId=chatgpt-route-inspector-firefox@local`、`strictMinVersion=128.0`。
- 保留原 27 项门禁的**全部语义**，只把检查 7 的 schema 期望值与构建同步；新增 5 项（20–24）。

### 反向验证（全部在仓库外临时副本 `D:\LAB\sync-v110-reverse-2026-10-01\`）

| 反例 | 预期 | 实测 |
| --- | --- | --- |
| 篡改 XPI（同 manifest、改 1 个 JS） | 浏览器启动前退出 2 | **退出 2**；`browserLaunched=false`；`0d.manifest-sha256` **PASS**（manifest 确实没变）而 `0a/0b/0c` FAIL |
| 已有 `--out` | 退出 6 且原文件不变 | **退出 6**，前后哈希 `0211419f…` 不变 |
| 错误 manifest（`strict_min_version` 改 120.0）经真实 CLI | 非零 | **退出 1**（FAIL 明确指出 `+ '120.0' / - '128.0'`） |
| 还原 manifest 后 | 0 | **退出 0**，`verify-firefox-dist: OK` |
| 禁两次目标导航的探针副本（`probe-no-navigation.py`） | 身份通过后检查 19 失败、退出 4 | **退出 4**；`0e.session-profile` PASS、`19` FAIL（"locked chatgpt tab not on any of ['/c/navcheck-conv']"）、31 passed / 1 failed |

## 8. 交付物与可复建性

| 交付物 | SHA-256 | 备注 |
| --- | --- | --- |
| `release/chatgpt-route-inspector-firefox-1.1.0.xpi` | `04af228b03f85e954d894a859fb87afcf1bfbc9cd449da881c2f25f99c0165ae` | 155451 字节，未签名 |
| `release/chatgpt-route-inspector-firefox-1.1.0.build.json` | `a2028179ed18602da5d6be288dd2142a0140dab0d64bfdb6fcd267afaba263a1` | 与 XPI 同一次打包 |
| `release/chatgpt-route-inspector-firefox-1.1.0-source.zip` | `51523360d4063fc939177672b9bf990278a1e0495f4e715f5e22b0cc49888846` | 76 条目 |
| `manifest.json`（包内/产物） | `19bec35aef869de7f9928b2385597d52684e6c113e9b2d7bc6997a9e3539f6ee` | — |
| 探针脚本 | `7c56cfd335db2e19e96b6fd7d58dd96882a2bef011536d4b4ff6a8f9a92f0ac6` | 结果 JSON 的 `probeSha256` 与之一致 |

> **打包致哈希变化（已如实记录，非缺陷）**：本轮 XPI 被打包了两次，**内容逐字节相同**
> （30 个路径全同，0 个内容差异），仅 **9 个 ZIP 条目的 mtime** 不同，导致压缩包整体 sha256
> 由 `45ce3d10…` 变为 `04af228b…`。上表中的哈希是**冻结的第二次打包**；
> 正向探针与仓库外复建**都是针对这个最终包重跑的**（首轮正向结果保留为
> `evidence/probe-positive-r1-superseded-packaging.json`，可对照：其 `manifestSha256`
> 与检查明细完全一致）。这正是 AGENTS.md 中「ZIP mtime 会让重打包哈希变化」那条约定。

**仓库外复建**：`D:\LAB\sync-v110-rebuild-2026-10-01\`，解压源码 ZIP → `npm ci` → `npm run build`
→ `npm run build:firefox` → `npm run verify:firefox`（均退出 0）→ 与交付 XPI **逐文件比对**：

```
rebuilt=30 xpi=30 recorded=30
REBUILD_MATCH: every rebuilt file matches the delivered XPI byte for byte
```

不是只看压缩包总哈希：**30 个路径逐一比对，内容逐一哈希**（脚本 `compare.py`，仓库外）。

源码包内容审计：含 `tsconfig.json`、`package-lock.json`、全部构建脚本（含 `verify-firefox-dist.mjs`、
`run-firefox-tooling-tests.mjs`）与 4 个新核心模块（`research.ts`、`task-captures.ts`、
`task-identity.ts`、`task-kind.ts`）；**不含**测试源码、证据、探针、依赖目录、`.log`、`dist/`、`release/`。
`BUILD-README.txt` 的构建步骤已按要求写全：`npm ci` → `npm run build` → `npm run build:firefox`
→ `npm run verify:firefox`。

### 旧交付物与历史证据未变（逐一复核）

- 1.0.9 XPI `34ca9440…da523`、源码 ZIP `0cc2412f…3d0`、build.json `15debe2a…9dab` —— 与任务书一致。
- `docs/verify-hardening-2026-09-27/snapshot-evidence-sha256.txt` 记录的 **92 个证据文件全部哈希未变**。
  该快照文件自身的第 93 行是**自引用行**，其值与会话前备份一致（不是本轮引入的变化）。

## 9. 上游接缝审计（附文件位置）

| 面 | 结论 | 位置 |
| --- | --- | --- |
| 权限 | **未新增**：`manifest/manifest.json` 只改 version 行；`permissions` / `host_permissions` / `content_scripts` 未动 | `manifest/manifest.json` |
| API | **未新增 `chrome.*` 调用**（对新增行做正则扫描为空）；badge 新增 IMG/DR 文案走既有 `chrome.action` | `src/background/service-worker.ts` |
| 迁移 | `core/migration.ts` 未改，仍走 `normalizeObservation → createTurn` 通用再归一；新增 4 个任务字段为 null 默认 | `src/core/observation.ts`、`src/core/turns.ts` |
| 脱敏 | 导出新增脱敏 `researchWidgetId` / `researchMessageId`；报告新增深研「规划模型/报告模型」行（只含 allowlist 字段） | `src/core/privacy.ts` |
| 任务关联 | 新增 `task-kind.ts` / `task-identity.ts` / `task-captures.ts`，按结构化 metadata（`system_hints`、`chatgpt_sdk`、`invoked_resource`）判定，**不读提示词正文**；`sse-decoder.ts` 的 KEYS 白名单新增字段，`report_message`/`widget_state` 在遍历时被显式跳过 | `src/core/task-kind.ts`、`src/core/response-parser.ts`、`src/core/sse-decoder.ts` |
| 规划/报告分离 | 报告模型经独立的 `researchFromMetadata` → `researchReportModel`，**不进入** planner 的 `assessRoute` 输入 | `src/core/research.ts` |
| Firefox 接缝 | 无新增 UI 入口（`src/ui` 只有既有页面被改，`uiEntries` 无需改）；唯一新 CSS 特性为既有 `:has()`；Gecko ID、`strict_min_version 128.0`、转换行为均未变 | `scripts/build.mjs`、`scripts/firefox-manifest.mjs` |

**几何确认**：`src/core/types.ts` 的 `RouteVerdict` 改为 `… | TaskKind`，
`assessRoute` 在 `fields.taskKind` 存在时**先递归评估证据再覆盖 verdict**，因此
图片/研究任务的 route 证据仍然保留而不是被丢弃。

## 10. `stream_parse_failed` 的处理立场

上游 v1.1.0 **没有**针对该路径的定点修复（`sse-decoder.ts` 只扩了 KEYS 白名单与
`widget_state`/`image_gen_title` 投影）。本轮**不因升级宣布该问题已修复**，
BLOCKED 第 4 项原样保留。探针检查 18 仍断言 `phase=failed` 保留 `errorCode=stream_parse_failed`
且不被误报为 completed（真机实测 PASS）。

## 11. 止损与迭代记录

- **未触发 3 轮止损**。唯一一次红灯是适配前的预期红灯（检查 7 schema），一次修复即通过。
- 迭代过程：反向验证的第一次真机运行因**临时副本路径与构建记录不一致**，
  在 `0c.dist-matches-record` 上失败（退出 2，不是被测项失败）。
  处理：用真实打包工具在该副本内重新打包，使身份自洽后复跑，
  得到 0c PASS、19 FAIL、退出 4 的干净信号。证据 `d-reverse-no-navigation.txt`（终次）。
- 未删除、未跳过、未弱化任何既有测试或断言；未改动业务源码。

## 12. 未完成项（不冒称全部完成）

见 `BLOCKED.md`。要点：签名与日常安装、成功真实 SSE 的会话身份与模型路由、
真实更新事件（1.0.9→1.1.0）、FF128 下限、额度专项、Chromium E2E（缺环境）。