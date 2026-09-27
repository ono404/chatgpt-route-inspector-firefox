# Firefox 版（自用本地构建）

与 Chromium 共用同一份源码，仅构建产物不同。业务代码零改动。

当前同步基线：上游 `Liu-Bot24/chatgpt-route-inspector` **v1.0.9**（`99f982d`）。上游业务源码与本仓库 `src/` 逐字节一致，差异只在构建与验证脚本。

v1.0.9 行为提示：升级公告改开上游固定站点 `https://rinotice.liu-qi.cn/`（`route:open-announcement` 与真实更新事件各开一次，存储键 `routeInspectorNotice109Shown`）；浮窗新增“疑似降级 / 无法判断”判定与提示；扩展连接失效时浮窗会提示刷新页面。隐私描述见上游 `PRIVACY.md`（2026-09-27 生效版）。

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

> ZIP 会记录文件 mtime 等元数据，重新打包的 XPI 哈希可能变化。记录必须与 XPI 同一次生成；不要把跨次重打包的哈希差异直接当成源码变化。

## AMO 升级提交与源码包（2026-09-27，v1.0.9）

在已有扩展条目上提交新版本，保持 ID `chatgpt-route-inspector-firefox@local` 不变：

- 扩展文件：`release/chatgpt-route-inspector-firefox-1.0.9.xpi`（本地未签名包，XPI SHA-256 `34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523`）。
- 源代码步骤：上传 `release/chatgpt-route-inspector-firefox-1.0.9-source.zip`（170835 字节，SHA-256 `0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0`）；包内 BUILD-README 写明 Windows 11 x64、Node 24.16.0、npm 12.0.1，以及 `npm ci` → `npm run build:firefox`。
- 源码包包含原始源码、资源、`tsconfig.json`（必须！esbuild 自动读取，缺了产出的 JS 少 `"use strict";`、哈希全变）、锁文件与构建脚本，不含用户导出、profile、验证日志或依赖目录。它是 commit `6f932e0` 的提交用源码快照。
- 已从源码包在独立临时目录安装依赖并构建，30 个输出文件与上述未签名 XPI 的路径和内容完全相同（REBUILD_MATCH，2026-09-27）。
- 1.0.7 的 AMO 上传完成、签名下载与日常覆盖安装均未确认；旧版签名包在原工作区 `release/signed/`，不能代替新版签名凭证。1.0.9 尚未提交 AMO。
- 获得签名后在 `about:addons` 齿轮菜单“从文件安装附加组件”覆盖升级；先导出备份，不卸载旧版。覆盖安装会触发一次 `https://rinotice.liu-qi.cn/` 公告页打开（真实更新事件，本轮仍未验证，见 BLOCKED 第 5 项）。

本轮干净安装依赖时 npm 报告 4 项依赖漏洞（3 moderate、1 high）及 esbuild 安装脚本被阻止的警告；构建仍成功。未做漏洞可达性分析，也未执行 `npm audit fix`，不能据此宣称依赖安全已验收。

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
3. 当前 `--dist` 的逐文件哈希 == 构建记录（链条：当前构建 → 记录 → XPI）；
4. 构建记录本身可读且字段类型正确（检查 `0f.build-record`）。

预期值只能来自本次构建记录，探针不会现读待测包给自己生成预期。**manifest 哈希仍然记录并与记录比对，但不是身份通过条件**：同一 `manifest.json` 配不同 JS 的包会被拒绝。

### 连接信任（在发任何状态修改命令之前）

只有 `WebDriver:NewSession` 在核验之前发出，因为身份信息由它返回。核验项（检查 `0e.session-profile`）：浏览器**确实回报**了 `moz:profile`、该目录与本次创建并启动的目录一致、以及路径比较本身没有异常。

任一项不成立时：记录 `0e.session-profile` 与 `0f.untrusted-connection` 失败，**立即停止**后续浏览器检查，并且

- 不发送 `Addon:Install` / `Addon:Uninstall`、不写存储、不导航、不创建扩展页面、不注入合成观测；
- 也**不发送 `WebDriver:DeleteSession`** —— 那可能关掉对端并不属于本任务的浏览器；只关闭自己这个 socket；
- 仍然停止本次启动的进程、删除本次创建的临时目录，并按码 4 退出且写出结果。

### 输入损坏也能留下结果

对合法命令行且输出可写的**新**文件，损坏输入不会抛 traceback，而是写出结果并在浏览器启动前失败：

| 情况 | 行为 |
| --- | --- |
| XPI 不是 ZIP / 已损坏 | `0b/0c/0d` 记失败并附解析错误，`0a` 仍按文件哈希判定；退出码 2 |
| ZIP 内缺 `manifest.json` | 同上，错误说明“archive has no manifest.json at its root” |
| 包内 `manifest.json` 不是合法 JSON | 同上，错误含 `JSONDecodeError` |
| 构建记录不存在 / JSON 非法 / 结构类型错误 | `0f.build-record` 记失败，身份不成立；退出码 2 |

结果 `meta` 含 `stage`、`reachedStages`、`fatal` 或失败检查的 detail、已执行检查、`exitCode`/`exitReason`、`startedAt`/`finishedAt` 与 `summary`（含 `browserLaunched` / `browserConnected` / `connectionTrusted`）。读不到的字段保持 `null` 并附 `identity.parseError`，不伪造完整身份。

### 输出保护

- 省略 `--out`：生成 `ff-probe-results-<label>-<时间戳>.json`，不会碰撞，**永远不会写旧的 `ff-probe-results.json`**。
- 指定的 `--out` 已存在（含“已存在的目录”）：默认拒绝覆盖，退出码 6，原文件字节不变；需要覆盖时显式加 `--force`。
- 输出目录不可创建/不可写：**在启动浏览器之前**就报错到 stderr 并以码 3 退出，不创建也不改动任何文件。

### 退出码

| 码 | 含义 |
| --- | --- |
| 0 | 所有预期检查都执行且全部通过 |
| 2 | 产物身份被拒（在连接浏览器之前），含损坏 XPI / 不可用构建记录 |
| 3 | 运行异常：启动失败、端口不可达、协议异常、清理异常，或输出路径不可写 |
| 4 | 有检查执行后失败；**连接不可信时的安全中止也归此类**（是“前置条件失败”而非“没跑”） |
| 5 | 结果不完整：有必需检查根本没执行（普通检查失败后未继续） |
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

- 2026-09-20，Firefox **156.0**（headless，探针自启的专用临时 profile），v1.0.7 构建 **23/23 通过、退出码 0**：
  `docs/upgrade-2026-09-20/evidence/r3-probe-positive.json`
  （构建记录、产物四项身份检查、会话 profile 与本次启动一致、加载零 manifest 错误、后台命名空间与 `await chrome.*`、
  Popup/诊断台/公告页渲染、合成观测经真实管线判定、chatgpt.com 上 MAIN hook 与 ISOLATED 浮窗、
  1.0.7 公告浮窗入口、capture context 注册、`auto_reasoning` 判定）。
- 反向（同轮实测，见同目录 `r3-*.log` / `.json`）：不存在的公告页 → 退出码 4；
  损坏 XPI / 包内缺 manifest / manifest JSON 非法 → 退出码 2 且写出结果、未启动浏览器；
  构建记录缺失 / 非法 JSON / 结构类型错误 → 退出码 2 且写出结果；
  **连接对端谎报 `moz:profile` → 退出码 4，对端收到的命令只有 `WebDriver:NewSession`（无任何 Addon/存储/导航/会话清理命令）**；
  输出目录不可写 → 退出码 3；`--out` 指向已有文件 → 退出码 6 且原文件哈希不变。
- 已知抖动（非缺陷）：`chatgpt.com` 响应慢时，探针可能报 `9/10.page-hook` 超时并退出 5。探针不重试、不静默通过，实测样本见
  `evidence/r3-probe-negative-badpage-attempt1-navtimeout.*`（同一条命令第二次即恢复为预期的退出码 4）。
- 验证工具回归测试：`npm run test:firefox-tooling`（49 项，合成夹具与脚本化 peer；不需要真实浏览器即可跑，只有“真实进程/真实浏览器”两项会按环境跳过）。
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
- 扩展 ID 为自用 ID（`chatgpt-route-inspector-firefox@local`）；旧版 1.0.5 已有签名包，新版状态见上方 AMO 提交说明。
- 用户真实导出已提供捕获与路由判定证据，但新样本 34 条 live 均报 `stream_parse_failed`；真实更新事件仍未验证。上游存在相同失败路径，尚不能证明同一流量在 Chromium 中也失败，详见 `BLOCKED.md`。
- **额度（`deep_research` / `image_gen`）未做真机专项验证**：真实导出有额度字段，但未与账号界面/重置行为对照，探针也没有专项断言。
- 上游仓库无 LICENSE 文件；作者署名保留在扩展 UI 内（未改动）。
