# BLOCKED（需人工验证项）

2026-10-01 升级前状态：下方为 v1.0.9 及更早版本的未完成项；用户尚未完成覆盖安装与真实使用测试，上游 v1.1.0 虽已发布，本地未同步。成功 SSE、真实更新事件、签名/安装等项目不能因决定直升 v1.1.0 而视为通过；新版的待办需在同步后按实际变化重新核定。现役代码和工作区状态见 PROGRESS.md 顶部。

状态更新至 2026-09-27 v1.0.9 / round2 独立验收；历史用户样本保留原日期，不能当作新版真实流量证据。

## 1. 真实登录对话的捕获链路（任务 4 第 3–7 项）— 部分验证，流式完成未通过
2026-09-20 用户提供真实导出，按其指定的本地时间 15:54 分界，100 条保留记录中有 63 条新样本：34 条 live（29 条 normal、5 条 unknown）与 29 条 reload（completed/unknown）。34 条 live 全部为 `failed/stream_parse_failed`，所以捕获及部分路由判定有实证，不能宣布完整生命周期通过。分界是用户提供的版本归属线索，导出本身不能证明所装 XPI 哈希。原始用户数据留在仓库外，不纳入源码包或 Git。

后续人工复核步骤：
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

## 4. `phase=failed / errorCode=stream_parse_failed`（历史遗留，尚无 Firefox 特有证据）— 根因未确认，真实新样本仍出现
2026-09-20 后续复核：新样本 34/34 live 出现该错误，不能继续描述为本次样本“偶发”。本地业务源码与上游 `d5524a0` 一致；上游 `tests/e2e/extension.spec.ts` 包含不支持的 delta 编码导致 `stream_parse_failed` 的用例，解码器与 catch 映射也保留此路径。这证明上游能产生同类错误，不证明用户这批流量就是该原因，也不等于已做同流量 Chromium/Firefox 对照。用户决策：以移植为主，暂无必要证据时不修改业务代码。

以下保留此前源码分析：
历史推断（1.0.5 时代）：两轮 live 记录失败前数据已收全故 verdict 正确，判为“尾部流问题”，三选一（body 缺失 / 单 SSE 事件超 1MB / 流中途被页面侧 abort），
上游 catch 吞掉原始 `error.name`，无法从导出区分；Chromium 对照二分默认关闭。

2026-09-20 对照 v1.0.7 源码复核（**不沿用旧推断当结论**）：
- 上游确实重写了流式解析（新增 `src/core/sse-decoder.ts`，delta/patch/truncate + 通道继承），并新增具名限额 `stream_event_too_large`（单事件 1MB）。
- 新增「无 SSE 分隔符的拼接 data 行」回退解析（注释明确写了 legacy 捕获场景），这是对同类失败的真实增强。
- 但 `failed()` 分支仍未特判页面侧 abort（`page-hook.ts` 无 AbortError / signal 处理），catch 映射后仍落到 `stream_parse_failed`。
- **结论：上游未做定点修复，也无“已消除”的直接证据。本项保持未确认，需真实流量复现才能定案。**
- 另注：v1.0.7 起 `errorCode` 会区分 `record_too_large` / `http_*` / `unexpected_content_type` / `response_clone_failed`，
  下一次真实出现时导出的错误码将比 1.0.5 更能定位原因。

## 5. 真实更新事件（1.0.5 → 1.0.7 → 1.0.9）— **仍未验证**
`src/background/upgrade-notice.ts` 只在 `onInstalled.reason === 'update'` 且 `previousVersion < 1.0.9` 时打开公告页（v1.0.9 起打开外部地址 `https://rinotice.liu-qi.cn/`，存储键 `routeInspectorNotice109Shown`）。
本轮临时加载（`Addon:Install {temporary:true}`）观察到 `reason=install`，**没有取得真实更新事件证据**，因此：
- 已分别通过探针和单测验证的部分：v1.0.9 外部公告导航、浮窗疑似降级提示入口与文案、`route:open-announcement` 消息链路、`isNoticeUpgrade` 的纯逻辑单测（上游 `tests/integration/upgrade-notice.test.ts`）；这些不等于真实更新事件。
- **未验证**：已安装旧版到 1.0.9 的真实升级路径（需兼容的已签名交付物）。
- 若需人工验证：保留实际已安装旧版与数据，备份后覆盖安装同 ID 的已签名 1.0.9，确认 `reason=update`、合法 `previousVersion < 1.0.9`、仅开一次外部公告且 `routeInspectorNotice109Shown` 被写入。

## 6. Firefox 128 下限 — **本次新增，未验证**
`strict_min_version = 128.0` 来自 MDN BCD（`content_scripts.world: MAIN` 自 128 起支持），本次未改动。
本轮使用 Firefox 156.0.1，**128 未实测**，不得据此宣称已在 128 上验证通过。

## 7. `npm run test:e2e` — **已尝试但未完成（缺环境，2026-09-27 复测）**
2026-09-27 复测：本机仍无 extension-capable Chromium，报错 `No extension-capable Chromium found. Run: npx playwright install chromium`（1 failed / 12 did not run，失败原因即该环境错误）。
证据：`docs/upgrade-2026-09-27/evidence/test-e2e-env.log`。按任务约束不安装浏览器；`build:e2e` 退出码 0。e2e 覆盖 Chromium 上运行的共享业务行为，不能代替 Firefox 真机验收。

## 8. 额度字段（`deep_research` / `image_gen`）真机 — **新增，未专项验证**
`src/core/usage-quota.ts`（`limits_progress` → 额度投影）有上游单元/集成测试覆盖，但**真机探针没有额度专项检查**：
`docs/upgrade-2026-09-20/evidence/r2-probe-positive.json` 的 22 项里不含任何额度断言。
因此**不得**把额度描述为“真机已走通”（第一轮报告中的该表述已勘误）。
2026-09-20 用户真实导出的 63 条新样本中，33 条含非空剩余额度字段，已有实际采集证据；仍未与账号界面数值、重置时间和变化过程对照，因此专项验证状态不变。

## 9. 探针的清理是尽力而为 — **已知局限，非缺陷**
探针只停止自己启动的进程并删除自己创建的临时 profile。若浏览器在启动初期被终止，它可能在删除后
再次写出文件（实测一次残留 `%TEMP%\ff-ri-probe-profiles\ff-ri-probe-*`）。
因此结果 JSON 记录的是**实际**结果（`summary.profileDirRemoved`），清理失败时会附 `notes`，
不假定“已删除”成立。

## 10. “连接不可信”只能靠脚本化对端复现 — **新增，方法学限制**
真实 Firefox 会如实回报自己的 `moz:profile`，因此**真机上无法自然产生**“对端谎报 profile”的情形。
该路径的验证由 `tests/firefox-tooling/fake_peer.py`（脚本化 TCP peer，占用探针端口并谎报 `moz:profile`）
与同目录的进程内假连接覆盖；本轮同时用**真实探针进程**对 peer 跑过一次，实测对端只收到 `WebDriver:NewSession`。
若要人工复现：让探针 `--port` 指向该 peer 的监听端口即可，命令见 `docs/upgrade-2026-09-20/UPGRADE-REPORT.md` §10。

## 11. 真机探针受 `chatgpt.com` 响应速度影响 — **新增，已知抖动（非缺陷）**
`9.page-hook-MAIN-world` / `10.bridge-overlay-ISOLATED` 需要在导航后执行脚本；站点响应慢时会 `timed out`，
2026-09-20 的历史运行连带 `11.notice-hint-1.0.7` 未执行，退出 5。当时遇到一次，
同一条命令第二次即恢复正常（退出码 4）。
证据：`docs/upgrade-2026-09-20/evidence/r3-probe-negative-badpage-attempt1-navtimeout.*`。
当前探针对异步状态做有限轮询，超时仍失败，不自动重跑整轮或把缺失检查当作通过；当前完整正向证据见独立验收 official.json。

## 12. 断线提示卡片（v1.0.9）本轮真机未复现 — **新增，方法学限制**
v1.0.9 上游新增"扩展连接失效 → 提示刷新"浮窗卡片。其逻辑由上游自带集成测试以 mock 拒绝覆盖（`tests/integration/bridge-lifecycle.test.ts`，本轮 327 项中包含）。
真机触发尝试（2026-09-27，FF156.0.1，探针 run1–run3 证据保留于 `docs/upgrade-2026-09-27/ff-probe-results-v1.0.9-2026-09-27*.json`）：
- Addon:Install 重装（update 型失效）与 Addon:Uninstall 两种方式，均未出现断线卡片。本轮未观察到孤儿内容脚本触发的发送失败，不能据此推断所有 Firefox 版本或失效场景都不可复现。
- 按止损规则停止该项：探针不把它列为必需检查（探针内留有说明注释），不伪造通过、不删除上游用例。
- 若要人工复核：需能产生真实“上下文失效”的场景；本轮 Marionette 方案未成功触发，其他方案尚未验证。

## 13. 公告站点为上游外部依赖 — **新增，说明**
v1.0.9 起公告打开上游固定地址 `https://rinotice.liu-qi.cn/`（扩展不发请求，是普通浏览器导航）。2026-09-27 真机实测该地址可达且返回公告内容（探针检查 15，真实导航一次，不附带任何扩展数据）。站点内容、可用性与长期存在由上游维护者决定，本移植不做承诺。

## 14. 新会话导航的成功流式响应路径 — **未覆盖**

round2 第 19 项已验证真实 tracker 导航、临时地址提升与浮窗归属；合成请求取得的是真实未认证拒绝响应。请求体 correlation 路径不等于成功 SSE 的 conversation_id/模型路由路径，后者及真实账号新会话仍待验证。详见 [独立验收](docs/upgrade-2026-09-27/independent-acceptance/ACCEPTANCE.md)。

## 2026-09-27 verify-hardening 轮状态
本轮无新增阻塞：manifest 完整对象比较与回归测试均已落地，冻结交付物、dist 与历史证据哈希未变。上一轮遗留问题（第 1–14 项）原样保留，未在本轮重跑浏览器探针或工具回归。
