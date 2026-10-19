> 2026-10-02 发布归并：当前主目录为 C:\workspace\chatgpt-route-inspector-firefox，分支 main，v1.1.0。用户接受已知流式限制并授权 GitHub 上传与清理；Mozilla 签名由用户执行，日常覆盖安装尚未完成。当前状态见 [STATUS.md](docs/publish-2026-10-02/STATUS.md)，以下保留历史记录。

# BLOCKED（需人工验证项）

> 2026-10-02 交接：第 1–16 项保留各轮次状态；检查 22 独立审查的新观察与判断分歧见 [HANDOFF.md](docs/handoff-2026-10-02/HANDOFF.md) 第 4 节。尚未修改代码，也未将审查者的 P2/候选修法确认为新的必修事项。

2026-10-01 升级后状态：本地已同步上游 **v1.1.0**（`dd5ea33`）并交付未签名包。
下方第 1–14 项为 v1.0.9 及更早版本的未完成项，**原样保留**；升级不使它们自动通过，
本轮也没有重跑其中任何一项的人工步骤。第 15 项记录本轮新增/复测的边界。
现役代码与工作区状态见 PROGRESS.md 顶部，本轮结果与证据见
[docs/upgrade-2026-10-01/UPGRADE-REPORT.md](docs/upgrade-2026-10-01/UPGRADE-REPORT.md)。

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

## 15. v1.1.0 同步轮新增与复测的边界 — **2026-10-01**

以下为本轮**如实记录**的边界，不是产品缺陷结论：

1. **成功流式响应的会话身份/模型路由仍未覆盖**（承接第 14 项）。v1.1.0 新增的检查 22
   （深研任务识别）与既有检查 19 一样，走的是**合成请求 + chatgpt.com 真实未认证拒绝响应**，
   因此证明了「请求侧任务识别与上下文关联」链路，**不证明**成功 SSE 内的
   `conversation_id` / 模型路由 / 研究任务关联。检查 22 的真实 UUID 仅证明 hook 自己生成 captureId。
2. **`stream_parse_failed` 仍未确认根因**（承接第 4 项）。上游 v1.1.0 未针对该路径定点修复
   （`sse-decoder.ts` 只扩了 KEYS 白名单与 `widget_state`/`image_gen_title` 投影）。
   **不因升级宣布已修复**；探针检查 18 只断言失败记录不被误报为 completed。
3. **Chromium E2E 仍缺环境**（承接第 7 项）。本轮 `npm run test:e2e` 退出 **1**：
   `No extension-capable Chromium found. Run: npx playwright install chromium`，
   1 failed / 12 did not run。证据 `docs/upgrade-2026-10-01/evidence/c-test-e2e.txt`；
   按约束未安装浏览器，`build:e2e` 退出 0 不代表 E2E 执行通过。
4. **真机版本为 Firefox 157.0，非 128**（承接第 6 项）。`strict_min_version 128.0` 未改动、
   仍**未在 128 上实测**。本轮 `moz:buildID=20260924084938`。
5. **v1.1.0 的图片任务/研究任务只做了合成断言**。检查 20/21/23/24 的输入是**合成 observation**
   （扩展上下文注入，或经真实扩展页读取 DOM）；没有任何一次**真实账号**的图片生成或深研请求。
   因此「识别正确」有代码级与 UI 级证据，**没有真实流量证据**。
6. **检查 22 的注入层级**：真实 **page-hook**（被测 XPI 内）解析探针发出的合成创建请求，
   故覆盖 page-hook → bridge → background；它**不经过** bridge 的 DOM 浮窗渲染，
   也**不覆盖** WebSocket/SSE 侧的 `task-captures` 路径（那条路径由上游单测
   `tests/unit/task-association.test.ts` 以合成数据覆盖）。
7. **反向验证的策略性取舍**：篡改 XPI 的反例在**仓库外临时副本**中重打包后才得到干净信号
   （`0c.dist-matches-record` 会因为记录里的绝对路径而先拒绝对照外的副本）。这**不是**放宽检查：
   终次运行的失败项是 `0a/0b/0c`，而 `0d.manifest-sha256` PASS，正是「同 manifest 异内容」被拒的实证。
8. **旧公告页仍在**：v1.1.0 未移除 1.0.9 公告页与去重逻辑，故 `src/ui/announcement/` 与
   `upgrade-notice.ts` 的版本语义、`tests/integration/upgrade-notice.test.ts` 均**保持 1.0.9**，
   未做全局版本替换。真实更新事件（1.0.9→1.1.0）因此仍**未验证**（承接第 5 项）。
9. **未签名、未上传 AMO、未日常安装**：本轮交付仅为本地未签名 XPI；签名与安装状态
   见 README-FIREFOX.md 的「AMO 提交资料」一节。
10. **`npm ci` 报 5 项依赖漏洞**（3 moderate、2 high），未做可达性分析、未升级依赖。
    证据 `docs/upgrade-2026-10-01/evidence/c-npm-ci.txt`。

## 16. 检查 22 误报加固轮新增与复测的边界 — **2026-10-02**

以下为本轮**如实记录**的边界，不是产品缺陷结论：

1. **本轮只加固检查 22 的“身份”判定，未改变其可见证据层级**。检查 22 仍走
   **合成创建请求 + chatgpt.com 真实未认证拒绝响应**，因此真机上该检查的捕获阶段为
   `phase=failed`（未登录 403），与本检查立意一致；**不证明**成功 SSE 内的
   `conversation_id`/模型路由/研究任务关联（承接第 14 项与上一节第 1 项）。
2. **加固只证明“本轮 page-hook 生成的捕获”可被锁定**，不新增真实账号流量证据；
   本轮**未登录、未发真实消息**，用的仍是专用临时 profile。
3. **真机为 Firefox 157.0，非 128**（承接第 15 节第 4 项）；`strict_min_version 128.0` 未改。
4. **脚本化反例的层级**：hook 未包装 fetch + 只给发送前旧记录的反例由**进程内脚本化
   Marionette 对端**证明（`C:\workspace\run-06`），不是真实浏览器；
   真机层由冻结包正向运行单独佐证。两者都**不能**代表“连接不可信”之外的真实故障注入。
5. **本轮自造缺陷已如实记录**：加固首版真机上 `found:null`，根因是本轮自有的 JS 调用笔误
   `})()` 漏传 `arguments[0]`（唯一标记丢失），非检查判定逻辑缺陷；与未改探针同日对照后定位，
   已修正并真机复现 32/32。诊断轮结果保留于证据目录。
6. **其余未完成项不受本轮影响**：签名/AMO/日常安装、成功真实 SSE、真实更新事件、FF128、
   额度专项、Chromium E2E（缺环境）均**仍待验证**；`stream_parse_failed` 根因仍未确认，
   本轮**未改业务代码**，不因加固宣布其已解决。
