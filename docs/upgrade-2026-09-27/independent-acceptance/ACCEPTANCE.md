# round2 独立验收结论（2026-09-27）

对象：C:\workspace\run-01，提交 8d01fd5。
结论：通过本轮两处假绿灯修复的验收。v1.0.9 源码同步与本地交付结论维持通过；不扩大到真实账号流量、成功 SSE、签名或日常安装。

## 本轮独立重跑

- npm run lint：退出 0。
- npm run test:firefox-tooling：56 项通过，退出 0。
- A 正式包：27/27，退出 0，见 official.json / official.log。
- B 旧 tracker 故障包：身份通过，第 19 项上下文关联断言失败，26 PASS / 1 FAIL，退出 4，见 old-tracker.json / old-tracker.log。
- C 禁导航探针：与当前正式探针仅两条目标 pushState 改为 void 0；身份通过后第 19 项拒绝未到达正式地址，26 PASS / 1 FAIL，退出 4，见 no-navigation.json / no-navigation.log。
- A 阶段核实：临时、正式、无关路径均正确；revision 为 0→2→4→5；前两阶段 context ID 保持，无关阶段切换；oursCurrent=false；无关页浮窗存在且显示等待下一次回答。
- 业务目录对上游 99f982d 及修正前 f1f198e 无差异；交付 worktree 干净；原工作区仍为四份文档修改和 .workbuddy/ 未跟踪状态。
- 正式 XPI、源码 ZIP、build.json 哈希保持原值；历史原始日志未修改。本次验收未修改业务源码、探针或提交。

## 哈希与措辞勘误

A/B 探针 SHA256：a204ae0afb0c413e4e8d6a0e4cf81fc5bfcf5c2ea87d654d04d85aa65d1da303。
C 禁导航副本 SHA256：aae7ba5d3b21eb49594334e76b7b0752846d235dbf58a87d6c95f16cedc74bfd。
执行者聊天报告末句“A/B/C 三份 JSON 记录一致”不准确；A/B 相同，C 因故意改动两行而不同。原始 JSON 与文件实测哈希正确，这不是证据造假或本轮阻塞项。

XPI SHA256：34ca9440d7ed25b7d40570a8272fa672fedbba8b4739f557f1075399ec2da523。
源码 ZIP SHA256：0cc2412fef597d0ea2d6a3b5ac2986c7f178f7a9c13a1c83e9f7a49cd16a73d0。
build.json SHA256：15debe2ae37957a21c7f91161e6627acc33afdd6dd67e29ae00268b6451e9dab。

## 保留边界

验收的是现有专用临时 profile 中的受控场景：合成请求、真实未认证拒绝响应、导航上下文及浮窗关联。成功流式响应身份与模型路由、真实账号流量、FF128、真实更新、断线卡片、Chromium E2E 缺环境等仍按已有记录保留。正式包未签名、未上传、未日常安装。

## 归档说明

2026-09-27 知识收尾将本报告和 3 份 JSON / 3 份日志保存为脱敏副本，将用户名替换为 <user>，统一为 LF 并去除行尾空白；原件继续保留。来源与复制前后 SHA-256 见 [PROVENANCE.json](PROVENANCE.json)。清单记录原件及归档文件的哈希；本报告另追加此归档说明。文中的工作区干净状态是验收当时快照，后续文档提交不改变代码验收对象。
