# CPaaS Skill Registry

> 团队共享的 CodeBuddy Skill 仓库 -- 在线 Skill 商店

## 在线访问

**https://sumn20.github.io/skill-registry**

Skill Store 网页支持搜索、分类筛选、详情查看和一键安装指引。

## Skill 一览

| Skill | 类型 | 说明 |
|-------|------|------|
| [rtc-knowledge](skills/rtc-knowledge/) | 知识库 | TRTC / Agora / ZEGO 三大 RTC 产品深度对比 |
| [im-knowledge](skills/im-knowledge/) | 知识库 | 腾讯云 IM / 环信 / 融云 / 网易云信全面对比 |
| [app-sdk-analysis](skills/app-sdk-analysis/) | 工具 | APK 逆向分析，识别集成的 SDK 供应商及版本 |
| [app-company-lookup](skills/app-company-lookup/) | 工具 | App 名称 - 开发公司双向查询 |
| [soul-ticket-dashboard](skills/soul-ticket-dashboard/) | 自动化 | Soul 工单深度分析 + TRTC 通话质量可视化 |
| [trtc-dashboard](skills/trtc-dashboard/) | 工具 | TRTC 监控面板直达链接生成 |

## 目录结构

```
.
├── index.html              # Skill 商店网页（GitHub Pages 入口）
├── registry.json           # 全局 Skill 索引（自动生成）
├── README.md
├── _template/              # 新 Skill 模板
│   ├── metadata.json
│   └── SKILL.md
├── scripts/
│   └── build_registry.py   # registry.json 构建脚本
└── skills/                 # 所有 Skill 目录
    ├── rtc-knowledge/
    ├── im-knowledge/
    ├── app-sdk-analysis/
    ├── app-company-lookup/
    ├── soul-ticket-dashboard/
    └── trtc-dashboard/
```

## 安装 Skill

### 方式一：克隆后复制

```bash
git clone https://github.com/sumn20/skill-registry.git
cp -r skill-registry/skills/rtc-knowledge /path/to/your/project/.codebuddy/skills/
```

### 方式二：Sparse Checkout（只拉需要的 Skill）

```bash
git clone --no-checkout --depth 1 https://github.com/sumn20/skill-registry.git
cd skill-registry
git sparse-checkout init --cone
git sparse-checkout set skills/rtc-knowledge
git checkout
```

## 贡献新 Skill

1. **Fork 仓库** 或创建新分支
2. **复制模板**：`cp -r _template skills/your-skill-name`
3. **编写 Skill**：
   - 修改 `metadata.json`（必填所有字段）
   - 编写 `SKILL.md`（Skill 的提示词和工作流）
   - 添加 `references/` 或 `scripts/`（可选）
4. **更新索引**：`python3 scripts/build_registry.py`
5. **提交 PR**

### metadata.json 规范

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | Yes | Skill 唯一标识（目录名） |
| `displayName` | string | Yes | 显示名称 |
| `description` | string | Yes | 一句话描述 |
| `version` | string | Yes | 语义化版本号 |
| `author` | string | Yes | 作者 |
| `category` | string | Yes | `knowledge` / `tool` / `automation` |
| `tags` | string[] | Yes | 搜索标签 |
| `dependencies` | string[] | No | 外部依赖 |
| `requirements.python` | boolean | No | 是否需要 Python |
| `requirements.env_vars` | string[] | No | 需要的环境变量 |

## 环境要求

- **基础**：Git, CodeBuddy
- **工具类 Skill**：Python 3.8+, pip
- **APK 分析**：额外需要 `apktool`（`brew install apktool`）
