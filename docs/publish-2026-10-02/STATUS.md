# v1.1.0 发布与工作区归并

2026-10-02，用户接受已知限制，授权上传私人 GitHub 仓库、归并主目录和清理相关临时内容；Mozilla 提交签名由用户在终端执行。本文件取代旧文档中的“现役目录”描述，历史报告与证据保留当时结论。

2026-10-19 仓库已公开，本机用户名与工作目录已脱敏。历史校验值对应脱敏前文件，不代表当前公开副本的字节身份；最新发布附件状态见下表及 [脱敏说明](../PRIVACY-REDACTION.md)。

## 当前交付

- 主工作区以当前克隆目录为准，分支 `main`，版本 v1.1.0。
- 公开仓库：<https://github.com/ono404/chatgpt-route-inspector-firefox>。
- 发布入口：<https://github.com/ono404/chatgpt-route-inspector-firefox/releases/tag/v1.1.0-firefox>；标注未签名自用构建及已知限制。
- 业务目录 `src schemas _locales icons manifest` 与上游 v1.1.0 `dd5ea3366cdb3ed85025fc7a41f6e89ff1ee7552` 的 Git 内容一致。本次只调整交付文档和 ESLint 对归档 Node 证据脚本的环境声明，未修改业务解析器。
- 用户真实导出、`.workbuddy/`、`.zcodeignore`、本地归档和依赖未上传。

## 验证与限制

本轮 typecheck、lint、442 项业务测试、82 项工具测试、Firefox 产物校验通过。迁移后的 Firefox / Chromium 各 30 文件，8 个 JS 逐字节一致；冻结发布文件与迁移前 SHA-256 一致。检查日志在本地 `local-archive/publish-checks-2026-10-02/`。此前 FF157 受控探针 32/32 是历史真机证据，本次没有启动浏览器或重复真实流量测试。

14:47 起真实样本：6 条 live，6 条 `stream_parse_failed`，0 条完成、0 条重复。旧版禁用并刷新后重复未再出现，不能推断流式失败已解决。上游同源码包含该失败路径，但缺少同流量跨浏览器对照，根因未确认。用户决定暂不修业务代码。WM 模型字段和路由展示不证明服务器真实内部推理模式。

Mozilla 尚未提交签名；新版尚未完成日常覆盖安装。真实更新事件、FF128、Chromium E2E 等未完成项保留在 BLOCKED.md。旧版签名包不能作为新版签名凭证。

## 当前公开文件

| 主目录 release 下文件 | SHA-256 |
|---|---|
| chatgpt-route-inspector-firefox-1.1.0.xpi | `04af228b03f85e954d894a859fb87afcf1bfbc9cd449da881c2f25f99c0165ae` |
| chatgpt-route-inspector-firefox-1.1.0.build.json | `4f7b019d47d573df03b6272b901986a9abdb1d2396103f43c92ec46c0ec7184b` |
| chatgpt-route-inspector-firefox-1.1.0-source.zip | `51523360d4063fc939177672b9bf990278a1e0495f4e715f5e22b0cc49888846` |

公开构建记录的本机绝对路径已替换为仓库相对路径，并同步更新 SHA256SUMS；XPI 与源码 ZIP 未重打包，哈希保持不变。再次运行探针时，在仓库根目录执行并指定 `--dist dist/firefox`，XPI 与构建记录放在 `release/`；输出必须用新的、不存在的路径。探针会自行启动专用浏览器，不能当作只读检查。

## 本地保全与清理

原主目录未提交的四份文档、旧签名包及生成物已复制至 `local-archive/2026-10-02-pre-consolidation/`，145 文件逐一验证；Git stash 和 `repository-all-refs.bundle` 保留旧分支与现场。未知 `.workbuddy/` 和 `.zcodeignore` 保留原位并仅用本地 exclude 排除。

`run-01` 与八个明确相关的 `run-*` 临时目录已压缩到 `local-archive/2026-10-02-consolidation/`，共九份 ZIP；逐文件读取比对 SHA-256，索引为 `ARCHIVE-INDEX.json`。只排除可重新生成的 node_modules、Python 缓存和另行保全的 Git 元数据。隔离 worktree 已由 Git 正常移除。

自动审批以 `blocked by policy` 拒绝递归删除，未提供更具体原因，命令未执行。八个临时目录与主目录旧 `.tmp`、output 改为移动至 `local-archive/retired-workspaces-2026-10-02/`，原路径均已腾空，保留可恢复备份。旧生成目录仍在 `local-archive/replaced-generated-2026-10-02/`，未声称已释放这些备份的磁盘空间。新的 release 只保留本次交付文件。Git 分支、标签与 stash 留存。
