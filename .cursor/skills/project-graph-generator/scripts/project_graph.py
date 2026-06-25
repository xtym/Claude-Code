#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Knowledge Graph Generator
生成和查询项目图谱，大幅减少 AI 对话中了解项目所需的 token。
"""
import os
import json
import hashlib
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import re

# 导入解析器
try:
    from parsers.php_parser import parse_php_file
    from parsers.vue_parser import parse_sfc_file
    from parsers.js_parser import parse_js_file
    from parsers.python_parser import parse_python_file
    from parsers.java_parser import parse_java_file
    from parsers.go_parser import parse_go_file
    from parsers.c_family_parser import parse_c_family_file
except ImportError as e:
    parse_php_file = None
    parse_sfc_file = None
    parse_js_file = None
    parse_python_file = None
    parse_java_file = None


# 默认忽略配置
DEFAULT_IGNORE_DIRS = {
    '.git', '.svn', '.hg', '.idea', '.vscode', '__pycache__',
    'vendor', 'node_modules', 'bower_components', 'dist', 'build',
    'runtime', 'storage', 'cache', 'logs', 'temp', 'tmp',
}

DEFAULT_IGNORE_FILES = {
    '.DS_Store', 'Thumbs.db', '.gitignore', '.gitattributes',
    '.env.local', '.env.test', '.env.production',
}


def _load_ignore_config() -> tuple:
    """加载忽略配置，支持外部配置文件"""
    # 配置文件路径
    config_path = Path(__file__).parent / 'ignore_config.json'
    
    # 如果配置文件存在，读取配置
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            ignore_dirs = set(config.get('ignore_dirs', []))
            ignore_files = set(config.get('ignore_files', []))
            
            # 合并默认配置和用户配置
            ignore_dirs = DEFAULT_IGNORE_DIRS | ignore_dirs
            ignore_files = DEFAULT_IGNORE_FILES | ignore_files
            
            return ignore_dirs, ignore_files
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] 配置文件读取失败: {e}，使用默认配置")
    
    # 返回默认配置
    return DEFAULT_IGNORE_DIRS, DEFAULT_IGNORE_FILES


# 加载忽略配置
IGNORE_DIRS, IGNORE_FILES = _load_ignore_config()


# 支持的文件类型及其解析器
SUPPORTED_EXTENSIONS = {
    '.php': 'php',
    '.vue': 'vue',
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.jsx': 'javascript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.c': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.h': 'cpp',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.xml': 'xml',
    '.md': 'markdown',
    '.txt': 'text',
    '.env': 'env',
    '.ini': 'ini',
    '.toml': 'toml',
    '.sql': 'sql',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.less': 'less',
}

class ProjectGraphGenerator:
    def __init__(self, project_path: str, graph_dir: str = '.marvis', use_tree_sitter: bool = False):
        self.project_path = Path(project_path).resolve()
        self.graph_dir = self.project_path / graph_dir
        self.graph_file = self.graph_dir / 'project-graph.json'
        self.markdown_file = self.graph_dir / 'project-graph.md'
        self.graph_data: Dict[str, Any] = {}
        self.use_tree_sitter = use_tree_sitter

        # 确保图谱目录存在
        self.graph_dir.mkdir(exist_ok=True)
    
    def load_existing_graph(self) -> bool:
        """加载现有的图谱数据"""
        if self.graph_file.exists():
            try:
                with open(self.graph_file, 'r', encoding='utf-8') as f:
                    self.graph_data = json.load(f)
                return True
            except (json.JSONDecodeError, IOError) as e:
                print(f"警告：无法加载现有图谱：{e}")
                return False
        return False
    
    def save_graph(self):
        """保存图谱数据到 JSON 和 Markdown"""
        # 更新元数据
        self.graph_data['meta'] = {
            'project_path': str(self.project_path),
            'generated_at': datetime.now().isoformat(),
            'version': '1.0',
            'total_files': len(self.graph_data.get('files', {})),
            'total_classes': len(self.graph_data.get('classes', {})),
        }
        
        # 保存 JSON
        with open(self.graph_file, 'w', encoding='utf-8') as f:
            json.dump(self.graph_data, f, indent=2, ensure_ascii=False)
        
        # 生成并保存 Markdown 摘要
        self.generate_markdown_summary()
        
        print(f"[OK] 图谱已保存到：{self.graph_file}")
        print(f"[INFO] 摘要已保存到：{self.markdown_file}")
    
    def generate_markdown_summary(self):
        """生成人类可读的 Markdown 摘要"""
        summary = []
        summary.append(f"# 项目图谱：{self.project_path.name}")
        summary.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary.append(f"项目路径：`{self.project_path}`")
        summary.append("")
        
        # 项目概览
        meta = self.graph_data.get('meta', {})
        summary.append("## [STAT] 项目概览")
        summary.append(f"- 文件总数：{meta.get('total_files', 0)}")
        summary.append(f"- 类总数：{meta.get('total_classes', 0)}")
        summary.append(f"- 目录数：{len(self.graph_data.get('directories', {}))}")
        summary.append("")
        
        # 目录结构（改进版：显示文件大小和类型）
        summary.append("## [TREE] 目录结构")
        directories = self.graph_data.get('directories', {})
        files_info = self.graph_data.get('files', {})
        
        # 按目录分组文件，显示大小和类型
        for dir_path, files in sorted(directories.items()):
            if files:
                summary.append(f"### {dir_path or '根目录'}")
                for file in files[:15]:  # 目录中显示前15个文件
                    # 查找文件的详细信息
                    file_key = None
                    for fk, fi in files_info.items():
                        if fi.get('relative_path', '').replace('\\', '/').endswith(file.replace('\\', '/')):
                            file_key = fk
                            break
                    size_kb = ""
                    file_type = ""
                    if file_key and file_key in files_info:
                        size = files_info[file_key].get('size', 0)
                        size_kb = f" ({size/1024:.1f}KB)" if size > 0 else ""
                        file_type = files_info[file_key].get('type', '')
                        if file_type and file_type != 'unknown':
                            file_type = f", {file_type}"
                    summary.append(f"- `{file}`{size_kb}{file_type}")
                if len(files) > 15:
                    summary.append(f"- ... 还有 {len(files) - 15} 个文件")
                summary.append("")
        
        # 关键类（改进版：显示属性表格、方法表格）
        summary.append("## [CLASS] 关键类")
        classes = self.graph_data.get('classes', {})
        for class_name, class_info in sorted(classes.items())[:30]:  # 显示前30个类
            summary.append(f"### `{class_name}`")
            summary.append(f"- **文件**: `{class_info.get('file', '')}`")
            if class_info.get('namespace'):
                summary.append(f"- **命名空间**: `{class_info['namespace']}`")
            if class_info.get('extends'):
                summary.append(f"- **继承**: `{class_info['extends']}`")
            if class_info.get('implements'):
                summary.append(f"- **实现**: `{', '.join(class_info['implements'])}`")
            if class_info.get('traits'):
                summary.append(f"- **Traits**: `{', '.join(class_info['traits'])}`")
            if class_info.get('dependencies'):
                summary.append(f"- **依赖**: `{', '.join(class_info['dependencies'])}`")
            
            # 属性表格
            properties = class_info.get('properties', [])
            if properties:
                summary.append("")
                summary.append("**属性**:")
                summary.append("| 可见性 | 类型 | 名称 | 默认值 | 注解 |")
                summary.append("|--------|------|------|--------|------|")
                for prop in properties:
                    attr_str = ', '.join([f"`#{a}`" for a in prop.get('attributes', [])]) if prop.get('attributes') else ''
                    static_str = 'static ' if prop.get('is_static') else ''
                    summary.append(f"| {prop.get('visibility', '')} {static_str}| {prop.get('type') or '-'} | ${prop.get('name', '')} | {prop.get('default') or '-'} | {attr_str} |")
            
            # 方法表格
            methods = class_info.get('methods', [])
            if methods:
                summary.append("")
                summary.append("**方法**:")
                summary.append("| 可见性 | 返回类型 | 名称 | 参数 | 注解 |")
                summary.append("|--------|----------|------|------|------|")
                for method in methods:
                    attr_str = ', '.join([f"`#{a}`" for a in method.get('attributes', [])]) if method.get('attributes') else ''
                    static_str = 'static ' if method.get('is_static') else ''
                    # 格式化参数
                    params = method.get('params', [])
                    params_str = ', '.join([f"{p.get('type', '')} ${p.get('name', '')}" if p.get('type') else f"${p.get('name', '')}" for p in params]) if params else ''
                    summary.append(f"| {method.get('visibility', '')} {static_str}| {method.get('return_type') or 'mixed'} | {method.get('name', '')} | {params_str} | {attr_str} |")
            summary.append("")
        
        # 配置信息
        configs = self.graph_data.get('configs', {})
        if configs:
            summary.append("## ⚙️ 配置信息")
            for key, value in sorted(configs.items())[:30]:  # 只显示前30个配置
                if value is not None and value != "":
                    summary.append(f"- `{key}`: `{value}`")
            summary.append("")
        
        # 依赖关系
        deps = self.graph_data.get('dependencies', {})
        if deps:
            summary.append("## [DEPS] 依赖关系")
            for dep, version in sorted(deps.items()):
                summary.append(f"- `{dep}`: `{version}`")
        
        with open(self.markdown_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(summary))
    
    def detect_changes(self) -> Set[str]:
        """检测变更的文件（使用 Git 或文件哈希）"""
        changed_files = set()
        
        # 尝试使用 Git
        if (self.project_path / '.git').exists():
            try:
                result = subprocess.run(
                    ['git', 'diff', '--name-status', 'HEAD'],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    timeout=30  # 30秒超时
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            # 格式: M  path/to/file.php
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                status, file_path = parts[0], parts[1]
                                if status in ['M', 'A', 'D', 'R']:
                                    changed_files.add(file_path)
                    print(f"[GIT] 检测到 {len(changed_files)} 个变更文件")
                    return changed_files
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        
        # 回退到文件哈希对比
        print("[SCAN] 使用文件哈希对比检测变更")
        existing_files = self.graph_data.get('files', {})
        
        for root, dirs, files in os.walk(self.project_path):
            # 过滤忽略的目录
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for file in files:
                if file in IGNORE_FILES:
                    continue
                
                file_path = Path(root) / file
                rel_path = str(file_path.relative_to(self.project_path))
                
                # 计算文件哈希
                try:
                    with open(file_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                except (IOError, OSError):
                    continue
                
                # 检查是否变更
                old_file_info = existing_files.get(str(file_path))
                if not old_file_info or old_file_info.get('hash') != file_hash:
                    changed_files.add(str(file_path))
        
        print(f"[SCAN] 哈希对比检测到 {len(changed_files)} 个变更文件")
        return changed_files
    
    def scan_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """扫描单个文件，提取关键信息"""
        if not file_path.exists():
            return None
        
        rel_path = str(file_path.relative_to(self.project_path))
        ext = file_path.suffix.lower()
        
        # 基础文件信息
        stat = file_path.stat()
        file_info = {
            'path': str(file_path),
            'relative_path': rel_path,
            'size': stat.st_size,
            'mtime': stat.st_mtime,
            'type': 'unknown',
        }
        
        # 计算哈希（对于超大文件只读取前1MB）
        try:
            with open(file_path, 'rb') as f:
                data = f.read(1024 * 1024)  # 只读取前1MB
                file_info['hash'] = hashlib.md5(data).hexdigest()
        except (IOError, OSError):
            file_info['hash'] = None
        
        # 跳过超大文件（> 5MB）的详细内容解析
        if stat.st_size > 5 * 1024 * 1024:
            file_info['type'] = 'large_file'
            return file_info
        
        # 根据扩展名解析内容（限制读取大小为1MB）
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024 * 1024)  # 只读取前1MB
        except (IOError, OSError, UnicodeDecodeError):
            return file_info
        
        # 解析不同类型文件
        if ext == '.php' and parse_php_file:
            php_file_info, class_info = parse_php_file(content, rel_path, self.use_tree_sitter)
            file_info.update(php_file_info)
            # 注册类信息
            if class_info:
                if 'classes' not in self.graph_data:
                    self.graph_data['classes'] = {}
                self.graph_data['classes'].update(class_info)
        elif ext == '.vue' and parse_sfc_file:
            file_info.update(parse_sfc_file(content, rel_path, self.use_tree_sitter))
        elif ext in ['.js', '.ts', '.jsx', '.tsx'] and parse_js_file:
            file_info.update(parse_js_file(content, rel_path, self.use_tree_sitter))
        elif ext == '.py' and parse_python_file:
            file_info.update(parse_python_file(content, rel_path, self.use_tree_sitter))
        elif ext == '.java' and parse_java_file:
            file_info.update(parse_java_file(content, rel_path, self.use_tree_sitter))
        elif ext == '.go' and parse_go_file:
            file_info.update(parse_go_file(content, rel_path, self.use_tree_sitter))
        elif ext in ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.cs'] and parse_c_family_file:
            file_info.update(parse_c_family_file(content, rel_path, self.use_tree_sitter))
        elif ext == '.json':
            file_info.update(self.parse_json_file(content))
        elif ext == '.env':
            file_info.update(self.parse_env_file(content))
        elif ext in ['.yaml', '.yml']:
            file_info.update(self.parse_yaml_file(content))

        return file_info

    def parse_json_file(self, content: str) -> Dict[str, Any]:
        """解析 JSON 文件"""
        result = {'type': 'json', 'summary': {}}
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                # 对于 composer.json
                if 'name' in data:
                    result['summary']['name'] = data.get('name')
                if 'dependencies' in data or 'require' in data:
                    deps = data.get('dependencies', data.get('require', {}))
                    if deps:
                        result['summary']['dependencies'] = list(deps.keys())
                        # 添加到依赖关系
                        if 'dependencies' not in self.graph_data:
                            self.graph_data['dependencies'] = {}
                        self.graph_data['dependencies'].update(deps)
        except json.JSONDecodeError:
            pass
        return result
    
    def parse_env_file(self, content: str) -> Dict[str, Any]:
        """解析 .env 文件"""
        result = {'type': 'env', 'summary': {}}
        configs = {}
        
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                configs[key] = value
        
        result['summary']['configs'] = configs
        
        # 添加到配置列表
        if 'configs' not in self.graph_data:
            self.graph_data['configs'] = {}
        self.graph_data['configs'].update(configs)
        
        return result
    
    def parse_yaml_file(self, content: str) -> Dict[str, Any]:
        """解析 YAML 文件（简化版）"""
        result = {'type': 'yaml', 'summary': {}}
        # 简单提取键值对
        configs = {}
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                configs[key] = value
        
        result['summary']['configs'] = configs
        return result
    
    def build_directory_tree(self):
        """构建目录树结构"""
        directories = {}
        
        for root, dirs, files in os.walk(self.project_path):
            # 计算相对于项目根的路径
            rel_root = Path(root).relative_to(self.project_path) if str(root) != str(self.project_path) else Path('.')
            
            # 过滤忽略的目录（支持 basename 和路径前缀匹配）
            def should_ignore_dir(d):
                if d in IGNORE_DIRS:
                    return True
                full_path = rel_root / d if str(rel_root) != '.' else d
                for ignore in IGNORE_DIRS:
                    if '/' in ignore or '\\' in ignore:
                        if str(full_path).startswith(ignore) or str(full_path).replace('\\', '/').startswith(ignore):
                            return True
                return False
            
            dirs[:] = [d for d in dirs if not should_ignore_dir(d)]
            
            rel_root = str(Path(root).relative_to(self.project_path))
            if rel_root == '.':
                rel_root = ''
            
            # 过滤忽略的文件
            filtered_files = [f for f in files if f not in IGNORE_FILES]
            
            if filtered_files:
                directories[rel_root] = filtered_files
        
        self.graph_data['directories'] = directories
    
    def generate(self, force_full_scan: bool = False):
        """生成或更新项目图谱"""
        print(f"[START] 开始生成项目图谱：{self.project_path}")
        
        # 加载现有图谱
        has_existing = self.load_existing_graph()
        
        if force_full_scan or not has_existing:
            print("[SCAN] 执行全量扫描...")
            self.graph_data = {
                'files': {},
                'directories': {},
                'classes': {},
                'configs': {},
                'dependencies': {},
            }
            self.build_directory_tree()
            
            # 扫描所有文件
            total_files = 0
            for root, dirs, files in os.walk(self.project_path):
                # 计算相对于项目根的路径
                rel_root = Path(root).relative_to(self.project_path) if root != str(self.project_path) else Path('.')
                
                # 过滤忽略的目录（支持 basename 和路径前缀匹配）
                def should_ignore_dir(d):
                    # 1. 检查目录名是否在 IGNORE_DIRS 中（basename 匹配）
                    if d in IGNORE_DIRS:
                        return True
                    # 2. 检查完整路径是否匹配路径前缀（如 public/apidoc）
                    full_path = rel_root / d if str(rel_root) != '.' else d
                    for ignore in IGNORE_DIRS:
                        if '/' in ignore or '\\' in ignore:
                            if str(full_path).startswith(ignore) or str(full_path).replace('\\', '/').startswith(ignore):
                                return True
                    return False
                
                dirs[:] = [d for d in dirs if not should_ignore_dir(d)]
                
                for file in files:
                    if file in IGNORE_FILES:
                        continue
                    
                    file_path = Path(root) / file
                    file_info = self.scan_file(file_path)
                    if file_info:
                        self.graph_data['files'][str(file_path)] = file_info
                        total_files += 1
                        if total_files % 100 == 0:
                            print(f"[PROGRESS] 已扫描 {total_files} 个文件...")
            
            print(f"[OK] 全量扫描完成，共扫描 {total_files} 个文件")
        else:
            print("[SCAN] 执行增量更新...")
            changed_files = self.detect_changes()
            
            if not changed_files:
                print(f"[OK] 没有检测到变更，图谱保持最新")
                return
            
            # 更新变更的文件
            for file_path_str in changed_files:
                file_path = Path(file_path_str)
                if not file_path.is_absolute():
                    file_path = self.project_path / file_path
                
                if file_path.exists():
                    file_info = self.scan_file(file_path)
                    if file_info:
                        self.graph_data['files'][str(file_path)] = file_info
                        print(f"[UPDATE] 更新：{file_path.relative_to(self.project_path)}")
                else:
                    # 文件被删除
                    if str(file_path) in self.graph_data.get('files', {}):
                        del self.graph_data['files'][str(file_path)]
                        print(f"[DELETE] 删除：{file_path.relative_to(self.project_path)}")
            
            # 重新构建目录树
            self.build_directory_tree()
            print(f"[OK] 增量更新完成，更新了 {len(changed_files)} 个文件")
        
        # 保存图谱
        self.save_graph()
    
    def query(self, query_type: str, query_value: str = None):
        """查询图谱信息"""
        if not self.load_existing_graph():
            print("[ERROR] 没有找到项目图谱，请先运行 generate 命令")
            return
        
        if query_type == 'files':
            self.query_files(query_value)
        elif query_type == 'classes':
            self.query_classes(query_value)
        elif query_type == 'configs':
            self.query_configs(query_value)
        elif query_type == 'deps':
            self.query_dependencies(query_value)
        elif query_type == 'summary':
            self.show_summary()
        else:
            print(f"[ERROR] 未知查询类型：{query_type}")
            print("可用查询类型：files, classes, configs, deps, summary")
    
    def query_files(self, pattern: str = None):
        """查询文件"""
        files = self.graph_data.get('files', {})
        
        if not pattern:
            # 显示文件统计
            print(f"[TREE] 文件总数：{len(files)}")
            
            # 按类型统计
            type_count = {}
            for file_info in files.values():
                file_type = file_info.get('type', 'unknown')
                type_count[file_type] = type_count.get(file_type, 0) + 1
            
            print("[STAT] 文件类型统计：")
            for file_type, count in sorted(type_count.items()):
                print(f"  {file_type}: {count}")
        else:
            # 搜索文件
            print(f"[SEARCH] 搜索文件（模式：{pattern}）：")
            matches = []
            for file_path, file_info in files.items():
                rel_path = file_info.get('relative_path', '')
                if pattern.lower() in rel_path.lower():
                    matches.append((rel_path, file_info))
            
            if matches:
                for rel_path, file_info in matches[:20]:  # 只显示前20个结果
                    file_type = file_info.get('type', 'unknown')
                    print(f"  [FILE] {rel_path} ({file_type})")
                if len(matches) > 20:
                    print(f"  ... 还有 {len(matches) - 20} 个结果")
            else:
                print("  没有找到匹配的文件")
    
    def query_classes(self, keyword: str = None):
        """查询类"""
        classes = self.graph_data.get('classes', {})
        
        if not keyword:
            # 显示所有类
            print(f"[CLASS] 类总数：{len(classes)}")
            for class_name, class_info in list(classes.items())[:20]:  # 只显示前20个
                file_path = class_info.get('file', 'N/A')
                print(f"  [CLASS] {class_name} (文件：{file_path})")
            if len(classes) > 20:
                print(f"  ... 还有 {len(classes) - 20} 个类")
        else:
            # 搜索类
            print(f"[SEARCH] 搜索类（关键词：{keyword}）：")
            matches = []
            for class_name, class_info in classes.items():
                if keyword.lower() in class_name.lower():
                    matches.append((class_name, class_info))
            
            if matches:
                for class_name, class_info in matches[:10]:  # 只显示前10个结果
                    file_path = class_info.get('file', 'N/A')
                    extends = class_info.get('extends', 'N/A')
                    method_count = len(class_info.get('methods', []))
                    print(f"  [CLASS] {class_name}")
                    print(f"     文件：{file_path}")
                    print(f"     继承：{extends}")
                    print(f"     方法数：{method_count}")
                    print()
                if len(matches) > 10:
                    print(f"  ... 还有 {len(matches) - 10} 个结果")
            else:
                print("  没有找到匹配的类")
    
    def query_configs(self, key: str = None):
        """查询配置"""
        configs = self.graph_data.get('configs', {})
        
        if not key:
            # 显示所有配置
            print(f"⚙️ 配置项总数：{len(configs)}")
            for config_key, value in list(configs.items())[:20]:  # 只显示前20个
                if value is not None and value != "":
                    print(f"  {config_key}: {value}")
            if len(configs) > 20:
                print(f"  ... 还有 {len(configs) - 20} 个配置项")
        else:
            # 搜索配置
            print(f"[SEARCH] 搜索配置（键：{key}）：")
            matches = []
            for config_key, value in configs.items():
                if key.lower() in config_key.lower():
                    matches.append((config_key, value))
            
            if matches:
                for config_key, value in matches[:10]:  # 只显示前10个结果
                    print(f"  {config_key}: {value}")
                if len(matches) > 10:
                    print(f"  ... 还有 {len(matches) - 10} 个结果")
            else:
                print("  没有找到匹配的配置项")
    
    def query_dependencies(self, package: str = None):
        """查询依赖关系"""
        deps = self.graph_data.get('dependencies', {})
        
        if not package:
            # 显示所有依赖
            print(f"[DEPS] 依赖总数：{len(deps)}")
            for dep, version in list(deps.items())[:20]:  # 只显示前20个
                print(f"  {dep}: {version}")
            if len(deps) > 20:
                print(f"  ... 还有 {len(deps) - 20} 个依赖")
        else:
            # 搜索依赖
            print(f"[SEARCH] 搜索依赖（包名：{package}）：")
            matches = []
            for dep, version in deps.items():
                if package.lower() in dep.lower():
                    matches.append((dep, version))
            
            if matches:
                for dep, version in matches:
                    print(f"  {dep}: {version}")
            else:
                print("  没有找到匹配的依赖")
    
    def show_summary(self):
        """显示项目摘要"""
        meta = self.graph_data.get('meta', {})
        
        print("[STAT] 项目图谱摘要")
        print("=" * 50)
        print(f"项目路径：{meta.get('project_path', 'N/A')}")
        print(f"生成时间：{meta.get('generated_at', 'N/A')}")
        print(f"文件总数：{meta.get('total_files', 0)}")
        print(f"类总数：{meta.get('total_classes', 0)}")
        print(f"配置项数：{len(self.graph_data.get('configs', {}))}")
        print(f"依赖数：{len(self.graph_data.get('dependencies', {}))}")
        print("=" * 50)
        
        # 显示图谱文件位置
        print(f"\n[FILE] 图谱文件：")
        print(f"  JSON: {self.graph_file}")
        print(f"  Markdown: {self.markdown_file}")
        
        # 建议
        print(f"\n[HINT] 建议：")
        print("  1. 将 project-graph.md 内容复制到对话中，让 AI 快速了解项目")
        print("  2. 使用 query 命令查找特定文件、类或配置")
        print("  3. 项目变更后运行 generate 更新图谱")

def main():
    parser = argparse.ArgumentParser(description='项目图谱生成器')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='生成或更新项目图谱')
    generate_parser.add_argument('project_path', help='项目路径')
    generate_parser.add_argument('--force', action='store_true', help='强制全量扫描')
    generate_parser.add_argument('--graph-dir', default='.marvis', help='图谱存储目录（默认：.marvis）')
    generate_parser.add_argument('--use-tree-sitter', action='store_true', help='使用 tree-sitter AST 解析（更准确但需要 tree-sitter-languages）')
    
    # query 命令
    query_parser = subparsers.add_parser('query', help='查询图谱信息')
    query_parser.add_argument('project_path', help='项目路径')
    query_parser.add_argument('query_type', choices=['files', 'classes', 'configs', 'deps', 'summary'],
                             help='查询类型：files=文件, classes=类, configs=配置, deps=依赖, summary=摘要')
    query_parser.add_argument('query_value', nargs='?', help='查询值（如文件名、类名、配置键等）')
    query_parser.add_argument('--graph-dir', default='.marvis', help='图谱存储目录（默认：.marvis）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'generate':
            generator = ProjectGraphGenerator(args.project_path, args.graph_dir, args.use_tree_sitter)
            generator.generate(force_full_scan=args.force)
        elif args.command == 'query':
            generator = ProjectGraphGenerator(args.project_path, args.graph_dir)
            generator.query(args.query_type, args.query_value)
    except Exception as e:
        print(f"[ERROR] 错误：{e}")
        sys.exit(1)

if __name__ == '__main__':
    main()