# Firefox 版（自用本地构建）

与 Chromium 共用同一份源码，仅构建产物不同。业务代码零改动。

## 安装依赖 / 构建

```powershell
npm ci
npm run build:firefox
```

输出目录：`dist/firefox/`（JS 与 Chromium 版字节一致，仅 `manifest.json` 不同）。

## Firefox 本地加载

1. 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件”。
2. 选择 `dist/firefox/manifest.json`。
3. 打开 `https://chatgpt.com/` 开始使用（页面的 Popup/浮窗/诊断台/设置与 Chromium 版一致）。

注意：临时加载重启后失效，需重新载入；这是未签名自用构建的正常限制。

## 已验证

- Firefox 154.0.1，真机 headless 实测 12/12（`ff-probe-results.json`，探针 `ff-marionette.py` 可重跑）：
  Manifest 零错误加载、后台启动、onboarding 自开、`await chrome.*`（storage/tabs/runtime/i18n/action-badge）原生可用、
  Popup/诊断台渲染、合成观测经真实管线判为 mismatch、chatgpt.com 上 MAIN 世界 fetch hook 与 ISOLATED 浮窗均工作。
- `npm run typecheck / lint / test（94/94）/ build / build:e2e / build:firefox` 全绿。

## 上游更新后

```powershell
git pull upstream main
npm ci
npm run build:firefox
```

Firefox 差异集中在 `scripts/firefox-manifest.mjs` + `scripts/build.mjs` 的 firefox target；上游业务变更无需合代码，直接重构建即可。

## 已知限制

- `strict_min_version = 128.0`（`content_scripts.world: MAIN` 的 Firefox 支持版本，MDN BCD）。
- 扩展 ID 为自用 ID（`chatgpt-route-inspector-firefox@local`），未做 AMO 签名。
- 需登录账号的真实对话捕获与长时间控制台观察尚未验证，步骤见 `BLOCKED.md`。
- 上游仓库无 LICENSE 文件；作者署名保留在扩展 UI 内（未改动）。
