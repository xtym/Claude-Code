"""
JavaScript / TypeScript 解析器
支持 ES6 模块、类、函数、接口、类型定义等
"""

import re
from typing import Dict, List, Any, Optional


def parse_js_file(content: str, rel_path: str, use_tree_sitter: bool = False) -> Dict[str, Any]:
    """解析 JavaScript/TypeScript 文件

    Args:
        content: 文件内容
        rel_path: 相对路径
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    # JavaScript 关键字列表（不能作为方法名）
    JS_KEYWORDS = {
        'break', 'case', 'catch', 'continue', 'debugger', 'default', 'delete',
        'do', 'else', 'finally', 'for', 'function', 'if', 'in', 'instanceof',
        'new', 'return', 'switch', 'this', 'throw', 'try', 'typeof', 'var',
        'void', 'while', 'with', 'yield', 'class', 'const', 'enum', 'export',
        'extends', 'import', 'super', 'implements', 'interface', 'let', 'package',
        'private', 'protected', 'public', 'static', 'yield', 'async', 'await',
        'of', 'null', 'true', 'false', 'undefined'
    }
    
    result = {
        'type': 'javascript',
        'summary': {}
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析
    # 判断是否包含 TypeScript 类型
    has_typescript = bool(re.search(r':\s*(string|number|boolean|any|void|never|unknown|object|\w+\[\]|Promise<|Record<|Partial<|Required<)', content))
    
    # 提取 import 语句
    imports = []
    for import_match in re.finditer(
        r'import\s+(?:{([^}]+?)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
        content
    ):
        named_imports = import_match.group(1)
        default_import = import_match.group(2)
        namespace_import = import_match.group(3)
        source = import_match.group(4)
        
        imports_entry = {
            'source': source,
            'items': []
        }
        
        if default_import:
            imports_entry['items'].append(default_import)
        if namespace_import:
            imports_entry['items'].append(f'* as {namespace_import}')
        if named_imports:
            for item in [i.strip() for i in named_imports.split(',')]:
                if item:
                    imports_entry['items'].append(item)
        
        imports.append(imports_entry)
    
    # 提取 export 语句
    exports = []
    for export_match in re.finditer(
        r'export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|enum)\s+(\w+)',
        content
    ):
        exports.append(export_match.group(1))
    
    # 提取类定义
    classes = []
    for class_match in re.finditer(
        r'class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
        content
    ):
        class_name = class_match.group(1)
        extends = class_match.group(2)
        implements_str = class_match.group(3)
        implements = [i.strip() for i in implements_str.split(',')] if implements_str else []
        
        # 提取类方法
        class_start = class_match.start()
        # 找到匹配的结束位置（简化处理，查找下一个 class 或文件结束）
        class_body_match = re.search(r'(?=\n\s*class\s|\Z)', content[class_start + len(f'class {class_name}'):])
        class_body_end = class_start + len(f'class {class_name}') + (class_body_match.start() if class_body_match else len(content))
        class_body = content[class_start:class_body_end]
        
        methods = []
        for method_match in re.finditer(
            r'(?:(public|private|protected|static)\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)(?:\s*:\s*[\w<>\[\]|]+)?\s*\{',
            class_body
        ):
            method_name = method_match.group(2)
            # 过滤掉 JavaScript 关键字
            if method_name in JS_KEYWORDS:
                continue
            visibility = method_match.group(1)
            is_static = visibility == 'static'
            if visibility:
                visibility = visibility if visibility != 'static' else 'public'
            if not is_static and visibility is None:
                visibility = 'public'
            methods.append({
                'name': method_name,
                'visibility': visibility or 'public',
                'is_static': is_static
            })
        
        classes.append({
            'name': class_name,
            'extends': extends,
            'implements': implements,
            'methods': methods
        })
    
    # 提取接口定义
    interfaces = []
    for iface_match in re.finditer(
        r'interface\s+(\w+)(?:\s+extends\s+([\w,\s]+))?',
        content
    ):
        iface_name = iface_match.group(1)
        extends = iface_match.group(2)
        extends_list = [e.strip() for e in extends.split(',')] if extends else []
        
        # 提取接口成员
        iface_start = iface_match.start()
        iface_body_match = re.search(r'(?=\n\s*\w|\Z)', content[iface_start + len(f'interface {iface_name}'):])
        iface_body_end = iface_start + len(f'interface {iface_name}') + (iface_body_match.start() if iface_body_match else len(content))
        iface_body = content[iface_start:iface_body_end]
        
        members = []
        for member_match in re.finditer(r'(\w+)(\?)?:\s*([^;]+)', iface_body):
            members.append({
                'name': member_match.group(1),
                'optional': member_match.group(2) == '?',
                'type': member_match.group(3).strip()
            })
        
        interfaces.append({
            'name': iface_name,
            'extends': extends_list,
            'members': members
        })
    
    # 提取类型定义
    type_aliases = []
    for type_match in re.finditer(
        r'type\s+(\w+)\s*=\s*([^;]+)',
        content
    ):
        type_aliases.append({
            'name': type_match.group(1),
            'definition': type_match.group(2).strip()
        })
    
    # 提取函数声明
    functions = []
    for func_match in re.finditer(
        r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)',
        content
    ):
        functions.append(func_match.group(1))
    
    # 提取 const/let/var 声明
    variables = []
    for var_match in re.finditer(
        r'(?:export\s+)?(?:const|let|var)\s+(\w+)(?:\s*:\s*[^=]+)?\s*=',
        content
    ):
        variables.append(var_match.group(1))
    
    result['summary'] = {
        'is_typescript': has_typescript,
        'imports': imports,
        'exports': exports,
        'classes': classes,
        'interfaces': interfaces,
        'type_aliases': type_aliases,
        'functions': functions,
        'variables': variables
    }

    return result


def _parse_with_tree_sitter(content: str, rel_path: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 JavaScript/TypeScript 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        # 根据文件扩展名判断语言
        ext = rel_path.lower().split('.')[-1] if '.' in rel_path else ''
        if ext in ('ts', 'tsx'):
            lang = get_language('typescript')
        else:
            lang = get_language('javascript')

        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            'type': 'javascript',
            'summary': {
                'is_typescript': ext in ('ts', 'tsx'),
                'imports': [],
                'exports': [],
                'classes': [],
                'interfaces': [],
                'type_aliases': [],
                'functions': [],
                'variables': [],
            },
            'tree_sitter_parsed': True
        }

        # 遍历 AST 提取信息
        _traverse_js_ast(tree.root_node, bytes(content, 'utf8'), result['summary'])

        return result

    except ImportError:
        return None
    except Exception:
        return None


def _traverse_js_ast(node: Any, content: bytes, summary: Dict) -> None:
    """遍历 JavaScript AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text

    node_type = node.type

    # import 语句
    if node_type == 'import_statement':
        text = extract_node_text(node, content)
        import_match = re.search(r'import\s+(?:{([^}]+?)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]', text)
        if import_match:
            named_imports = import_match.group(1)
            default_import = import_match.group(2)
            namespace_import = import_match.group(3)
            source = import_match.group(4)

            imports_entry = {'source': source, 'items': []}

            if default_import:
                imports_entry['items'].append(default_import)
            if namespace_import:
                imports_entry['items'].append(f'* as {namespace_import}')
            if named_imports:
                for item in [i.strip() for i in named_imports.split(',')]:
                    if item:
                        imports_entry['items'].append(item)

            summary['imports'].append(imports_entry)

    # export 语句
    elif node_type == 'export_statement':
        text = extract_node_text(node, content)
        export_match = re.search(r'export\s+(?:default\s+)?(?:const|let|var|function|class|interface|type|enum)\s+(\w+)', text)
        if export_match:
            summary['exports'].append(export_match.group(1))

    # 类定义
    elif node_type == 'class_declaration':
        text = extract_node_text(node, content)
        class_match = re.search(r'class\s+(\w+)(?:\s+extends\s+(\w+))?', text)
        if class_match:
            class_info = {
                'name': class_match.group(1),
                'extends': class_match.group(2),
                'methods': []
            }
            summary['classes'].append(class_info)

    # 函数声明
    elif node_type == 'function_declaration':
        text = extract_node_text(node, content)
        func_match = re.search(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', text)
        if func_match:
            summary['functions'].append(func_match.group(1))

    # 递归遍历子节点
    for child in node.children:
        _traverse_js_ast(child, content, summary)
