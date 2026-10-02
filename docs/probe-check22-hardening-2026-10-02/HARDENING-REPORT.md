# 探针检查 22 加固报告（2026-10-02）

## 结论

检查 22（`22.deep-research-capture-taskkind`）此前只判断“存在一条 taskKind=deep_research 的记录，
且 captureId 不以 `ff-probe` 开头”。captureId 缺失时被转成空串，空串不以 `ff-probe` 开头，
于是**缺失/空/伪造身份、旧记录、错误标记、错误 tab、无 revision 增长都能冒充本轮 page-hook 捕获**。
本轮只在探针检查 22 及其必要局部支撑内做最小加固，使其必须证明**本轮由 page-hook 生成的新捕获**：

- 冻结正式包（未签名 XPI `04af228b…65ae`）真机 32/32、退出 0，检查 22 取得**本轮新生成**的
  合法 UUID（不在发送前集合中），tag/context/pageUrl 与锁定页及后台 context 一致，后台 state
  revision 由 14 增长到 17。
- 脚本化对端反例：关掉 hook 包装（`fetchName=fetch`）且只提供一条发送前旧记录时，身份门禁通过后
  检查 22 失败、整轮退出 4；恢复合法对端后再次 32/32、退出 0。
- 未改业务源码、schemas、manifest、构建/打包/校验器、其他检查；冻结交付物与历史证据哈希不变。

修后探针 SHA256：`17297ab4e1d394f0b150fbcc5493cd1369c1271b1002f17e56087bed254e681e`
（旧：`7c56cfd335db2e19e96b6fd7d58dd96882a2bef011536d4b4ff6a8f9a92f0ac6`）。

## 缺口（任务 A：先在未改探针上复现）

新增 16 个工具回归用例，先在**未改动的探针**（`git HEAD:e830b4e`，哈希 `7c56cfd3…0ac6`，
仓库外副本 `D:\LAB\sync-v110-check22-red-2026-10-02`）上运行。逐项单独运行、解析探针自身汇总行：

| 反例 | 未改探针退出码 | 应为 |
| --- | --- | --- |
| missing / empty / blank / malformed captureId | 0 | 4 |
| context 缺失 / context 错配 | 0 | 4 |
| 原生 fetch（fetchName=fetch） | 0 | 4 |
| 合法 UUID 但属于发送前旧记录 | 0 | 4 |
| 错误请求标记 | 0 | 4 |
| 错误 tab | 0 | 4 |
| 错误 pageUrl | 0 | 4 |
| 无 revision 增长 | 0 | 4 |
| 多个 chatgpt.com 页面（歧义） | 0 | 4 |
| 无任何捕获产生 | 4（已拒绝） | 4 |
| 请求未发出 | 4（已拒绝） | 4 |
| 合法新捕获 | 0（但旧 detail 缺新证据字段，用例报错） | 0 |

即 **13 个非法身份反例在未改探针上“不该退出 0 却退出 0”**。原始输出：
`red-unchanged-probe.txt`、`red-per-test-isolated.txt`、`red-attribution.txt`（均在证据目录）。

## 修法（任务 B：最小局部改动）

仅改 `ff-marionette.py` 检查 22 块（第 949–1095 行）与两条 import（`secrets`、`urlsplit`）。
`git diff HEAD -U0` 的改动 hunk 全部落在该块内，其他检查未动。判定须同时满足：

1. **锁定唯一准确页面**：`chatgpt_pages()` 逐个 handle 解析 URL 的 scheme/host，只接受
   `https://chatgpt.com` 且 path 为 `/` 的页面；页面数必须恰好 1，否则失败（不靠 URL 包含字符串）。
   结果读取时再次核对，锁定页必须仍是同一 handle、同一 origin/path。
2. **发送前读后台状态**：`chrome.tabs.query({url:'https://chatgpt.com/*'})` 必须恰好 1 个 tab；
   读该 tab 的后台 `captureContexts[tabId]`（id/pageUrl/revision）、state revision 与既有 capture 集合；
   任一必要字段缺失即失败。tabId 用与后台一致的值寻址。
3. **唯一请求标记**：`secrets.token_hex(8)` 生成 `gpt-6-dr-<16hex>`，请求体与结果查找共用同一值。
4. **走被测 hook**：在锁定页面调用包装后的 `window.fetch('/backend-api/f/conversation', POST)`；
   必须 `started===true` 且 `fetchName==="routeInspectorFetch"`。不预填 captureId/context，
   不发 `route:observation` 或 postMessage 制造通过记录。
5. **结果必须是发送前不存在的新捕获**：captureId 非空、passed `^[0-9a-f-]{36}$` UUID 形态、
   不以 `ff-probe` 开头、且不在 `beforeIds` 中；taskKind 与 verdict 均为 `deep_research`；
   requestedModel 完全等于本轮标记；记录 tabId/captureContextId/pageUrl 与锁定页及后台当前
   context 一致；后台 state revision 严格大于发送前的值。
6. **轮询有上限**（24×0.5s）：缺失/歧义/旧结果/字段错/超时一律失败并退出 4，不降级为可选。

夹具（`fake_marionette.py`）新增 `drLock`（发送前快照：tab、context、revision、beforeIds）、
`drAfter`（结果时 revision）、`drTurn`（hook 推导的捕获；默认填 marker/锁定 tabId/pageUrl/contextId，
测试只覆盖一个键即破坏一个条件），以及脚本化应答 `drWrapped`；新增 `extra_chatgpt_pages` 开关制造
页面歧义。假对端体现前后 revision 变化、动态标记与有效 UUID，不为全部脚本返回万能成功。

## 红→绿

- 红（未改探针）：如上表，13 个非法身份反例退出 0。
- 绿（修后探针）：16 个新用例全过，工具套件 `Ran 82 tests … OK`、退出 0（基线 66 + 新增 16）。
- 说明：真机首轮加固版曾定位并修正一处本轮自有的 JS 调用笔误（见「真机」段），随后移除一处未使用的
  结果字段，探针哈希由 `d5148fcd…265f` 变为最终 `17297ab4…681e`；下表门禁、真机与脚本化对端
  均以最终哈希重跑。

## 门禁（修后，逐条退出码；原始日志 `*.log` 同目录）

| 命令 | 退出码 | 结果 |
| --- | --- | --- |
| `npm run typecheck` | 0 | tsc --noEmit 通过 |
| `npm run lint` | 0 | eslint 通过 |
| `npm test` | 0 | 38 文件 / **442 passed / 0 failed / 0 skipped**；覆盖率 98.1 stmts / 91.79 branch / 100 funcs（阈值 80/80/80/70 未改） |
| `npm run test:firefox-tooling` | 0 | **Ran 82 tests，OK**（66 基线 + 16 新增） |
| `npm run verify:firefox` | 0 | extension=30 firefox=30 identical=true，8 个 JS 逐字节一致，OK |

## 真机（任务 D）

命令：

```
py -3 -B ff-marionette.py \
  --xpi release/chatgpt-route-inspector-firefox-1.1.0.xpi \
  --expect-build-record release/chatgpt-route-inspector-firefox-1.1.0.build.json \
  --dist dist/firefox --label check22-fixed-r2 --out <唯一新路径>
```

- 结果：**32 passed / 0 failed / 0 missing -> exit 0**，`probeSha256=17297ab4…681e`，
  继续绑定原 XPI `04af228b…65ae`（0a 逐字节相等）。
- 检查 22 证据：`markerModel=gpt-6-dr-2e0a23f736ea4d57`，`tabId=5`，
  `ctxId=b8961c3e-b577-4961-90b2-9198e31c2dea`，`beforeRevision=14`，
  `beforeIds=["ff-probe-suspect-live"]`，`afterRevision=17`，
  `pageUrl=https://chatgpt.com/`，新捕获 `1a85ec40-6917-4fb8-b66b-608321e128d5`（合法 UUID，
  不在 beforeIds 中，taskKind/verdict 均 deep_research）。
- 过程中诊断：首轮加固版真机报 `found:null`。经与**未改探针**同机对照（未改探针同日仍 32/32），
  定位为本轮自有的 JS 调用笔误（`})()` 漏传 `arguments[0]`，标记丢失），已修正。这与检查 22
  的判定无关，属本轮自造缺陷，已在真机上复现并消除。诊断轮结果
  `probe-frozen-diag-*.json` 保留。

## 脚本化对端反例（任务 D，可复现）

仓库外 `D:\LAB\sync-v110-check22-scripted-2026-10-02\scripted_negatives.py`，用与本轮修后
探针同哈希（`17297ab4…681e`）的字节副本驱动进程内脚本化 Marionette 对端：

- 反例（hook 未包装 fetch 且只给发送前旧记录）：`identityOk=true`、`failedChecks=["22…"]`、
  `check22ok=false`、进程退出 **4**。
- 恢复合法对端：`32 passed / 0 failed / 0 missing -> exit 0`，`check22ok=true`。
- 输出 `positive-restored` / `negative-hookless-old-record` 两份 JSON 与 `scripted-negatives.txt`。
- 层级说明：脚本化对端证明探针拒绝 hook-less/旧记录捕获；真机层由上面的冻结包运行单独佐证。

## 边界与未验证（不得据此宣称）

- 只证明“请求侧任务识别 + 身份锁定”在受控临时 profile 场景成立，未证明成功真实 SSE、
  未登录/登录账号的真实流量、真实更新事件、FF128、额度专项、Chromium E2E、签名/AMO/日常安装。
- `stream_parse_failed` 根因未确认（见 BLOCKED.md），本轮未改业务代码。
- 检查 22 加固后，真机上本检查的捕获阶段为 `phase=failed`（未登录 403 拒绝），与本检查立意一致。