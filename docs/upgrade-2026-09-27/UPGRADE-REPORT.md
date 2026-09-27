# 升级报告：v1.0.7 → v1.0.9（2026-09-27）

## 1. 结论概要

- 上游 `v1.0.9`（`99f982dd089b020afa85b897b07edfb340cc58dd`，3 提交 40 文件 +1056/-357）已按 merge 纳入分支 `codex/sync-upstream-v1.0.9`，业务同源检查为空。
- 本轮全部门禁（typecheck / lint / test / test:firefox-tooling / build / build:firefox / build:notice / build:e2e / verify:firefox / package:firefox）退出码 0。
- FF156.0.1 真机探针正向 **27/27 通过、退出码 0**（含 5 个 v1.0.9 新检查）；篡改反向验证在启动浏览器前拒绝、退出码 2；输出覆盖保护实测退出码 6。
- 源码 ZIP 在仓库外独立解压、`npm ci`、`build:firefox` 后与交付 XPI **30/30 逐文件一致**。
- 交付物全部**未签名、未上传、未安装**到日常浏览器。签名与覆盖安装仍待人工处理。

## 2. 提交与隔离工作区

| 提交 | 内容 |
| --- | --- |
| `b1f06aa` | v1.0.7 现场四文档快照（与原工作区未提交版本哈希一致：AGENTS `3ee2cdfa…`、BLOCKED `5c0d4c57…`、PROGRESS `a1c67800…`、README-FIREFOX `89584045…`） |
| `55d3ccf` | merge 上游 `99f982d`（唯一冲突 `package.json`：双侧 scripts 合并，保留 build:notice/build:e2e 上游定义 + 本地 Firefox scripts） |
| `6f932e0` | 探针与工具夹具的 v1.0.9 语义适配 |

隔离 worktree：`D:\LAB\sync-v109-isolated`（从 `909941e` 建立；无 managed worktree 工具，按任务书降级用 `git worktree`）。原工作区 `D:\LAB\火狐浏览器插件制作2` 全程未动（四个文档的未提交修改保留原样，`.workbuddy/` 未复制、未改动）。

## 3. 上游 v1.0.9 行为变化（实测核实，不凭文件名）

- schema `1.7.0 → 1.8.0`；verdict 新增 `suspected_downgrade`、`work_unverifiable`。
- 新建会话：`local-chatgpt:` 临时地址到正式地址期间保持同一 capture context（`capture-context.ts`）；两个不同草稿绝不合并。
- `suspected_downgrade`：仅对已完成的 live（page_fetch/page_websocket）或 reload（conversation_record）网络响应、有 server/response 证据、无 `resolved_model_slug`、基础判定 normal/unknown 时给出；failed/responding 或有 resolved 均不给（上游 `tests/unit/turns.test.ts` 条件逐条镜像到探针检查 16/17/18）。
- 公告：本地浮窗 1.0.7 入口删除（`notice-hint.ts` 整文件删除），`route:open-announcement` 改为无条件打开固定地址 `https://rinotice.liu-qi.cn/`，存储键 `routeInspectorNotice109Shown`；本地 `ui/announcement/` 页面保留并改为 1.0.9 版本公告内容；新增独立公告站点构建 `scripts/build-notice.mjs`（`build:e2e` 现在含 `build:notice`）。
- `PRIVACY.md` 已由上游如实更新（2026-09-27 生效，写明升级时打开公告站点一次及服务端可见的标准 HTTP 头信息）。
- `page-hook.ts`、`sse-decoder.ts` 本体未变——`stream_parse_failed` 的既有未确认项不因本次升级改变。
- 无新增依赖、无新增扩展权限（仍是 `permissions: ["storage"]` + 两个 chatgpt host）。

## 4. 门禁实录（最终冻结代码后逐条执行）

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | 通过 |
| `npm run lint` | 0 | 通过 |
| `npm test` | 0 | 34 文件 / **327 passed** / 0 failed / 0 skipped；覆盖率 97.29% stmts / 91.82% branch / 100% funcs（阈值全过，均不低于基线 97.19/91.37/100） |
| `npm run test:firefox-tooling` | 0 | **49 passed**（与升级前持平，未删改任何既有测试） |
| `npm run build` | 0 | dist/extension |
| `npm run build:firefox` | 0 | dist/firefox |
| `npm run build:notice` | 0 | dist/notice（上游新增） |
| `npm run build:e2e` | 0 | 含 build:notice |
| `npm run verify:firefox` | 0 | extension=30 firefox=30 identical=true，8 个 JS 逐字节一致 |
| `npm run package:firefox` | 0 | XPI + 同次 build.json，回读校验 30 files identical |
| `npm run test:e2e` | 1 | **环境缺项**：`No extension-capable Chromium found`（证据 `evidence/test-e2e-env.log`）；按约束不安装浏览器，沿用 BLOCKED 第 7 项 |

原始输出：`docs/upgrade-2026-09-27/evidence/`。

## 5. 真机探针（Firefox 156.0.1，专用临时 profile，headless）

迭代过程（全部结果 JSON 均保留，未覆盖任何旧文件）：

| 运行 | 结果 | 用途 |
| --- | --- | --- |
| run1（`ff-probe-results-v1.0.9-2026-09-27.json`） | 24/28，退出 4 | 首轮红灯：检查 11/15/19/20 失败，保留证据 |
| run2 | 25/28，退出 4 | 修复 19（脚本漏传 `arguments[0]`）；11/15/20 继续诊断 |
| run3 | 25/28，退出 4 | 15 证实 `tabs.query` 读不到第三方 tab URL（无 tabs 权限）；20 两种触发均无断线卡片 |
| run4（`…-run4.json`） | **27/27，退出 0** | 全部通过 |
| final（`ff-probe-positive-final-v1.0.9-2026-09-27.json` + `evidence/probe-positive-final.log`） | **27/27，退出 0** | 冻结代码最终正向 |

检查 11（suspect 提示）最终形态：合成观测经**真实 page-hook → bridge → background 管线**（`window.postMessage` 信封，sender.tab 即 chatgpt.com 标签页），浮窗经真实广播渲染出 `suspect-trigger`，链接指向 `https://rinotice.liu-qi.cn/`。数据是合成的，管线和渲染是真实的——验证层级已在检查注释中标明。

检查 15（公告目标）：`route:open-announcement` 实际打开新标签页，URL 由浏览器侧 `WebDriver:GetCurrentURL` 核实为 `https://rinotice.liu-qi.cn/`（扩展无 tabs 权限，`tabs.query` 读不到第三方 URL，这是 Firefox 权限模型的正确行为）；页面加载成功（标题 "Route Inspector · 1.0.9 版本公告"），路由历史不变。**注意：真机探针运行会对该公开公告站点发起一次普通浏览器导航（不附带任何扩展数据）。**

篡改反向验证：仓库外 `D:\LAB\sync-v109-tamper`（`make_tampered_copy.py`，manifest 不变、`content/page-hook.js` 篡改）→ 探针 **退出码 2**，"artifact identity rejected before browser interaction"，浏览器未启动（`evidence/probe-tampered-run.log`、`ff-probe-tampered-verified-v1.0.9-2026-09-27.json`）。输出保护：`--out` 指向已存在文件实测 **退出码 6**、原文件未动。

## 6. 检查 20（扩展上下文失效提示）的止损记录

v1.0.9 上游新增"扩展连接失效 → 刷新页面"卡片。其逻辑由**上游自带集成测试覆盖**（`tests/integration/bridge-lifecycle.test.ts`：mock 发送拒绝后断言刷新提示，本轮 327 项中含它）。为补真机层验证，探针尝试了真实触发：Addon 重装（update 型失效）与 Addon 卸载，连续 3 轮（run1–run3，证据保留）均未出现卡片——FF156 在 addon 卸载/重装时不会把页面内内容脚本留成孤儿，点击路径无从触发拒绝。按止损规则停止该项：**不保留为必需真机检查、不伪造通过**；探针内留有说明注释，本条记入 BLOCKED.md。

## 7. 交付物（全部未签名，不上传）

| 文件 | SHA-256 |
| --- | --- |
| `release/chatgpt-route-inspector-firefox-1.0.9.xpi` | `34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523` |
| 包内 `manifest.json` | `b8957ae63a39dc392d693081e31e80e201eee4a093b168f78a3eacdd075e07a9`（gecko ID `chatgpt-route-inspector-firefox@local`，min 128.0，version 1.0.9） |
| `release/chatgpt-route-inspector-firefox-1.0.9.build.json` | 与 XPI 同次打包，`dist-matches-record` 探针检查通过 |
| `release/chatgpt-route-inspector-firefox-1.0.9-source.zip` | `0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0`（72 文件，170835 字节） |

源码 ZIP 复建验证：仓库外新目录解压 → `npm ci`（退出 0）→ `npm run build:firefox`（退出 0）→ 与交付 XPI 逐文件比对 **30/30 路径与内容一致（REBUILD_MATCH）**。实际环境：Node v24.16.0 / npm 12.0.1。
复建过程中的发现：源码包若缺 `tsconfig.json`，esbuild 自动读取失效，7 个 JS 少 `"use strict";` 前缀、哈希全部变化——已把 `tsconfig.json` 纳入源码包并在包内 BUILD-README 写明。该发现同时解释了"重打包哈希必变"的另一种成因（构建输入差异，而非 ZIP 元数据）。

## 8. 同源声明（本轮实测）

- `git diff --exit-code 99f982d -- src schemas _locales icons manifest`：合并后工作区与最终提交**均为空**。
- `verify-firefox-dist`：两 target 路径集合双向一致、8 个 JS 逐字节一致。
- 上游测试原样同步（未改上游测试）；测试数 301 → 327，净增 26 项全部来自上游目标提交；本地既有保护用例（manifest-firefox、firefox-upgrade-migration、探针原 23 项必需检查、工具回归 49 项）全部保留且通过；探针必需检查 23 → 27（净增 4 项真机检查，1 项旧版语义检查按上游行为替换）。

## 9. 遗留与阻塞（详见 BLOCKED.md）

1. 真实更新事件（`reason=update`，键 `routeInspectorNotice109Shown`）：临时加载无法产生，仍未验证（原第 5 项延续，目标版本更新为 1.0.9）。
2. FF128 下限：仍未实测（原第 6 项）。
3. `test:e2e`：本机无 extension-capable Chromium，本轮再次实测确认（原第 7 项，证据 `evidence/test-e2e-env.log`）。
4. `stream_parse_failed`：上游未改 page-hook/sse-decoder，根因未确认（原第 4 项延续）。
5. **新增**：断线提示卡片的真机复现在 FF156 不可行（Gecko 不留孤儿内容脚本），逻辑层以上游 mock 集成测试为准。
6. 公告站点 `https://rinotice.liu-qi.cn/` 为上游固定地址，本轮仅记录"真实可达、返回公告内容"，不对其内容与可用性作长期承诺。
7. 签名与日常覆盖安装：未签名、未上传 AMO、未安装（管理者既定范围）。
