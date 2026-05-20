# ArkTS Code Knowledge Graph Parser

一个用于解析 ArkTS/HarmonyOS 代码并构建知识图谱的 Python 工具。

## 功能特性

- **代码解析**: 解析 ArkTS 源码，提取类、方法、属性、装饰器等信息
- **调用关系分析**: 自动识别方法调用关系，包括 `this.method()` 和 `Class.method()` 形式
- **组件嵌套识别**: 识别 ArkUI 组件的嵌套关系（Column、Row、Text 等）
- **装饰器支持**: 完整支持 `@Component`、`@Entry`、`@State`、`@Builder` 等 ArkTS 装饰器
- **知识图谱存储**: 使用 SQLite 存储解析结果，支持复杂查询
- **可视化导出**: 支持导出为 JSON 格式，可配合 HTML 查看器可视化

## 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/arkts-code-graph.git
cd arkts-code-graph

# 无需额外依赖，使用 Python 标准库
```

## 快速开始

```python
from arkts_code_graph import ArkTSParser, CodeKnowledgeGraph

# 解析单个文件
parser = ArkTSParser()
result = parser.parse_file('path/to/your.ets')

# 查看解析结果
for cls in result.classes:
    print(f"类: {cls.name}")
    for method in cls.methods:
        print(f"  方法: {method.name} -> {method.return_type}")
        print(f"    调用: {[c[0] for c in method.called_methods]}")

# 构建整个项目的知识图谱
graph = CodeKnowledgeGraph('knowledge.db')
graph.build('path/to/project')
graph.close()
```

## 支持的语法特性

### 类和组件

- 普通 class 声明
- `struct` 组件（ArkTS 特有）
- `extends` 继承
- `implements` 接口实现
- `abstract class` 抽象类
- `declare class` 声明类

### 方法和属性

- 普通方法声明
- `async` 异步方法
- `static` 静态方法
- `public/private/protected` 访问修饰符
- `override` 重写标记
- 抽象方法（无方法体）
- 泛型返回类型（支持跨行）
- Rest 参数 (`...args`)
- 可选参数 (`param?`)

### 装饰器

- `@Component` 组件装饰器
- `@Entry` 入口装饰器
- `@State` 状态装饰器
- `@Prop` 属性装饰器
- `@Link` 双向绑定装饰器
- `@Builder` 构建器装饰器
- `@Watch` 监听装饰器
- `@Provide/@Consume` 跨层传递装饰器
- `@StorageLink/@StorageProp` 存储装饰器

### 特殊语法

- 模板字符串插值（支持深度嵌套）
- 对象字面量返回类型
- 函数类型参数和返回值
- 泛型类型参数

## 测试覆盖

项目经过 13 轮严格测试，覆盖：

1. **基础语法解析** - 类、方法、属性
2. **装饰器处理** - 各种装饰器组合
3. **调用关系提取** - 方法调用链
4. **组件嵌套** - ArkUI 组件树
5. **边界情况** - 特殊字符、Unicode、超长行
6. **错误恢复** - 不完整代码的容错处理
7. **真实项目模式** - 大型组件、复杂状态管理

## 项目结构

```
arkts-code-graph/
├── arkts_code_graph.py      # 主解析器
├── arkts_code_graph_optimized.py  # 优化版本
├── export_graph.py          # 图谱导出工具
├── code_graph_viewer.html   # 可视化查看器
└── README.md               # 项目文档
```

## API 参考

### ArkTSParser

```python
parser = ArkTSParser()
result = parser.parse_file('file.ets')  # 解析单个文件
results = parser.parse_project('project/')  # 解析整个项目
```

### ArkTSFile

```python
result.path          # 文件路径
result.line_count    # 行数
result.classes       # 类列表
```

### ArkTSClass

```python
cls.name             # 类名
cls.extends          # 父类名
cls.implements       # 实现的接口列表
cls.decorators       # 装饰器列表
cls.methods          # 方法列表
cls.properties       # 属性列表
```

### ArkTSMethod

```python
method.name              # 方法名
method.return_type       # 返回类型
method.params            # 参数列表
method.called_methods    # 调用的方法
method.nested_components # 嵌套组件（仅 build 方法）
method.decorators        # 装饰器列表
method.is_abstract       # 是否抽象方法
method.is_static         # 是否静态方法
```

### CodeKnowledgeGraph

```python
graph = CodeKnowledgeGraph('db.sqlite')
graph.build('project/')   # 构建知识图谱
graph.execute_sql(sql)    # 执行 SQL 查询
graph.export_json()       # 导出为 JSON
graph.close()             # 关闭连接
```

## 已修复的 Bug

| 版本 | Bug 描述 |
|------|----------|
| R3 | 模板字符串插值深度污染 |
| R4 | 返回类型 `()` 干扰 |
| R5 | 属性装饰器污染方法列表 |
| R6 | Rest 参数名未清理 `...` 前缀 |
| R7 | 可选参数名未清理 `?` 后缀 |
| R8 | `parse` 方法被错误过滤 |
| R9 | `declare class` 方法无法识别 |
| R10 | 抽象类方法无法识别 |
| R12 | 跨行泛型返回类型无法解析 |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
