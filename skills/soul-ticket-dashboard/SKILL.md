---
name: soul-ticket-dashboard
description: Soul 工单深度分析工具。当用户提到"分析soul的工单"、"soul工单"、"soul反馈表"等关键词并提供 Excel 表格时，自动执行此 skill，读取工单表格中的反馈渠道、channelId、反馈时间，拼接 TRTC 仪表盘 URL、通话详情页 URL，并进行深度事件分析和根因推断。
---

# Soul 工单深度分析 (v4)

## 用途
批量为 Soul 语音/视频反馈工单生成 TRTC 仪表盘链接、通话详情页链接，并自动分析通话事件、音频指标，输出简洁排查结论和问题标签。

## 触发时机
当用户提到以下关键词并附带 Excel 表格时触发：
- "分析soul的工单"
- "soul工单"
- "soul反馈表"
- "soul仪表盘"
- "soul深度分析"

## 前置依赖

```bash
pip install openpyxl playwright
playwright install chromium
```

## 执行流程

### 模式一：基础模式（仅搜索页 URL）

```bash
python3 {skill_base_dir}/scripts/gen_dashboard.py <input.xlsx> <output.xlsx>
```

生成 U 列「仪表盘」——TRTC 监控搜索页 URL，可直接点击打开查看房间列表。

### 模式二：详情模式（搜索页 + 通话详情页 URL）

```bash
python3 {skill_base_dir}/scripts/gen_dashboard.py <input.xlsx> <output.xlsx> --detail
```

额外获取 V 列「通话详情」——TRTC 通话详情页 URL。

**前置条件**：需要 OA 登录认证。脚本通过 Playwright 持久化浏览器上下文实现自动登录：
- 首次运行会弹出 Chromium 浏览器窗口，需要手动完成 iOA 验证
- 验证成功后 Cookie 持久化保存在 `~/.soul-trtc-profile`，后续运行自动复用

### 模式三：深度分析（推荐，完整功能）

```bash
python3 {skill_base_dir}/scripts/gen_dashboard.py <input.xlsx> <output.xlsx> --deep
```

`--deep` 隐含 `--detail` 和 `--analyze`，一次性完成所有功能：
1. 拼接仪表盘搜索页 URL（U列）
2. 获取通话详情页 URL（V列）
3. 调用 TRTC 深度 API，分析双端事件 + 音频指标
4. 生成**简洁排查结论**（T列）+ **问题标签**（S列）

每条工单调用 5-6 个 TRTC API：
- `getUserInfo(sender)` + `getUserInfo(receiver)` → 获取设备/网络/TinyId
- `getElasticSearchData(IndexType=event, DataType=detail_event)` × 2 → 双端事件列表
- `getElasticSearchData(IndexType=up, DataType=aCapEnergy)` → 发送端采集音量
- `getElasticSearchData(IndexType=down, DataType=aPlayEnergy)` → 接收端播放音量

### 参数说明
| 参数 | 说明 |
|------|------|
| `<input.xlsx>` | 用户提供的 Soul 工单 Excel 文件路径 |
| `<output.xlsx>` | 输出文件路径 |
| `--detail` | 获取通话详情页 URL（需 OA 登录） |
| `--analyze` | 生成排查结论（隐含 `--detail`） |
| `--deep` | 深度分析模式（隐含 `--analyze` 和 `--detail`） |

## 表格结构约定

### 输入列（按列名自动定位）
| 列名 | 说明 | 必需 |
|------|------|------|
| 反馈渠道 | 语音匹配 / 私聊语音 / 视频匹配 | ✅ |
| channelId | 通话房间标识（字符串房间号） | ✅ |
| 反馈时间 | 用户反馈的时间点 | ✅ |
| 反馈文本 | 包含问题类型、peerUIDs等信息 | 深度分析需要 |
| 手机型号 | 用户手机型号 | 可选 |
| 系统 | 操作系统（iOS/安卓） | 可选 |
| 版本 | APP版本 | 可选 |
| network | 网络类型 | 可选 |
| 是否为扬声器 | 扬声器状态 | 可选 |
| 耳机类型 | 耳机类型 | 可选 |
| 呼叫方uid | 呼叫方用户ID（备选） | 可选 |
| 被呼叫方uid | 被呼叫方用户ID（备选） | 可选 |

### 输出列
| 列 | 列号 | 列名 | 说明 |
|----|------|------|------|
| S | 19 | 问题标签 | 自动填充问题分类标签（如"mute操作"、"未调用startlocalaudio"） |
| T | 20 | 排查结论 | **简洁结论**（如"android上行端 mute 静音"、"iOS 切后台未执行 startLocalAudio"） |
| U | 21 | 仪表盘 | TRTC 监控搜索页 URL |
| V | 22 | 通话详情 | TRTC 通话详情页 URL（仅 `--detail` 模式） |

## sdkAppId 映射规则
| 反馈渠道 | sdkAppId |
|---------|----------|
| 语音匹配 | 1600050511 |
| 视频匹配 | 1600050511 |
| 私聊语音 | 1600050509 |

## 排查结论体系 (v4)

结论风格参照人工排查样本，**简洁直接，指明平台和端**：

### 结论类型（按优先级排列）

| 优先级 | 结论 | 问题标签 | 说明 |
|--------|------|---------|------|
| 1 | 房内只有一个人 | 房间只有一个人 | 房间只有1个用户 |
| 2 | {平台} 上行端超时退房 | 断连超时退房 | 超时断连退出 |
| 3 | {平台} 无采集权限 | 没有麦克风权限 | 无麦克风权限 |
| 4 | {平台}采集启动失败 | - | 可能有系统电话抢占 |
| 5 | {平台}上行端 mute 静音 | mute操作 | 对端调用了mute |
| 6 | iOS 切后台未执行 startLocalAudio | 未调用startlocalaudio | iOS切后台后未恢复采集 |
| 7 | android 后台采集无声 | 安卓后台采集无声 | 安卓切后台后采集无声 |
| 8 | {平台}上行端采播打断 | 正常采集打断事件 | 采集被系统打断 |
| 9 | {平台}采集无声 | - | 采集音量大量为零 |
| 10 | {平台}采集弱音 | - | 采集音量很低 |
| 11 | iOS 漏回声？ | 回声问题 | 回声/杂音问题 |
| 12 | 疑似没讲话 | - | 数据正常但音量低 |
| 13 | 数据正常 | - | 无任何异常 |

其中 `{平台}` 会根据 getUserInfo 或反馈者系统反推自动填充为 `android` / `iOS` / `未知`。

## 事件分析引擎检测项 (v4 增强)

| 检测项 | 事件码 | 说明 |
|--------|--------|------|
| APP前后台切换 | 2001 | Para1=1切后台, Para1=0回前台 |
| 停止采集/静音 | 3001 | Para1=1 表示停止 |
| 本地mute静音 | 3011 | Para1=1 mute, Para1=0 取消 |
| 采集打断开始 | 3005 | 系统级打断（如电话） |
| 采集打断恢复 | 3006 | 打断恢复 |
| 采集启动失败 | 3013 | 麦克风采集启动失败 |
| 麦克风权限 | 3014 | Para1=0 无权限 |
| startLocalAudio | 6001 | 调用startLocalAudio |
| stopLocalAudio | 6002 | 调用stopLocalAudio |
| 采样率异常变更 | 3008 | 前后两次采样率不同 |
| 首帧音频缺失 | 5009 | 无此事件表示未发送首帧 |
| 超时退房 | 7001(P1=2) | 断连超时退出 |
| 在后台退出通话 | 7001 | 切后台后直接退出 |
| 音频采集音量 | - | >80%为零=采集无声, avg<200=弱音 |
| 音频播放音量 | - | >80%为零=播放无声 |

## URL 格式

### 搜索页 URL
```
https://trtc-monitor.woa.com/?sdkAppId={sdkAppId}&roomNum={channelId}&environment=inland&startTs={startTs}&endTs={endTs}
```

### 通话详情页 URL
```
https://trtc-monitor.woa.com/trtc/monitor/call-details?commId={CommId}&userId=&roomNum={RoomNum}&roomStr={channelId}&createTime={CreateTime}&destroyTime={DestroyTime}&duration={Duration}&finished=true&sdkAppid={sdkAppId}&environment=inland
```

## Playwright 持久化上下文
- Profile路径: `~/.soul-trtc-profile`
- 用于 OA 登录 Cookie 持久化，首次需手动完成 iOA 验证
- 验证成功后后续运行自动复用登录态

## 输出要求
- URL 单元格显示原始 URL 全文
- 同时设为可点击超链接（蓝色下划线）
- 已有链接的行自动跳过（基础/详情模式）
- 深度分析模式会覆盖已有结论
- 问题标签仅在有匹配标签时写入

## 故障排除
- **Playwright 未安装**：运行 `pip install playwright && playwright install chromium`
- **OA 登录超时**：5分钟内未完成验证会自动退出，重新运行即可
- **API 无返回**：可能房间号不存在或时间范围不匹配，会跳过该行
- **运行速度**：深度分析每条约 8-10 秒（5-6 个 API 调用），100 条预计约 15 分钟

## 版本历史
- **v1**: 基础 URL 拼接
- **v2**: 深度分析 + 根因推断
- **v3**: 根因独立列(U列)
- **v4**: 学习人工排查样本，全面优化：
  - 结论改为简洁风格（匹配老板排查习惯）
  - 去掉独立根因列，结论本身就是根因
  - 新增问题标签自动生成(S列)
  - 新增 12+ 种根因类型（mute、startLocalAudio、采集打断、无权限、房间只有一个人等）
  - 事件分析引擎增加 7 个新检测项（3011/3005/3006/3013/3014/6001/6002）
  - 平台自动检测（android/iOS），结论中指明对端平台
  - 音频指标分析增加弱音检测（avg<200）
