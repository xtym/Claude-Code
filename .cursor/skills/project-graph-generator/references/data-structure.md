# 图谱数据结构

## JSON 结构 (project-graph.json)

```json
{
  "meta": {
    "project_path": "/absolute/path/to/project",
    "generated_at": "2024-01-01T00:00:00",
    "version": "1.0",
    "total_files": 150,
    "total_classes": 45
  },
  "files": {
    "/path/to/file.php": {
      "path": "/absolute/path/to/file.php",
      "relative_path": "src/Controller/UserController.php",
      "size": 2048,
      "mtime": 1234567890.0,
      "hash": "md5_hash_value",
      "type": "php",
      "summary": {
        "namespace": "App\\Controller",
        "class_name": "UserController",
        "methods": ["index", "show", "store", "update", "destroy"],
        "properties": ["userService", "validator"]
      }
    }
  },
  "directories": {
    "src/Controller": ["UserController.php", "AuthController.php"],
    "src/Model": ["User.php", "Post.php"]
  },
  "classes": {
    "App\\Controller\\UserController": {
      "file": "src/Controller/UserController.php",
      "namespace": "App\\Controller",
      "extends": null,
      "methods": ["index", "show", "store", "update", "destroy"],
      "properties": ["userService", "validator"]
    }
  },
  "configs": {
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "APP_ENV": "development",
    "APP_DEBUG": "true"
  },
  "dependencies": {
    "php": ">=7.4",
    "laravel/framework": "^8.0",
    "guzzlehttp/guzzle": "^7.0"
  }
}
```

## 字段说明

### meta（元数据）
| 字段 | 类型 | 说明 |
|------|------|------|
| project_path | string | 项目根目录的绝对路径 |
| generated_at | string | 图谱生成时间（ISO 8601 格式） |
| version | string | 图谱数据结构的版本号 |
| total_files | int | 扫描的文件总数 |
| total_classes | int | 发现的类总数 |

### files（文件信息）
| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 文件的绝对路径（键） |
| relative_path | string | 相对于项目根目录的路径 |
| size | int | 文件大小（字节） |
| mtime | float | 最后修改时间（时间戳） |
| hash | string | 文件内容的 MD5 哈希（用于变更检测） |
| type | string | 文件类型（基于扩展名） |
| summary | object | 特定于文件类型的摘要信息 |

### directories（目录树）
| 字段 | 类型 | 说明 |
|------|------|------|
| [目录路径] | array | 目录下的文件名列表 |

### classes（类信息）
| 字段 | 类型 | 说明 |
|------|------|------|
| file | string | 类所在的文件路径（相对路径） |
| namespace | string | 命名空间 |
| extends | string/null | 父类名称 |
| methods | array | 类中定义的方法名称列表 |
| properties | array | 类中定义的属性名称列表 |

### configs（配置信息）
| 字段 | 类型 | 说明 |
|------|------|------|
| [配置键] | string | 配置值 |

### dependencies（依赖关系）
| 字段 | 类型 | 说明 |
|------|------|------|
| [包名] | string | 版本要求 |