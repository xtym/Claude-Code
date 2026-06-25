# 使用示例

## 1. 生成图谱

### 首次生成（全量扫描）
```bash
python scripts/project_graph.py generate /path/to/project
```

### 强制全量重新扫描
```bash
python scripts/project_graph.py generate /path/to/project --force
```

### 指定图谱存储目录
```bash
python scripts/project_graph.py generate /path/to/project --graph-dir .marvis
```

## 2. 查询图谱

### 查看项目摘要
```bash
python scripts/project_graph.py query /path/to/project summary
```

### 查找文件
```bash
# 查看所有文件统计
python scripts/project_graph.py query /path/to/project files

# 搜索包含 "controller" 的文件
python scripts/project_graph.py query /path/to/project files controller
```

### 查找类
```bash
# 列出所有类
python scripts/project_graph.py query /path/to/project classes

# 搜索包含 "User" 的类
python scripts/project_graph.py query /path/to/project classes User
```

### 查询配置
```bash
# 显示所有配置项
python scripts/project_graph.py query /path/to/project configs

# 搜索包含 "DB" 的配置项
python scripts/project_graph.py query /path/to/project configs DB
```

### 查询依赖
```bash
# 显示所有依赖包
python scripts/project_graph.py query /path/to/project deps

# 搜索特定依赖
python scripts/project_graph.py query /path/to/project deps laravel
```

## 3. 在 AI 对话中使用

### 方式 1：发送 Markdown 摘要（推荐）
1. 运行 `generate` 命令生成图谱
2. 打开 `.marvis/project-graph.md` 文件
3. 将内容复制到 AI 对话中

### 方式 2：直接读取 JSON 图谱
1. 在对话中请求 AI 读取 `.marvis/project-graph.json`
2. AI 可以解析 JSON 获取结构化的项目信息

### 方式 3：在提示词中引用
```
我有一个项目路径在 /path/to/project，已经生成了项目图谱。
请在执行任务前先读取 project-graph.json 了解项目结构。
```

## 4. 增量更新

在项目有代码变更后，运行：
```bash
python scripts/project_graph.py generate /path/to/project
```
脚本会自动检测变更的文件，只更新有变化的部分。

## 5. 集成到 Git 工作流

可以在 `.git/hooks/post-merge` 和 `.git/hooks/post-checkout` 中添加：
```bash
python scripts/project_graph.py generate /path/to/project
```

## 6. Token 节省效果

| 场景 | 不使用图谱 | 使用图谱 | 节省 |
|------|------------|----------|------|
| 中等项目（200文件） | 30000-60000 tokens | 2000-4000 tokens | ~90% |
| 大型项目（1000+文件） | 100000+ tokens | 5000-8000 tokens | ~93% |
| 微服务项目 | 15000-25000 tokens | 1000-2000 tokens | ~90% |