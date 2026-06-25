"""
Vue 单文件组件（SFC）解析器
支持 <script setup> 和 <script> 块
"""

import re
from typing import Dict, List, Any, Optional


def parse_sfc_file(content: str, rel_path: str, use_tree_sitter: bool = False) -> Dict[str, Any]:
    """解析 Vue SFC 文件

    Args:
        content: 文件内容
        rel_path: 相对路径
        use_tree_sitter: 是否使用 tree-sitter AST 解析（更准确）

    Returns:
        包含解析结果的字典
    """
    result = {
        'type': 'vue',
        'summary': {}
    }

    # 尝试使用 tree-sitter 解析（如果启用且可用）
    if use_tree_sitter:
        ts_result = _parse_with_tree_sitter(content, rel_path)
        if ts_result:
            return ts_result

    # 回退到正则表达式解析
    # 提取 <script setup> 块
    script_setup_match = re.search(
        r'<script\s+setup[^>]*>(.*?)</script>',
        content,
        re.DOTALL | re.IGNORECASE
    )
    script_setup_content = script_setup_match.group(1) if script_setup_match else None
    
    # 提取 <script> 块（不含 setup）
    script_match = re.search(
        r'<script(?!\s+setup)[^>]*>(.*?)</script>',
        content,
        re.DOTALL | re.IGNORECASE
    )
    script_content = script_match.group(1) if script_match else None
    
    # 提取 <template> 块
    template_match = re.search(
        r'<template[^>]*>(.*?)</template>',
        content,
        re.DOTALL | re.IGNORECASE
    )
    template_content = template_match.group(1) if template_match else None
    
    # 解析 script setup（优先）
    if script_setup_content:
        result['summary'] = _parse_script_setup(script_setup_content)
        # 从文件名推断组件名
        if 'component_name' not in result['summary']:
            result['summary']['component_name'] = _infer_component_name(rel_path)
    elif script_content:
        result['summary'] = _parse_script(script_content)
        if 'component_name' not in result['summary']:
            result['summary']['component_name'] = _infer_component_name(rel_path)
    else:
        result['summary']['component_name'] = _infer_component_name(rel_path)
    
    # 解析 template 中的组件使用
    if template_content:
        result['summary']['template_components'] = _extract_template_components(template_content)
    
    result['summary']['has_script_setup'] = script_setup_content is not None
    result['summary']['has_template'] = template_content is not None
    
    return result


def _infer_component_name(rel_path: str) -> str:
    """从文件路径推断组件名"""
    # 移除 .vue 后缀
    name = rel_path.replace('\\', '/').split('/')[-1].replace('.vue', '')
    # 转换为 PascalCase
    return ''.join(word.capitalize() for word in re.split(r'[-_]', name))


def _parse_script_setup(content: str) -> Dict[str, Any]:
    """解析 <script setup> 内容"""
    result = {
        'script_type': 'setup',
        'vue_version': '3',
        'imports': [],
        'components_used': [],
        'composables_used': [],
        'props': [],
        'emits': [],
        'expose': []
    }
    
    # 提取 import 语句
    for import_match in re.finditer(
        r'import\s+(?:{([^}]+)}|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
        content
    ):
        named_imports = import_match.group(1)
        default_import = import_match.group(2)
        source = import_match.group(3)
        
        imports_entry = {
            'source': source,
            'items': []
        }
        
        if default_import:
            imports_entry['items'].append(default_import)
            # 判断是否是组件（首字母大写或 PascalCase）
            if _is_component_name(default_import):
                result['components_used'].append(default_import)
            elif _is_composable_name(default_import):
                result['composables_used'].append(default_import)
        
        if named_imports:
            for item in [i.strip() for i in named_imports.split(',')]:
                if item:
                    imports_entry['items'].append(item)
                    if _is_component_name(item):
                        result['components_used'].append(item)
                    elif _is_composable_name(item):
                        result['composables_used'].append(item)
        
        result['imports'].append(imports_entry)
    
    # 提取 defineProps
    props_match = re.search(
        r'defineProps\s*<([\s\S]+?)>\s*\(',
        content
    )
    if props_match:
        result['props'] = _parse_type_props(props_match.group(1))
    else:
        # 尝试对象语法 - 使用 _find_matching_brace 处理嵌套
        define_props_match = re.search(r'defineProps\s*\(', content)
        if define_props_match:
            define_props_start = content.find('{', define_props_match.end())
            if define_props_start != -1:
                define_props_end = _find_matching_brace(content, define_props_start + 1)
                if define_props_end != -1:
                    props_content = content[define_props_start + 1:define_props_end]
                    result['props'] = _parse_object_props(props_content)
    
    # 提取 defineEmits
    emits_match = re.search(
        r'defineEmits\s*\(\s*\[([^\]]+)\]\s*\)',
        content
    )
    if emits_match:
        for emit in re.findall(r'[\'"]([^\'"]+)[\'"]', emits_match.group(1)):
            result['emits'].append(emit)
    
    # 提取 defineExpose
    expose_match = re.search(
        r'defineExpose\s*\(\s*\{([^}]+)\}\s*\)',
        content
    )
    if expose_match:
        for prop in re.findall(r'(\w+)', expose_match.group(1)):
            result['expose'].append(prop)
    
    # 提取 withDefaults
    with_defaults_match = re.search(
        r'withDefaults\s*\(\s*defineProps\s*<([\s\S]+?)>\s*,\s*\{([\s\S]+?)\}\s*\)',
        content
    )
    if with_defaults_match:
        type_str = with_defaults_match.group(1)
        defaults_str = with_defaults_match.group(2)
        result['props'] = _parse_type_props_with_defaults(type_str, defaults_str)
    
    # 提取 ref/reactive/computed 变量名（用于识别响应式状态）
    for ref_match in re.finditer(
        r'(?:const|let|var)\s+(\w+)\s*=\s*(ref|reactive|computed|readonly)\s*\(',
        content
    ):
        var_name = ref_match.group(1)
        if var_name not in result.get('reactive_vars', []):
            if 'reactive_vars' not in result:
                result['reactive_vars'] = []
            result['reactive_vars'].append(var_name)
    
    return result


def _find_matching_brace(content: str, start: int) -> int:
    """找到匹配的右大括号位置，处理嵌套情况和字符串内容"""
    stack = [start - 1]  # 预先压入起始位置的左括号
    i = start
    in_string = False
    string_char = None

    while i < len(content):
        c = content[i]

        # 处理字符串
        if c in ['"', "'", '`'] and (i == 0 or content[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = c
            elif c == string_char:
                in_string = False
                string_char = None

        # 只有不在字符串内时才处理括号
        if not in_string:
            if c == '{':
                stack.append(i)
            elif c == '}':
                if stack:
                    stack.pop()
                    if not stack:
                        return i

        i += 1

    return -1


def _parse_script(content: str) -> Dict[str, Any]:
    """解析普通 <script> 内容（支持 Vue 2 和 Vue 3 选项式 API）"""
    result = {
        'script_type': 'classic',
        'vue_version': 'unknown',
        'imports': [],
        'components_used': [],
        'props': [],
        'emits': [],
        'data': [],
        'methods': [],
        'computed': [],
        'watch': [],
        'lifecycle_hooks': [],
        'mixins': [],
        'filters': [],
        'directives': []
    }
    
    # 检测 Vue 版本（通过特征判断）
    has_composition_api = bool(re.search(r'\b(ref|reactive|computed|onMounted|onUpdated|onUnmounted)\s*\(', content))
    has_setup = bool(re.search(r'\bsetup\s*\(', content))
    result['vue_version'] = '3' if (has_composition_api or has_setup) else '2'
    
    # 提取 export default（使用更好的括号匹配）
    export_start = content.find('export default')
    if export_start != -1:
        brace_start = content.find('{', export_start)
        if brace_start != -1:
            brace_end = _find_matching_brace(content, brace_start + 1)
            if brace_end != -1:
                export_content = content[brace_start + 1:brace_end]
                
                # 提取 components
                components_match = re.search(r'components\s*:\s*\{([^}]*)\}', export_content)
                if components_match:
                    for comp in re.findall(r'(\w+)', components_match.group(1)):
                        result['components_used'].append(comp)
                
                # 提取 props
                props_match = re.search(r'props\s*:\s*(.+)', export_content, re.DOTALL)
                if props_match:
                    props_str = props_match.group(1).strip()
                    if props_str.startswith('['):
                        # 数组语法：props: ['name', 'age']
                        for prop in re.findall(r'[\'"]([^\'"]+)[\'"]', props_str):
                            result['props'].append({'name': prop, 'type': None, 'required': True})
                    elif props_str.startswith('{'):
                        # 对象语法，需要找匹配的括号
                        props_start = export_content.find('props') + len('props')
                        brace_pos = export_content.find('{', props_start)
                        if brace_pos != -1:
                            props_brace_end = _find_matching_brace(export_content, brace_pos + 1)
                            if props_brace_end != -1:
                                props_content = export_content[brace_pos + 1:props_brace_end]
                                result['props'] = _parse_object_props(props_content)
                
                # 提取 emits（Vue 3）
                emits_match = re.search(r'emits\s*:\s*(\{[^}]+\}|\[[^\]]+\])', export_content)
                if emits_match:
                    emits_str = emits_match.group(1)
                    if emits_str.startswith('['):
                        for emit in re.findall(r'[\'"]([^\'"]+)[\'"]', emits_str):
                            result['emits'].append(emit)
                    else:
                        for emit in re.findall(r'[\'"]([^\'"]+)[\'"]', emits_str):
                            result['emits'].append(emit)
                
                # 提取 data（支持 data() {} 和 data: function() {}）
                data_method_match = re.search(r'data\s*(?::\s*(?:function\s*)?)?\(\s*\)\s*(?:=>)?\s*\{', export_content)
                if data_method_match:
                    # 找到 data() { 的位置，然后找匹配的 }
                    data_start = export_content.find('data', data_method_match.start() - len(export_content))
                    brace_pos = export_content.find('{', data_start)
                    if brace_pos != -1:
                        data_brace_end = _find_matching_brace(export_content, brace_pos + 1)
                        if data_brace_end != -1:
                            data_content = export_content[brace_pos + 1:data_brace_end]
                            # data_content 应该是 return { ... } 格式
                            return_match = re.search(r'return\s*\{', data_content)
                            if return_match:
                                return_brace_pos = data_content.find('{', return_match.start())
                                if return_brace_pos != -1:
                                    return_brace_end = _find_matching_brace(data_content, return_brace_pos + 1)
                                    if return_brace_end != -1:
                                        return_content = data_content[return_brace_pos + 1:return_brace_end]
                                        for var in re.findall(r'(\w+)\s*:', return_content):
                                            result['data'].append(var)
                
                # 提取 methods
                methods_section = re.search(r'methods\s*:', export_content)
                if methods_section:
                    methods_start = methods_section.end()
                    brace_pos = export_content.find('{', methods_start)
                    if brace_pos != -1:
                        methods_brace_end = _find_matching_brace(export_content, brace_pos + 1)
                        if methods_brace_end != -1:
                            methods_content = export_content[brace_pos + 1:methods_brace_end]
                            # 按逗号分割成各个方法
                            items = re.split(r',(?![^"]*")', methods_content)
                            for item in items:
                                # 匹配方法名（后跟括号）
                                match = re.search(r'(\w+)\s*\(', item)
                                if match:
                                    name = match.group(1)
                                    if name not in result['methods']:
                                        result['methods'].append(name)
                
                # 提取 computed
                computed_section = re.search(r'computed\s*:', export_content)
                if computed_section:
                    computed_start = computed_section.end()
                    brace_pos = export_content.find('{', computed_start)
                    if brace_pos != -1:
                        computed_brace_end = _find_matching_brace(export_content, brace_pos + 1)
                        if computed_brace_end != -1:
                            computed_content = export_content[brace_pos + 1:computed_brace_end]
                            # 按逗号分割成各个属性
                            items = re.split(r',(?![^"]*")', computed_content)
                            for item in items:
                                # 匹配属性名（后跟冒号或左括号）
                                match = re.search(r'(\w+)\s*[:(]', item)
                                if match:
                                    name = match.group(1)
                                    if name not in result['computed']:
                                        result['computed'].append(name)
                
                # 提取 watch
                watch_match = re.search(r'watch\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', export_content, re.DOTALL)
                if watch_match:
                    for watch in re.findall(r'(\w+)', watch_match.group(1)):
                        if watch not in result['watch']:
                            result['watch'].append(watch)
                
                # 提取 lifecycle hooks
                lifecycle_hooks = [
                    'beforeCreate', 'created', 'beforeMount', 'mounted', 'beforeUpdate', 'updated',
                    'beforeUnmount', 'unmounted', 'errorCaptured', 'renderTracked', 'renderTriggered',
                    'activated', 'deactivated', 'serverPrefetch'
                ]
                for hook in lifecycle_hooks:
                    if re.search(rf'\b{hook}\s*\(', export_content):
                        result['lifecycle_hooks'].append(hook)
                
                # 提取 mixins
                mixins_match = re.search(r'mixins\s*:\s*\[([^\]]+)\]', export_content)
                if mixins_match:
                    for mixin in re.findall(r'(\w+)', mixins_match.group(1)):
                        result['mixins'].append(mixin)
                
                # 提取 filters（Vue 2）
                filters_section = re.search(r'filters\s*:', export_content)
                if filters_section:
                    filters_start = filters_section.end()
                    brace_pos = export_content.find('{', filters_start)
                    if brace_pos != -1:
                        filters_brace_end = _find_matching_brace(export_content, brace_pos + 1)
                        if filters_brace_end != -1:
                            filters_content = export_content[brace_pos + 1:filters_brace_end]
                            # 按逗号分割成各个 filter
                            items = re.split(r',(?![^"]*")', filters_content)
                            for item in items:
                                # 匹配 filter 名（后跟括号）
                                match = re.search(r'(\w+)\s*\(', item)
                                if match:
                                    name = match.group(1)
                                    if name not in result['filters']:
                                        result['filters'].append(name)
                
                # 提取 directives（Vue 2）
                directives_match = re.search(r'directives\s*:\s*\{([^}]*)\}', export_content)
                if directives_match:
                    for d in re.findall(r'(\w+)', directives_match.group(1)):
                        result['directives'].append(d)
    
    # 提取 import 语句
    for import_match in re.finditer(
        r'import\s+(?:{([^}]+)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
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
            if _is_component_name(default_import):
                result['components_used'].append(default_import)
        
        if namespace_import:
            imports_entry['items'].append(f'* as {namespace_import}')
        
        if named_imports:
            for item in [i.strip() for i in named_imports.split(',')]:
                if item:
                    imports_entry['items'].append(item)
                    if _is_component_name(item):
                        result['components_used'].append(item)
        
        result['imports'].append(imports_entry)
    
    return result


def _parse_type_props(type_str: str) -> List[Dict[str, Any]]:
    """解析 TypeScript 类型定义的 props"""
    props = []
    # 移除空白字符，统一格式
    type_str = ' '.join(type_str.split())
    # 移除外层大括号（如果有）
    type_str = type_str.strip()
    if type_str.startswith('{') and type_str.endswith('}'):
        type_str = type_str[1:-1].strip()
    # 匹配 key?: type 或 key: type 格式（支持数组类型如 [Number, String]）
    for prop_match in re.finditer(r'(\w+)\s*\??:\s*(\[.+?\]|\w+(?:\s*\|\s*\w+)*)', type_str):
        prop_name = prop_match.group(1)
        prop_type = prop_match.group(2).strip()
        # 移除可能的问号后的 required 标记
        required = '?' not in prop_match.group(0).split(':')[0]
        props.append({
            'name': prop_name,
            'type': prop_type,
            'required': required
        })
    return props


def _parse_type_props_with_defaults(type_str: str, defaults_str: str) -> List[Dict[str, Any]]:
    """解析带 withDefaults 的 TypeScript props"""
    props = _parse_type_props(type_str)
    # 解析默认值
    defaults = {}
    for default_match in re.finditer(r'(\w+)\s*:\s*([^,]+)', defaults_str):
        defaults[default_match.group(1)] = default_match.group(2).strip()
    # 合并默认值
    for prop in props:
        if prop['name'] in defaults:
            prop['default'] = defaults[prop['name']]
            prop['required'] = False
    return props


def _strip_comments(text: str) -> str:
    """移除 JavaScript/TypeScript 注释"""
    # 移除单行注释 //
    text = re.sub(r'//[^\n]*', '', text)
    # 移除多行注释 /* ... */
    text = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', text)
    return text


def _parse_object_props(props_str: str) -> List[Dict[str, Any]]:
    """解析对象语法定义的 props（支持 Vue 2 嵌套格式和 Vue 3 简单格式）"""
    props = []
    
    # 先移除注释，避免注释中的内容被错误解析
    props_str = _strip_comments(props_str)
    
    # 处理 Vue 2 嵌套对象格式: title: { type: String, required: true }
    # 需要用括号匹配来提取完整的 { ... } 块
    i = 0
    while i < len(props_str):
        # 查找 prop 名称和冒号
        prop_match = re.match(r'(\w+)\s*:', props_str[i:])
        if prop_match:
            prop_name = prop_match.group(1)
            after_name = props_str[i + prop_match.end():]
            
            # 检查冒号后是否是 {
            if after_name.strip().startswith('{'):
                # 找到嵌套对象的结束括号
                brace_start = props_str.find('{', i + prop_match.end())
                if brace_start != -1:
                    brace_end = _find_matching_brace(props_str, brace_start + 1)
                    if brace_end != -1:
                        prop_def = props_str[brace_start + 1:brace_end]
                        
                        prop_type = None
                        prop_required = True
                        prop_default = None
                        
                        # 提取 type（支持数组类型如 [Number, String]）
                        type_match = re.search(r'type\s*:\s*(\[.+?\]|\w+(?:\s*\|\s*\w+)*)', prop_def)
                        if type_match:
                            prop_type = type_match.group(1).strip()
                        
                        # 提取 required
                        if 'required' in prop_def:
                            required_match = re.search(r'required\s*:\s*([^\s,]+)', prop_def)
                            if required_match and required_match.group(1).strip() in ['false', 'False']:
                                prop_required = False
                        
                        # 提取 default
                        default_match = re.search(r'default\s*:\s*([^\s,]+)', prop_def)
                        if default_match:
                            prop_default = default_match.group(1).strip()
                        
                        props.append({
                            'name': prop_name,
                            'type': prop_type,
                            'required': prop_required,
                            'default': prop_default
                        })
                        
                        i = brace_end + 1
                        continue
            
            # Vue 3 简单格式: title: String
            # 或者 Vue 2 但没有嵌套对象的情况
            # 检查冒号后是否是简单类型（after_name 已经是从 ":" 后开始的）
            simple_match = re.match(r'\s*([^\s,]+)', after_name)
            if simple_match:
                prop_type = simple_match.group(1).strip()
                props.append({
                    'name': prop_name,
                    'type': prop_type,
                    'required': True,
                    'default': None
                })
                i += prop_match.end() + simple_match.end()
                continue
        
        i += 1
    
    return props


def _extract_template_components(template: str) -> List[str]:
    """从模板中提取使用的组件"""
    components = []
    
    # 匹配 <ComponentName 或 <component-name
    for match in re.finditer(r'<([A-Z][a-zA-Z]*|[a-z]+-[a-z]+(?:-[a-z]+)*)', template):
        tag = match.group(1)
        # 跳过 HTML 原生标签
        if tag.lower() not in HTML_TAGS:
            components.append(tag)
    
    return list(set(components))


def _is_component_name(name: str) -> bool:
    """判断是否像是组件名（PascalCase 或包含 -）"""
    if not name:
        return False
    # PascalCase
    if name[0].isupper() and name[0].isalpha():
        return True
    # 包含 - 的命名（如 my-component）
    if '-' in name:
        return True
    return False


def _is_composable_name(name: str) -> bool:
    """判断是否像是 composable 名（use 开头或 camelCase）"""
    if not name:
        return False
    # use 开头
    if name.startswith('use'):
        return True
    # camelCase 但不是 PascalCase
    if name[0].islower() and '_' not in name and name[0].isalpha():
        return True
    return False


HTML_TAGS = {
    'html', 'head', 'body', 'div', 'span', 'p', 'a', 'img', 'ul', 'ol', 'li',
    'table', 'tr', 'td', 'th', 'form', 'input', 'button', 'label', 'select',
    'option', 'textarea', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'footer',
    'nav', 'main', 'section', 'article', 'aside', 'address', 'blockquote',
    'pre', 'code', 'em', 'strong', 'i', 'b', 'u', 's', 'sub', 'sup', 'br', 'hr',
    'dl', 'dt', 'dd', 'figure', 'figcaption', 'details', 'summary', 'video',
    'audio', 'source', 'canvas', 'svg', 'path', 'circle', 'rect', 'line', 'polyline',
    'polygon', 'text', 'g', 'defs', 'use', 'style', 'script', 'template', 'slot'
}


def _parse_with_tree_sitter(content: str, rel_path: str) -> Optional[Dict[str, Any]]:
    """使用 tree-sitter 解析 Vue SFC 文件"""
    try:
        from tree_sitter import Parser
        from tree_sitter_languages import get_language

        # Vue 文件使用 JavaScript 语言解析器（Vue 的 script 部分是 JS）
        lang = get_language('javascript')
        parser = Parser(lang)
        tree = parser.parse(bytes(content, 'utf8'))

        result = {
            'type': 'vue',
            'summary': {
                'component_name': _infer_component_name(rel_path),
                'imports': [],
                'components_used': [],
                'props': [],
                'emits': [],
            },
            'tree_sitter_parsed': True
        }

        # 遍历 AST 提取信息
        _traverse_vue_ast(tree.root_node, bytes(content, 'utf8'), result['summary'])

        return result

    except ImportError:
        # tree-sitter-languages 未安装
        return None
    except Exception as e:
        # 解析失败，返回 None 使用正则回退
        return None


def _traverse_vue_ast(node: Any, content: bytes, summary: Dict) -> None:
    """遍历 Vue AST 节点提取信息"""
    from tree_sitter_helper import extract_node_text, find_children_by_type

    node_type = node.type

    # 提取 import 语句
    if node_type == 'import_statement':
        text = extract_node_text(node, content)
        import_match = re.search(r'import\s+(?:{([^}]+)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]', text)
        if import_match:
            named_imports = import_match.group(1)
            default_import = import_match.group(2)
            namespace_import = import_match.group(3)
            source = import_match.group(4)

            imports_entry = {'source': source, 'items': []}

            if default_import:
                imports_entry['items'].append(default_import)
                if _is_component_name(default_import):
                    summary['components_used'].append(default_import)

            if namespace_import:
                imports_entry['items'].append(f'* as {namespace_import}')

            if named_imports:
                for item in [i.strip() for i in named_imports.split(',')]:
                    if item:
                        imports_entry['items'].append(item)
                        if _is_component_name(item):
                            summary['components_used'].append(item)

            summary['imports'].append(imports_entry)

    # 递归遍历子节点
    for child in node.children:
        _traverse_vue_ast(child, content, summary)
