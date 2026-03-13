---
name: trtc-dashboard
description: "从用户输入中提取 sdkAppId/userId/roomNum/时间/问题描述等信息，通过 TRTC 内网 API 深度分析通话数据并给出排查结论。当用户提到仪表盘、监控链接、TRTC查询、通话质量排查，或者给出包含 sdkAppId/房间号/userId 等信息的内容时自动触发。"
---

# TRTC 通话排查助手

## 触发条件

以下任一情况触发本技能：
- 用户提到"仪表盘"、"监控链接"、"排查"、"通话质量"
- 用户给出包含 sdkAppId、userId、roomNum 的文字/表格/文档
- 用户直接给出参数要求排查或生成链接

## 输入参数

| 参数 | 必填 | 说明 | 模糊匹配 |
|------|------|------|---------|
| sdkAppId | 是 | 缺少则询问 | sdkappid、appid、应用ID |
| userId | 否 | 用于搜索 | userid、用户ID、UID |
| roomNum | 否 | 房间号 | roomnum、roomid、房间号 |
| 问题描述 | 否 | 用于辅助理解场景 | 问题、描述、反馈、现象 |
| 发送端userId | 否 | 被投诉方 | sender、发送方 |
| 接收端userId | 否 | 反馈方/投诉方 | receiver、接收方 |
| environment | 自动 | 200开头→intl，其他→inland | 环境、站点 |
| 时间 | 否 | 见下方规则 | time、日期、通话时间 |

### 时间处理

| 用户输入 | startTs | endTs |
|---------|---------|-------|
| 不提供 | 当前时间 - 14天 00:00:00 | 当前时间所在日 23:59:59 |
| 只给日期 | 当天 00:00:00 | 当天 23:59:59 |
| 日期+时间点 | 该时间点 - 30分钟 | 该时间点 + 30分钟 |
| 起止时间 | 起始时间戳 | 结束时间戳 |

**年份推断**：不带年份 → 当前年份。**时间戳必须用 python3 代码计算，禁止心算。**

## 经验库（自学习）

本 skill 维护一个经验库文件 `{skill_base_dir}/lessons.md`，用于沉淀排查中的纠错经验。

### 排查前：读取经验

**每次执行排查前，必须先读取 `{skill_base_dir}/lessons.md`**，将已有经验作为判断的补充依据。如果当前案例的数据特征匹配某条经验规则，应优先采纳经验规则的判断逻辑。

### 被纠正时：写入经验

当用户指出结论错误并给出正确结论时，**必须立即将本次纠正追加到 `{skill_base_dir}/lessons.md`**，格式：

```markdown
## [序号] 简短标题
- **场景**: 什么数据特征触发了这个判断
- **错误结论**: AI 给出的错误判断
- **正确结论**: 用户纠正后的正确判断
- **根因**: 为什么判断错了（数据缺失/阈值不对/优先级错误/...）
- **经验规则**: 提炼出的通用规则，未来遇到类似场景直接套用
- **日期**: YYYY-MM-DD
```

### 经验应用优先级

1. 经验规则中的**强信号**（如"系统播放设备音量=0"）优先于脚本 infer_conclusion 的默认判断
2. 如果经验规则与脚本结论矛盾，以经验规则为准，并在输出中标注"(基于经验库)"
3. 如果脚本结论已经被页面事件覆盖过，不再用经验规则二次覆盖

## 执行流程

### Step 0: 读取经验库

```
读取 {skill_base_dir}/lessons.md，记住所有经验规则。
```

### Step 1: 提取参数 & 计算时间戳

从用户输入中提取所有参数。用 Python 精确计算**秒级**时间戳：
```python
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=8))
dt = datetime(2026, 3, 4, 22, 47, 0, tzinfo=tz)
ts = int(dt.timestamp())
```

关键：如果用户提到了两个 userId 和一个"听不到/看不到"之类的描述，需要判断谁是发送端谁是接收端：
- **反馈者 = 接收端**（听不到别人声音的那个人）
- **被投诉方 = 发送端**（声音/画面传不过来的那个人）

### Step 2: 调用脚本

```bash
python3 {skill_base_dir}/scripts/get_detail_url.py \
  --sdkappid {sdkAppId} \
  --start-ts {startTs} \
  --end-ts {endTs} \
  [--room {roomNum}] \
  [--userid {userId}] \
  [--environment {environment}] \
  [--sender {发送端userId}] \
  [--receiver {接收端userId}] \
  [--description "{问题描述}"]
```

**前置条件**：`pip install playwright && playwright install chromium`

脚本会自动执行：
1. **getRoomList** → 获取 CommId，拼接通话详情页 URL
2. **getUserInfo** (双端) → 获取设备型号、系统、网络、TinyId
3. **getElasticSearchData**(detail_event) × 2 → 双端事件列表
4. **getElasticSearchData**(aCapEnergy) → 发送端采集音量
5. **getElasticSearchData**(aPlayEnergy) → 接收端播放音量
6. 基于真实数据 → 推断结论

**首次运行**会弹出浏览器窗口，需手动完成 iOA 验证。之后 Cookie 自动复用（`~/.trtc-dashboard-profile`）。

脚本输出 JSON：
```json
{
  "success": true,
  "detail_url": "https://trtc-monitor.woa.com/trtc/monitor/call-details?commId=xxx&...",
  "room_info": { "comm_id": "xxx", "duration": 3600, "user_count": 2, ... },
  "deep_analysis": {
    "sender": { "platform": "android", "findings": ["APP切后台(17:05:23)"], "flags": {...} },
    "receiver": { "platform": "iOS", "findings": [], "flags": {...} },
    "audio": { "cap_stats": {"avg": 0, "zero_pct": 95, "silent": true}, "play_stats": {...} }
  },
  "conclusion": "android 后台采集无声",
  "tag": "安卓后台采集无声"
}
```

### Step 3: 输出结论

**只输出结论和通话详情链接，不写报告、不做额外总结。**

## 输出格式

```
**结论：android 后台采集无声**

通话详情：https://trtc-monitor.woa.com/trtc/monitor/call-details?commId=xxx&...
```

输出要求：
1. **只输出两行**：结论 + 通话详情 URL，不要输出通话时长/房间/设备等信息
2. **结论必须来自脚本返回的 `conclusion` 字段**，不要自己猜测
3. 链接可直接点击，不要代码块包裹
4. 如果没有提供 sender/receiver，只输出通话详情 URL
5. **不要写分析报告，不要输出排查数据明细**

## 降级策略

1. **无 sender/receiver** → 只输出详情 URL，不给结论
2. **脚本获取通话详情失败** → 输出搜索页 URL
3. **深度分析部分 API 失败** → 输出已获取的数据 + "部分数据缺失"提示

## 搜索页 URL（降级用）

```
https://trtc-monitor.woa.com/?sdkAppId={sdkAppId}[&userId={userId}][&roomNum={roomNum}]&environment={environment}&startTs={startTs_ms}&endTs={endTs_ms}
```
搜索页 URL 使用**毫秒级**时间戳（×1000），参数为空时不拼接。

## 注意事项

1. **时间戳必须用代码计算**，禁止心算
2. **sdkAppId 不能为空**，缺少则询问用户
3. **链接要可直接点击**
4. **结论基于数据，不猜测**——没有数据就说"数据不足"
5. **批量查询时每条之间间隔 0.3 秒**，避免 API 限流
6. **用户纠正时必须写入经验库**——这是强制要求，不可跳过
7. **排查前必须读取经验库**——已有经验优先于默认判断逻辑
