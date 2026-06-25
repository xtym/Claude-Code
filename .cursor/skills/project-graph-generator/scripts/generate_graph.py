#!/usr/bin/env python3
"""
生成项目图谱的简化脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from project_graph import ProjectGraphGenerator

def main():
    if len(sys.argv) < 2:
        print("用法：python generate_graph.py <项目路径> [--force] [--graph-dir .marvis]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    force = '--force' in sys.argv
    graph_dir = '.marvis'
    
    # 提取 --graph-dir 参数
    for i, arg in enumerate(sys.argv):
        if arg == '--graph-dir' and i + 1 < len(sys.argv):
            graph_dir = sys.argv[i + 1]
    
    print(f"🚀 开始生成项目图谱：{project_path}")
    generator = ProjectGraphGenerator(project_path, graph_dir)
    generator.generate(force_full_scan=force)

if __name__ == '__main__':
    main()