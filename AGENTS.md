# AGENTS.md — chatgpt-route-inspector（Firefox 自用移植）

Chromium 上游同源码 + 独立 Firefox 构建 target 的自用移植。读 PROGRESS.md / BLOCKED.md 恢复上下文。
> 2026-10-01：上游已发布 v1.1.0（标签 `dd5ea33`），本地仍是 v1.0.9，尚未同步新版或完成日常覆盖安装、真实流量验收。当前有未提交的校验器补强、回归测试和文档；先读 PROGRESS.md 顶部现役交接，升级时保全这些改动。下方 v1.0.9 数字只适用于该版。
当前同步基线：上游 v1.0.9（`99f982d`），Git 内容与上游一致；本机检出文本存在换行转换（`core.autocrlf=true`，相对上游 blob 仅 CRLF/LF 差异）。
当前交付位于 `D:\LAB\sync-v109-isolated`，分支 `codex/sync-upstream-v1.0.9`；原工作区仍为 v1.0.7，勿混用产物。独立验收见 [验收记录](docs/upgrade-2026-09-27/independent-acceptance/ACCEPTANCE.md)。

## 怎么跑

- `npm ci` → `npm run typecheck` / `npm run lint` / `npm test`（v1.0.9 校验补强后上次实测 336 passed，含未提交 9 项；本次知识收尾未重跑）/ `npm run build`
- Firefox 版：`npm run build:firefox` → `dist/firefox/`；本地加载见 README-FIREFOX.md
- Firefox 产物校验 / 打包：`npm run verify:firefox` / `npm run package:firefox`
- 验证工具回归测试：`npm run test:firefox-tooling`（Python，56 项；合成夹具 + 脚本化 Marionette peer；仅“真实进程/真实浏览器”两项按环境跳过）
- 真机验证探针（**自己启动浏览器**，专用临时 profile）：
  `python ff-marionette.py --xpi <打包产物> --expect-build-record <release/*.build.json> --out <新结果路径>`
  （FF156+ 必须 `-remote-allow-system-access`，探针启动命令已内置；结果进按日期命名的 `ff-probe-results-*.json`，省略 `--out` 时自动生成、绝不覆盖旧文件）
- 探针退出码：0 全通过 / 2 产物身份被拒（含损坏 XPI、不可用构建记录）/ 3 运行异常（含输出路径不可写）/ 4 有检查失败（含**连接不可信时的安全中止**）/ 5 检查没跑全 / 6 拒绝覆盖已有输出 / 64 参数错。
- 探针在核验连接身份（`moz:profile` 必须等于本次创建并启动的 profile）之前只发 `WebDriver:NewSession`；核验不过就停手，且**不发送 `DeleteSession`**，只关自己的 socket。

## 技术栈

TypeScript + esbuild（background=esm，content/UI=iife），vitest，零新增依赖。业务代码 `chrome.*` 保持原样（FF154/156 原生返回 Promise，已实测）。

## 目录与约定

- `manifest/manifest.json` 是 Chromium 唯一真相源；`scripts/firefox-manifest.mjs` 做 Firefox 转换（background 双声明、删 chrome 专属、加 gecko）。
- 业务源码不分叉；两 target JS 产物应逐字节一致（除 manifest）——由 `scripts/verify-firefox-dist.mjs` 强制校验，包含引用完整性、路径集合双向比对、`src/ui` 锚点完整性检查，以及 manifest 与源真相（extension==`manifest/manifest.json`、firefox==`toFirefoxManifest(...)`）的完整对象比较；回归测试在 `tests/integration/firefox-dist-verifier.test.ts`。
- 上游新增 UI 页面必须同步加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面。
- `strict_min_version 128.0` 是功能下限（world:MAIN），不是猜的。
- `release/*.build.json` 是探针的“预期值”，必须与 XPI 同一次打包生成；ZIP 的 mtime 等元数据可能导致重打包哈希变化，比较源码复现时还须逐文件比对。
- 源码快照包必须包含 `tsconfig.json`：esbuild 会自动读取它，缺了会让产出的 JS 少 `"use strict";` 前缀（哈希全部变化）。
- `docs/**/evidence/*.log` 被全局 `*.log` 规则忽略，提交时必须用**精确路径** `git add -f`（禁止 `git add -f` 整个目录）。
- 上游无 LICENSE 文件；作者署名在 UI 内，不动。

## 当前状态和下一步

- 已闭环：v1.0.9 同步（上游 `99f982d`，merge `55d3ccf`）、327 业务测试 + 56 项工具回归通过，FF156.0.1 真机 27/27（退出码 0）；旧 tracker 与禁导航反例均身份通过后在第 19 项失败、退出 4。产物篡改拒绝退出 2，输出保护退出 6。覆盖范围与证据见独立验收记录。
- 用户真实导出已复核，捕获与部分路由判定有证据；流式完成仍异常，不能称完整通过。真实更新事件、FF128、Chromium E2E 与额度专项验证仍待补，详见 BLOCKED.md。
- 已知抖动：`chatgpt.com` 慢时探针可能超时、检查不完整并退出 5；异步状态有限轮询超时仍失败，不静默通过。“连接不可信”的反例由脚本化 peer 覆盖。见 BLOCKED.md 第 10/11 项。
- 已知项：34 条 live `stream_parse_failed` 根因未确认（v1.0.9 未改 page-hook/sse-decoder）；按用户决定暂不改业务代码。
- v1.0.9 断线提示卡片在本轮 FF156.0.1 尝试中未复现，不能推广为所有场景不可复现；目前以上游 mock 集成测试为依据，见 BLOCKED 第 12 项。
- 探针第 11 项只覆盖 bridge→background→浮窗渲染；第 19 项真实导航检查要求每阶段证实浏览器实际到达目标路径、后台 context.pageUrl 同步且 revision 更新后，才断言 ID 保持/切换，浮窗读取锁定句柄并核实地址（合成输入 + 真实未认证拒绝，见 docs/upgrade-2026-09-27/review-fix-round2/REVIEW-FIX-ROUND2-REPORT.md）；流式响应身份路径仍未覆盖。
- AMO 源码包、签名与安装状态统一见 README-FIREFOX.md；本地可复现不等于已签名或日常安装完成。
- 推私人仓库前确认：`dist/` `coverage/` `node_modules/` `release/` 均被 `.gitignore` 排除；用户真实导出附件在 profile 目录内，永不进仓库。
