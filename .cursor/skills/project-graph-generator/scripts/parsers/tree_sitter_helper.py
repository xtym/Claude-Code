"""
tree-sitter 统一辅助模块
提供自动下载语言包和统一的 AST 解析接口
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.request import urlopen, Request
from urllib.error import URLError

# tree-sitter 的官方语言包仓库
TREE_SITTER_REPO = "https://github.com/tree-sitter/tree-sitter"
LANGUAGES_JSON_URL = "https://raw.githubusercontent.com/tree-sitter/tree-sitter/master/cli/src/languages.json"

# 语言包映射：语言名 -> github 仓库名
LANGUAGE_REPOS = {
    "python": "tree-sitter-python",
    "java": "tree-sitter-java",
    "go": "tree-sitter-go",
    "c": "tree-sitter-c",
    "cpp": "tree-sitter-cpp",
    "csharp": "tree-sitter-c-sharp",
    "javascript": "tree-sitter-javascript",
    "typescript": "tree-sitter-typescript",
    "rust": "tree-sitter-rust",
    "ruby": "tree-sitter-ruby",
    "php": "tree-sitter-php",
    "html": "tree-sitter-html",
    "css": "tree-sitter-css",
    "scss": "tree-sitter-scss",
    "json": "tree-sitter-json",
    "yaml": "tree-sitter-yaml",
    "toml": "tree-sitter-toml",
    "sql": "tree-sitter-sql",
    "bash": "tree-sitter-bash",
    "markdown": "tree-sitter-markdown",
}

# 缓存目录
def get_cache_dir() -> Path:
    """获取 tree-sitter 语言包缓存目录"""
    home = Path.home()
    cache_dir = home / ".cache" / "tree-sitter-languages"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class TreeSitterHelper:
    """tree-sitter 统一辅助类"""

    _instances: Dict[str, Any] = {}
    _languages_json: Optional[Dict[str, str]] = None

    def __init__(self, language: str):
        self.language = language
        self.lang_repo = LANGUAGE_REPOS.get(language.lower())
        self.cache_dir = get_cache_dir()
        self.lib_path: Optional[Path] = None

    @classmethod
    def get_language(cls, language: str) -> Any:
        """
        获取指定语言的 tree-sitter Language 对象
        支持自动下载
        """
        if language.lower() not in LANGUAGE_REPOS:
            raise ValueError(f"不支持的语言: {language}")

        if language.lower() in cls._instances:
            return cls._instances[language.lower()]

        instance = cls(language)
        cls._instances[language.lower()] = instance
        return instance

    def _get_local_version(self) -> Optional[str]:
        """获取本地已安装的语言包版本"""
        lang_cache = self.cache_dir / self.lang_repo
        version_file = lang_cache / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return None

    def _download_and_extract(self) -> Path:
        """下载并提取语言包"""
        print(f"正在下载 tree-sitter 语言包: {self.language} ({self.lang_repo})")

        try:
            # 构建 GitHub API URL 获取最新 release
            api_url = f"https://api.github.com/repos/tree-sitter/{self.lang_repo}/releases/latest"
            request = Request(api_url, headers={"User-Agent": "Python"})
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
                version = data.get("tag_name", "").lstrip("v")

            # 下载语言包
            download_url = f"https://github.com/tree-sitter/{self.lang_repo}/archive/refs/tags/v{version}.tar.gz"
            print(f"下载地址: {download_url}")

            # 下载到临时文件
            request = Request(download_url, headers={"User-Agent": "Python"})
            with urlopen(request, timeout=60) as response:
                tar_data = response.read()

            # 解压到临时目录
            import tarfile
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
                tmp.write(tar_data)
                tmp_path = tmp.name

            extract_dir = self.cache_dir / self.lang_repo
            if extract_dir.exists():
                shutil.rmtree(extract_dir)

            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(self.cache_dir)
            os.unlink(tmp_path)

            # 重命名为不带版本号的目录
            extracted_dir = self.cache_dir / f"{self.lang_repo}-{version}"
            if extracted_dir.exists() and extracted_dir != extract_dir:
                shutil.move(str(extracted_dir), str(extract_dir))

            # 保存版本信息
            (extract_dir / "VERSION").write_text(version)

            self.lib_path = extract_dir / "src" / "parser.c"
            print(f"已安装 {self.language} v{version}")
            return extract_dir

        except (URLError, json.JSONDecodeError, tarfile.TarError) as e:
            raise RuntimeError(f"下载 tree-sitter {self.language} 语言包失败: {e}")

    def ensure_installed(self) -> bool:
        """确保语言包已安装"""
        if self.lib_path and self.lib_path.exists():
            return True

        try:
            self._download_and_extract()
            return True
        except Exception as e:
            print(f"警告: {e}")
            return False

    @staticmethod
    def is_available() -> bool:
        """检查 tree-sitter 是否可用"""
        try:
            from tree_sitter_languages import get_language
            return True
        except ImportError:
            return False

    @staticmethod
    def get_language_via_package(language: str) -> Any:
        """
        通过 tree-sitter-languages 包获取 Language 对象
        这是首选方法，更可靠
        """
        if not TreeSitterHelper.is_available():
            raise ImportError("请安装 tree-sitter-languages: pip install tree-sitter-languages")

        from tree_sitter_languages import get_language

        # 映射语言名
        lang_map = {
            "python": "python",
            "java": "java",
            "go": "go",
            "c": "c",
            "cpp": "cpp",
            "csharp": "c_sharp",
            "javascript": "javascript",
            "typescript": "typescript",
            "rust": "rust",
            "ruby": "ruby",
            "php": "php",
            "html": "html",
            "css": "css",
            "json": "json",
            "yaml": "yaml",
            "toml": "toml",
            "sql": "sql",
            "bash": "bash",
        }

        ts_lang = lang_map.get(language.lower(), language.lower())
        return get_language(ts_lang)


def parse_with_tree_sitter(content: str, language: str) -> Optional[Any]:
    """
    使用 tree-sitter 解析代码

    Args:
        content: 代码内容
        language: 语言名 (python, java, go, c, cpp, csharp, javascript, typescript)

    Returns:
        tree_sitter.Tree 对象，失败返回 None
    """
    try:
        from tree_sitter import Parser

        lang = TreeSitterHelper.get_language_via_package(language)
        parser = Parser(lang)
        return parser.parse(bytes(content, "utf8"))
    except ImportError:
        print("警告: tree-sitter-languages 未安装，AST 解析将不可用")
        print("安装命令: pip install tree-sitter-languages")
        return None
    except Exception as e:
        print(f"警告: tree-sitter 解析 {language} 失败: {e}")
        return None


def extract_node_text(node: Any, content: bytes) -> str:
    """从 tree-sitter 节点提取文本"""
    return content[node.start_byte:node.end_byte].decode("utf8")


def get_node_children(node: Any, child_type: str) -> list:
    """获取指定类型的子节点"""
    return [child for child in node.children if child.type == child_type]


def find_children_by_type(node: Any, type_name: str) -> list:
    """递归查找所有指定类型的子节点"""
    result = []
    for child in node.children:
        if child.type == type_name:
            result.append(child)
        result.extend(find_children_by_type(child, type_name))
    return result


# 导出常用函数
__all__ = [
    'TreeSitterHelper',
    'parse_with_tree_sitter',
    'extract_node_text',
    'get_node_children',
    'find_children_by_type',
]