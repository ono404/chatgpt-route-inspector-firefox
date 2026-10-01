# verify-firefox-dist 补强报告（2026-09-27，verify-hardening 轮）

范围与白名单执行情况、命令与退出码、红→绿证据、哈希核对结论。执行者本轮实测均在本文件与同目录日志中留原始输出；历史数字注明出处，不与本轮实测混写。

## 1. 任务 0：起点与冻结核对（本轮实测）

| 核对项 | 结果 |
| --- | --- |
| 分支 | `codex/sync-upstream-v1.0.9` |
| HEAD | `2470d15af18ce85e7b4d9c464c53091dd5e1f497`（与任务书一致），开工时工作树干净 |
| XPI SHA-256 | `34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523` ✔ |
| 源码 ZIP SHA-256 | `0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0` ✔ |
| build.json SHA-256 | `15debe2ae37957a21c7f91161e6627acc33afdd6dd67e29ae00268b6451e9dab` ✔ |
| dist 快照 | 94 个文件逐文件 SHA-256 → `snapshot-dist-sha256.txt` |
| 历史证据快照 | 92 个 `docs/**/evidence/*` 文件 → `snapshot-evidence-sha256.txt`（文件含自引用行，比对时排除） |
| Node / npm | v24.16.0 / 12.0.1 |
| npm test 基线 | 退出 0，34 文件 327 passed（`log-task0-npm-test-baseline.txt`） |

## 2. 缺陷确认（旧校验器漏检）

旧 `scripts/verify-firefox-dist.mjs` 对 Firefox manifest 只做逐字段守卫（manifest_version / gecko 三字段 / `background.scripts` 是数组），对 Chromium manifest 只比 version 与 permissions。`tests/integration/firefox-dist-verifier.test.ts` 的 7 项变异在旧实现下 CLI 全部退出 0（漏检）：

红证据：`log-taskB-red-old-verifier-final-test.txt`（最终版测试文件对 HEAD 旧校验器实跑：vitest 退出 1，7 failed / 2 passed；拍摄方式为临时把 `scripts/verify-firefox-dist.mjs` 置回 `git show HEAD:` 版本、跑完即恢复并复验绿灯）；首次红证据 `log-taskB-red-old-verifier.txt`（类型修正前的同变异集测试，结论一致）。

| 变异 | 旧实现 | 新实现 |
| --- | --- | --- |
| Firefox version 改 `0.0.0-tampered` | 退出 0（漏检） | 非 0，manifest 比较失败 |
| permissions 增 `bookmarks` | 退出 0（漏检） | 非 0 |
| host_permissions 增 `https://example.com/*` | 退出 0（漏检） | 非 0 |
| MAIN world 降级 ISOLATED | 退出 0（漏检） | 非 0 |
| `background.scripts` 清空 `[]` | 退出 0（旧数组判断放行） | 非 0 |
| `background.type` 改 `classic` | 退出 0（漏检） | 非 0 |
| `data_collection_permissions.required` 改 `["none","locationInfo"]` | 退出 0（旧检查只看 `[0]`） | 非 0 |

绿证据：`log-taskB-green-new-verifier.txt`（9/9 通过，含合法夹具两次通过 + 变异后恢复合法夹具复验）。

## 3. 校验器改动（最小补强）

- `scripts/verify-firefox-dist.mjs`：删除被完整比较覆盖的逐字段守卫与 Chromium 侧两字段抽查，改为——
  - extension manifest 必须整体 `deepStrictEqual` 源真相 `manifest/manifest.json`；
  - firefox manifest 必须整体 `deepStrictEqual` `toFirefoxManifest(manifest/manifest.json)`（复用 `scripts/firefox-manifest.mjs` 同一转换函数，不手写第二份规则；`node:assert` 深比较，键序/缩进不参与）。
- 原有路径集合双向比对、逐文件字节一致（JS 强制）、引用存在性、`src/ui` 锚点完整性检查全部保留；`tests/unit/manifest-firefox.test.ts` 转换函数独立单测原样保留。
- 无新依赖、无校验框架、无多层抽象。

## 4. 回归测试（tests/integration/firefox-dist-verifier.test.ts）

- 真实启动 CLI（`node scripts/verify-firefox-dist.mjs <ext> <ff>`，异步 `spawn`，无 mock、无替换检查逻辑）。
- 夹具：系统临时目录 `mkdtemp`，复制冻结 `dist/extension` 与 `dist/firefox`；输入缺失时在 `beforeAll` 抛错，不跳过。每次变异从合法夹具重新复制，只改 `manifest.json` 一处；断言非零退出且输出含 `manifest`、不含 `references missing file`（证明失败由 manifest 不匹配触发）。
- 结尾复验合法夹具仍退出 0（restore check）。
- 测试运行结束删除本轮自建的临时目录（`afterAll`）。

## 5. 收尾门禁（本轮实测，日志见本目录）

| 命令 | 退出码 | 摘要 |
| --- | --- | --- |
| `node node_modules/typescript/bin/tsc --noEmit` | 0 | 无输出 |
| `node node_modules/eslint/bin/eslint.js .` | 0 | 无输出 |
| `npm test`（vitest run --coverage） | 0 | 35 文件 336 passed（原 327 + 新 9），0 failed，无新增 skip/todo |
| `node scripts/verify-firefox-dist.mjs` | 0 | `extension=30 firefox=30`、8 JS 字节一致、`OK` |

覆盖率（v8，`src/core/**`，阈值 80/80/80/70 未改）：statements 97.29 / branches 91.81 / functions 100 / lines 97.29。基线 branches 为 91.83，终跑 91.81——差异为 v8 覆盖率运行间抖动（本轮 0.02 个百分点），远高于阈值 70，`src/` 未改动。

## 6. 哈希与反向核对（收尾复比，本轮实测）

- dist：94 文件快照复比 **逐一相同**（`DIST_UNCHANGED`）。
- 历史证据：92 文件快照复比 **逐一相同**（快照文件自引用行除外，属预期）。
- 三份 release 冻结文件：收尾复测 SHA-256 与任务书完全一致（见 §1 表）。
- 白名单外 Git 内容：`git status --porcelain -uall` 仅含 `AGENTS.md`、`PROGRESS.md`、`README-FIREFOX.md`、`BLOCKED.md`、`scripts/verify-firefox-dist.mjs`（修改）与 `tests/integration/firefox-dist-verifier.test.ts`、`docs/verify-hardening-2026-09-27/**`（新增），均在白名单内。`src/`、`manifest/`、构建脚本、探针、既有测试零改动。

## 7. 文档修改（任务 C）

- `AGENTS.md` / `README-FIREFOX.md`：同源表述改为"Git 内容与上游一致；本机检出文本存在换行转换（`core.autocrlf=true`，相对上游 blob 仅 CRLF/LF 差异）"，保留"两 target 8 个 JS 产物字节一致"结论。
- `README-FIREFOX.md`：校验清单第 6 条改为 manifest 完整对象比较说明；AMO 节新增源码 ZIP 勘误——包内 BUILD-README 漏了 `npm run build`，正确顺序为 `npm ci` → `npm run build` → `npm run build:firefox` → `npm run verify:firefox`（校验脚本同时需要两个 dist 目录）。**冻结 ZIP 未重新打包**；勘误依据是已读的 `scripts/build.mjs` / `scripts/verify-firefox-dist.mjs` 与既有产物（并实读 ZIP 内 `source/BUILD-README.txt` 确认原文只写 `npm ci` → `npm run build:firefox`），本轮未重跑复建验证。
- `PROGRESS.md`：开工回执 + 本轮结果记录。
- `BLOCKED.md`：仅追加"本轮无新增阻塞"状态，历史第 1–14 项原样保留。

## 8. 限制与下一轮入口

- 本轮未运行构建/打包/浏览器探针/真实账号流量（按任务书），历史 327/56/27 等数字均为历史记录而非本轮复跑。
- `stream_parse_failed` 根因仍未解决（v1.0.9 未改业务代码），保留为下一轮真实账号 + 成功 SSE 验收入口：见 `BLOCKED.md` 第 14 项与 README-FIREFOX"已验证"节。
- 源码 ZIP 内 BUILD-README 的遗漏靠外部勘误修正，旧包读者须同时看 `README-FIREFOX.md` AMO 节勘误条目。
