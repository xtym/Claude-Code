#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHP 文件解析器
支持正则表达式解析和 Tree-sitter AST 解析
"""
import re
from typing import Dict, Any, Optional, Tuple


def parse_php_file(content: str, rel_path: str, use_tree_sitter: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """解析 PHP 文件，提取类信息

    Args:
        content: 文件内容
        rel_path: 相对路径
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）
    
    Returns:
        Tuple: (file_info, class_info)
        - file_info: 文件基本信息，包含 summary
        - class_info: 类注册信息，用于添加到 graph_data['classes']
    """
    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_php_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result, {}
    
    # 回退到正则表达式解析
    return _parse_php_with_regex(content, rel_path)


def _parse_php_with_tree_sitter(content: str, rel_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """使用 tree-sitter 解析 PHP 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language
        
        lang = get_language('php')
        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))
        
        result = {
            'type': 'php',
            'summary': {
                'namespace': '',
                'imports': [],
                'traits': [],
                'class_name': '',
                'methods': [],
                'properties': [],
                'dependencies': [],
            },
            'tree_sitter_parsed': True
        }
        
        # 遍历 AST 提取信息
        _traverse_php_ast(tree.root_node, bytes(content, 'utf8'), result)
        
        # 提取类注册信息
        class_info = _extract_class_info_from_summary(result['summary'], rel_path)
        
        return result, class_info
        
    except ImportError:
        return None, {}
    except Exception:
        return None, {}


def _traverse_php_ast(node: Any, content: bytes, result: Dict) -> None:
    """遍历 PHP AST 节点提取信息"""
    from .tree_sitter_helper import extract_node_text
    
    node_type = node.type
    
    # namespace 声明
    if node_type == 'namespace_name':
        text = extract_node_text(node, content).strip()
        if '\\' in text or '.' in text:
            result['summary']['namespace'] = text.replace('.', '\\')
    
    # use 声明
    elif node_type == 'name':
        text = extract_node_text(node, content).strip()
        if text and '\\' in text and text not in result['summary']['imports']:
            result['summary']['imports'].append(text)
    
    # class 声明
    elif node_type == 'class_declaration':
        text = extract_node_text(node, content)
        class_match = re.search(r'class\s+(\w+)', text)
        if class_match:
            result['summary']['class_name'] = class_match.group(1)
    
    # method 声明
    elif node_type == 'method_declaration':
        text = extract_node_text(node, content)
        method_match = re.search(r'(public|protected|private)?\s*(static\s+)?function\s+(\w+)\s*\(', text)
        if method_match:
            result['summary']['methods'].append({
                'name': method_match.group(3),
                'visibility': method_match.group(1) or 'public',
                'is_static': method_match.group(2) is not None,
                'attributes': [],
            })
    
    # property 声明
    elif node_type in ('property_element', 'class_property'):
        text = extract_node_text(node, content)
        prop_match = re.search(r'(public|protected|private)?\s*static\s+\$\w+', text)
        if prop_match:
            result['summary']['properties'].append({
                'name': extract_node_text(node, content).split('$')[-1] if '$' in text else '',
                'visibility': prop_match.group(1) or 'public',
                'is_static': prop_match.group(2) is not None,
                'attributes': [],
            })
    
    # 递归遍历子节点
    for child in node.children:
        _traverse_php_ast(child, content, result)


def _parse_php_with_regex(content: str, rel_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """使用正则表达式解析 PHP 文件"""
    result = {'type': 'php', 'summary': {}}
    class_info = {}
    
    # 提取命名空间
    namespace_match = re.search(r'namespace\s+([\w\\]+);', content)
    if namespace_match:
        result['summary']['namespace'] = namespace_match.group(1)
    
    # 提取 use 语句（用于依赖推断）
    use_statements = {}
    for use_match in re.finditer(r'use\s+([\w\\]+)(?:\s+as\s+(\w+))?;', content):
        full_class_name = use_match.group(1)
        alias = use_match.group(2)
        short_name = full_class_name.split('\\')[-1]
        use_statements[alias or short_name] = full_class_name
    result['summary']['imports'] = list(use_statements.values())
    
    # 提取 Trait
    traits = []
    for trait_match in re.finditer(r'use\s+([\w\\]+)(?:\s*,\s*([\w\\]+))*;', content):
        trait_names = [t for t in trait_match.groups() if t]
        if trait_names:
            traits.extend(trait_names)
    result['summary']['traits'] = traits
    
    # 提取类信息
    class_match = re.search(r'class\s+(\w+)(?:\s+extends\s+([\w\\]+))?(?:\s+implements\s+([\w\\,\s]+))?', content)
    if class_match:
        class_name = class_match.group(1)
        result['summary']['class_name'] = class_name
        
        # 完整类名
        full_class_name = class_name
        if 'namespace' in result['summary']:
            full_class_name = f"{result['summary']['namespace']}\\{class_name}"
        
        # 提取 PHP 8 Attributes（类级别的）
        class_attributes = re.findall(r'#\[([\w\\]+)(?:\([^)]*\))?\]', content)
        class_attr_match = re.search(r'^(?:abstract\s+|final\s+)?class\s', content, re.MULTILINE)
        if class_attr_match:
            class_start = class_attr_match.start()
            class_attrs = []
            for attr_match in re.finditer(r'#\[([\w\\]+)(?:\([^)]*\))?\]', content[:class_start]):
                class_attrs.append(attr_match.group(1))
            class_attributes = class_attrs
        
        # 提取方法
        methods = _extract_php_methods(content)
        
        # 提取属性
        properties = _extract_php_properties(content)
        
        # 推断依赖关系（基于属性类型）
        dependencies = []
        for prop in properties:
            if prop['type']:
                prop_type = prop['type']
                if prop_type in use_statements:
                    dep_short = prop_type.split('\\')[-1]
                    if dep_short not in dependencies:
                        dependencies.append(dep_short)
                elif '\\' in prop_type:
                    dep_short = prop_type.split('\\')[-1]
                    if dep_short not in dependencies:
                        dependencies.append(dep_short)
        
        result['summary']['methods'] = methods
        result['summary']['properties'] = properties
        result['summary']['dependencies'] = dependencies
        
        # 构建类注册信息
        implements_str = class_match.group(3)
        implements = [i.strip() for i in implements_str.split(',')] if implements_str else []
        
        class_info[full_class_name] = {
            'file': rel_path,
            'namespace': result['summary'].get('namespace'),
            'extends': class_match.group(2),
            'implements': implements,
            'traits': traits,
            'properties': properties,
            'methods': methods,
            'attributes': class_attributes,
            'dependencies': dependencies,
        }
    
    return result, class_info


def _extract_class_info_from_summary(summary: Dict, rel_path: str) -> Dict[str, Any]:
    """从 summary 构建类注册信息（用于 tree-sitter 模式）"""
    class_info = {}
    if summary.get('class_name'):
        full_class_name = summary['class_name']
        if summary.get('namespace'):
            full_class_name = f"{summary['namespace']}\\{summary['class_name']}"
        
        class_info[full_class_name] = {
            'file': rel_path,
            'namespace': summary.get('namespace'),
            'extends': None,
            'implements': [],
            'traits': summary.get('traits', []),
            'properties': summary.get('properties', []),
            'methods': summary.get('methods', []),
            'attributes': [],
            'dependencies': summary.get('dependencies', []),
        }
    return class_info


def _extract_php_methods(content: str) -> list:
    """提取 PHP 类方法"""
    methods = []
    method_pattern = r'(public|protected|private)\s+(static\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([\w\\\[\]|?]+))?'
    
    # 首先收集所有 attribute 及其位置
    all_attributes = []
    for attr_match in re.finditer(r'#\[([\w\\]+)(?:\([^)]*\))?\]', content):
        all_attributes.append({
            'name': attr_match.group(1),
            'pos': attr_match.start()
        })
    
    for method_match in re.finditer(method_pattern, content):
        visibility = method_match.group(1)
        is_static = method_match.group(2) is not None
        method_name = method_match.group(3)
        params_str = method_match.group(4)
        return_type = method_match.group(5)
        
        # 解析参数
        params = []
        if params_str.strip():
            for param_match in re.finditer(r'((?:[\w\\\[\]|?]+)\s+)?\$(\w+)(?:\s*=\s*([^,]+))?', params_str):
                param_type = param_match.group(1)
                param_name = param_match.group(2)
                param_default = param_match.group(3)
                params.append({
                    'name': param_name,
                    'type': param_type.strip() if param_type else None,
                    'default': param_default.strip() if param_default else None
                })
        
        # 解析方法上的 attributes
        method_start = method_match.start()
        method_attrs = _get_method_attributes(content, method_start, method_name, all_attributes)
        
        methods.append({
            'name': method_name,
            'visibility': visibility,
            'is_static': is_static,
            'return_type': return_type.strip() if return_type else None,
            'params': params,
            'attributes': method_attrs
        })
    
    return methods


def _get_method_attributes(content: str, method_start: int, method_name: str, all_attributes: list) -> list:
    """获取方法上的 attributes"""
    property_pattern = r'(public|protected|private)\s+(static\s+)?((?:[\w\\\[\]|?]+)\s+)?\$(\w+)'
    method_attrs = []
    
    for attr in reversed(all_attributes):
        if attr['pos'] < method_start:
            between = content[attr['pos']:method_start]
            
            # 检查是否有属性声明在中间（说明 attr 属于属性，不属于方法）
            prop_match = re.search(property_pattern, between)
            if prop_match:
                break
            
            # 检查是否有其他方法声明
            func_match = re.search(r'\bfunction\s+(\w+)\s*\(', between)
            if func_match:
                if func_match.group(1) == method_name:
                    method_attrs.insert(0, attr['name'])
                    break
                else:
                    break
            
            # 没有属性声明，没有其他方法声明 -> attr 可能属于当前方法
            method_attrs.insert(0, attr['name'])
            break
    
    return method_attrs


def _extract_php_properties(content: str) -> list:
    """提取 PHP 类属性"""
    properties = []
    property_pattern = r'(public|protected|private)\s+(static\s+)?((?:[\w\\\[\]|?]+)\s+)?\$(\w+)(?:\s*=\s*([^;]+))?'
    
    for prop_match in re.finditer(property_pattern, content):
        visibility = prop_match.group(1)
        is_static = prop_match.group(2) is not None
        prop_type = prop_match.group(3)
        prop_name = prop_match.group(4)
        default = prop_match.group(5)
        
        # 解析属性上的 attributes
        prop_start = prop_match.start()
        before_prop = content[:prop_start]
        last_attr_pos = before_prop.rfind('#[')
        prop_attrs = []
        if last_attr_pos != -1:
            line_start = before_prop.rfind('\n', 0, last_attr_pos)
            context = before_prop[line_start:prop_start] if line_start != -1 else before_prop[:prop_start]
            if 'function' not in context and 'class' not in context:
                for attr_match in re.finditer(r'#\[([\w\\]+)(?:\([^)]*\))?\]', context):
                    prop_attrs.append(attr_match.group(1))
        
        properties.append({
            'name': prop_name,
            'type': prop_type.strip() if prop_type else None,
            'visibility': visibility,
            'is_static': is_static,
            'default': default.strip() if default else None,
            'attributes': prop_attrs
        })
    
    return properties
