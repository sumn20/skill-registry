---
name: app-company-lookup
description: 查询App归属公司或公司旗下App。当用户提供一个App名称，查询它的开发商/运营商/归属公司；或提供一个公司名称，查询该公司发布了哪些App。数据来源为腾讯应用宝(sj.qq.com)和web搜索。触发词包括：查一下这个App是哪个公司的、这个公司有什么App、App归属、开发商是谁、运营商查询、公司查App、App查公司、应用宝查询。
---

# App-Company Lookup Skill

## Purpose

查询 App 与公司之间的归属关系，支持双向查询：
1. **App → 公司**：给定 App 名称，查询其开发商和运营商
2. **公司 → App**：给定公司名称，查询该公司旗下发布的 App

## Workflow

### 场景1：App 名称 → 查公司归属

这是最稳定可靠的路径。

**Step 1**: 运行脚本搜索 App 名称

```bash
python3 <skill_dir>/scripts/search_app.py "<App名称>" --detail --limit 5
```

脚本访问 `https://sj.qq.com/search?q=<App名称>`，从页面 `__NEXT_DATA__` JSON 中提取结构化数据，返回 JSON 结果，包含字段：
- `name`: App名称
- `package_name`: 包名
- `developer`: 开发商
- `operator`: 运营商
- `icp_number`: 备案号
- `icp_entity`: 备案主体
- `version`: 版本号
- `size`: APK大小
- `category`: 分类

**Step 2**: 从返回结果中找到目标 App（名称最匹配的），输出结果

格式：

```
## 🔍 App 归属查询结果

| 项目 | 信息 |
|------|------|
| App名称 | [name] |
| 包名 | [package_name] |
| 开发商 | [developer] |
| 运营商 | [operator] |
| 备案号 | [icp_number] |
| 版本 | [version] |
| 大小 | [size] |
| 应用宝链接 | [detail_url] |
```

### 场景2：公司名称 → 查旗下 App

此场景需要两步走，因为应用宝不支持按公司名精确搜索。

**Step 1**: 用 web_search 搜索公司的 App 产品

```
搜索词: "{公司名}" App 应用宝
或: "{公司名}" 开发的App
或: "{公司简称}" 旗下产品
```

从搜索结果中提取可能的 App 名称列表。

**Step 2**: 逐个在应用宝验证

对搜索到的每个 App 名称，运行脚本验证：

```bash
python3 <skill_dir>/scripts/search_app.py "<App名称>" --detail --limit 3
```

检查返回 JSON 中第一条结果的 `developer` 字段是否包含目标公司名。

**Step 3**: 汇总输出

格式：

```
## 🏢 公司App查询结果

**公司**: [公司全称]

### 确认归属的App
| App名称 | 包名 | 开发商 | 运营商 | 应用宝链接 |
|---------|------|--------|--------|-----------|
| [name] | [pkg] | [dev] | [op] | [url] |

### ⚠️ 说明
- 以上结果基于应用宝(sj.qq.com)公开数据
- 如App已下架或未在应用宝上架，则无法查到
- 公司可能通过子公司/关联公司发布App，需结合天眼查等工商信息综合判断
```

## Fallback

如果脚本运行失败（如 playwright 未安装），可以用纯 web 方式替代：

1. 用 `web_fetch` 访问 `https://sj.qq.com/appdetail/{package_name}` 获取详情
2. 从页面的 `__NEXT_DATA__` JSON 中提取 `developer`（开发商）和 `operator`（运营商）字段
3. `icp_number` 为备案号，`icp_entity` 为备案主体

## Dependencies

- Python 3.8+
- playwright (`pip3 install playwright && python3 -m playwright install chromium`)

## Limitations

- 应用宝搜索按 App 名称模糊匹配，不支持按公司名精确搜索
- 已下架或未在应用宝上架的 App 无法查到
- 部分 App 详情页可能缺少运营商或备案号字段
- 公司可能通过子公司/关联公司发布 App，单纯应用宝数据可能不完整
