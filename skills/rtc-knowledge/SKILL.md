# RTC Knowledge Skill — 实时音视频行业知识库

## Metadata
- **skill_name**: rtc-knowledge
- **version**: 1.0.0
- **description**: 腾讯TRTC、声网Agora、即构ZEGO 三大 RTC 厂商的产品功能、API、定价、架构对比知识库。服务于 TRTC 技术支持和产品架构工作。
- **author**: sumn
- **created**: 2026-03-10
- **tags**: RTC, TRTC, Agora, ZEGO, 音视频, 实时通信

## Context

用户（老板）是**腾讯TRTC的技术支持和产品架构**角色，需要：
1. 深入掌握 TRTC 全部能力，为客户提供技术方案
2. 了解竞品（声网Agora、即构ZEGO）的功能和定价，用于竞品对比和竞标
3. 能够快速回答客户关于三家产品的差异化问题

## When to Load

当对话涉及以下关键词时自动加载此 Skill：
- TRTC、实时音视频、腾讯RTC
- 声网、Agora、shengwang
- 即构、ZEGO、zego
- RTC 定价、RTC 报价、RTC 对比
- 音视频通话、互动直播、连麦、低延时
- 云端录制、混流、转推CDN
- AI 降噪、AI 字幕、对话式 AI

## References

详细知识分文件存储：
- `references/trtc-full.md` — 腾讯 TRTC 完整产品知识（功能/API/定价/套餐/架构）
- `references/agora-full.md` — 声网 Agora 完整产品知识
- `references/zego-full.md` — 即构 ZEGO 完整产品知识
- `references/comparison.md` — 三家横向对比（定价/功能/优劣势/选型建议）

## Usage Guidelines

1. **回答 TRTC 相关问题时**：优先引用 `trtc-full.md`，给出精确的 API 名称、参数和最佳实践
2. **竞品对比时**：引用 `comparison.md`，客观呈现数据，突出 TRTC 差异化优势
3. **报价对比时**：给出三家的精确单价表和套餐包方案，标注数据来源时间
4. **技术方案设计时**：结合 TRTC 的产品功能矩阵，推荐最佳架构组合
5. **注意**：价格信息可能随时间变化，重要商务场景建议确认官网最新价格
6. **⚠️ TRTC 计费核心规则（必须严格遵循）**：
   - **纯音频**：按每人**在房时长**计费，不是按订阅流数计费
   - **视频场景**：按**订阅方接收到的视频流**计费，有视频订阅就**不再额外收音频费用**
   - 发送方开了视频 ≠ 发送方按视频计费，费用取决于「该用户订阅了什么」
   - 混合时段（先视频后音频）按时段拆分，分别计费
   - 详见 `trtc-full.md` 第五章的 4 个场景示例
