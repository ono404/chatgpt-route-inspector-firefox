# BLOCKED（需人工验证项）

保留历史条目；状态按 2026-09-20 升级后实测更新。

## 1. 真实登录对话的捕获链路（任务 4 第 3–7 项）— 仍待人工验证
步骤：
1. Firefox 打开 `about:debugging` → “此 Firefox” → “载入临时附加组件” → 选择 `dist/firefox/manifest.json`（或打包后的任意文件）。
2. 打开 `https://chatgpt.com/` 并登录，进入一个已有会话或新建会话。
3. 点工具栏扩展图标 → 确认 Popup 显示“实时监听”。
4. 发送一条消息，等待回答完成。
5. 检查 Popup 与页面浮窗显示“请求模型 → 响应路由”（如 `GPT 5.x Pro → GPT 5.x ...`）， verdict 非持续 `—`。
6. 打开“路由诊断台”，确认本轮记录存在且字段完整。

## 2. 长时间运行的控制台错误观察（任务 4 第 8 项）— 仍待人工验证
用户 2026-09-03 实测报告：暂无报错。2026-09-20 探针为单次 headless 短时运行，不构成长时观察。

## 3. 真实导出核验（2026-09-03，用户提供诊断台 Markdown+JSON 导出）— 历史结论（针对 1.0.5）
结论：核心链路真实工作，非样子货；与上游功能一致（bundle 逐字节同源）。
证据：请求侧字段群（requestedModel/conversationMode/thinkingEffort/planType/toolInvoked/fastConvo）只能来自真实请求体解析；
响应侧 `server_ste_metadata.model_slug`+`resolved_model_slug` 与上游 fixtures 真实流量同形；PoW 十六进制→十进制换算复算正确；
verdict/reasons 与 assessment.ts 规则逐条对应；durationMs/时间戳/parserHealth/requestId 脱敏/captureId 格式全部自洽。

## 4. `phase=failed / errorCode=stream_parse_failed`（历史遗留，非移植引入）— **本次复核后仍为未确认**
历史推断（1.0.5 时代）：两轮 live 记录失败前数据已收全故 verdict 正确，判为“尾部流问题”，三选一（body 缺失 / 单 SSE 事件超 1MB / 流中途被页面侧 abort），
上游 catch 吞掉原始 `error.name`，无法从导出区分；Chromium 对照二分默认关闭。

2026-09-20 对照 v1.0.7 源码复核（**不沿用旧推断当结论**）：
- 上游确实重写了流式解析（新增 `src/core/sse-decoder.ts`，delta/patch/truncate + 通道继承），并新增具名限额 `stream_event_too_large`（单事件 1MB）。
- 新增「无 SSE 分隔符的拼接 data 行」回退解析（注释明确写了 legacy 捕获场景），这是对同类失败的真实增强。
- 但 `failed()` 分支仍未特判页面侧 abort（`page-hook.ts` 无 AbortError / signal 处理），catch 映射后仍落到 `stream_parse_failed`。
- **结论：上游未做定点修复，也无“已消除”的直接证据。本项保持未确认，需真实流量复现才能定案。**
- 另注：v1.0.7 起 `errorCode` 会区分 `record_too_large` / `http_*` / `unexpected_content_type` / `response_clone_failed`，
  下一次真实出现时导出的错误码将比 1.0.5 更能定位原因。

## 5. 真实更新事件（1.0.5 → 1.0.7）— **本次新增，未验证**
`src/background/upgrade-notice.ts` 只在 `onInstalled.reason === 'update'` 且 `previousVersion < 1.0.7` 时打开公告页。
临时加载（`Addon:Install {temporary:true}`）在 Firefox 中始终以 `reason=install` 触发，**无法产生真实更新事件**，因此：
- 已用真实流量替代验证的部分：公告页本体渲染、浮窗公告入口存在与文案、`route:open-announcement` 消息链路、`isNoticeUpgrade` 的纯逻辑单测（上游 `tests/integration/upgrade-notice.test.ts`）。
- **未验证**：从已安装 1.0.5 的真实升级路径（需签名安装或 AMO/自签名分发）。
- 若需人工验证：用签名 XPI 安装 1.0.5 → 覆盖安装 1.0.7，确认仅开一次公告页且 `routeInspectorNotice107Shown` 被写入。

## 6. Firefox 128 下限 — **本次新增，未验证**
`strict_min_version = 128.0` 来自 MDN BCD（`content_scripts.world: MAIN` 自 128 起支持），本次未改动。
本机仅安装 Firefox 156.0，**128 未实测**，不得据此宣称已在 128 上验证通过。

## 7. `npm run test:e2e` — **本次新增，未执行（缺环境）**
本机无 extension-capable Chromium，报错 `No extension-capable Chromium found. Run: npx playwright install chromium`。
按本次任务约束不做工具安装，故未执行；`npm run build:e2e` 已通过。e2e 覆盖的是 Chromium 侧行为，与 Firefox 产物无关。

## 8. 额度字段（`deep_research` / `image_gen`）真机 — **新增，未专项验证**
`src/core/usage-quota.ts`（`limits_progress` → 额度投影）有上游单元/集成测试覆盖，但**真机探针没有额度专项检查**：
`docs/upgrade-2026-09-20/evidence/r2-probe-positive.json` 的 22 项里不含任何额度断言。
因此**不得**把额度描述为“真机已走通”（第一轮报告中的该表述已勘误）。
要补验需在真实账号下触发额度接口（`conversation_init` / `limits_progress`），属需要人工与真实账号的操作。

## 9. 探针的清理是尽力而为 — **已知局限，非缺陷**
探针只停止自己启动的进程并删除自己创建的临时 profile。若浏览器在启动初期被终止，它可能在删除后
再次写出文件（实测一次残留 `%TEMP%\ff-ri-probe-profiles\ff-ri-probe-*`）。
因此结果 JSON 记录的是**实际**结果（`summary.profileDirRemoved`），清理失败时会附 `notes`，
不假定“已删除”成立。
