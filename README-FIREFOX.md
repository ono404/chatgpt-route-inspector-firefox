# Firefox 版（自用本地构建）

> 2026-10-02 交接入口：[HANDOFF.md](docs/handoff-2026-10-02/HANDOFF.md)。本地已同步上游 **v1.1.0**（`dd5ea33`），最近代码提交 `cdbf1b3`；门禁和受控真机正向通过，额外探针边界观察留待接手者判断。
> 交付仍是**未签名本地包**——未上传 AMO、未完成日常覆盖安装。

与 Chromium 共用同一份源码，仅构建产物不同。业务代码零改动。

当前同步基线：上游 `Liu-Bot24/chatgpt-route-inspector` **v1.1.0**（`dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552`，tag `v1.1.0`）。**Git 内容**与上游完全一致（`src/` 等业务目录对上游提交 diff 为空），差异只在构建与验证脚本；本机检出文本因 `core.autocrlf=true` 存在换行转换（相对上游 blob 仅 CRLF/LF 差异，不影响构建产物）。两 target 的 8 个 `.js` 产物字节一致。

v1.1.0 行为提示：新增「**图片生成**」「**深度研究**」两种结论，避免把这两类专用任务误判为降级或路由错配；深度研究记录会分列显示**规划模型**与**报告模型**（两者相互独立，报告模型不参与规划者的路由判定）。升级公告仍走上游固定站点 `https://rinotice.liu-qi.cn/`（包内 1.0.9 公告页与去重逻辑在 v1.1.0 **仍然保留**，真机检查 14/15 照常通过）。浮窗继续保留「疑似降级 / 无法判断」判定与断线提示刷新卡片。隐私描述见上游 `PRIVACY.md`。

当前交付工作区：`D:\LAB\sync-v109-isolated`，分支 `codex/sync-upstream-v1.1.0`。本轮报告与证据见 [升级报告](docs/upgrade-2026-10-01/UPGRADE-REPORT.md)。

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
6. **manifest 完整对象比较**（2026-09-27 补强）：extension 侧 `manifest.json` 必须整体等于源真相 `manifest/manifest.json`，Firefox 侧必须整体等于 `toFirefoxManifest(manifest/manifest.json)`（复用构建同一转换函数，`node:assert` 深比较；键序与缩进不参与比较）。替换了旧的逐字段守卫——旧写法对 version 改错、增加 permissions/host_permissions、改 MAIN world、清空 `background.scripts`、改 `background.type`、`data_collection_permissions` 多值等情况会漏检（回归测试 `tests/integration/firefox-dist-verifier.test.ts` 固定这 7 类变异）。

**已知边界**：仅靠第 1 条的两侧互比，无法发现“两个 target 同时漏掉”某个新增页面。第 5 条把这一盲区收窄到存在于 `src/` 的 UI 页面，但仍**看不到**“上游新增了 `uiEntries` 条目而对应 HTML/TS 文件不存在”的情况，也看不到非 HTML 资源的遗漏。

`package:firefox` 写出 `release/chatgpt-route-inspector-firefox-<版本>.build.json`：包含 XPI 整体 sha256、manifest sha256、逐文件 sha256、`distDir` 与打包时间。打包后脚本会**回读刚写出的压缩包**，与 `dist/firefox` 逐文件比对，不一致就不写记录（非零退出）。该记录是探针的“预期值”来源。

> ZIP 会记录文件 mtime 等元数据，重新打包的 XPI 哈希可能变化。记录必须与 XPI 同一次生成；不要把跨次重打包的哈希差异直接当成源码变化。

## v1.1.0 AMO 提交资料（2026-10-01，尚未上传）

以下是本轮生成的交付物；**尚未上传 AMO、尚未签名**：

- 扩展文件：`release/chatgpt-route-inspector-firefox-1.1.0.xpi`（本地未签名包，155451 字节，XPI SHA-256 `04af228b03f85e954d894a859fb87afcf1bfbc9cd449da881c2f25f99c0165ae`）。
- 同次构建记录：`release/chatgpt-route-inspector-firefox-1.1.0.build.json`（SHA-256 `a2028179ed18602da5d6be288dd2142a0140dab0d64bfdb6fcd267afaba263a1`）。
- 源代码步骤：上传 `release/chatgpt-route-inspector-firefox-1.1.0-source.zip`（76 条目，SHA-256 `51523360d4063fc939177672b9bf990278a1e0495f4e715f5e22b0cc49888846`）；包内 BUILD-README 写明 Windows 11 x64、Node 24.16.0、npm 12.0.1，以及完整构建步骤 `npm ci` → `npm run build` → `npm run build:firefox` → `npm run verify:firefox`。
- 源码包包含原始源码、资源、`tsconfig.json`（必须！esbuild 自动读取，缺了产出的 JS 少 `"use strict";`）、锁文件与全部构建脚本，不含用户导出、profile、验证日志、探针、测试源码或依赖目录。它是 `770095f` 的提交用源码快照。
- **已从源码包在独立临时目录安装依赖并构建**（`npm ci` → `build` → `build:firefox` → `verify:firefox` 全部退出 0），30 个输出文件与上述未签名 XPI 的**路径和内容逐文件完全相同**（REBUILD_MATCH，2026-10-01，脚本 `compare.py` 在仓库外运行）。
- 既有扩展 ID `chatgpt-route-inspector-firefox@local`、`strict_min_version 128.0` 保持不变。旧版签名包在原工作区 `release/signed/`，不能代替新版签名凭证。
- 获得签名后在 `about:addons` 齿轮菜单“从文件安装附加组件”覆盖升级；先导出备份，不卸载旧版。符合版本条件且未记录已展示的覆盖安装按代码设计会触发一次 `https://rinotice.liu-qi.cn/` 公告页打开（真实更新事件，本轮仍未验证，见 BLOCKED 第 5 项）。

本轮干净安装依赖时 npm 报告 5 项依赖漏洞（3 moderate、2 high）及 esbuild 安装脚本被阻止的警告；构建仍成功。未做漏洞可达性分析，也未执行 `npm audit fix`，不能据此宣称依赖安全已验收。

### 上一版（v1.0.9）历史资料（保留备查）

`release/chatgpt-route-inspector-firefox-1.0.9.xpi`（XPI SHA-256 `34ca9440…da523`）、源码 ZIP `0cc2412f…3d0`、build.json `15debe2a…9dab` 均未改动，仍可用于回归对照。

## Firefox 本地加载

1. 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件”。
2. 选择 `dist/firefox/manifest.json`。
3. 打开 `https://chatgpt.com/` 开始使用（页面的 Popup/浮窗/诊断台/设置/公告页与 Chromium 版一致）。

注意：临时加载重启后失效，需重新载入；这是未签名自用构建的正常限制。

## 真机验证探针

探针**自己启动浏览器**：创建全新专用临时 profile、自行挑选一个空闲端口、以隐藏窗口启动 Firefox、连接、跑完检查、只停掉自己启动的那个实例，随后删除自己创建的 profile（`--keep-profile` / `--keep-browser` 可保留）。它不会附着到、也不会停止任何它没有启动的浏览器，也不碰日常 profile。

```powershell
Set-Location D:\LAB\sync-v109-isolated
# 复验使用冻结 XPI、同次 build.json 和匹配 dist，不要重新打包。
py -B ff-marionette.py `
  --xpi "release\chatgpt-route-inspector-firefox-1.1.0.xpi" `
  --expect-build-record "release\chatgpt-route-inspector-firefox-1.1.0.build.json" `
  --dist "dist\firefox" `
  --out "docs\upgrade-2026-10-01\evidence\probe-<新场景>.json" `
  --label <标签> --commit <commit>
```

> `python` 在本机是 WindowsApps 别名（退出 9009），一律用 `py`。

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

## 已验证（2026-10-01，v1.1.0）

- v1.1.0 同步门禁：**442 项业务测试**（38 文件）、typecheck、lint、build、build:firefox、build:notice、build:e2e、verify:firefox、package:firefox 全部退出 0；工具回归 **66 项通过**；源码 ZIP 仓库外复建与 XPI **30/30 文件逐文件一致**。完整记录见 [升级报告](docs/upgrade-2026-10-01/UPGRADE-REPORT.md)。
- Firefox **157.0** 专用临时 profile 中正式包 **32/32，退出 0**（`moz:buildID=20260924084938`，连接信任前置门禁通过）。相对 v1.0.9 的 27 项，保留原有全部检查语义，新增检查 **20–24**：图片/研究任务 verdict、规划/报告模型分离、真实 page-hook 的任务识别（检查 22 拿到 hook 生成的真实 UUID，非预填）、诊断台两个新标签与两行模型展示。
- 红→绿：适配前同一 v1.1.0 包 **26 passed / 1 failed**（检查 7 的 schema 期望 1.8.0 vs 实际 1.9.0）退出 4；适配后 32/32 退出 0。schema 期望改为与 `ROUTE_SCHEMA_VERSION` 等值比较，并保留两个错误 schema 反例（1.8.0 / 2.0.0 均须失败）。
- 真机反向（仓库外临时副本）：篡改 XPI 退出 **2**（浏览器未启动，`0d.manifest-sha256` PASS 而 `0a/0b/0c` FAIL）；已有 `--out` 退出 **6** 且原文件哈希不变；坏 manifest 经真实 CLI 退出 **1**、还原后 **0**；禁导航反例身份通过后第 19 项 FAIL、退出 **4**。
- 检查 11 从 postMessage 注入合成观测，只覆盖 bridge→background→浮窗；检查 19 与 22 经真实 page-hook，但输入为合成请求、响应为真实未认证拒绝。**均不覆盖成功 SSE 内的会话身份、模型路由或真实账号完整流量。**
- `test:e2e` 本轮再次尝试仍退出 1：缺 extension-capable Chromium，1 failed / 12 did not run。构建 E2E 通过不等于 E2E 执行通过。其余边界见 [BLOCKED](BLOCKED.md) 第 15 项。

### 检查 22 误报加固（2026-10-02）

- 背景：`22.deep-research-capture-taskkind` 此前只在“有 taskKind=deep_research 且 captureId 不以 `ff-probe` 开头”时通过，captureId 缺失会被转成空串而误通过——缺失/空/伪造身份、旧记录、错标记、错 tab、无 revision 增长均可冒充本轮捕获。
- 加固后判定（冻结包真机 **32/32，退出 0**，探针 `17297ab4…681e`，继续绑定原 XPI `04af228b…65ae`）：锁定**唯一** `https://chatgpt.com` 首页句柄 ↔ 后台 tabId；发送前读该 tab 的 context/state revision/既有 capture 集合；本轮唯一标记 `gpt-6-dr-<16hex>`；必须走 page-hook 的 `routeInspectorFetch`；结果是发送前不存在、合法 UUID 且非 `ff-probe*` 的新捕获，taskKind/verdict 均 `deep_research`，tabId/context/pageUrl 一致，state revision 严格增长（真机 14→17）；异常一律失败退出 4。
- 红→绿：未改探针上 **13** 个非法身份反例“不该退出 0 却退出 0”；加固后工具回归 **82 项**（66 基线 + 16 新增）全过。报告 [HARDENING-REPORT](docs/probe-check22-hardening-2026-10-02/HARDENING-REPORT.md)。

### 历史验收（v1.0.9，2026-09-27）

- 327 项业务测试 / 工具 56 项；Firefox 156.0.1 正式包 27/27 退出 0。详见 [v1.0.9 独立验收](docs/upgrade-2026-09-27/independent-acceptance/ACCEPTANCE.md)。
- 更早的损坏输入及连接信任证据保留在 [v1.0.7 历史报告](docs/upgrade-2026-09-20/UPGRADE-REPORT.md)，其 301/49/23 项结果不代表当前版本计数。

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
  **本机只装了 Firefox 157，128 下限未在 128 上实测过**。
- 扩展 ID 为自用 ID（`chatgpt-route-inspector-firefox@local`）；旧版 1.0.5 已有签名包，新版状态见上方 AMO 提交说明。
- 用户真实导出已提供捕获与路由判定证据，但新样本 34 条 live 均报 `stream_parse_failed`；上游 v1.1.0 **未**对该路径定点修复，本轮**不宣布已解决**。真实更新事件（1.0.9→1.1.0）仍未验证。详见 `BLOCKED.md` 第 4/5 项。
- **额度（`deep_research` / `image_gen`）未做真机专项验证**：真实导出有额度字段，但未与账号界面/重置行为对照，探针也没有专项断言。
- v1.1.0 的图片/研究任务断言**全部使用合成输入**（检查 20/21/23/24 为合成 observation，检查 22 为合成创建请求 + 真实未认证拒绝响应），**没有真实账号的图片生成或深度研究流量证据**。
- 上游仓库无 LICENSE 文件；作者署名保留在扩展 UI 内（未改动）。
