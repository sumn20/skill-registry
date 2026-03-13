---
name: trtc-dashboard
description: "从用户输入（文字、表格、文档）中提取 sdkAppId/userId/roomNum/时间 等信息，拼接 TRTC 监控仪表盘链接。当用户提到仪表盘、监控链接、TRTC查询、通话质量排查，或者给出包含 sdkAppId/房间号/userId 等信息的内容时自动触发。"
---

# TRTC 监控仪表盘链接生成器

## 触发条件

以下任一情况触发本技能：
- 用户提到"仪表盘"、"监控链接"、"排查"、"通话质量"
- 用户给出包含 sdkAppId、userId、roomNum 的文字/表格/文档
- 用户直接给出参数要求生成链接

## URL 模板

```
https://trtc-monitor.woa.com/?sdkAppId={sdkAppId}[&userId={userId}][&roomNum={roomNum}]&environment={environment}&startTs={startTs}&endTs={endTs}
```

## 参数规则

### sdkAppId（必填）
- 不能为空，必须存在
- 用于判断环境（见 environment 规则）

### userId（可选）
- 可以为空，为空时 **不拼接** 此参数
- 从输入中提取，可能的字段名：userId、用户ID、user_id、用户标识

### roomNum（可选）
- 可以为空，为空时 **不拼接** 此参数
- 从输入中提取，可能的字段名：roomNum、roomId、房间号、房间ID、room

### environment（自动判断）
- 规则优先级：
  1. 用户明确说明"国际站" → `intl`
  2. sdkAppId 以 `200` 开头 → `intl`
  3. 其他所有情况 → `inland`

### startTs / endTs（毫秒级时间戳，UTC+8 北京时间）

**时间处理规则（按优先级）：**

| 用户输入 | startTs | endTs |
|---------|---------|-------|
| 不提供时间 | 当前时间 - 14天 00:00:00.000 | 当前时间所在日 23:59:59.999 |
| 只给日期（如"3月4日"） | 当天 00:00:00.000 | 当天 23:59:59.999 |
| 给日期+单个时间点（如"3月4日 22:47"） | 该时间点的毫秒时间戳 | 该时间点 + 5分钟 |
| 给起止时间（如"22:47 ~ 22:50"） | 起始时间的毫秒时间戳 | 结束时间的毫秒时间戳 |
| 给毫秒时间戳 | 直接使用 | 直接使用 |

**年份推断**：用户只说"X月X日"不带年份 → 使用系统 Current date 中的当前年份。

**时间戳计算**：必须用代码（python3）精确计算，**禁止心算**。示例：
```python
from datetime import datetime, timezone, timedelta
tz = timezone(timedelta(hours=8))
dt = datetime(2026, 3, 4, 0, 0, 0, tzinfo=tz)
ts = int(dt.timestamp() * 1000)
```

## 输入解析

用户输入可能是以下任一形式，需要自动识别并提取参数：

### 1. 直接文字
```
sdkappid：1600092866 房间号：ic4ex78iy6lqp1 userid：bhhcefebjjcicagb 时间：3月4日
```
→ 提取各字段，拼接1条链接

### 2. 表格（Markdown/Excel/截图文字）
```
| sdkAppId | userId | roomNum | 时间 |
|----------|--------|---------|------|
| 1600092866 | abc123 | room001 | 3月4日 |
| 2000012345 | def456 | room002 | 3月5日 14:30 |
```
→ 逐行提取，拼接多条链接，用序号列出

### 3. 文档/长文本
从中提取所有出现的 sdkAppId、userId、roomNum、时间信息，可能散落在不同段落。

### 4. 批量同 sdkAppId
用户可能给一个 sdkAppId + 多组 userId/roomNum/时间 → 每组生成一条链接。

## 字段名模糊匹配

输入中的字段名可能不标准，需模糊识别：

| 标准参数 | 可能的输入写法 |
|---------|--------------|
| sdkAppId | sdkappid、appid、SDK AppId、应用ID、AppID |
| userId | userid、用户ID、user_id、用户标识、UID |
| roomNum | roomnum、roomid、房间号、房间ID、room、RoomId |
| environment | 环境、站点、国内站/国际站 |
| 时间 | time、日期、date、时间段、通话时间 |

## 输出格式

### 单条链接
```
https://trtc-monitor.woa.com/?sdkAppId=1600092866&userId=bhhcefebjjcicagb&roomNum=ic4ex78iy6lqp1&environment=inland&startTs=1772553600000&endTs=1772639999999

> 📋 environment: inland | 时间: 2026-03-04 00:00:00 ~ 23:59:59
```

### 多条链接（表格/批量输入）
```
**1.** userId: abc123 | roomNum: room001
https://trtc-monitor.woa.com/?sdkAppId=...&userId=abc123&roomNum=room001&environment=inland&startTs=...&endTs=...

**2.** userId: def456 | roomNum: room002
https://trtc-monitor.woa.com/?sdkAppId=...&userId=def456&roomNum=room002&environment=intl&startTs=...&endTs=...
```

## 注意事项

1. **时间戳必须用代码计算**，不能心算，避免年份/月份换算错误
2. **参数为空就不拼接**，不要拼 `&userId=&roomNum=`
3. **sdkAppId 不能为空**，如果输入中没有 sdkAppId，必须向用户询问
4. **链接要可直接点击**，不要用代码块包裹主链接
5. **批量时注明序号和关键标识**，方便用户区分
