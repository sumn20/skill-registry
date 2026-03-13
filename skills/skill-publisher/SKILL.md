---
name: skill-publisher
description: 将 Skill ZIP 包发布到 GitHub Skill Registry。当用户提供一个 skill 的 zip 文件和作者名称时，自动解压分析内容、生成 metadata.json 和介绍描述、上传到 GitHub 仓库并更新 registry。触发词包括：发布 skill、上传 skill、publish skill、skill 上架、把这个 skill 发布到商店、上传到 registry、发到 skill-registry。
---

# Skill Publisher

## Purpose

将一个 CodeBuddy Skill 的 ZIP 包发布到 GitHub Skill Registry (`https://github.com/sumn20/skill-registry`)。

完整流程：解压 ZIP → 分析内容 → 自动生成 metadata.json → 通过 GitHub API 上传所有文件 → 更新 registry.json → 完成发布。

## Prerequisites

- **GitHub Token**: 需要有 `sumn20/skill-registry` 仓库写权限的 Personal Access Token
  - 从 macOS Keychain 自动获取: `git credential-osxkeychain get` (protocol=https, host=github.com)
  - 或用户手动提供
- **Python 3.8+**
- **网络访问**: 需要能访问 GitHub API

## Workflow

### Step 0: 收集信息

从用户获取以下信息（必需项标 *）：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| * zip_path | ZIP 文件路径 | — |
| * author | 作者名称 | — |
| category | 分类: knowledge / tool / automation | 自动推断 |
| version | 版本号 | 1.0.0 |

### Step 1: 解压并分析 ZIP 内容

```bash
# 创建临时目录
mkdir -p /tmp/skill-publish-tmp
# 解压
unzip -o "<zip_path>" -d /tmp/skill-publish-tmp/
```

然后分析解压后的目录结构：

```bash
find /tmp/skill-publish-tmp/ -type f | head -50
```

**关键检查**：
1. 确认有 `SKILL.md` 文件（Skill 的核心定义文件）
2. 确定 skill 名称（取目录名，或从 SKILL.md 的 front matter `name` 字段获取）
3. 如果 ZIP 内只有一层根目录，以该目录名作为 skill name
4. 如果 ZIP 内直接就是文件（无包裹目录），以 zip 文件名（去掉 .zip）作为 skill name

**读取 SKILL.md**，提取关键信息用于后续生成 metadata。

### Step 2: 自动生成 metadata.json

基于 SKILL.md 内容和目录分析，生成 `metadata.json`。

**分类自动推断规则**：
- 有 `references/` 目录且无 `scripts/` → `knowledge`（知识库型）
- 有 `scripts/` 目录 → `tool`（工具型）
- SKILL.md 中提到"自动化"、"定时"、"automation" → `automation`
- 默认 → `tool`

**生成内容**：

```json
{
  "name": "<skill-name>",
  "displayName": "<从 SKILL.md 标题或内容生成的中文友好名称>",
  "description": "<从 SKILL.md 内容自动生成的一句话描述，100字以内，说明该 skill 做什么、解决什么问题>",
  "version": "<version>",
  "author": "<author>",
  "category": "<knowledge|tool|automation>",
  "tags": ["<从内容提取的5-8个关键词标签>"],
  "dependencies": ["<从 requirements.txt 或 SKILL.md Dependencies 段提取>"],
  "requirements": {
    "python": <true|false>,
    "env_vars": ["<从 SKILL.md 提取的环境变量>"]
  }
}
```

将 metadata.json 写入解压目录中（与 SKILL.md 同级）。

**重要**：displayName 和 description 必须自己根据 SKILL.md 内容理解后撰写，要通俗易懂，面向团队成员，不要直接复制 SKILL.md 原文。

### Step 3: 获取 GitHub Token

```bash
# 尝试从 macOS Keychain 获取
printf "protocol=https\nhost=github.com\n" | git credential-osxkeychain get 2>&1
```

从输出中提取 `password=` 后面的值作为 token。如果获取失败，请求用户手动提供。

### Step 4: 上传到 GitHub

运行发布脚本：

```bash
python3 <skill_dir>/scripts/publish_skill.py \
  --skill-dir "/tmp/skill-publish-tmp/<skill-name>" \
  --token "<github_token>" \
  --repo "sumn20/skill-registry" \
  --branch "main" \
  --author "<author>"
```

脚本会：
1. 读取本地 skill 目录的所有文件
2. 获取仓库当前 `main` 分支的最新 commit SHA 和 tree SHA
3. 为每个文件创建 blob（GitHub API）
4. 创建新的 tree（包含原有 tree + 新增的 skill 文件）
5. 创建 commit
6. 更新 `main` 分支 ref 指向新 commit
7. 下载并更新 `registry.json`，添加新 skill 的信息
8. 再次 commit 更新后的 `registry.json`

### Step 5: 验证发布结果

```bash
# 验证文件存在
curl -s "https://api.github.com/repos/sumn20/skill-registry/contents/skills/<skill-name>" | python3 -c "import sys,json; files=json.load(sys.stdin); print(f'文件数: {len(files)}'); [print(f'  {f[\"name\"]}') for f in files]"
```

### Step 6: 清理

```bash
rm -rf /tmp/skill-publish-tmp
```

### Step 7: 输出结果

格式：

```
## Skill 发布成功！

| 项目 | 信息 |
|------|------|
| Skill 名称 | <displayName> (<name>) |
| 作者 | <author> |
| 分类 | <category> |
| 版本 | <version> |
| 文件数 | <N> |
| 仓库地址 | https://github.com/sumn20/skill-registry/tree/main/skills/<name> |
| 商店页面 | https://sumn20.github.io/skill-registry/ |

标签: <tag1>, <tag2>, ...

描述: <description>
```

## Error Handling

| 错误 | 处理 |
|------|------|
| ZIP 解压失败 | 检查文件路径和格式，提示用户 |
| 找不到 SKILL.md | 提示用户：ZIP 中必须包含 SKILL.md |
| GitHub Token 无效 | 提示用户检查 token 权限 |
| 仓库中已存在同名 skill | 提示用户确认是否覆盖更新 |
| API 速率限制 | 等待后重试 |

## Dependencies

- Python 3.8+
- `requests` (`pip3 install requests`)

## Limitations

- 仅支持发布到 `sumn20/skill-registry` 仓库
- 需要有该仓库的写权限
- 单次上传的文件总大小不超过 GitHub API 限制（单文件 100MB，blob API 单次请求 ≤ 100MB）
