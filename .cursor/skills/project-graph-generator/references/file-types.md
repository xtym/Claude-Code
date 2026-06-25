# 支持的文件类型和解析规则

## 文件类型识别

基于文件扩展名自动识别文件类型：

| 扩展名 | 类型 | 解析器 | 提取信息 |
|--------|------|--------|----------|
| .php | php | PHP 解析器 | 命名空间、类名、方法、属性、继承关系 |
| .py | python | 通用解析器 | 文件大小、修改时间、哈希 |
| .js | javascript | 通用解析器 | 文件大小、修改时间、哈希 |
| .ts | typescript | 通用解析器 | 文件大小、修改时间、哈希 |
| .java | java | 通用解析器 | 文件大小、修改时间、哈希 |
| .go | go | 通用解析器 | 文件大小、修改时间、哈希 |
| .rs | rust | 通用解析器 | 文件大小、修改时间、哈希 |
| .rb | ruby | 通用解析器 | 文件大小、修改时间、哈希 |
| .json | json | JSON 解析器 | 包名、依赖关系（composer.json/package.json） |
| .yaml | yaml | YAML 解析器 | 键值对配置 |
| .yml | yaml | YAML 解析器 | 键值对配置 |
| .xml | xml | 通用解析器 | 文件大小、修改时间、哈希 |
| .md | markdown | 通用解析器 | 文件大小、修改时间、哈希 |
| .txt | text | 通用解析器 | 文件大小、修改时间、哈希 |
| .env | env | ENV 解析器 | 环境变量键值对 |
| .ini | ini | 通用解析器 | 文件大小、修改时间、哈希 |
| .toml | toml | 通用解析器 | 文件大小、修改时间、哈希 |
| .sql | sql | 通用解析器 | 文件大小、修改时间、哈希 |
| .html | html | 通用解析器 | 文件大小、修改时间、哈希 |
| .css | css | 通用解析器 | 文件大小、修改时间、哈希 |
| .scss | scss | 通用解析器 | 文件大小、修改时间、哈希 |
| .less | less | 通用解析器 | 文件大小、修改时间、哈希 |

## 忽略的目录

以下目录在扫描时会被自动忽略：

- `.git`, `.svn`, `.hg` - 版本控制系统
- `.idea`, `.vscode` - IDE 配置
- `__pycache__` - Python 缓存
- `vendor`, `node_modules`, `bower_components` - 依赖包
- `dist`, `build` - 构建输出
- `runtime`, `storage`, `cache`, `logs`, `temp`, `tmp` - 运行时文件

## 忽略的文件

以下文件在扫描时会被自动忽略：

- `.DS_Store`, `Thumbs.db` - 系统文件
- `.gitignore`, `.gitattributes` - Git 配置
- `.env.local`, `.env.test`, `.env.production` - 环境特定配置

## PHP 解析器详情

PHP 解析器使用正则表达式提取以下信息：

1. **命名空间**：`namespace App\Controller;`
2. **类名**：`class UserController extends BaseController`
3. **方法**：`public function index()`, `protected function validate()`
4. **属性**：`protected $userService;`, `private $validator;`
5. **继承关系**：`extends BaseController`

## JSON 解析器详情

JSON 解析器特别处理以下文件：

- **composer.json**：提取 `name`、`require`、`require-dev` 依赖
- **package.json**：提取 `name`、`dependencies`、`devDependencies`

## ENV 解析器详情

ENV 解析器提取所有非注释的键值对：

```
DB_HOST=localhost
DB_PORT=3306
APP_ENV=development
```

## 变更检测机制

1. **优先使用 Git**：如果项目是 Git 仓库，使用 `git diff --name-status HEAD` 检测变更
2. **回退到哈希对比**：如果不是 Git 仓库，计算每个文件的 MD5 哈希并与上次扫描结果对比