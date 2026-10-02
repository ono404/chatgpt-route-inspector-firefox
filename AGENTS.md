# AGENTS.md — chatgpt-route-inspector（Firefox 自用移植）

Chromium 上游同源码 + 独立 Firefox 构建 target 的自用移植。读 PROGRESS.md / BLOCKED.md 恢复上下文。
当前同步基线：上游 **v1.1.0**（`dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552`，tag `v1.1.0`），Git 内容与上游一致；本机检出文本存在换行转换（`core.autocrlf=true`，相对上游 blob 仅 CRLF/LF 差异）。
当前交付位于 `D:\LAB\sync-v109-isolated`，分支 `codex/sync-upstream-v1.1.0`；原工作区仍为 v1.0.7，勿混用产物。本轮结果见 [升级报告](docs/upgrade-2026-10-01/UPGRADE-REPORT.md)。

## 怎么跑

- `npm ci` → `npm run typecheck` / `npm run lint` / `npm test`（v1.1.0 本轮实测 **38 文件 442 passed，0 failed / 0 skipped**，覆盖率 98.1/91.8/100）/ `npm run build`
- Firefox 版：`npm run build:firefox` → `dist/firefox/`；本地加载见 README-FIREFOX.md
- Firefox 产物校验 / 打包：`npm run verify:firefox` / `npm run package:firefox`
- 验证工具回归测试：`npm run test:firefox-tooling`（Python，**82 项**＝66 基线 + 16 项检查 22 身份反例；合成夹具 + 脚本化 Marionette peer；仅“真实进程/真实浏览器”两项按环境跳过）
- 真机验证探针（**自己启动浏览器**，专用临时 profile）：
  `py -B ff-marionette.py --xpi <打包产物> --expect-build-record <release/*.build.json> --dist dist/firefox --out <新结果路径>`
  （`python` 在本机是 WindowsApps 别名，退出 9009，一律用 `py`；FF156+ 必须 `-remote-allow-system-access`，探针启动命令已内置；省略 `--out` 时自动生成、绝不覆盖旧文件）
- 探针退出码：0 全通过 / 2 产物身份被拒（含损坏 XPI、不可用构建记录）/ 3 运行异常（含输出路径不可写）/ 4 有检查失败（含**连接不可信时的安全中止**）/ 5 检查没跑全 / 6 拒绝覆盖已有输出 / 64 参数错。
- 探针在核验连接身份（`moz:profile` 必须等于本次创建并启动的 profile）之前只发 `WebDriver:NewSession`；核验不过就停手，且**不发送 `DeleteSession`**，只关自己的 socket。
- 探针的 schema 期望是常量 `ROUTE_SCHEMA_VERSION`（当前 `1.9.0`），检查 7 做**等值**断言；升级时同步这个常量，**不要**改成“存在即可”。
- 检查 22（`22.deep-research-capture-taskkind`，2026-10-02 加固）：必须锁定**唯一** `https://chatgpt.com` 首页句柄并与后台 tabId 对应；发送前读该 tab 的 context（id/pageUrl/revision）、state revision 与既有 capture 集合；请求用本轮唯一标记 `gpt-6-dr-<16hex>`；必须走 page-hook 的 `routeInspectorFetch`（核对 `started===true` 与 `fetchName`）；结果须是发送前不存在、UUID 形态合法且非 `ff-probe*` 的新捕获，taskKind/verdict 均为 `deep_research`，tabId/context/pageUrl 与锁定值一致，state revision 严格增长。缺失/歧义/旧结果/超时一律失败退出 4，**不得**降级为可选。

## 技术栈

TypeScript + esbuild（background=esm，content/UI=iife），vitest，零新增依赖。业务代码 `chrome.*` 保持原样（FF154/156/157 原生返回 Promise，已实测）。

## 目录与约定

- `manifest/manifest.json` 是 Chromium 唯一真相源；`scripts/firefox-manifest.mjs` 做 Firefox 转换（background 双声明、删 chrome 专属、加 gecko）。
- 业务源码不分叉；两 target JS 产物应逐字节一致（除 manifest）——由 `scripts/verify-firefox-dist.mjs` 强制校验，包含引用完整性、路径集合双向比对、`src/ui` 锚点完整性检查，以及 manifest 与源真相（extension==`manifest/manifest.json`、firefox==`toFirefoxManifest(...)`）的完整对象比较；回归测试在 `tests/integration/firefox-dist-verifier.test.ts`。
- 上游新增 UI 页面必须同步加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面。v1.1.0 **没有**新增 UI 入口，`uiEntries` 无需改动。
- `strict_min_version 128.0` 是功能下限（world:MAIN），不是猜的。v1.1.0 唯一新增 CSS 特性是**既有** `:has()`，不抬高下限。
- `release/*.build.json` 是探针的“预期值”，必须与 XPI 同一次打包生成；ZIP 的 mtime 等元数据可能导致重打包哈希变化，比较源码复现时还须逐文件比对。
- 源码快照包必须包含 `tsconfig.json`：esbuild 会自动读取它，缺了会让产出的 JS 少 `"use strict";` 前缀（哈希全部变化）。BUILD-README 的构建步骤必须写全 `npm ci` → `npm run build` → `npm run build:firefox` → `npm run verify:firefox`（`verify:firefox` 同时读两个 target，缺 `dist/extension` 会报错）。
- `docs/**/evidence/*.log` 被全局 `*.log` 规则忽略，提交时必须用**精确路径** `git add -f`（禁止 `git add -f` 整个目录）。本轮证据用 `.txt` 命名，不受该规则影响。
- 上游无 LICENSE 文件；作者署名在 UI 内，不动。

## 当前状态和下一步

- 已闭环：v1.1.0 同步（上游 `dd5ea33`，merge `770095f`）、442 业务测试 + 66 项工具回归通过，FF157.0 真机 **32/32（退出码 0）**；源码 ZIP 仓库外复建与 XPI 30/30 逐文件一致。反向：篡改 XPI 退出 2、输出保护退出 6、坏 manifest 退出 1、禁导航反例第 19 项失败退出 4。证据见 `docs/upgrade-2026-10-01/`。
- v1.1.0 新增断言（检查 20–24）**全部使用合成输入**：20/21/23/24 为合成 observation，22 为真实 page-hook 处理合成创建请求（响应为真实未认证拒绝）。**无真实账号图片生成/深度研究流量证据**。
- 用户真实导出已复核，捕获与部分路由判定有证据；流式完成仍异常，不能称完整通过。真实更新事件、FF128、Chromium E2E 与额度专项验证仍待补，详见 BLOCKED.md（第 15 项为本轮新增边界）。
- 已知抖动：`chatgpt.com` 慢时探针可能超时、检查不完整并退出 5；异步状态有限轮询超时仍失败，不静默通过。“连接不可信”的反例由脚本化 peer 覆盖。见 BLOCKED.md 第 10/11 项。
- 已知项：34 条 live `stream_parse_failed` 根因未确认（上游 v1.1.0 **未**定点修复）；按用户决定暂不改业务代码，**不因升级宣布已解决**。
- 检查 11 只覆盖 bridge→background→浮窗渲染；检查 19/22 要求每阶段证实浏览器实际到达目标路径、后台 context.pageUrl 同步且 revision 更新后，才断言 ID 保持/切换，浮窗读取锁定句柄并核实地址（合成输入 + 真实未认证拒绝）。流式响应身份路径仍未覆盖。
- 检查 22 加固（2026-10-02，报告 `docs/probe-check22-hardening-2026-10-02/HARDENING-REPORT.md`）：未改业务源码/其他检查，仅改探针检查 22 与工具测试。修后探针 `17297ab4…681e`，冻结包真机 32/32 退出 0；未改探针上 13 个非法身份反例曾“不该退出 0 却退出 0”。冻结交付物与历史证据哈希不变。
- v1.1.0 仍保留 1.0.9 公告页与去重逻辑，故**禁止**对版本字符串做全局替换；`src/ui/announcement/`、`upgrade-notice.ts`、`tests/integration/upgrade-notice.test.ts` 的 1.0.9 语义是有意保留的。
- AMO 源码包、签名与安装状态统一见 README-FIREFOX.md；本地可复现不等于已签名或日常安装完成。**本轮未 push**。
- 推私人仓库前确认：`dist/` `coverage/` `node_modules/` `release/` 均被 `.gitignore` 排除；用户真实导出附件在 profile 目录内，永不进仓库。
