"""
Go 解析器
提取 Go 代码中的包、导入、结构体、接口、函数、类型别名等信息
"""

import re
from typing import Dict, List, Any, Optional


def parse_go_file(content: str, rel_path: str = "", use_tree_sitter: bool = False) -> Dict[str, Any]:
    """
    解析 Go 文件

    Args:
        content: 文件内容
        rel_path: 相对路径（用于推断包名）
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    result = {
        "type": "go",
        "package": "",
        "imports": [],
        "types": [],       # type X struct 和 type X interface
        "functions": [],   # func X()
        "variables": [],   # var X 和 const X
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析

    # 移除注释
    clean_content = _remove_comments(content)

    # 提取 package 声明
    package_match = re.search(r'^\s*package\s+(\w+)', clean_content, re.MULTILINE)
    if package_match:
        result["package"] = package_match.group(1)

    # 提取 imports
    result["imports"] = _extract_imports(clean_content)

    # 解析顶层定义
    result["types"], result["functions"], result["variables"] = _parse_top_level(clean_content)

    return result


def _remove_comments(content: str) -> str:
    """移除注释"""
    # 单行注释
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    # 多行注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    return content


def _extract_imports(content: str) -> List[Dict[str, Any]]:
    """提取导入语句"""
    imports = []

    # import "fmt"
    for match in re.finditer(r'import\s+"([^"]+)"', content):
        imports.append({
            "path": match.group(1),
            "names": []
        })

    # import "os" // alias
    for match in re.finditer(r'import\s+(\w+)\s+"([^"]+)"', content):
        imports.append({
            "path": match.group(2),
            "names": [match.group(1)]
        })

    # import ( ... )
    block_match = re.search(r'import\s*\(([^)]+)\)', content, re.DOTALL)
    if block_match:
        import_block = block_match.group(1)
        # 逐行解析
        for line in import_block.split('\n'):
            line = line.strip()
            if not line or line.startswith('//'):
                continue

            # import "fmt"
            m = re.match(r'"([^"]+)"', line)
            if m:
                imports.append({
                    "path": m.group(1),
                    "names": []
                })
                continue

            # import f "fmt"
            m = re.match(r'(\w+)\s+"([^"]+)"', line)
            if m:
                imports.append({
                    "path": m.group(2),
                    "names": [m.group(1)]
                })

    return imports


def _parse_top_level(content: str) -> tuple:
    """解析顶层定义"""
    types = []
    functions = []
    variables = []

    i = 0
    while i < len(content):
        # 跳过空白
        while i < len(content) and content[i] in ' \t\n':
            i += 1

        if i >= len(content):
            break

        remaining = content[i:]

        # type 定义
        if remaining.startswith('type '):
            parsed, end = _parse_type_def(remaining)
            if parsed:
                types.append(parsed)
                i += end
                continue

        # func 定义
        if remaining.startswith('func '):
            parsed, end = _parse_func_def(remaining)
            if parsed:
                functions.append(parsed)
                i += end
                continue

        # var 定义
        if remaining.startswith('var '):
            parsed, end = _parse_var_def(remaining)
            if parsed:
                variables.append(parsed)
                i += end
                continue

        # const 定义
        if remaining.startswith('const '):
            parsed, end = _parse_const_def(remaining)
            if parsed:
                variables.append(parsed)
                i += end
                continue

        # 不认识的，跳过到下一个标记
        i += 1

    return types, functions, variables


def _parse_type_def(content: str) -> tuple:
    """解析 type 定义"""
    # type X struct { ... }
    # type X interface { ... }
    # type X = ...

    match = re.match(r'type\s+(\w+)(?:\s*\[([^\]]+)\])?\s*(?:struct|interface|=)', content)
    if not match:
        return None, 0

    name = match.group(1)
    type_params = match.group(2)

    # 判断类型
    if 'struct' in content[match.end():match.end()+10]:
        return _parse_struct_def(content, name, type_params)
    elif 'interface' in content[match.end():match.end()+12]:
        return _parse_interface_def(content, name, type_params)
    else:
        # 类型别名 type X = Y
        alias_match = re.search(r'=\s*(.+?)(?:\n|$)', content[match.end():])
        if alias_match:
            return {
                "name": name,
                "kind": "alias",
                "type_params": type_params,
                "alias_type": alias_match.group(1).strip(),
            }, alias_match.end() + match.end()

    return None, 0


def _parse_struct_def(content: str, name: str, type_params: Optional[str]) -> tuple:
    """解析 struct 定义"""
    result = {
        "name": name,
        "kind": "struct",
        "type_params": type_params,
        "fields": [],
    }

    # 找到 body
    body_start = content.find('{')
    if body_start == -1:
        return result, 0

    body_content, body_end = _extract_go_body(content, body_start)
    result["body_end_pos"] = body_start + body_end + 1

    # 解析字段
    # 格式: Name Type `tag`
    field_pattern = r'(\w+)\s+(\w+(?:\[[^\]]+\])?(?:\s*\*\s*\w+)*(?:\[\])?)\s*(?:`([^`]*)`)?'

    for match in re.finditer(field_pattern, body_content):
        field_name = match.group(1)
        field_type = match.group(2)
        field_tag = match.group(3)

        # 跳过方法
        if '(' in field_type:
            continue

        result["fields"].append({
            "name": field_name,
            "type": field_type.strip(),
            "tag": field_tag,
        })

    return result, body_start + body_end + 1


def _parse_interface_def(content: str, name: str, type_params: Optional[str]) -> tuple:
    """解析 interface 定义"""
    result = {
        "name": name,
        "kind": "interface",
        "type_params": type_params,
        "methods": [],
    }

    # 找到 body
    body_start = content.find('{')
    if body_start == -1:
        return result, 0

    body_content, body_end = _extract_go_body(content, body_start)
    result["body_end_pos"] = body_start + body_end + 1

    # 解析方法签名
    # 格式: MethodName(params) returnType
    # 或: MethodName() (returnType, error)
    method_pattern = r'(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\))?'

    for match in re.finditer(method_pattern, body_content):
        method_name = match.group(1)
        params = _parse_go_params(match.group(2))
        returns = match.group(3)

        # 跳过嵌入接口
        if not params and not returns:
            continue

        result["methods"].append({
            "name": method_name,
            "params": params,
            "returns": returns.split(',') if returns else [],
        })

    return result, body_start + body_end + 1


def _parse_func_def(content: str) -> tuple:
    """解析 func 定义"""
    # func X()
    # func (recv) X()

    match = re.match(r'func\s+(?:\(([^)]+)\)\s+)?(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]+)\))?', content)
    if not match:
        return None, 0

    receiver = match.group(1)
    name = match.group(2)
    params_str = match.group(3)
    returns_str = match.group(4)

    result = {
        "name": name,
        "receiver": receiver,
        "params": _parse_go_params(params_str),
        "returns": [r.strip() for r in returns_str.split(',')] if returns_str else [],
    }

    # 找到函数体结尾
    body_start = content.find('{')
    if body_start != -1:
        _, body_end = _extract_go_body(content, body_start)
        return result, body_start + body_end + 1

    # 没有函数体（接口方法声明）
    return result, match.end()


def _parse_var_def(content: str) -> tuple:
    """解析 var 定义"""
    # var X Type = value
    # var X = value
    # var ( X Type = value; Y Type = value )

    if content.startswith('var '):
        content = content[4:]

    # 变量块 var ( ... )
    if content.startswith('('):
        body_content, body_end = _extract_go_body(content, 0)
        variables = []

        for line in body_content.split(';'):
            line = line.strip()
            if not line:
                continue

            parts = line.split('=')
            name = parts[0].strip().split()[0] if parts else ""
            var_type = parts[0].strip().split()[1] if len(parts[0].strip().split()) > 1 else ""

            variables.append({
                "name": name,
                "type": var_type,
                "value": parts[1].strip() if len(parts) > 1 else None,
            })

        return {"variables": variables}, body_end + 1

    # 单个 var
    parts = content.split('=')
    name_type = parts[0].strip().split()
    name = name_type[0] if name_type else ""
    var_type = name_type[1] if len(name_type) > 1 else ""

    return {
        "name": name,
        "type": var_type,
        "value": parts[1].strip() if len(parts) > 1 else None,
    }, 0


def _parse_const_def(content: str) -> tuple:
    """解析 const 定义（与 var 类似）"""
    return _parse_var_def(content)


def _extract_go_body(content: str, start: int) -> tuple:
    """提取 Go 代码块（平衡大括号）"""
    if content[start] != '{':
        return "", 0

    count = 0
    begin = start
    for i in range(start, len(content)):
        if content[i] == '{':
            count += 1
        elif content[i] == '}':
            count -= 1
            if count == 0:
                return content[begin+1:i], i
    return content[begin+1:], len(content)


def _parse_go_params(params_str: str) -> List[str]:
    """解析 Go 函数参数"""
    if not params_str.strip():
        return []

    params = []
    for param in params_str.split(','):
        param = param.strip()
        if not param:
            continue

        # 格式: name Type 或 just Type
        parts = param.split()
        if len(parts) >= 2:
            # 最后一个是类型
            params.append(f"{parts[-2]} {parts[-1]}")
        else:
            params.append(parts[0])

    return params


def _parse_with_tree_sitter(content: str, rel_path: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 Go 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        lang = get_language('go')
        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            "type": "go",
            "package": "",
            "imports": [],
            "types": [],
            "functions": [],
            "variables": [],
            "tree_sitter_parsed": True
        }

        # 遍历 AST 提取信息
        _traverse_go_ast(tree.root_node, bytes(content, 'utf8'), result)

        return result

    except ImportError:
        return None
    except Exception:
        return None


def _traverse_go_ast(node: Any, content: bytes, result: Dict) -> None:
    """遍历 Go AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text

    node_type = node.type

    # package 声明
    if node_type == 'package_identifier':
        text = extract_node_text(node, content).strip()
        if text and not result['package']:
            result['package'] = text

    # import 声明
    elif node_type in ('import_declaration', 'import_spec'):
        text = extract_node_text(node, content)
        import_match = re.search(r'"([^"]+)"', text)
        if import_match:
            result['imports'].append({
                "path": import_match.group(1),
                "names": []
            })

    # type 声明
    elif node_type == 'type_declaration':
        text = extract_node_text(node, content)
        type_match = re.search(r'type\s+(\w+)', text)
        if type_match:
            type_info = {
                "name": type_match.group(1),
                "kind": "unknown",
                "fields": [],
            }
            if 'struct' in text:
                type_info["kind"] = "struct"
            elif 'interface' in text:
                type_info["kind"] = "interface"
            result['types'].append(type_info)

    # 函数声明
    elif node_type == 'function_declaration':
        text = extract_node_text(node, content)
        func_match = re.search(r'func\s+(\w+)', text)
        if func_match:
            result['functions'].append({
                "name": func_match.group(1),
                "params": [],
                "returns": [],
            })

    # 递归遍历子节点
    for child in node.children:
        _traverse_go_ast(child, content, result)


# 导出函数
__all__ = ['parse_go_file']