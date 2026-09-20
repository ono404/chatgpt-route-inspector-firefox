# Firefox 版（自用本地构建）

与 Chromium 共用同一份源码，仅构建产物不同。业务代码零改动。

当前同步基线：上游 `Liu-Bot24/chatgpt-route-inspector` **v1.0.7**（`d5524a0`）。上游业务源码与本仓库 `src/` 逐字节一致，差异只在构建与验证脚本。

## 安装依赖 / 构建

```powershell
npm ci
npm run build            # dist/extension（Chromium）
npm run build:firefox    # dist/firefox
```

输出目录：`dist/firefox/`（JS 与 Chromium 版字节一致，仅 `manifest.json` 不同）。

## 产物校验与打包

```powershell
npm run verify:firefox    # 产物完整性 / 同源校验
npm run package:firefox   # 打包 dist/firefox -> release/*.xpi，并写出构建记录
```

`verify:firefox` 检查的内容：

1. 两个 target 的**路径集合双向比对**（任一侧缺失即失败）；
2. 除 `manifest.json` 外逐文件字节一致，所有 `.js` 强制逐字节一致；
3. 任一 `manifest.json` 引用的本地文件都存在；
4. 任一产物内 `.html` 引用的本地文件都存在；
5. 以 `src/ui/**/index.html` 为锚点，确认每个 UI 页面都进了**两个** target；
6. Firefox 侧 gecko 声明守卫（`manifest_version` / 无 `minimum_chrome_version` / ID / `strict_min_version` / `data_collection_permissions`）。

**已知边界**：仅靠第 1 条的两侧互比，无法发现“两个 target 同时漏掉”某个新增页面。第 5 条把这一盲区收窄到存在于 `src/` 的 UI 页面，但仍**看不到**“上游新增了 `uiEntries` 条目而对应 HTML/TS 文件不存在”的情况，也看不到非 HTML 资源的遗漏。

`package:firefox` 写出 `release/chatgpt-route-inspector-firefox-<版本>.build.json`：包含 XPI 整体 sha256、manifest sha256、逐文件 sha256、`distDir` 与打包时间。打包后脚本会**回读刚写出的压缩包**，与 `dist/firefox` 逐文件比对，不一致就不写记录（非零退出）。该记录是探针的“预期值”来源。

> zip 会记录每个文件的 mtime，因此**每次重新打包 XPI 哈希都会变**。记录必须与 XPI 同一次生成；不要把跨次重打包的哈希差异当成源码变化。

## Firefox 本地加载

1. 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件”。
2. 选择 `dist/firefox/manifest.json`。
3. 打开 `https://chatgpt.com/` 开始使用（页面的 Popup/浮窗/诊断台/设置/公告页与 Chromium 版一致）。

注意：临时加载重启后失效，需重新载入；这是未签名自用构建的正常限制。

## 真机验证探针

探针**自己启动浏览器**：创建全新专用临时 profile、自行挑选一个空闲端口、以隐藏窗口启动 Firefox、连接、跑完检查、只停掉自己启动的那个实例，随后删除自己创建的 profile（`--keep-profile` / `--keep-browser` 可保留）。它不会附着到、也不会停止任何它没有启动的浏览器，也不碰日常 profile。

```powershell
npm run build:firefox
npm run package:firefox

python ff-marionette.py `
  --xpi "release\chatgpt-route-inspector-firefox-1.0.7.xpi" `
  --expect-build-record "release\chatgpt-route-inspector-firefox-1.0.7.build.json" `
  --out "docs\upgrade-2026-09-20\evidence\probe-<场景>.json" `
  --label <标签> --commit <commit>
```

### 产物身份（在连接浏览器之前完成）

必须**同时**成立，否则退出码 2 且不会安装/卸载任何东西：

1. XPI 整体 sha256 == 构建记录（或 `--expect-xpi-sha256`）给出的预期值；
2. XPI 内路径集合与逐文件内容 == `--dist`（默认 `dist/firefox`）当前内容；
3. 当前 `--dist` 的逐文件哈希 == 构建记录（链条：当前构建 → 记录 → XPI）。

预期值只能来自本次构建记录，探针不会现读待测包给自己生成预期。**manifest 哈希仍然记录并与记录比对，但不是身份通过条件**：同一 `manifest.json` 配不同 JS 的包会被拒绝。

### 输出保护

- 省略 `--out`：生成 `ff-probe-results-<label>-<时间戳>.json`，不会碰撞，**永远不会写旧的 `ff-probe-results.json`**。
- 指定的 `--out` 已存在：默认拒绝覆盖，退出码 6，原文件字节不变；需要覆盖时显式加 `--force`。

### 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 所有预期检查都执行且全部通过 |
| 2 | 产物身份被拒（在连接浏览器之前） |
| 3 | 运行异常：启动失败、端口不可达、协议异常或清理异常 |
| 4 | 有检查执行后失败 |
| 5 | 结果不完整：有必需检查根本没执行 |
| 6 | 拒绝覆盖已存在的 `--out` |
| 64 | 命令行参数错误 |

失败时仍会尽量写出结果文件（含已跑过的检查、失败原因与汇总），不会因为清理过程把失败吞掉。

### `meta` 记录内容

实际起止时间、`probeSha256`、被测 XPI / manifest 哈希、构建记录路径与记录自身 sha256、`git` HEAD 与是否存在未提交修改（含 `git status --porcelain` 原文）、本次启动的浏览器 exe / pid / 端口 / profile 绝对路径 / 完整命令行，以及浏览器**自己回报**的 `moz:profile`、`moz:buildID`、`browserVersion`、`moz:headless`。

profile 以浏览器回报的 `moz:profile` 为准并校验其等于本次启动用的临时目录（检查 `0e.session-profile`）；环境变量或调用方标签不能冒充。

### 环境注意事项

- **Firefox 156 起必须 `-remote-allow-system-access`**（探针启动命令已内置）：否则对扩展页（特权上下文）执行脚本会报
  `ExecuteScript and ExecuteAsyncScript are not supported for privileged browsing contexts`。
  该限制只影响探针工具，不影响扩展自身运行；FF154 无此限制，历史 12/12 是 FF154 结果。

## 已验证

- 2026-09-20，Firefox **156.0**（headless，探针自启的专用临时 profile），v1.0.7 构建 **22/22 通过、退出码 0**：
  `docs/upgrade-2026-09-20/evidence/r2-probe-positive.json`
  （产物四项身份检查、加载零 manifest 错误、后台命名空间与 `await chrome.*`、Popup/诊断台/公告页渲染、
  合成观测经真实管线判定、chatgpt.com 上 MAIN hook 与 ISOLATED 浮窗、1.0.7 公告浮窗入口、
  capture context 注册、`auto_reasoning` 判定、会话 profile 与本次启动一致）。
- 反向（同一轮实测，见同目录 `r2-probe-negative-*.log` / `.json`）：不存在的公告页 → 退出码 4；
  篡改一个 JS 保持 manifest 不变 → 退出码 2 且未连接浏览器；浏览器启动异常 → 退出码 3；
  `--out` 指向已有文件 → 退出码 6 且原文件哈希不变。
- 验证工具回归测试：`npm run test:firefox-tooling`（28 项，合成夹具，不依赖真实浏览器）。
- `npm run typecheck / lint / test（301/301）/ build / build:firefox / build:e2e / verify:firefox / package:firefox` 全绿（2026-09-20）。

## 上游更新后

上游业务源码不分叉，常规同步 = 合并上游 + 重新构建：

```powershell
git fetch upstream --tags
git switch -c codex/sync-upstream-<版本>
git merge --no-ff <上游目标 SHA>
npm ci
npm run build            # 先构建两个普通目标
npm run build:firefox
npm run verify:firefox   # 再校验：它读的是已经构建好的 dist，必须放在 build 之后
npm run test:firefox-tooling
```

合并冲突可能出现在任何被双方同时修改的文件上，不限于某个固定清单；`scripts/build.mjs` 与 `package.json` 是历史上最常同时被改的两个。
若上游新增 UI 页面，必须把它加入 `scripts/build.mjs` 的 `uiEntries`，否则 Firefox 产物缺页面（`verify:firefox` 会报路径集合不一致）。

## 已知限制

- `strict_min_version = 128.0`（`content_scripts.world: MAIN` 的 Firefox 支持版本，MDN BCD）。
  **本机只装了 Firefox 156，128 下限未在 128 上实测过**。
- 扩展 ID 为自用 ID（`chatgpt-route-inspector-firefox@local`），未做 AMO 签名。
- 需登录账号的真实对话捕获、真实 1.0.5→1.0.7 更新事件（`onInstalled.reason=update`）尚未验证，见 `BLOCKED.md`。
- **额度（`deep_research` / `image_gen`）未做真机专项验证**：现有探针项目里没有额度专项检查，仅有上游单元/集成测试结论。
- 上游仓库无 LICENSE 文件；作者署名保留在扩展 UI 内（未改动）。
