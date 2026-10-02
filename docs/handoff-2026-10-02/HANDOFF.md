# Firefox v1.1.0 交接 — 2026-10-02

用途：恢复进度、查找证据，并由接手者独立评估下一步。用户要求：**不要把上一位 LLM 的技术判断或修法写成既定结论**。下面区分本地事实、历史验证和审查意见；审查严重性、反例是否符合目标、是否需要改代码均待重新判断。

## 1. 从哪里接手

| 目录 | 本次收尾核对的状态 | 使用方式 |
| --- | --- | --- |
| `D:\LAB\sync-v109-isolated` | 现役 v1.1.0 工作树；分支 `codex/sync-upstream-v1.1.0`；HEAD `cdbf1b35c16ef9e996d509bdbcee94e93c78c368` | 先读本文件，再读该目录 AGENTS.md、PROGRESS.md 顶部及 BLOCKED.md 第 15–16 项 |
| `D:\LAB\火狐浏览器插件制作2` | 旧 v1.0.7 工作树；HEAD `909941e60b2cb97f58ca3be41c3354c7e5f2416c` | 历史参考；不要因当前会话 cwd 在此而把它当新版工作区 |

本次文档收尾开始前，现役工作树干净；原目录已有四文档修改及未知 `.workbuddy/`、`.zcodeignore`。本次只改交接文档和导航，不提交、不 push、不修改代码、不重新构建/打包、不清理现场。收尾后现役工作树存在本次未提交文档和证据归档，HEAD 仍为 cdbf1b3；接手时请重新看 `git status`。

## 2. 已完成的工作及来源

目标上游 tag 是 v1.1.0 `dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552`。这是本次同步目标，未据此断言它仍是远端最新版本。收尾再次核对 `git diff dd5ea336 HEAD -- src schemas _locales icons manifest` 为空；Firefox 业务源码保持与该上游同源。

| 提交 | 已提交内容 |
| --- | --- |
| `73696a7` | 先保全原有未提交的 manifest 校验器补强、回归测试与文档 |
| `0c46668` | 升级开工回执与基线 |
| `770095f` | 合并上游 dd5ea336，双亲为 0c46668 与 dd5ea336 |
| `e830b4e` | 探针适配 schema 1.9.0 等值断言，新增 v1.1.0 任务判定/UI 检查 |
| `cdbf1b3` | 加固检查 22 的捕获身份，工具回归从 66 到 82 项；未改业务源码、冻结包或其他探针检查 |

v1.1.0 新增图片生成、深度研究任务结论与规划/报告模型分列。包内 1.0.9 公告页和相关版本语义仍由上游保留，不能把所有 1.0.9 字符串当成漏升级。

检查 22 现实现可直接看 `ff-marionette.py:949–1095`：枚举页面、读取后台快照、生成随机请求标记、经包装后的 fetch 发请求、轮询匹配记录、核对 UUID/新旧集合/tab/context/pageUrl/state revision。实现是否满足所有期望，请从代码和规格重新判断。

## 3. 验证到了哪一层

上一轮本会话在 cdbf1b3 上独立复跑了下列门禁；本次 neat-freak 收尾只复核证据、Git、哈希与文档，不再次运行测试或启动浏览器。

| 项目 | 独立复跑结果 | 证据范围 |
| --- | --- | --- |
| typecheck / lint / verify:firefox | 均退出 0；verify 为 30=30，8 个 JS 一致 | 本地代码/产物门禁 |
| npm test | 38 文件、442 passed，退出 0；覆盖率 98.1/91.79/100/98.1 | 业务测试，不能替代真实账号流量 |
| test:firefox-tooling | 82 tests，OK，退出 0 | 合成夹具与脚本化对端 |
| 冻结包真机 | Firefox 157.0，32/32，退出 0；probeSha256 与提交一致 | 专用临时 profile，连接信任门禁通过，进程停止且 profile 已删除 |
| 独立脚本化抽查 | 空/缺失 ID、原生 fetch、旧 ID、结果时错 context/pageUrl 均使检查 22 失败并退出 4；合法对照退出 0 | 探针控制流，不是真实站点故障注入 |

真机检查 22 的输入是合成创建请求，响应是实际未认证拒绝；它提供请求侧识别链路证据，未覆盖成功 SSE 或真实账号图片/研究任务。独立结果中的标记为 `gpt-6-dr-610ba408c3ed716c`，匹配捕获 UUID `4c132e6e-0635-417a-938b-33e174b25b28`，state revision 14→17。结果 detail 存在既有 600 字符截断，完整判据须结合代码，不能假定 detail 是完整可解析 JSON。

升级轮的源码 ZIP 仓库外复建、30/30 文件比较、旧交付物和历史证据保全、XPI 篡改/输出保护/禁导航等反例见 [升级报告](../upgrade-2026-10-01/UPGRADE-REPORT.md)。其中部分复建也曾由本会话独立复核；本次收尾没有重做这些耗时步骤。

## 4. 两项需要独立评估的观察

### 页面端口

可复现事实：`chatgpt_pages()` 在第 979 行判断 scheme 与 hostname，保存 handle/path，没有比较 port。脚本化对端只把首页 `GetCurrentURL` 改成 `https://chatgpt.com:444/`，后台 context/捕获仍为 `https://chatgpt.com/`，当前探针检查 22 PASS、整轮退出 0。

上一位审查者将它判作 P2，并建议校验 HTTPS 有效端口 443。**这是审查意见和候选修法，不是已经确定的下一步要求。** 该反例人为制造了浏览器 URL 与后台状态不一致，未在真实 Firefox 上构造端口 444 的服务。接手者应评估：这是否属于页面身份门禁要拒绝的输入；夹具是否准确代表目标失配；真实链路中的其他检查能否覆盖；严重性与修改收益是否成立。可以确认、降级或否定原判断，并记录依据。

### 同一标记的多条捕获

可复现事实：结果查询用 `.find`，存在两条同标记/tab/context 的合法新捕获时选择第一条，Python 接受该结果。独立脚本化运行退出 0；抽取实际查询 JS 在 Node 上重放，也返回第一条和两条 markerMatches。

上一位审查者把这一项列为非阻塞观察：若目标只是证明“存在本轮新捕获”，多条记录本身并不推翻它；若目标是证明唯一结果，才需要额外基数约束。现有明确测试覆盖的是多个页面的歧义。请先判断所需语义，不因报告出现“歧义”两个字就扩大修复范围。

两项尚未修改代码。原执行报告称该轮闭环，原审查报告则保留端口缺口；这是需要按证据裁决的结论差异。归档的旧审查报告中的 P2、通过/不通过及建议均保留为历史观点，不具有新的执行授权。

## 5. 冻结交付物

目录均为 `D:\LAB\sync-v109-isolated\release`；本次重新计算哈希一致。

| 文件 | SHA-256 |
| --- | --- |
| `chatgpt-route-inspector-firefox-1.1.0.xpi` | `04af228b03f85e954d894a859fb87afcf1bfbc9cd449da881c2f25f99c0165ae` |
| `chatgpt-route-inspector-firefox-1.1.0.build.json` | `a2028179ed18602da5d6be288dd2142a0140dab0d64bfdb6fcd267afaba263a1` |
| `chatgpt-route-inspector-firefox-1.1.0-source.zip` | `51523360d4063fc939177672b9bf990278a1e0495f4e715f5e22b0cc49888846` |
| 现役探针 `ff-marionette.py` | `17297ab4e1d394f0b150fbcc5493cd1369c1271b1002f17e56087bed254e681e` |

源包是升级合并时的构建源码快照，不含探针和测试；后续只改探针时未重做源包。XPI、build record 与对应 dist 需要来自同次打包；ZIP 的 mtime 会影响整体哈希，复现比较还要逐文件核对。签名/安装用法见 [README-FIREFOX.md](../../README-FIREFOX.md)。

## 6. 尚未验证或未裁决

- 成功真实 SSE 的会话身份/模型路由；真实账号图片生成与深度研究流量。
- `stream_parse_failed` 根因仍未确认；历史真实样本存在失败，不能因升级或探针加固宣布解决。用户此前选择暂不改业务代码，若后续改变范围应以新的明确指示为准。
- 真实更新事件（1.0.9→1.1.0）、Firefox 128 下限、额度专项、日常覆盖安装、AMO/签名完成凭证。
- Chromium E2E：升级轮因缺 extension-capable Chromium 退出 1；未安装所缺浏览器；build:e2e 成功不能算 E2E 通过。
- 历史 npm ci 报 5 项依赖漏洞，未做可达性判断/升级；这是历史扫描输出，本次没有重新审计。
- 当前远端/push 状态本次未查询；执行者报告未 push，本会话未 push。不据此断言外部人员也未更新远端。
- 两项探针边界观察的必要性、严重性和最终处置，见上一节，由接手者判断。

完整历史限制在 [BLOCKED.md](../../BLOCKED.md)，原条目保留。

## 7. 证据入口与复核方式

- 执行者升级证据：[UPGRADE-REPORT.md](../upgrade-2026-10-01/UPGRADE-REPORT.md)。
- 执行者检查 22 加固证据：[HARDENING-REPORT.md](../probe-check22-hardening-2026-10-02/HARDENING-REPORT.md)。
- 本会话独立结果：本目录 `evidence/`；索引/来源/复制前后哈希见 `evidence/ARCHIVE.json`。`prior-review.md` 是原审查意见，`independent-positive.json` 是独立真机结果。
- 可选重现：先把 `evidence/` 整目录复制到新的仓库外目录，再从现役工作区用 `py -3 -B <新目录>/adversarial.py` 与 `node <新目录>/replay-poll.mjs` 运行。脚本使用现役探针、项目测试夹具或提取的 JS，结果写在脚本同目录；先复制可保留原归档。不要把重现夹具的成功当作真机验证。
- 上一轮独立运行全套日志与剩余反例仍在 `C:\Users\gyjxjkg\AppData\Local\Temp\ff-check22-accept-a755a99d0a10457891ac8785e3720425`。主要脚本/结果已复制归档，原现场未删除。
- 升级前保全目录仍在 `D:\LAB\sync-v110-backup-2026-10-01`，本次只确认 HASHES.sha256 存在，未重新逐项比对备份。

本机 `py -3` 当前可用，指向 Python 3.14；上一轮工具测试/独立探针使用的路径是 `C:\Users\gyjxjkg\.workbuddy\binaries\python\versions\3.13.12\python.exe`，路径名不能当作解释器实际版本。工具 runner 会打印所选解释器，复验时按实际输出记证据。

## 8. 本次 neat-freak 收尾的六个事实面

| 事实面 | 状态 | 本次处理与限度 |
| --- | --- | --- |
| 代码 | verified-current | 重新核对 HEAD、分支、上游业务目录 diff、现役探针；未改代码 |
| 受控运行/发布 | pending | 本会话前轮独立真机 32/32 证据已归档；真实账号、签名安装和外部发布状态仍未验证 |
| 文档 | changed-and-verified | 新增本交接与独立证据归档；更新现役入口及旧目录导航，历史报告正文不改 |
| 规则 | changed-and-verified | 两工作树各有 AGENTS.md；本次盘点未发现项目内额外规则/override；上级 D: 与 D:\LAB 未发现 AGENTS/CLAUDE；仅更新交接指针与明显错表述 |
| 记忆 | out-of-scope | Codex 生成记忆为 generated-read-only，存在旧版摘要，仅作检索线索；没有写入记忆或未知 .workbuddy 内容 |
| 工作区 | pending | 两 worktree、备份与临时现场全保留；文档未提交；原目录已有改动保留，没有删除候选或自动清场 |

盘点：排除 Git 内部、依赖、构建/交付及输出目录后，收尾前现役目录 368 文件/17 Markdown，原目录 246 文件/11 Markdown。当前源码包、历史证据及备份均无需为此次文档收尾重建或清理。

本次修改前的四文档备份、文件枚举和哈希快照在 `C:\Users\gyjxjkg\AppData\Local\Temp\ff-neat-handoff-cb20fb422e6b4174b9f0ed6a32c4ee7c`。文档变更通过 diff、路径/链接存在性、归档哈希及非文档文件不变检查验收，结果见本目录 `CLOSEOUT-VERIFICATION.json`。

收尾检查仍有 Git 换行提示：现役四文档修改前已是 LF，配置为 `core.autocrlf=true`，Git 提示未来检出可能转为 CRLF；本次保留其原有换行风格，`git diff --check` 退出 0，未修改 Git 配置。
