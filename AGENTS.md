# AGENTS.md — chatgpt-route-inspector（Firefox 自用移植）

Chromium 上游同源码 + 独立 Firefox 构建 target 的自用移植。读 PROGRESS.md / BLOCKED.md 恢复上下文。

## 怎么跑

- `npm ci` → `npm run typecheck` / `npm run lint` / `npm test`（94 passed）/ `npm run build`
- Firefox 版：`npm run build:firefox` → `dist/firefox/`；本地加载见 README-FIREFOX.md
- 真机验证探针：`python ff-marionette.py`（需本机 Firefox + Marionette），结果进 `ff-probe-results.json`

## 技术栈

TypeScript + esbuild（background=esm，content/UI=iife），vitest，零新增依赖。业务代码 `chrome.*` 保持原样（FF154 原生返回 Promise，已实测）。

## 目录与约定

- `manifest/manifest.json` 是 Chromium 唯一真相源；`scripts/firefox-manifest.mjs` 做 Firefox 转换（background 双声明、删 chrome 专属、加 gecko）。
- 业务源码不分叉；两 target JS 产物应逐字节一致（除 manifest）。
- `strict_min_version 128.0` 是功能下限（world:MAIN），不是猜的。
- 上游无 LICENSE 文件；作者署名在 UI 内，不动。

## 当前状态和下一步

- 已闭环：构建、测试、FF154 真机 12/12、用户登录态导出取证全过。
- 唯一已知项：live 记录偶发 `phase=failed/stream_parse_failed`（尾部流问题，verdict 正确，详见 BLOCKED.md）。
- 推私人仓库前确认：`dist/` `coverage/` `node_modules/` 均被 `.gitignore` 排除；用户真实导出附件在 profile 目录内，永不进仓库。
