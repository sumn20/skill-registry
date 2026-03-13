---
name: app-sdk-analysis
description: Analyze Android apps to identify integrated SDKs and third-party libraries. This skill should be used when the user provides an app name or package name and wants to know what SDKs are integrated in the app. It generates a professional analysis report covering SDK categories (audio/video, ads, analytics, payment, social, etc.), giving actionable competitive intelligence for RTC and audio-video market analysis. Trigger phrases include SDK分析, 竞品分析, 分析这个App的SDK, 这个应用用了什么SDK, 看看这个app集成了什么.
---

# App SDK Analysis Skill

## Purpose

Analyze Android applications to identify all integrated SDKs and third-party libraries, then generate a professional analysis report. The report covers SDK categorization (audio/video, ads, analytics, crash monitoring, payment, push notification, social sharing, etc.), giving actionable competitive intelligence especially for the RTC/audio-video market.

## When to Use

- User provides an app name (e.g., "微信", "抖音", "快手", "Clubhouse") or Android package name (e.g., "com.tencent.mobileqq")
- User asks to analyze what SDKs an app uses
- User wants competitive intelligence on third-party library usage
- User needs to understand the technology stack of a specific Android app

## Workflow

### Step 1: Identify the App

When user provides an app name or package name:

1. If a **package name** is provided (e.g., `com.tencent.mobileqq`), use it directly.
2. If an **app name** is provided (e.g., "微信"), search the web to find the correct package name. Common mappings are available in `references/common-apps.md`.
3. Confirm the app identity with the user if ambiguous.

### Step 2: Obtain the APK File

Use one of these methods to obtain the APK:

#### Method A: Download from App Store (应用宝)

Construct the app store info URL and download URL using this pattern:

1. Visit the app detail page: `https://sj.qq.com/appdetail/{package_name}`
2. Extract version and MD5 from the page's `__NEXT_DATA__` JSON:
   - Path: `props.pageProps.dynamicCardResponse.data.components[1].data.itemData[0]`
   - Fields: `version_name`, `md_5`
3. Construct download URL: `https://imtt2.dd.qq.com/sjy.00008/sjy.00004/16891/apk/{md5}.apk?fsname={package_name}_{version}.apk`

Use the `web_fetch` tool to access the app store page and extract info.

#### Method B: Download from APKPure

1. Construct APKPure download URL: `https://d.apkpure.com/b/XAPK/{package_name}?version=latest`
2. Or search: `https://apkpure.com/search?q={package_name}`

#### Method C: User provides APK file

If the user has the APK file locally, proceed directly to analysis.

### Step 3: Analyze the APK

**⚡ 使用内置脚本，无需现写代码。** 所有可复用工具位于 `scripts/` 目录。

#### 3.1 一站式扫描（推荐）

直接运行 `scan_apk.py`，一条命令完成 .so 扫描 + Manifest 解析 + SDK 匹配：

```bash
# 人类可读输出
python3 <skill_dir>/scripts/scan_apk.py <apk_path>

# JSON 输出（供程序消费或生成报告）
python3 <skill_dir>/scripts/scan_apk.py <apk_path> --json

# 指定 aapt 路径（脚本也会自动查找）
python3 <skill_dir>/scripts/scan_apk.py <apk_path> --aapt /path/to/aapt
```

`scan_apk.py` 会自动：
- 扫描所有 `.so` 文件，按架构分组 + 去重
- 提取 `AndroidManifest.xml`（二进制 AXML 格式）并解析所有组件
- 匹配内置的 SDK 特征库（.so 文件名 + Manifest 组件前缀）
- 自动查找系统中的 `aapt` 获取精确基本信息
- 扫描 `assets/` 目录

#### 3.2 单独解析 Manifest（可选）

如果只需要解析 Manifest：

```bash
# 先从 APK 提取 Manifest
unzip -o <apk_path> AndroidManifest.xml -d <temp_dir>/

# 解析
python3 <skill_dir>/scripts/parse_manifest.py <temp_dir>/AndroidManifest.xml
```

#### 3.3 补充搜索（按需）

`scan_apk.py` 的内置特征库覆盖常见 SDK，但不可能穷举。对于新出现的或小众 SDK，可以用 `unzip -l` + `grep` 做针对性搜索：

```bash
# 搜索特定关键词
unzip -l <apk_path> | grep -iE "(livekit|zego|agora|trtc)"

# 统计文件数
unzip -l <apk_path> | grep -iE "(zego)" | wc -l
```

#### 3.4 SDK 分类体系
匹配到的 SDK 按 16 个分类归类。详见 `references/sdk-categories.md`。

#### 3.5 扩展特征库
如需添加新 SDK 特征，直接编辑 `scripts/scan_apk.py` 中的 `KNOWN_SO_SIGNATURES` 和 `KNOWN_COMPONENT_PREFIXES` 字典。

### Step 4: Generate the Analysis Report

**Output Path**: Always save the report to `<workspace>/reports/` directory. Create the directory if it doesn't exist.

File naming convention: `<AppName>_SDK分析报告.md` (e.g., `会玩App_SDK分析报告.md`)

```bash
mkdir -p <workspace>/reports/
```

Generate a comprehensive report in the following format:

```markdown
# 📱 [App Name] SDK 分析报告

## 基本信息
| 项目 | 信息 |
|------|------|
| 应用名称 | [App Name] |
| 包名 | [package name] |
| 版本 | [version] |
| 目标 SDK | [targetSdkVersion] |
| 分析时间 | [timestamp] |

## 📊 SDK 统计概览
- 总计识别 SDK 数量: [N]
- 分类分布: [按类别统计]

## 🎥 音视频 SDK
[List audio/video SDKs with details]

## 👥 社交分享 SDK
[List social SDKs]

## 📢 广告 SDK
[List ad SDKs]

## 📊 数据分析 SDK
[List analytics SDKs]

## ⚠️ 崩溃监测 SDK
[List crash monitoring SDKs]

## 📲 消息推送 SDK
[List push notification SDKs]

## 💳 支付 SDK
[List payment SDKs]

## 📍 地图定位 SDK
[List map/location SDKs]

## 🔒 安全加密 SDK
[List security SDKs]

## ⚙️ 开发框架 SDK
[List framework SDKs]

## 🌐 网络通信 SDK
[List network SDKs]

## 🤖 人工智能 SDK
[List AI SDKs]

## 📦 其他 SDK
[List uncategorized SDKs]

## 💡 分析洞察
- 音视频技术栈分析（重点关注 RTC 供应商）
- 第三方服务依赖分析
- 技术选型特点
- 竞品对比建议
```

### Step 5: RTC/Audio-Video Deep Analysis

For audio/video SDKs specifically, provide deeper analysis:

1. **Identify RTC Provider**: Determine if the app uses 声网(Agora), 腾讯TRTC, 即构(ZEGO), 火山引擎RTC, 网易云信, 融云, or others
2. **Video/Audio Players**: Identify media player libraries (ExoPlayer, IJKPlayer, etc.)
3. **Live Streaming SDKs**: Detect live streaming capabilities
4. **WebRTC Usage**: Check for native WebRTC integration
5. **Competitive Insight**: Provide analysis of what the SDK choice means for competitive positioning

### Step 6: Output Text Summary (MUST be a standalone clean message)

After the Markdown report is saved, **always** generate a concise text summary and output it directly in the conversation as your reply.

**⚠️ CRITICAL OUTPUT RULE: The text summary MUST be the LAST and ONLY content in the assistant's final reply message.**

This means:
1. **Before outputting the summary**, complete ALL internal operations first: save the report file, update todo items, update memory files, etc.
2. **The summary message itself must contain NOTHING else** — no tool calls, no todo updates, no cleanup commands, no "让我更新记忆" or "现在清理临时文件" remarks. Just the pure analysis result.
3. **Cleanup (Step 7) should happen in a SEPARATE turn** after the summary has been delivered, or be batched into the same tool call batch as the report save (before the text output).
4. This ensures mobile users see a clean, readable result — not a wall of interleaved tool operations and analysis text.

**Execution sequence for the final phase:**
```
[Tool call batch 1] Save report file + Update todos + Update memory + Cleanup temp files (all in parallel)
[Assistant text reply] ONLY the text summary below — nothing else
```

**Summary format**:

```
## [App Name] SDK分析总结

**基本信息**：[包名] [版本] | [APK大小] | [架构] | [.so数量] | [SDK总数] | [开发者]

### 音视频方案
| RTC供应商 | 状态 | 证据 |
|-----------|------|------|
| [供应商名] | ✅/❌ | [关键.so或组件] |

- [集成深度和特色能力说明]

### 其他SDK一览
| 分类 | SDK |
|------|-----|
| [分类名] | [SDK列表] |
...

### 关键洞察
1. [洞察1]
2. [洞察2]
3. [洞察3]

⚠️ 以上为APK静态分析结论，仅能确认SDK是否集成，无法判断各功能的实际使用场景和业务权重。
```

**Rules**:
1. Keep the summary concise — aim for quick readability on a phone screen
2. Only state facts that static analysis can confirm (SDK is/isn't integrated)
3. Do NOT speculate on which SDK is "primary" vs "secondary" — static analysis cannot determine business-level routing
4. The Markdown file is the detailed record; the text summary is the quick-read version
5. **The text summary must be a standalone, clean message with zero operational noise**

### Step 7: Cleanup (Non-blocking)

After the analysis report AND text summary have been fully delivered to the user, clean up the downloaded APK and temporary files to free disk space.

**⚠️ CRITICAL: This step must NEVER block the delivery of results.**

**Execution rules:**
1. **Timing**: Only execute cleanup AFTER the Markdown report is saved AND the text summary has been output in the conversation. The user must already have all results before cleanup begins.
2. **Non-blocking**: Use `requires_approval: false` for the cleanup command — the `apk-temp/` directory is created by this skill within the workspace and is safe to delete without user confirmation.
3. **Graceful failure**: If cleanup fails for any reason (e.g., directory already deleted, permission issue), simply note it and move on. Never retry or ask the user to intervene.
4. **No user action required**: The user should NOT need to approve, click, or interact with this step in any way. This is especially important for mobile users who cannot access the IDE approval UI.

```bash
# This command MUST use requires_approval: false
rm -rf <workspace>/apk-temp/ && echo "✅ 已清理 apk-temp 缓存目录" || echo "⚠️ 清理跳过（目录可能已不存在）"
```

> 💡 If the cleanup step is somehow skipped or fails, the `apk-temp/` directory can be manually deleted later. It will NOT affect the analysis report.

## Directory Structure

After analysis, the workspace should look like this:

```
<workspace>/
├── reports/                          # 📄 所有分析报告输出目录
│   ├── XXApp_SDK分析报告.md
│   └── YYApp_SDK分析报告.md
├── .codebuddy/skills/app-sdk-analysis/  # 🔧 Skill 文件
│   ├── SKILL.md
│   ├── scripts/                     # 🔧 可复用工具脚本
│   │   ├── scan_apk.py             #   一站式 APK 扫描（.so + Manifest + SDK匹配）
│   │   └── parse_manifest.py       #   AXML Manifest 解析器
│   └── references/
│       ├── rtc-vendor-signatures.md
│       ├── common-apps.md
│       └── sdk-categories.md
└── app-sdk-analysis.zip              # 📦 可分享的 Skill 包
```

> ⚠️ `apk-temp/` is a temporary directory used during analysis and should NOT exist after Step 7 cleanup. If cleanup was skipped (e.g., mobile session), it can be manually deleted later.

## Important Notes

- The analysis is based on static scanning of the APK's binary structure - it cannot detect SDKs that are loaded dynamically at runtime
- Some SDKs may use code obfuscation making identification harder
- The rules database covers 2358+ known libraries but is not exhaustive
- Always note the analysis timestamp as SDK usage may change between app versions
- When the APK cannot be obtained automatically, guide the user to manually download and provide the APK file

## Reference Files

- `references/sdk-categories.md`: Complete SDK category definitions and common SDKs per category
- `references/common-apps.md`: Common app name to package name mappings
- `references/rtc-vendor-signatures.md`: RTC vendor SDK identification signatures
