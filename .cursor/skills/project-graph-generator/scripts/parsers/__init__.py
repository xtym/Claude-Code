"""
多语言解析器
"""

from .php_parser import parse_php_file
from .vue_parser import parse_sfc_file
from .js_parser import parse_js_file
from .python_parser import parse_python_file
from .java_parser import parse_java_file
from .go_parser import parse_go_file
from .c_family_parser import parse_c_family_file

__all__ = [
    'parse_php_file',
    'parse_sfc_file',
    'parse_js_file',
    'parse_python_file',
    'parse_java_file',
    'parse_go_file',
    'parse_c_family_file',
]