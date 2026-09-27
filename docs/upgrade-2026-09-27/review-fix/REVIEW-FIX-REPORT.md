# 复审修正报告：新会话导航验证（2026-09-27）

对应管理者独立验收 `REVIEW.md`（P2 两项）。本轮只改验证工具与文档；业务源码、正式交付包、旧证据零改动。

## 1. 交付物哈希复核（本轮首尾各核一次，均未变）

| 文件 | SHA-256 |
| --- | --- |
| `release/chatgpt-route-inspector-firefox-1.0.9.xpi` | `34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523` |
| `release/chatgpt-route-inspector-firefox-1.0.9-source.zip` | `0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0` |
| `release/chatgpt-route-inspector-firefox-1.0.9.build.json` | `15debe2ae37957a21c7f91161e6627acc33afdd6dd67e29ae00268b6451e9dab` |

## 2. P2-A：第 19 项替换为真实导航检查

**旧第 19 项缺陷确认**：预填 captureId/captureContextId 后从扩展页直发 `route:observation`，只测后台合并。管理者用旧 tracker 故障包实测原探针 27/27 退出 0（`mutant-probe.json`），本轮已复核同一结论。

**新第 19 项（`19.new-chat-navigation-association`）的输入与覆盖边界**：
- 被测代码：XPI 内真实 page-hook（解析受控请求体、生成 captureId `crypto.randomUUID()`、调用 startLive、wrapped `history.pushState` 驱动 tracker 导航）、真实 CaptureContextTracker、真实 bridge→background 状态管线、真实浮窗渲染。检查自身不预填任何 ID、不发送 `route:observation`、不伪造 postMessage 观测信封。
- 合成输入的边界（如实声明）：请求体与导航目标是探针构造的合成数据；响应是 chatgpt.com 对未认证请求的真实拒绝（403/422），不是真实账号流量。
- **受控响应为什么不可行**：page-hook 的 `isAllowedRequest` 只检查同源（chatgpt.com）请求，任何跨源受控 Response 都进不了检查管线（方案 A 实测失败，`attempt1-plan-a-official-v1.0.9.json` 保留）。因此"服务端会话身份"经由请求体 correlation（第二个创建请求体携带 `conversation_id`，由真实请求解析器读出）进入 tracker（`observeLive`→提升），"后续响应到达"由真实 403/422 拒绝承担（failed 观测并回落到同一记录）。
- **关键时序**：创建请求发起后、响应到达前完成临时地址导航（与真实"新会话请求在途时导航"一致）。响应先行到达会触发 `abandonCreation` 使 `liveStarted=false`，后续提升语义无法成立（真实流量中响应流持续数秒，不受此影响；此差异已在本报告记录）。
- 覆盖的场景步骤（对应任务书 1–5）：请求启动与 ID 生成 ✓；history 导航到 `/c/local-chatgpt%3A…` ✓；会话关联与正式地址导航（correlation 路径，非流式身份——**流式响应内的 `conversation_id` 事件路径未覆盖**，Chromium E2E/真实流量仍未验证）✓；请求模型保持在同一当前记录且浮窗显示 ✓；切无关会话后不再是当前记录 ✓。

**红→绿（同一冻结探针 `ff-marionette.py` sha256 `6690f89c…`）**：

| 被测包 | 身份检查 | 第 19 项 | 退出码 |
| --- | --- | --- | --- |
| 正式 XPI（`34ca9440…`）+ 原 build.json/dist | PASS | PASS（creationCtx==tempCtx==formalCtx==response.ctx，浮窗显示 `请求模型gpt-5-6-pro-navcheck`） | **0**（27/27） |
| 旧 tracker 故障包（`2d9b8b78…`）+ 其匹配 build.json/dist | PASS（0a–0d 全过） | **FAIL**：correlated request 的 ctx ≠ creationCtx（旧 tracker 在临时地址导航后更换了上下文 ID） | **4**（26/1） |

证据：`positive-official-v1.0.9.json`、`mutant-old-tracker-v1.0.9.json`、`evidence/probe-official-final.log`、`evidence/probe-mutant-final.log`。故障包及匹配记录来自管理者审计目录（已复制为 `mutant-package/`），仅作验证夹具，不是交付物。

迭代过程（12 次尝试全部保留，`attempt*-official-v1.0.9.json` / `pre-freeze-mutant-*.json`）：方案 A（跨源受控 SSE）1 次失败后按止损切换；方案 B 迭代修正了三个探针自身缺陷（Marionette 把 Python None 变 undefined、exe 未切回被测标签页、响应早于导航到达破坏创建链），非盲试。

## 3. P2-B：第 11 项表述修正

第 11 项检查本体保留（其覆盖有效）。注释与报告统一改为：
**"从 postMessage 注入合成观测，验证 bridge→background→浮窗渲染；不覆盖 page-hook 捕获解析。"**
（原文"真实 page-hook → bridge → background"越过了实际验证范围——注入的是已解析 observation 信封，跳过 page-hook 的 fetch/WebSocket 捕获与解析。）

## 4. 冻结验证（逐条实际退出码）

| 命令/检查 | 结果 |
| --- | --- |
| `npm run test:firefox-tooling` | 退出 0，**53 项通过**（原 49 项保留 + 新增 4 项导航回归：`test_ff_marionette_nav_check.py`，覆盖导航断言失败→进入 results→退出 4 的传播，含临时地址换 ID、正式地址丢失提升、无关会话未退出三种故障注入） |
| `npm run lint` | 退出 0 |
| `git diff --exit-code 4ae924d -- src schemas manifest _locales icons` | 退出 0（业务源码零改动） |
| `git diff --exit-code 99f982d -- src schemas manifest _locales icons` | 退出 0（上游同源保持） |
| 正式包探针（冻结探针） | 退出 0，27/27 |
| 故障包探针（冻结探针） | 退出 4，第 19 项 FAIL |
| 正式 XPI / 源码 ZIP / build.json 哈希复验 | 未变（见 §1） |
| `evidence/freeze-tooling.log`、`evidence/freeze-lint.log` | 原始输出留存 |

## 5. 剩余边界（不因本轮改变）

Chromium E2E 缺环境、FF128 下限、真实更新事件、断线卡片真机不可复现、真实账号流量的流式解析问题（`stream_parse_failed`）继续按 BLOCKED.md 保留；新会话导航的**流式响应身份路径**与真实账号流量仍未覆盖。
