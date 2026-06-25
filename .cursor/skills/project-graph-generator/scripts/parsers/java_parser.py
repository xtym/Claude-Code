"""
Java 解析器
提取 Java 代码中的类、接口、枚举、方法、字段、注解等信息
"""

import re
from typing import Dict, List, Any, Optional


def parse_java_file(content: str, rel_path: str = "", use_tree_sitter: bool = False) -> Dict[str, Any]:
    """
    解析 Java 文件

    Args:
        content: 文件内容
        rel_path: 相对路径（用于推断包名）
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    result = {
        "type": "java",
        "package": "",
        "imports": [],
        "classes": [],
        "interfaces": [],
        "enums": [],
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析

    # 提取 package 声明
    package_match = re.search(r'^\s*package\s+([\w.]+)\s*;', content, re.MULTILINE)
    if package_match:
        result["package"] = package_match.group(1)

    # 提取 imports
    for import_match in re.finditer(r'^\s*import\s+([\w.*]+)\s*;', content, re.MULTILINE):
        result["imports"].append(import_match.group(1))

    # 移除注释和字符串以便更好地解析
    clean_content = _remove_comments_and_strings(content)

    # 解析类型定义（类、接口、枚举）
    result["classes"], result["interfaces"], result["enums"] = _parse_type_definitions(clean_content)

    return result


def _remove_comments_and_strings(content: str) -> str:
    """移除注释和字符串字面量"""
    # 单行注释
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    # 多行注释
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # 字符串字面量（简化处理）
    content = re.sub(r'"(?:[^"\\]|\\.)*"', '""', content)
    # 字符字面量
    content = re.sub(r"'(?:[^'\\]|\\.)*'", "''", content)
    return content


def _parse_type_definitions(content: str) -> tuple:
    """解析类、接口、枚举定义"""
    classes = []
    interfaces = []
    enums = []

    # 匹配类型定义
    # 支持: class, interface, enum, record (Java 14+)
    type_pattern = r'(?:@\w+(?:\([^)]*\))?\s+)*(public\s+)?(class|interface|enum|record)\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([\w,<\s>]+))?(?:\s+implements\s+([\w,<\s>]+))?'

    for match in re.finditer(type_pattern, content):
        access = match.group(1) or "default"
        type_kind = match.group(2)
        name = match.group(3)
        extends = match.group(4)
        implements = match.group(5)

        # 提取注解
        annotations = _extract_annotations_before(content, match.start())

        type_info = {
            "name": name,
            "kind": type_kind,
            "access": "public" if access else "default",
            "annotations": annotations,
            "extends": extends.strip() if extends else None,
            "implements": [i.strip() for i in implements.split(',')] if implements else [],
            "type_params": _extract_type_params(content, match.end()),
            "fields": [],
            "methods": [],
        }

        # 提取类体内容
        body_start = content.find('{', match.end())
        if body_start != -1:
            body_content, body_end = _extract_balanced_braces(content, body_start)
            if type_kind == 'class' or type_kind == 'record':
                type_info["fields"], type_info["methods"] = _parse_class_body(body_content)
                classes.append(type_info)
            elif type_kind == 'interface':
                type_info["methods"] = _parse_interface_methods(body_content)
                interfaces.append(type_info)
            elif type_kind == 'enum':
                type_info["fields"], type_info["methods"] = _parse_enum_body(body_content)
                enums.append(type_info)

    return classes, interfaces, enums


def _extract_annotations_before(content: str, pos: int) -> List[str]:
    """提取位置之前的注解"""
    before = content[:pos]
    # 找最后几行
    lines = before.rstrip().split('\n')
    annotations = []

    for line in lines[-5:]:  # 只检查最后5行
        line = line.strip()
        if line.startswith('@'):
            ann_match = re.match(r'@(\w+)(?:\(([^)]*)\))?', line)
            if ann_match:
                ann_name = ann_match.group(1)
                ann_args = ann_match.group(2)
                if ann_args:
                    annotations.append(f"{ann_name}({ann_args})")
                else:
                    annotations.append(ann_name)
        elif line.endswith('{') or line.endswith(';') or line.startswith('class') or line.startswith('interface') or line.startswith('enum'):
            break

    return annotations


def _extract_type_params(content: str, pos: int) -> Optional[str]:
    """提取泛型类型参数"""
    # 查找 <...> 模式
    segment = content[pos:pos+200]
    match = re.search(r'<([^>]+)>', segment)
    if match:
        return match.group(1)
    return None


def _extract_balanced_braces(content: str, start: int) -> tuple:
    """提取平衡的大括号内容"""
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
    """解析类体，提取字段和方法"""
    fields = []
    methods = []

    # 匹配字段
    # 格式: [注解] [修饰符] 类型 名称 [= 值];
    field_pattern = r'(?:@\w+(?:\([^)]*\))?\s+)*((?:public|protected|private)\s+)?(?:static\s+)?(?:final\s+)?(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)(?:\s*=\s*([^;]+))?\s*;'

    # 匹配方法
    method_pattern = r'(?:@\w+(?:\([^)]*\))?\s+)*((?:public|protected|private)\s+)?(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:synchronized\s+)?(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)\s*\(([^)]*)\)(?:\s+throws\s+([^{]+))?'

    for match in re.finditer(field_pattern, body):
        annotations = _extract_annotations_before(body, match.start())
        access = match.group(1) or "private"
        field_type = match.group(2)
        name = match.group(3)
        default_value = match.group(4)

        fields.append({
            "name": name,
            "type": field_type,
            "access": access.strip(),
            "annotations": annotations,
            "default": default_value.strip() if default_value else None,
        })

    for match in re.finditer(method_pattern, body):
        annotations = _extract_annotations_before(body, match.start())
        access = match.group(1) or "private"
        return_type = match.group(2)
        name = match.group(3)
        params_str = match.group(4)
        throws = match.group(5)

        # 跳过构造函数（返回类型与方法名在一起会混淆）
        if return_type == name:
            continue

        params = _parse_java_params(params_str)

        methods.append({
            "name": name,
            "return_type": return_type,
            "params": params,
            "access": access.strip(),
            "annotations": annotations,
            "throws": throws.strip() if throws else None,
        })

    return fields, methods


def _parse_interface_methods(body: str) -> List[Dict]:
    """解析接口方法"""
    methods = []

    # 接口方法格式: [注解] 返回类型 方法名(参数);
    method_pattern = r'(?:@\w+(?:\([^)]*\))?\s+)*(\w+(?:<[^>]+>)?(?:\[\])?)\s+(\w+)\s*\(([^)]*)\)'

    for match in re.finditer(method_pattern, body):
        annotations = _extract_annotations_before(body, match.start())
        return_type = match.group(1)
        name = match.group(2)
        params_str = match.group(3)

        # 跳过构造函数
        if return_type == name:
            continue

        params = _parse_java_params(params_str)

        methods.append({
            "name": name,
            "return_type": return_type,
            "params": params,
            "annotations": annotations,
        })

    return methods


def _parse_enum_body(body: str) -> tuple:
    """解析枚举体"""
    fields = []
    methods = []

    # 枚举常量
    enum_constants = []
    for const_match in re.finditer(r'(\w+)(?:\([^)]*\))?(?:\s*,\s*;|\s*;)', body):
        const_name = const_match.group(1)
        if const_name and not const_name.startswith('{'):
            enum_constants.append(const_name)

    fields.append({
        "name": "values",
        "type": "enum",
        "constants": enum_constants,
        "access": "public",
        "annotations": [],
    })

    # 枚举方法（类似类）
    enum_methods = _parse_class_body(body)
    methods = enum_methods[1]  # 取方法部分

    return fields, methods


def _parse_java_params(params_str: str) -> List[str]:
    """解析 Java 方法参数列表"""
    if not params_str.strip():
        return []

    params = []
    for param in params_str.split(','):
        param = param.strip()
        if param:
            # 参数格式: 类型 名称
            parts = param.split()
            if len(parts) >= 2:
                params.append(f"{parts[0]} {parts[-1]}")
            else:
                params.append(param)

    return params


def _parse_with_tree_sitter(content: str, rel_path: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 Java 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        lang = get_language('java')
        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            "type": "java",
            "package": "",
            "imports": [],
            "classes": [],
            "interfaces": [],
            "enums": [],
            "tree_sitter_parsed": True
        }

        # 遍历 AST 提取信息
        _traverse_java_ast(tree.root_node, bytes(content, 'utf8'), result)

        return result

    except ImportError:
        return None
    except Exception:
        return None


def _traverse_java_ast(node: Any, content: bytes, result: Dict) -> None:
    """遍历 Java AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text

    node_type = node.type

    # package 声明
    if node_type == 'package_declaration':
        text = extract_node_text(node, content)
        pkg_match = re.search(r'package\s+([\w.]+)', text)
        if pkg_match:
            result['package'] = pkg_match.group(1)

    # import 语句
    elif node_type == 'import_declaration':
        text = extract_node_text(node, content)
        import_match = re.search(r'import\s+([\w.*]+)', text)
        if import_match:
            result['imports'].append(import_match.group(1))

    # 类声明
    elif node_type == 'class_declaration':
        text = extract_node_text(node, content)
        class_match = re.search(r'(?:@\w+\([^)]*\)\s+)*(?:public\s+)?class\s+(\w+)', text)
        if class_match:
            result['classes'].append({
                "name": class_match.group(1),
                "kind": "class",
                "access": "public" if "public" in text else "default",
                "annotations": [],
                "extends": None,
                "implements": [],
                "fields": [],
                "methods": [],
            })

    # 接口声明
    elif node_type == 'interface_declaration':
        text = extract_node_text(node, content)
        iface_match = re.search(r'(?:@\w+\([^)]*\)\s+)*(?:public\s+)?interface\s+(\w+)', text)
        if iface_match:
            result['interfaces'].append({
                "name": iface_match.group(1),
                "access": "public" if "public" in text else "default",
                "annotations": [],
                "extends": [],
                "methods": [],
            })

    # 递归遍历子节点
    for child in node.children:
        _traverse_java_ast(child, content, result)


# 导出函数
__all__ = ['parse_java_file']