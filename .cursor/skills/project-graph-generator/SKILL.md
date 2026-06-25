---
name: project-graph-generator
description: >
  为任意项目生成结构化的知识图谱，大幅减少 AI 对话中 "了解项目" 所需的 token 消耗（从 30000-60000 降至 2000-4000 tokens）。
  该技能在以下场景应被触发：
  (1) 用户说 "分析项目"、"了解项目结构"、"生成项目图谱"、"扫描项目"、"让我了解这个项目" 或类似请求时；
  (2) 用户询问 "这个项目有哪些文件/类/控制器/依赖" 等需要全面了解项目的问题时；
  (3) 用户说 "更新项目图谱"、"刷新项目信息" 或项目代码有变更后需要重新扫描时；
  (4) 其他技能（如 brainstorming、code-review、bug-fix）执行前用户要求 "先了解项目" 时；
  (5) 用户想查找特定类、配置、依赖关系，且已存在图谱时。
  支持 PHP、Python、JavaScript、TypeScript、Java、Go 等多语言项目，自动检测 Git 变更进行增量更新。
---

# Project Knowledge Graph Generator

为任意项目生成结构化的知识图谱，支持增量更新和灵活查询。

## 快速开始

### 生成项目图谱

```bash
python scripts/project_graph.py generate <项目路径>
# 强制全量扫描
python scripts/project_graph.py generate <项目路径> --force
```

首次运行执行全量扫描。后续运行自动进行增量更新（检测 Git 变更或文件哈希差异）。

**参数**：
- `project_path`（必需）：项目根目录的绝对路径
- `--force`（可选）：强制全量重新扫描，忽略增量检测
- `--graph-dir`（可选）：图谱存储目录，默认为项目根目录下的 `.marvis`

**产出**：在 `--graph-dir` 目录下生成两个文件：
- `project-graph.json`：结构化图谱数据（供程序/AI 解析）
- `project-graph.md`：人类可读的 Markdown 摘要（可直接复制到对话中使用）

### 查询项目图谱

```bash
python scripts/project_graph.py query <项目路径> <查询类型> [查询值]
```

**查询类型**：
| 命令 | 说明 | 示例 |
|------|------|------|
| `summary` | 查看项目摘要（文件数、类数、依赖数等） | `query /path summary` |
| `files` | 查找/统计文件 | `query /path files controller` |
| `classes` | 查找/统计类 | `query /path classes User` |
| `configs` | 查找/统计配置项 | `query /path configs DB` |
| `deps` | 查找/统计依赖包 | `query /path deps laravel` |

## 工作流程

### 场景 A：用户要求分析项目

1. 确认项目路径（如果用户没有提供，询问项目根目录绝对路径）
2. 运行 `python scripts/project_graph.py generate <项目路径>`
3. 如果生成成功，将 `project-graph.json` 的内容读入上下文以全面了解项目
4. 如果用户需要人类可读的摘要，直接打开 `<项目路径>/.marvis/project-graph.md` 将内容复制给用户

### 场景 B：用户需要查找特定信息

1. 确认项目路径和查询条件
2. 运行 `python scripts/project_graph.py query <项目路径> <类型> <查询值>`
3. 将查询结果呈现给用户
4. 如果图谱不存在，先生成图谱再查询

### 场景 C：用户修改了代码后需要更新

1. 运行 `python scripts/project_graph.py generate <项目路径>`
2. 脚本会自动检测变更（优先使用 Git，回退到文件哈希对比）
3. 如果检测到变更，执行增量更新；如果无变更，直接报告图谱已是最新

### 场景 D：在对话中使用图谱内容

1. 先运行 `generate` 确保图谱存在且是最新
2. 读取 `project-graph.md` 内容（约 2000-4000 tokens，远小于直接读取项目源码的 30000-60000 tokens）
3. 将 Markdown 内容提供给 AI 对话上下文

## 图谱内容

图谱包含以下结构化信息：

- **目录树**：完整的项目目录结构（忽略 vendor/node_modules/dist 等）
- **文件信息**：每个文件的路径、大小、类型、MD5 哈希（用于变更检测）
- **类信息**（PHP/Java 等语言）：命名空间、类名、方法、属性、继承关系
- **配置信息**：从 .env、config/*.php、app.yaml 等提取的环境变量和配置
- **依赖关系**：从 composer.json/package.json 等提取的第三方依赖

详细的数据结构说明见 [references/data-structure.md](references/data-structure.md)。

## 支持的解析器

| 文件类型 | 解析器 | 提取内容 |
|----------|--------|----------|
| `.php` | PHP 正则解析器 | 命名空间、类名、方法、属性、继承 |
| `.json`（composer.json） | JSON 解析器 | 包名、依赖关系 |
| `.env` | ENV 解析器 | 环境变量键值对 |
| `.yaml`/`.yml` | YAML 简化解器 | 顶层键值对 |

其他文件类型（.py/.js/.ts/.java/.go 等）记录元数据（路径、大小、修改时间、哈希），不提取语义内容。

支持的文件类型和详细信息见 [references/file-types.md](references/file-types.md)。

## 变更检测逻辑

1. **Git 仓库**：执行 `git diff --name-status HEAD` 检测变更
2. **非 Git 仓库**：计算每个文件的 MD5 哈希，与旧图谱中的哈希对比
3. **仅变更文件重新扫描**：只重新扫描变更/新增的文件，大幅减少扫描时间

## Token 节省效果

| 项目规模 | 不使用图谱 | 使用图谱 | 节省 |
|----------|-----------|----------|------|
| 小型项目 (<100 文件) | 10000-20000 tokens | 1000-2000 tokens | ~90% |
| 中等项目 (100-500 文件) | 30000-60000 tokens | 2000-4000 tokens | ~90% |
| 大型项目 (500+ 文件) | 60000-100000+ tokens | 4000-8000 tokens | ~90% |

## 技术细节

### 依赖要求
- Python 3.7+
- 标准库：os, json, hashlib, argparse, subprocess, pathlib, re, datetime
- 无需安装第三方依赖

### 文件结构
```
project-graph-generator/
├── SKILL.md                          # 此文件
├── scripts/
│   ├── project_graph.py              # 主脚本（生成+查询+所有逻辑）
│   ├── generate_graph.py             # 生成命令的简化入口
│   └── query_graph.py                # 查询命令的简化入口
├── references/
│   ├── data-structure.md             # 图谱 JSON 数据结构文档
│   ├── usage-examples.md             # 使用示例（含 AI 对话集成方法）
│   └── file-types.md                 # 支持的文件类型和解析规则
└── assets/
    └── template-graph.json           # 图谱 JSON 模板
```

## 注意事项

1. **所有图片处理在本地完成**，不上传任何照片到网络
2. 图谱存储在项目的 `.marvis` 目录中，应加入 `.gitignore`
3. 首次全量扫描可能需要数秒到数十秒（取决于项目文件数）
4. 增量更新通常只需几秒
5. 运行时会在控制台输出进度信息（含 emoji 标记），方便用户观察进展

## 常见问题

**Q: 图谱占用多少磁盘空间？**
A: JSON 文件通常在 100KB-2MB，Markdown 文件在 50KB-500KB。

**Q: 如何处理二进制文件？**
A: 二进制文件会被跳过，只扫描文本文件。计算哈希时如遇到读取错误会记录并跳过。

**Q: 图谱可以跨机器共享吗？**
A: JSON 文件中存储了绝对路径（如 `files` 键），跨机器共享时需要重新生成。