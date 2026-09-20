# AGENTS.md — chatgpt-route-inspector（Firefox 自用移植）

Chromium 上游同源码 + 独立 Firefox 构建 target 的自用移植。读 PROGRESS.md / BLOCKED.md 恢复上下文。
当前同步基线：上游 v1.0.7（`d5524a0`），`src/` 与上游逐字节一致。

## 怎么跑

- `npm ci` → `npm run typecheck` / `npm run lint` / `npm test`（301 passed）/ `npm run build`
- Firefox 版：`npm run build:firefox` → `dist/firefox/`；本地加载见 README-FIREFOX.md
- Firefox 产物校验 / 打包：`npm run verify:firefox` / `npm run package:firefox`
- 验证工具回归测试：`npm run test:firefox-tooling`（Python，合成夹具，不需要真实浏览器）
- 真机验证探针（**自己启动浏览器**，专用临时 profile）：
  `python ff-marionette.py --xpi <打包产物> --expect-build-record <release/*.build.json> --out <新结果路径>`
  （FF156+ 必须 `-remote-allow-system-access`，探针启动命令已内置；结果进按日期命名的 `ff-probe-results-*.json`，省略 `--out` 时自动生成、绝不覆盖旧文件）
- 探针退出码：0 全通过 / 2 产物身份被拒 / 3 运行异常 / 4 有检查失败 / 5 检查没跑全 / 6 拒绝覆盖已有输出。

## 技术栈

TypeScript + esbuild（background=esm，content/UI=iife），vitest，零新增依赖。业务代码 `chrome.*` 保持原样（FF154/156 原生返回 Promise，已实测）。

## 目录与约定

- `manifest/manifest.json` 是 Chromium 唯一真相源；`scripts/firefox-manifest.mjs` 做 Firefox 转换（background 双声明、删 chrome 专属、加 gecko）。
- 业务源码不分叉；两 target JS 产物应逐字节一致（除 manifest）——由 `scripts/verify-firefox-dist.mjs` 强制校验，包含引用完整性、路径集合双向比对与 `src/ui` 锚点完整性检查。
- 上游新增 UI 页面必须同步加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面。
- `strict_min_version 128.0` 是功能下限（world:MAIN），不是猜的。
- `release/*.build.json` 是探针的“预期值”，必须与 XPI 同一次打包生成；zip 记录 mtime，重打包必然改变 XPI 哈希。
- `docs/**/evidence/*.log` 被全局 `*.log` 规则忽略，提交时必须用**精确路径** `git add -f`（禁止 `git add -f` 整个目录）。
- 上游无 LICENSE 文件；作者署名在 UI 内，不动。

## 当前状态和下一步

- 已闭环：v1.0.5→v1.0.7 同步（merge `d5524a0`）、门禁全绿（301 tests + 28 项工具回归）、FF156.0 真机 22/22（退出码 0）、产物四级身份核对、四类反向验证（坏页面/篡改 JS/启动异常/拒绝覆盖）+ 输出保护。
- 未验证项：真实登录对话捕获、真实更新事件（临时加载无法产生 `onInstalled.reason=update`）、FF128 下限实测、`test:e2e`（本机无 extension-capable Chromium）、**额度字段无真机专项检查**。详见 BLOCKED.md。
- 唯一已知项：live 记录偶发 `phase=failed/stream_parse_failed`（详见 BLOCKED.md，上游未定点修复，仍为未确认）。
- 推私人仓库前确认：`dist/` `coverage/` `node_modules/` `release/` 均被 `.gitignore` 排除；用户真实导出附件在 profile 目录内，永不进仓库。
