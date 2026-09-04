# BLOCKED（需人工验证项）

机器可验证项已全部通过（见 `ff-probe-results.json`，12/12）。以下两项 Agent 无法执行（需登录 ChatGPT 账号并肉眼确认），未伪造为已验证：

## 1. 真实登录对话的捕获链路（任务 4 第 3–7 项）
步骤：
1. Firefox 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件” → 选择 `dist/firefox/manifest.json`（或打包后的任意文件）。
2. 打开 `https://chatgpt.com/` 并登录，进入一个已有会话或新建会话。
3. 点工具栏扩展图标 → 确认 Popup 显示“实时监听”。
4. 发送一条消息，等待回答完成。
5. 检查 Popup 与页面浮窗显示“请求模型 → 响应路由”（如 `GPT 5.x Pro → GPT 5.x ...`）， verdict 非持续 `—`。
6. 打开“路由诊断台”，确认本轮记录存在且字段完整。

## 2. 长时间运行的控制台错误观察（任务 4 第 8 项）
用户 2026-09-03 实测报告：暂无报错。

## 3. 真实导出核验（2026-09-03，用户提供诊断台 Markdown+JSON 导出）
结论：核心链路真实工作，非样子货；与上游功能一致（bundle 逐字节同源）。
证据：请求侧字段群（requestedModel/conversationMode/thinkingEffort/planType/toolInvoked/fastConvo）只能来自真实请求体解析；
响应侧 `server_ste_metadata.model_slug`+`resolved_model_slug` 与上游 fixtures 真实流量同形；PoW 十六进制→十进制换算复算正确；
verdict/reasons 与 assessment.ts 规则逐条对应；durationMs/时间戳/parserHealth/requestId 脱敏/captureId 格式全部自洽。
遗留异常（非移植引入）：两轮 live 记录 phase=failed/errorCode=stream_parse_failed，但失败前数据已收全故 verdict 正确。
解析器本身不可能抛异常（全 guarded），只剩三种可能：body 缺失 / 单个 SSE 事件超 1MB / 流中途被页面侧 abort；
上游 catch 吞掉了原始 error.name（Chromium 版同有此缺口），故无法从导出区分。用户 2026-09-03 确认：两轮回答在页面上均完整显示
→ 证实为尾部流问题（页面侧 abort / 超大尾事件），verdict 不受影响；Chromium 对照二分降级为可选（仅满足好奇心，不影响结论），默认关闭。
