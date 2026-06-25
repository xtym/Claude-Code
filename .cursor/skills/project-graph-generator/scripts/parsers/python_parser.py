"""
Python 解析器
提取 Python 代码中的类、函数、导入、装饰器等信息
"""

import re
from typing import Dict, List, Any, Optional


def parse_python_file(content: str, rel_path: str = "", use_tree_sitter: bool = False) -> Dict[str, Any]:
    """
    解析 Python 文件

    Args:
        content: 文件内容
        rel_path: 相对路径（用于推断模块名）
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    result = {
        "type": "python",
        "module": _infer_module_name(rel_path),
        "classes": [],
        "functions": [],
        "imports": [],
        "decorators": [],
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析

    lines = content.split('\n')
    in_class_body = False
    class_indent = 0
    current_class = None

    # 提取 docstring
    result["docstring"] = _extract_module_docstring(content)

    # 逐行分析
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        # 跳过空行和注释
        if not stripped or stripped.startswith('#'):
            i += 1
            continue

        # 检测装饰器
        if stripped.startswith('@'):
            decorator_info = _parse_decorator(stripped)
            if decorator_info:
                if current_class:
                    if "class_decorators" not in current_class:
                        current_class["class_decorators"] = []
                    current_class["class_decorators"].append(decorator_info)
                else:
                    result["decorators"].append(decorator_info)
            i += 1
            continue

        # 检测类定义
        if 'class ' in stripped and ':' in stripped:
            # 完成上一个类
            if current_class:
                result["classes"].append(current_class)

            class_info = _parse_class_line(stripped, lines, i)
            current_class = class_info
            in_class_body = True
            class_indent = indent
            i += 1
            continue

        # 类体结束
        if in_class_body and indent <= class_indent and stripped and not stripped.startswith('#'):
            if stripped.startswith('@'):
                decorator_info = _parse_decorator(stripped)
                if decorator_info:
                    if "class_decorators" not in current_class:
                        current_class["class_decorators"] = []
                    current_class["class_decorators"].append(decorator_info)
                i += 1
                continue
            else:
                result["classes"].append(current_class)
                current_class = None
                in_class_body = False

        # 检测函数定义
        func_match = re.match(r'(async\s+)?def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^:]+))?', stripped)
        if func_match:
            is_async = bool(func_match.group(1))
            func_name = func_match.group(2)
            params_str = func_match.group(3)
            return_type = func_match.group(4)

            # 跳过类内部方法（类体已处理）
            if in_class_body:
                params = _parse_params(params_str)
                method_info = {
                    "name": func_name,
                    "params": params,
                    "return_type": return_type.strip() if return_type else None,
                    "is_async": is_async,
                    "decorators": [],
                }
                # 检查后续行是否有装饰器
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith('@'):
                    decorator_info = _parse_decorator(lines[j].strip())
                    if decorator_info:
                        method_info["decorators"].append(decorator_info)
                    j += 1

                if "methods" not in current_class:
                    current_class["methods"] = []
                current_class["methods"].append(method_info)
                i = j
                continue

            # 模块级函数
            func_info = {
                "name": func_name,
                "params": _parse_params(params_str),
                "return_type": return_type.strip() if return_type else None,
                "is_async": is_async,
                "decorators": [],
            }

            # 检查后续行是否有装饰器
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith('@'):
                decorator_info = _parse_decorator(lines[j].strip())
                if decorator_info:
                    func_info["decorators"].append(decorator_info)
                j += 1

            result["functions"].append(func_info)
            i = j
            continue

        # 检测导入语句
        import_info = _parse_import_line(stripped)
        if import_info:
            result["imports"].append(import_info)

        i += 1

    # 处理最后一个类
    if current_class:
        result["classes"].append(current_class)

    return result


def _infer_module_name(rel_path: str) -> str:
    """从文件路径推断模块名"""
    if not rel_path:
        return ""

    # 移除文件扩展名
    module_path = rel_path.replace('.py', '')

    # 处理 __init__.py
    if module_path.endswith('__init__'):
        module_path = module_path[:-9]

    # 转换为点分隔格式
    module_name = module_path.replace('/', '.').replace('\\', '.')

    # 移除开头的点
    module_name = module_name.lstrip('.')

    return module_name


def _extract_module_docstring(content: str) -> Optional[str]:
    """提取模块级 docstring"""
    lines = content.split('\n')
    if not lines:
        return None

    # 检查是否有 docstring
    first_line = lines[0].strip()
    if first_line.startswith('"""') or first_line.startswith("'''"):
        quote = first_line[:3]
        if first_line.count(quote) >= 2:
            # 单行 docstring
            return first_line.strip(quote)
        # 多行 docstring
        docstring_lines = [first_line.replace(quote, '')]
        for line in lines[1:]:
            if quote in line:
                docstring_lines.append(line.split(quote)[0])
                break
            docstring_lines.append(line)
        return '\n'.join(docstring_lines).strip()

    return None


def _parse_decorator(stripped: str) -> Optional[Dict[str, Any]]:
    """解析装饰器"""
    # 移除 @
    dec = stripped[1:].strip()

    # 检查是否有参数
    if '(' in dec:
        match = re.match(r'(\w+)\s*\((.*)\)', dec)
        if match:
            return {
                "name": match.group(1),
                "args": match.group(2),
            }
    else:
        match = re.match(r'(\w+)', dec)
        if match:
            return {
                "name": match.group(1),
                "args": None,
            }

    return None


def _parse_class_line(stripped: str, lines: List[str], start_idx: int) -> Dict[str, Any]:
    """解析类定义行"""
    result = {
        "name": "",
        "bases": [],
        "decorators": [],
        "methods": [],
    }

    # 匹配 class X(Y, Z):
    match = re.match(r'class\s+(\w+)(?:\(([^)]*)\))?', stripped)
    if match:
        result["name"] = match.group(1)
        bases = match.group(2)
        if bases:
            result["bases"] = [b.strip() for b in bases.split(',')]

    return result


def _parse_params(params_str: str) -> List[str]:
    """解析函数参数列表"""
    if not params_str.strip():
        return []

    params = []
    for param in params_str.split(','):
        param = param.strip()
        if param:
            params.append(param)

    return params


def _parse_import_line(stripped: str) -> Optional[Dict[str, Any]]:
    """解析导入语句"""
    # import x
    if stripped.startswith('import '):
        module = stripped[7:].strip()
        return {
            "type": "import",
            "module": module,
            "names": [module.split('.')[0]],
        }

    # from x import y, z
    from_match = re.match(r'from\s+([\w.]+)\s+import\s+(.*)', stripped)
    if from_match:
        module = from_match.group(1)
        names_str = from_match.group(2)

        # 解析导入的名称
        names = []
        # 处理括号形式: from x import (y, z)
        if names_str.strip().startswith('('):
            names_str = names_str.strip()[1:-1]

        for name in names_str.split(','):
            name = name.strip()
            if name:
                # 处理 "x as y" 形式
                if ' as ' in name:
                    name = name.split(' as ')[0].strip()
                names.append(name)

        return {
            "type": "from_import",
            "module": module,
            "names": names,
        }

    return None


def _parse_with_tree_sitter(content: str, rel_path: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 Python 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        lang = get_language('python')
        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            "type": "python",
            "module": _infer_module_name(rel_path),
            "classes": [],
            "functions": [],
            "imports": [],
            "decorators": [],
            "tree_sitter_parsed": True
        }

        # 遍历 AST 提取信息
        _traverse_python_ast(tree.root_node, bytes(content, 'utf8'), result)

        return result

    except ImportError:
        return None
    except Exception:
        return None


def _traverse_python_ast(node: Any, content: bytes, result: Dict) -> None:
    """遍历 Python AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text

    node_type = node.type

    # import 语句
    if node_type == 'import_statement':
        text = extract_node_text(node, content)
        import_match = re.match(r'import\s+([\w.]+)', text)
        if import_match:
            result['imports'].append({
                "type": "import",
                "module": import_match.group(1),
                "names": [import_match.group(1).split('.')[0]],
            })

    # from ... import 语句
    elif node_type == 'import_from_statement':
        text = extract_node_text(node, content)
        from_match = re.match(r'from\s+([\w.]+)\s+import\s+(.+)', text)
        if from_match:
            module = from_match.group(1)
            names_str = from_match.group(2)
            names = [n.strip() for n in names_str.replace('(', '').replace(')', '').split(',')]
            result['imports'].append({
                "type": "from_import",
                "module": module,
                "names": names,
            })

    # 类定义
    elif node_type == 'class_definition':
        text = extract_node_text(node, content)
        class_match = re.search(r'class\s+(\w+)', text)
        if class_match:
            result['classes'].append({
                "name": class_match.group(1),
                "bases": [],
                "decorators": [],
                "methods": [],
            })

    # 函数定义
    elif node_type in ('function_definition', 'async_function_definition'):
        text = extract_node_text(node, content)
        func_match = re.search(r'(?:async\s+)?def\s+(\w+)\s*\(', text)
        if func_match:
            result['functions'].append({
                "name": func_match.group(1),
                "params": [],
                "return_type": None,
                "is_async": node_type == 'async_function_definition',
                "decorators": [],
            })

    # 装饰器
    elif node_type == 'decorator':
        text = extract_node_text(node, content).strip()
        if text.startswith('@'):
            result['decorators'].append({"name": text[1:], "args": None})

    # 递归遍历子节点
    for child in node.children:
        _traverse_python_ast(child, content, result)


# 导出函数
__all__ = ['parse_python_file']