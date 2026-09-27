# v1.0.9 独立验收（2026-09-27）

对象：D:\LAB\sync-v109-isolated，提交 4ae924d，固定上游 99f982dd089b020afa85b897b07edfb340cc58dd。
结论：源码同步与交付包一致性通过；验证证据需要修正，暂不接受“全量验证完成”。未发现本次 Firefox 业务源码分叉；以下发现是验证缺口，不是认定交付包存在导航缺陷。

## P2：第 19 项无法发现新会话导航修复失效

位置：ff-marionette.py:875-905。
该检查预填相同 captureId 和 captureContextId，再从扩展页直接发送 route:observation，断言后台合并为一条记录。没有调用页面 history 导航，没有让 page-hook/CaptureContextTracker 生成和延续 ID，也没有检查切换页面后的当前浮窗记录。因此它验证的是既有后台合并，不能验证 v1.0.9 的临时会话导航修复。

独立反向实验（全部在本报告旁的临时 source/source 中，正式源码和交付包未改）：
1. 从交付源码 ZIP 解压、npm ci、构建；Firefox 30 个输出路径和内容与正式 XPI 完全一致。
2. 仅把临时副本 src/core/capture-context.ts 恢复为 d5524a0 的旧文件，重新构建打包并生成匹配的新预期记录，使身份检查合法通过。
3. 用真实 tracker 代码调用 startLive() → navigate('/c/local-chatgpt%3Adraft')：交付版保留 ID，旧 tracker 改变 ID。见 tracker-comparison.json。
4. 原封不动运行 4ae924d 的完整 Firefox 探针检测该故障副本，仍然 27/27、退出码 0；第 19 项 PASS。见 mutant-probe.json。

最小修正：保留业务源码与上游一致，只修验证入口。第 19 项必须经过真实 page-hook 的受控合成输入和页面 history 导航，让受测代码自己产生捕获关联，再断言临时地址→正式地址的当前记录与无关会话隔离。沿用本次故障副本做反向验证，要求修复后的探针在导航语义检查上失败（不能只靠包身份拒绝），正式包通过。做不到则明确列为真机未覆盖，不再把 27/27 当该场景已验证。

## P2：第 11 项的管线说明越过实际验证范围

位置：ff-marionette.py:679-684，docs/upgrade-2026-09-27/UPGRADE-REPORT.md:61。
注释与报告声称“真实 page-hook → bridge → background”。实际注入 window.postMessage 的已解析 observation 信封，跳过 page-hook 的 fetch/WebSocket 捕获和解析；真正覆盖 bridge → background → 浮窗渲染。此检查本身对后半段有效，只需准确改名/改说明；无需为修文案改业务代码。

## 独立重跑结果

- 当前工作区与最终提交的 src/schemas/_locales/icons/manifest 对固定上游均无差异，上游测试亦原样保留。
- typecheck、lint 退出 0；34 文件 327 测试通过，0 失败/跳过；覆盖率 97.29% statements、91.81% branches、100% functions。
- Firefox tooling 49 项通过；verify:firefox 通过，30/30 路径一致、8 个 JS 同源。
- 交付源码包在新的仓库外目录 npm ci、build、build:firefox、build:e2e（包含 build:notice）全部退出 0。
- 源码 ZIP 的业务文件集合及内容与交付仓库一致；复建 Firefox 30/30 与 XPI 逐文件一致；XPI、build.json 的 30 项哈希一致。
- 正式包 Firefox 探针 27/27、退出 0，见 positive.json；这仅证明当前断言通过，不扩大其覆盖范围。
- 保持 manifest 不变、篡改 JS 的包退出 2，未启动浏览器，见 tampered.json。
- 已有输出路径保护退出 6。
- Chromium E2E 重新运行退出 1：No extension-capable Chromium found；13 项中首项在 beforeAll 失败，后 12 项未运行，不是产品断言失败。
- FF128、真实更新、真实流量 stream_parse_failed、断线提示卡片、签名与日常安装仍未验证。
- 当前验收没有修改交付仓库源码或提交。隔离 worktree 仍干净，原工作区仍为 909941e、四份文档修改与 .workbuddy/ 未跟踪状态。三个原文档与 b1f06aa 快照一致；PROGRESS 快照另含执行者开工回执。

## 交付包复算

XPI SHA256: 34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523
Source ZIP SHA256: 0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0
旧最终探针记录的 probeSha256 与当前 ff-marionette.py 文件哈希相符。

本目录 mutant-package 是故意撤回修复的验收故障夹具，不是交付物，不能用于日常安装。审查脚本、故障副本和 JSON 仅存于该临时验收目录，未进 Git。
