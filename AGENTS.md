# AGENTS.md — chatgpt-route-inspector（Firefox 自用移植）

Chromium 上游同源码 + 独立 Firefox 构建 target 的自用移植。读 PROGRESS.md / BLOCKED.md 恢复上下文。
当前同步基线：上游 v1.0.9（`99f982d`），`src/` 与上游逐字节一致。

## 怎么跑

- `npm ci` → `npm run typecheck` / `npm run lint` / `npm test`（301 passed）/ `npm run build`
- Firefox 版：`npm run build:firefox` → `dist/firefox/`；本地加载见 README-FIREFOX.md
- Firefox 产物校验 / 打包：`npm run verify:firefox` / `npm run package:firefox`
- 验证工具回归测试：`npm run test:firefox-tooling`（Python，49 项；合成夹具 + 脚本化 Marionette peer；仅“真实进程/真实浏览器”两项按环境跳过）
- 真机验证探针（**自己启动浏览器**，专用临时 profile）：
  `python ff-marionette.py --xpi <打包产物> --expect-build-record <release/*.build.json> --out <新结果路径>`
  （FF156+ 必须 `-remote-allow-system-access`，探针启动命令已内置；结果进按日期命名的 `ff-probe-results-*.json`，省略 `--out` 时自动生成、绝不覆盖旧文件）
- 探针退出码：0 全通过 / 2 产物身份被拒（含损坏 XPI、不可用构建记录）/ 3 运行异常（含输出路径不可写）/ 4 有检查失败（含**连接不可信时的安全中止**）/ 5 检查没跑全 / 6 拒绝覆盖已有输出 / 64 参数错。
- 探针在核验连接身份（`moz:profile` 必须等于本次创建并启动的 profile）之前只发 `WebDriver:NewSession`；核验不过就停手，且**不发送 `DeleteSession`**，只关自己的 socket。

## 技术栈

TypeScript + esbuild（background=esm，content/UI=iife），vitest，零新增依赖。业务代码 `chrome.*` 保持原样（FF154/156 原生返回 Promise，已实测）。

## 目录与约定

- `manifest/manifest.json` 是 Chromium 唯一真相源；`scripts/firefox-manifest.mjs` 做 Firefox 转换（background 双声明、删 chrome 专属、加 gecko）。
- 业务源码不分叉；两 target JS 产物应逐字节一致（除 manifest）——由 `scripts/verify-firefox-dist.mjs` 强制校验，包含引用完整性、路径集合双向比对与 `src/ui` 锚点完整性检查。
- 上游新增 UI 页面必须同步加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面。
- `strict_min_version 128.0` 是功能下限（world:MAIN），不是猜的。
- `release/*.build.json` 是探针的“预期值”，必须与 XPI 同一次打包生成；ZIP 的 mtime 等元数据可能导致重打包哈希变化，比较源码复现时还须逐文件比对。
- 源码快照包必须包含 `tsconfig.json`：esbuild 会自动读取它，缺了会让产出的 JS 少 `"use strict";` 前缀（哈希全部变化）。
- `docs/**/evidence/*.log` 被全局 `*.log` 规则忽略，提交时必须用**精确路径** `git add -f`（禁止 `git add -f` 整个目录）。
- 上游无 LICENSE 文件；作者署名在 UI 内，不动。

## 当前状态和下一步

- 已闭环：v1.0.5→v1.0.9 同步（merge `99f982d`）、门禁全绿（327 业务测试 + 49 项工具回归）、FF156.0.1 真机 27/27（退出码 0，含 suspect 浮窗提示、公告 HTTPS 目标、新判定与 local-chatgpt 关联检查）、产物身份核对、连接信任前置门禁、损坏输入留证、反向验证（退出码 2）+ 输出保护（退出码 6）。
- 用户真实导出已复核，捕获与部分路由判定有证据；流式完成仍异常，不能称完整通过。真实更新事件、FF128、Chromium E2E 与额度专项验证仍待补，详见 BLOCKED.md。
- 已知非缺陷抖动：`chatgpt.com` 慢时探针报 `9/10` 超时并退出 5（不重试、不静默通过）；“连接不可信”只能靠脚本化 peer 复现。见 BLOCKED.md 第 10/11 项。
- 已知项：34 条 live `stream_parse_failed` 根因未确认（v1.0.9 未改 page-hook/sse-decoder）；按用户决定暂不改业务代码。
- v1.0.9 断线提示卡片的真机触发在 FF156 不可复现（Gecko 不留孤儿内容脚本），逻辑层以上游 mock 集成测试为准，见 BLOCKED 第 12 项。
- AMO 源码包、签名与安装状态统一见 README-FIREFOX.md；本地可复现不等于已签名或日常安装完成。
- 推私人仓库前确认：`dist/` `coverage/` `node_modules/` `release/` 均被 `.gitignore` 排除；用户真实导出附件在 profile 目录内，永不进仓库。
