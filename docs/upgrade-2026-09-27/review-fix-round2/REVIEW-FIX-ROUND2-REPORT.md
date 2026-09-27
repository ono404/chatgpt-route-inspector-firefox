# 复审修正报告 round2：导航与浮窗假绿灯（2026-09-27）

对应管理者复审 `C:\Users\<user>\AppData\Local\Temp\route-v109-rereview-b62218f3a6d24b46bb313d741197451b\REVIEW.md`（P2-1、P2-2）。只改探针第 19 项、工具回归与文档；业务源码、正式交付包、旧证据零改动。

## 1. 交付物哈希复核（未变）

XPI `34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523`；源码 ZIP `0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0`；build.json `15debe2ae37957a21c7f91161e6627acc33afdd6dd67e29ae00268b6451e9dab`。

## 2. P2-1 修正：每阶段先证明导航已发生

第 19 项（`19.new-chat-navigation-association`）的阶段判定重写：

- **锁定标签页**：检查开始时做一次 `chrome.tabs.query` 并记录 tabId；此后所有后台查询都显式使用该 tabId，不再每轮重查第一个匹配。
- **导航前基线**：记录该 tab 的 `context.pageUrl`、`revision`、`id`（首页 `https://chatgpt.com/`，revision 0 起点）。
- **三个阶段（临时 / 正式 / 无关）都要求**：
  1. `history.pushState` 调用返回的 `location.pathname` 等于目标路径（push 后实际地址，不忽略返回值）；
  2. 后台 `captureContexts[tabId].pageUrl` 已到达目标路径；
  3. `revision` 严格大于上一阶段观察值（状态新鲜度证明，"期望 ID 相同"不再能充当状态新鲜的证据）。
  到达后才断言 context ID 保持（临时/正式）或切换（无关）。
- **浮窗读取**：每次读取前用目标路径 `find_handle` 切回句柄，且匹配句柄的 `GetCurrentURL` 必须以 `https://chatgpt.com` 开头（防止扩展页面路径碰巧包含目标片段——这正是本轮发现的一个真实陷阱：pushState 在错误窗口执行时会把扩展页 URL 变成 `moz-extension://…/c/navcheck-conv`）；读取脚本回报 `location.pathname` 并参与断言。
- **无关阶段**：`oursCurrent` 显式断言为 `false`，且覆盖正式阶段实际展示的两个 captureId（首个请求 + correlatedCaptureId）；浮窗必须真实存在（`.probe` 元素存在）且不再显示旧标记——浮窗缺失不能当作"旧记录已消失"。
- **超时/停留首页/旧 revision/错误地址/拿错标签页**均导致第 19 项失败。
- **证据不截断**：第 19 项 detail 改为完整 JSON（`results` 中不截断，包含探针/XPI/记录哈希、tabId、各阶段浏览器地址、pageUrl/revision/id、两个 captureId、浮窗存在性与文本、各阶段 ok）。

## 3. 真机验收（冻结探针 `ff-marionette.py` sha256 `a204ae0afb0c…`）

| 场景 | 结果 |
| --- | --- |
| A. 正式 XPI + 原 build.json/dist | **27/27，退出 0**。阶段证据：temp 到达 `/c/local-chatgpt%3Anavcheck-draft`（rev 0→2，ctx 保持）；formal 到达 `/c/navcheck-conv`（rev 2→4，ctx 保持）；unrelated 到达 `/c/navcheck-unrelated`（rev 4→5，ctx 切换，oursCurrent=false）；浮窗在 formal 显示 `gpt-5-6-pro-navcheck`、在 unrelated 显示"等待下一次回答" |
| B. 旧 tracker 故障包（`2d9b8b78…`）+ 匹配记录/dist | 身份 0a PASS 后第 19 项 FAIL（correlated request 的 ctx ≠ creationCtx），**退出 4** |
| C. 冻结探针副本仅禁用 temp/formal 两次 pushState（`probe-no-navigation.py`，保留全部等待/断言/无关导航） | 身份 PASS 后第 19 项 FAIL（`locked chatgpt tab not on any of ['/c/navcheck-conv']`——浏览器未到达目标），**退出 4** |

对照管理者反例：round1 探针在同样禁导航条件下 27/27 退出 0（`tempPageUrl` 停在首页）——假绿灯已消除。

## 4. 工具回归（`tests/firefox-tooling/test_ff_marionette_nav_check.py`）

**56 项全部通过**（原 49 项保护用例不变；导航回归从 4 项扩到 7 项，新增：无导航的旧 pageUrl/revision 状态、pushState 返回 pathname 不匹配、切换后浮窗缺失；改写：temp/formal 上下文改变与 unrelated 记录残留注入为完整 pageUrl/revision/id 形状）。脚本化 peer 只证明断言与失败传播，A/B/C 为真机证据。

## 5. 覆盖边界（不变）

合成请求 + 未认证拒绝响应（403/422/401）：不验证成功流式响应携带的会话身份与模型路由；请求体 correlation 不等于流式 `conversation_id` 事件路径。真实账号流量仍未覆盖。

## 6. 迭代记录（全部留证 `attempt*.json`、`evidence/probe-*.log`）

5 次迭代，均为探针自身缺陷的定位与修复：①`requested_poll`/`ctx_state_poll` 的 JS 以 `})()` 结尾导致 Marionette 参数未传入（两处）；②formal/unrelated 的 pushState 在扩展 shell 页执行（上轮已修过同类问题，本轮重写时遗漏——扩展页 URL 因此变成 `moz-extension://…/c/navcheck-conv`，新阶段断言正确识别了"context 停留旧地址"）；③`go_page` 片段匹配需核实 chatgpt.com origin。无业务代码改动。
