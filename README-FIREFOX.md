# Firefox 版（自用本地构建）

与 Chromium 共用同一份源码，仅构建产物不同。业务代码零改动。

当前同步基线：上游 `Liu-Bot24/chatgpt-route-inspector` **v1.0.7**（`d5524a0`）。上游业务源码与本仓库 `src/` 逐字节一致，差异只在构建与验证脚本。

## 安装依赖 / 构建

```powershell
npm ci
npm run build:firefox
```

输出目录：`dist/firefox/`（JS 与 Chromium 版字节一致，仅 `manifest.json` 不同）。

## 产物与打包校验

```powershell
npm run verify:firefox    # 两 target 路径集合 / JS 逐字节同源 / manifest+HTML 引用完整性 / gecko 声明
npm run package:firefox   # 打包 dist/firefox -> release/*.xpi，并输出 manifest.json 与逐文件 sha256
```

`package:firefox` 会写出 `release/chatgpt-route-inspector-firefox-<版本>.build.json`，其中 `manifestSha256` 供探针核对，避免误测旧 XPI。

## Firefox 本地加载

1. 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件”。
2. 选择 `dist/firefox/manifest.json`。
3. 打开 `https://chatgpt.com/` 开始使用（页面的 Popup/浮窗/诊断台/设置/公告页与 Chromium 版一致）。

注意：临时加载重启后失效，需重新载入；这是未签名自用构建的正常限制。

## 真机验证探针

```powershell
npm run build:firefox
npm run package:firefox
# 用专用临时 profile 启动（不要用日常 profile）：
& "C:\Program Files\Mozilla Firefox\firefox.exe" -headless -no-remote -marionette `
  -remote-allow-system-access -profile "$env:TEMP\ff-ri-profile" about:blank
python ff-marionette.py --xpi "release\chatgpt-route-inspector-firefox-1.0.7.xpi" `
  --expect-manifest-sha256 <build.json 里的 manifestSha256> `
  --out "ff-probe-results-v1.0.7-<日期>.json" --label <标签> --commit <commit>
```

- **Firefox 156 起必须加 `-remote-allow-system-access`**：否则对扩展页（特权上下文）执行脚本会报
  `ExecuteScript and ExecuteAsyncScript are not supported for privileged browsing contexts`。
  该限制在 154 上不存在，历史 12/12 记录即 FF154 结果。
- `--expect-manifest-sha256` 与 XPI 内 `manifest.json` 实际哈希不一致时探针立即退出（码 2），不会把旧包当本次构建。
- 探针只对**调用方启动的**临时 profile 实例操作；`Addon:Uninstall` 仅作用于该专用 profile。
- 结果 JSON 顶层是 `{meta, results}`，`meta` 记录日期、commit、XPI 与 manifest 哈希、Firefox 版本。

## 已验证

- 2026-09-20，Firefox **156.0**（headless，专用临时 profile），v1.0.7 构建 **18/18 通过**：
  `docs/upgrade-2026-09-20/ff-probe-results-v1.0.7-2026-09-20.json`
  （manifest 零错误加载、后台命名空间与 `await chrome.*`、Popup/诊断台/公告页渲染、合成观测经真实管线判定、
  chatgpt.com 上 MAIN hook 与 ISOLATED 浮窗、1.0.7 公告浮窗入口、capture context 注册、`auto_reasoning` 判定）
- `npm run typecheck / lint / test（301/301）/ build / build:firefox / build:e2e / verify:firefox` 全绿（2026-09-20）。

## 上游更新后

上游业务源码不分叉，常规同步 = 合并上游 + 重新构建：

```powershell
git fetch upstream --tags
git switch -c codex/sync-upstream-<版本>
git merge --no-ff <上游目标 SHA>
npm ci
npm run verify:firefox
npm run build:firefox
```

冲突只会出现在 `scripts/build.mjs`（Firefox target 与上游新增 UI 入口同文件）与 `package.json`。
若上游新增 UI 页面，必须把它加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面（`verify:firefox` 会报路径集合不一致）。

## 已知限制

- `strict_min_version = 128.0`（`content_scripts.world: MAIN` 的 Firefox 支持版本，MDN BCD）。
  **本机只装了 Firefox 156，128 下限未在 128 上实测过**。
- 扩展 ID 为自用 ID（`chatgpt-route-inspector-firefox@local`），未做 AMO 签名。
- 需登录账号的真实对话捕获、真实 1.0.5→1.0.7 更新事件（`onInstalled.reason=update`）尚未验证，见 `BLOCKED.md`。
- 上游仓库无 LICENSE 文件；作者署名保留在扩展 UI 内（未改动）。
