#!/usr/bin/env python3
"""
查询项目图谱的简化脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project_graph import ProjectGraphGenerator

def main():
    if len(sys.argv) < 3:
        print("用法：python query_graph.py <项目路径> <查询类型> [查询值]")
        print("查询类型：files, classes, configs, deps, summary")
        print("示例：")
        print("  python query_graph.py /path/to/project summary")
        print("  python query_graph.py /path/to/project files controller")
        print("  python query_graph.py /path/to/project classes User")
        sys.exit(1)
    
    project_path = sys.argv[1]
    query_type = sys.argv[2]
    query_value = sys.argv[3] if len(sys.argv) > 3 else None
    graph_dir = '.marvis'
    
    # 提取 --graph-dir 参数
    for i, arg in enumerate(sys.argv):
        if arg == '--graph-dir' and i + 1 < len(sys.argv):
            graph_dir = sys.argv[i + 1]
    
    print(f"🔍 查询项目图谱：{project_path}")
    generator = ProjectGraphGenerator(project_path, graph_dir)
    generator.query(query_type, query_value)

if __name__ == '__main__':
    main()