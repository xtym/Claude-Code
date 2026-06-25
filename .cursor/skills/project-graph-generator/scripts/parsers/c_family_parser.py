"""
C/C++/C# 解析器
提取 C、C++、C# 代码中的命名空间、类、结构体、枚举、函数、变量等信息
"""

import re
from typing import Dict, List, Any, Optional


def parse_c_family_file(content: str, rel_path: str = "", use_tree_sitter: bool = False) -> Dict[str, Any]:
    """
    解析 C/C++/C# 文件

    Args:
        content: 文件内容
        rel_path: 相对路径（用于判断语言类型）
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    # 根据扩展名判断语言类型
    lang_type = _detect_c_family_language(rel_path)

    result = {
        "type": lang_type,
        "language": lang_type,
        "includes": [],     # C/C++: #include
        "usings": [],       # C#: using
        "namespaces": [],
        "classes": [],
        "structs": [],
        "enums": [],
        "interfaces": [],   # C# 特有
        "functions": [],
        "variables": [],
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path, lang_type)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析

    # 移除注释
    clean_content = _remove_comments(content)

    # 提取 includes/usings
    if lang_type in ("c", "cpp"):
        result["includes"] = _extract_includes(clean_content)
    else:  # csharp
        result["usings"] = _extract_usings(clean_content)
        result["interfaces"] = _parse_interfaces(clean_content)

    # 解析顶层定义
    result["namespaces"], result["classes"], result["structs"], result["enums"], result["functions"], result["variables"] = _parse_top_level_defs(clean_content, lang_type)

    return result


def _detect_c_family_language(rel_path: str) -> str:
    """根据文件扩展名检测 C 家族语言类型"""
    ext = rel_path.lower().split('.')[-1] if '.' in rel_path else ''

    if ext == 'cs':
        return 'csharp'
    elif ext == 'cpp' or ext == 'cc' or ext == 'cxx':
        return 'cpp'
    elif ext == 'c':
        return 'c'
    elif ext == 'h' or ext == 'hpp' or ext == 'hh':
        return 'cpp'  # 头文件按 C++ 处理
    elif ext == 'cs':
        return 'csharp'
    else:
        return 'c'  # 默认


def _remove_comments(content: str) -> str:
    """移除注释"""
    # 单行注释
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    # 多行注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    return content


def _extract_includes(content: str) -> List[str]:
    """提取 #include 语句"""
    includes = []

    # #include <xxx>
    for match in re.finditer(r'#\s*include\s*<([^>]+)>', content):
        includes.append(f"<{match.group(1)}>")

    # #include "xxx"
    for match in re.finditer(r'#\s*include\s*"([^"]+)"', content):
        includes.append(f"\"{match.group(1)}\"")

    return includes


def _extract_usings(content: str) -> List[str]:
    """提取 C# using 语句"""
    usings = []

    for match in re.finditer(r'^\s*using\s+([\w.]+)(?:\s*=\s*[^;]+)?;', content, re.MULTILINE):
        usings.append(match.group(1))

    return usings


def _parse_interfaces(content: str) -> List[Dict]:
    """解析 C# 接口定义"""
    interfaces = []

    interface_pattern = r'(?:\[.*?\]\s*)*interface\s+(\w+)(?:\s*:\s*([^{]+))?'

    for match in re.finditer(interface_pattern, content):
        name = match.group(1)
        extends = match.group(2)

        interface_info = {
            "name": name,
            "extends": [e.strip() for e in extends.split(',')] if extends else [],
            "methods": [],
        }

        # 提取接口体
        body_start = content.find('{', match.end())
        if body_start != -1:
            body_content, _ = _extract_cpp_body(content, body_start)
            interface_info["methods"] = _parse_cpp_methods(body_content)

        interfaces.append(interface_info)

    return interfaces


def _parse_top_level_defs(content: str, lang_type: str) -> tuple:
    """解析顶层定义"""
    namespaces = []
    classes = []
    structs = []
    enums = []
    functions = []
    variables = []

    i = 0
    while i < len(content):
        while i < len(content) and content[i] in ' \t\n':
            i += 1

        if i >= len(content):
            break

        remaining = content[i:]

        # namespace
        if remaining.startswith('namespace '):
            parsed, end = _parse_namespace(remaining)
            if parsed:
                namespaces.append(parsed)
                i += end
                continue

        # class
        if remaining.startswith('class '):
            parsed, end = _parse_class(remaining, lang_type)
            if parsed:
                classes.append(parsed)
                i += end
                continue

        # struct
        if remaining.startswith('struct '):
            parsed, end = _parse_struct(remaining, lang_type)
            if parsed:
                structs.append(parsed)
                i += end
                continue

        # enum
        if remaining.startswith('enum '):
            parsed, end = _parse_enum(remaining)
            if parsed:
                enums.append(parsed)
                i += end
                continue

        # template function (C++)
        if remaining.startswith('template '):
            func_info, end = _parse_template_function(remaining)
            if func_info:
                functions.append(func_info)
                i += end
                continue

        # 函数定义（返回类型 函数名(...)）
        func_info, end = _try_parse_function(remaining, lang_type)
        if func_info:
            functions.append(func_info)
            i += end
            continue

        # 跳过不认识的行
        i += 1

    return namespaces, classes, structs, enums, functions, variables


def _parse_namespace(content: str) -> tuple:
    """解析 namespace 定义"""
    match = re.match(r'namespace\s+(\w+)(?:\s*\{\s*)?', content)
    if not match:
        return None, 0

    name = match.group(1)
    result = {
        "name": name,
        "classes": [],
        "structs": [],
        "functions": [],
    }

    # 如果有花括号，提取内容
    if '{' in content[match.end():match.end()+5]:
        body_start = content.find('{', match.end())
        body_content, body_end = _extract_cpp_body(content, body_start)
        result["_body_content"] = body_content
        return result, body_start + body_end + 1

    return result, match.end()


def _parse_class(content: str, lang_type: str) -> tuple:
    """解析 class 定义"""
    # class [模板] ClassName [: BaseClass]
    match = re.match(r'class\s+(\w+)(?:\s*:\s*([^{]+))?', content)
    if not match:
        return None, 0

    name = match.group(1)
    bases = match.group(2)

    result = {
        "name": name,
        "bases": [b.strip() for b in bases.split(',')] if bases else [],
        "templates": _extract_templates(content),
        "access_specifier": "private",  # 默认 private
        "fields": [],
        "methods": [],
    }

    # 找类体
    body_start = content.find('{')
    if body_start != -1:
        body_content, body_end = _extract_cpp_body(content, body_start)
        result["fields"], result["methods"] = _parse_class_body(body_content)

        # 更新访问修饰符（第一个可见成员的修饰符）
        if "public:" in body_content:
            result["access_specifier"] = "public"
        elif "private:" in body_content:
            result["access_specifier"] = "private"

        return result, body_start + body_end + 1

    return result, match.end()


def _parse_struct(content: str, lang_type: str) -> tuple:
    """解析 struct 定义"""
    match = re.match(r'struct\s+(\w+)(?:\s*:\s*([^{]+))?', content)
    if not match:
        return None, 0

    name = match.group(1)
    bases = match.group(2)

    result = {
        "name": name,
        "bases": [b.strip() for b in bases.split(',')] if bases else [],
        "templates": _extract_templates(content),
        "access_specifier": "public",  # struct 默认 public
        "fields": [],
        "methods": [],
    }

    # 找结构体体
    body_start = content.find('{')
    if body_start != -1:
        body_content, body_end = _extract_cpp_body(content, body_start)
        result["fields"], result["methods"] = _parse_class_body(body_content)
        return result, body_start + body_end + 1

    return result, match.end()


def _parse_enum(content: str) -> tuple:
    """解析 enum 定义"""
    # enum [class/struct] EnumName { values }
    match = re.match(r'enum\s+(?:class\s+|struct\s+)?(\w+)', content)
    if not match:
        return None, 0

    name = match.group(1)
    result = {
        "name": name,
        "values": [],
        "is_scoped": "class" in content[:match.end()],
    }

    # 找枚举体
    body_start = content.find('{')
    if body_start != -1:
        body_content, body_end = _extract_cpp_body(content, body_start)

        # 提取枚举值
        for val_match in re.finditer(r'(\w+)(?:\s*=\s*\d+)?', body_content):
            val = val_match.group(1)
            if val != name:  # 避免把 enum 名称也加进去
                result["values"].append(val)

        return result, body_start + body_end + 1

    return result, match.end()


def _extract_templates(content: str) -> Optional[str]:
    """提取模板参数"""
    match = re.search(r'template\s*<([^>]+)>', content)
    if match:
        return match.group(1)
    return None


def _extract_cpp_body(content: str, start: int) -> tuple:
    """提取 C++ 代码块（平衡大括号）"""
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


def _parse_class_body(body: str) -> tuple:
    """解析类体"""
    fields = []
    methods = []

    # 分割成单独的定义
    lines = body.split('\n')
    current_access = "private"

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 访问修饰符
        if line.startswith('public:'):
            current_access = "public"
            continue
        elif line.startswith('private:'):
            current_access = "private"
            continue
        elif line.startswith('protected:'):
            current_access = "protected"
            continue

        # 解析字段或方法
        parsed = _parse_field_or_method(line, current_access)
        if parsed:
            if parsed["kind"] == "field":
                fields.append(parsed)
            else:
                methods.append(parsed)

    return fields, methods


def _parse_field_or_method(line: str, access: str) -> Optional[Dict]:
    """解析字段或方法"""
    # 移除修饰符和注释
    clean_line = line.rstrip(';').strip()

    # 模板函数跳过
    if clean_line.startswith('template '):
        return None

    # 检查是否有参数列表（方法）
    paren_match = re.search(r'\(([^)]*)\)\s*(?:const)?\s*(?:override|noexcept)?\s*[{;]', clean_line)
    if paren_match:
        # 这是一个方法
        # 提取返回类型和方法名
        before_paren = clean_line[:paren_match.start()].strip()
        # 返回类型是最后一部分
        parts = before_paren.split()
        if len(parts) >= 2:
            return_type = ' '.join(parts[:-1])
            name = parts[-1]
        else:
            return_type = parts[0] if parts else "void"
            name = "unknown"

        return {
            "kind": "method",
            "name": name,
            "return_type": return_type,
            "params": [p.strip() for p in paren_match.group(1).split(',') if p.strip()],
            "access": access,
        }
    else:
        # 这是一个字段
        parts = clean_line.split()
        if len(parts) >= 2:
            ftype = parts[-2]
            fname = parts[-1].rstrip(';')
            return {
                "kind": "field",
                "name": fname,
                "type": ftype,
                "access": access,
            }

    return None


def _parse_cpp_methods(body: str) -> List[Dict]:
    """解析 C++ 方法（从类体中提取）"""
    methods = []

    for line in body.split('\n'):
        line = line.strip()
        if not line or line.endswith(':') or line.startswith('public') or line.startswith('private') or line.startswith('protected'):
            continue

        parsed = _parse_field_or_method(line, "private")
        if parsed and parsed["kind"] == "method":
            methods.append(parsed)

    return methods


def _parse_template_function(content: str) -> tuple:
    """解析模板函数"""
    match = re.match(r'template\s*<[^>]+>\s*(.+?)\s*\(([^)]*)\)', content, re.DOTALL)
    if not match:
        return None, 0

    # 简化处理
    return {
        "name": "template_function",
        "template": True,
    }, 0


def _try_parse_function(content: str, lang_type: str) -> tuple:
    """尝试解析函数定义"""
    # C++: ReturnType FunctionName(params)
    # C#: ReturnType FunctionName(params)

    # 跳过模板和方法体开始
    if content.startswith('template ') or content.startswith('virtual ') or content.startswith('override ') or content.startswith('inline '):
        return None, 0

    # 尝试匹配函数签名
    # 格式: [修饰符] 返回类型 函数名(参数)
    match = re.match(r'(?:inline\s+)?((?:const\s+)?(?:volatile\s+)?(?:unsigned\s+)?(?:\w+(?:\s*\*|\s*&|\s*\*&)?(?:\s+(?:const|volatile))?\s+)+)(\w+)\s*\(([^)]*)\)', content)

    if match:
        return_type = match.group(1).strip()
        name = match.group(2)
        params = match.group(3)

        # 找函数体
        body_start = content.find('{')
        if body_start != -1:
            _, body_end = _extract_cpp_body(content, body_start)
            return {
                "name": name,
                "return_type": return_type,
                "params": [p.strip() for p in params.split(',') if p.strip()],
            }, body_start + body_end + 1

    return None, 0


def _parse_with_tree_sitter(content: str, rel_path: str, lang_type: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 C/C++/C# 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        # 根据语言类型选择 tree-sitter 语言
        lang_map = {
            "c": "c",
            "cpp": "cpp",
            "csharp": "c_sharp",
        }
        ts_lang = lang_map.get(lang_type, "cpp")
        lang = get_language(ts_lang)

        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            "type": lang_type,
            "language": lang_type,
            "includes": [],
            "usings": [],
            "namespaces": [],
            "classes": [],
            "structs": [],
            "enums": [],
            "interfaces": [],
            "functions": [],
            "variables": [],
            "tree_sitter_parsed": True
        }

        # 遍历 AST 提取信息
        _traverse_cpp_ast(tree.root_node, bytes(content, 'utf8'), result, lang_type)

        return result

    except ImportError:
        return None
    except Exception:
        return None


def _traverse_cpp_ast(node: Any, content: bytes, result: Dict, lang_type: str) -> None:
    """遍历 C/C++/C# AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text

    node_type = node.type

    # #include (C/C++)
    if node_type == 'preproc_include':
        text = extract_node_text(node, content)
        inc_match = re.search(r'#\s*include\s*(["<])([^>"]+)[">]', text)
        if inc_match:
            result['includes'].append(f"{inc_match.group(1)}{inc_match.group(2)}{inc_match.group(1)}")

    # using (C#)
    elif node_type == 'using_directive':
        text = extract_node_text(node, content)
        using_match = re.search(r'using\s+([\w.]+)', text)
        if using_match:
            result['usings'].append(using_match.group(1))

    # namespace
    elif node_type == 'namespace_identifier':
        text = extract_node_text(node, content).strip()
        if text and text not in result['namespaces']:
            result['namespaces'].append(text)

    # class 或 struct
    elif node_type in ('class_specifier', 'struct_specifier'):
        text = extract_node_text(node, content)
        name_match = re.search(r'(class|struct)\s+(\w+)', text)
        if name_match:
            type_kind = name_match.group(1)
            type_info = {
                "name": name_match.group(2),
                "kind": type_kind,
                "access_specifier": "private" if type_kind == "class" else "public",
                "fields": [],
                "methods": [],
            }
            if type_kind == "struct":
                result['structs'].append(type_info)
            else:
                result['classes'].append(type_info)

    # enum
    elif node_type == 'enum_specifier':
        text = extract_node_text(node, content)
        enum_match = re.search(r'enum\s+(?:class\s+|struct\s+)?(\w+)', text)
        if enum_match:
            result['enums'].append({
                "name": enum_match.group(1),
                "values": [],
            })

    # 函数声明
    elif node_type == 'function_declaration':
        text = extract_node_text(node, content)
        func_match = re.search(r'((?:[\w*&]+\s+)+)(\w+)\s*\(', text)
        if func_match:
            result['functions'].append({
                "name": func_match.group(2),
                "return_type": func_match.group(1).strip(),
                "params": [],
            })

    # 递归遍历子节点
    for child in node.children:
        _traverse_cpp_ast(child, content, result, lang_type)


# 导出函数
__all__ = ['parse_c_family_file']