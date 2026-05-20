#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArkTS 代码知识图谱构建工具 - 优化版本
针对大文件性能优化
"""

import os
import re
import sqlite3
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ArkTSMethod:
    """ArkTS 方法"""
    name: str
    class_name: str
    return_type: str
    params: List[Dict]
    decorators: List[str]
    called_methods: List[Tuple[str, str, str, str]] = field(default_factory=list)
    nested_components: List[str] = field(default_factory=list)


@dataclass
class ArkTSClass:
    """ArkTS 类/组件"""
    name: str
    file_path: str
    is_component: bool = False
    is_entry: bool = False
    parent_class: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    methods: List[ArkTSMethod] = field(default_factory=list)


@dataclass
class ArkTSFile:
    """ArkTS 文件"""
    path: str
    classes: List[ArkTSClass] = field(default_factory=list)
    imports: List[Dict] = field(default_factory=list)
    line_count: int = 0


class ArkTSParser:
    """ArkTS 代码解析器 - 优化版本"""

    # 正则表达式
    RE_CLASS = re.compile(r'\bclass\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?')
    RE_STRUCT = re.compile(r'\bstruct\s+(\w+)')
    RE_IMPORT = re.compile(r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]')
    RE_METHOD_CALL = re.compile(r'(?:this\.|(\w+)\.)(\w+)\s*\(')
    RE_COMPONENT_USAGE = re.compile(r'\b([A-Z][a-zA-Z0-9]*)\s*\(')

    def __init__(self):
        self.keywords = {
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
            'continue', 'return', 'new', 'typeof', 'instanceof',
            'in', 'of', 'class', 'extends', 'implements', 'import', 'export',
            'from', 'as', 'try', 'catch', 'finally', 'throw', 'async', 'await',
            'function', 'const', 'let', 'var', 'static', 'private', 'public',
            'protected', 'abstract', 'override', 'super', 'this',
            'true', 'false', 'null', 'undefined', 'void', 'type', 'interface',
            'enum', 'namespace', 'module', 'declare', 'require', 'constructor',
        }
        self.arkts_ui_components = {
            'Column', 'Row', 'Stack', 'List', 'Grid', 'Scroll', 'Tabs', 'TabContent',
            'Swiper', 'Text', 'Button', 'Image', 'TextInput', 'TextArea', 'Toggle',
            'Slider', 'Select', 'Dialog', 'Alert', 'ActionSheet', 'LoadingProgress',
            'Progress', 'Gauge', 'QRCode', 'Marquee', 'RichText', 'Span',
            'Container', 'Panel', 'Popup', 'Navigation', 'NavDestination',
            'WebView', 'Video', 'XComponent', 'Canvas', 'If', 'ForEach',
            'LazyForEach', 'ListItem', 'GridItem', 'TabBarItem', 'Gesture',
            'ListItemGroup', 'Search', 'SearchBar', 'Blank', 'Divider', 'Flex',
            'Badge', 'Circle', 'Ellipse', 'Line', 'Path', 'Polygon', 'Polyline',
            'Rect', 'Shape', 'Stepper', 'StepperItem', 'TabsController',
            'TextClock', 'TextPicker', 'TimePicker', 'Web', 'Counter',
            'DataPanel', 'Form', 'GridRow', 'GridCol', 'MenuItem', 'Menu',
            'NavRouter', 'SideBarContainer', 'Radio', 'Rating', 'Checkbox',
        }

    def parse_project(self, project_path: str) -> List[ArkTSFile]:
        """解析整个 ArkTS 项目"""
        files = []
        exclude_dirs = {'node_modules', 'oh_modules', 'build', '.git', '.idea', 'hvigor'}

        for root, dirs, filenames in os.walk(project_path):
            # 排除不需要的目录
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for filename in filenames:
                if filename.endswith(('.ets', '.ts')):
                    file_path = os.path.join(root, filename)
                    arkts_file = self.parse_file(file_path)
                    if arkts_file:
                        files.append(arkts_file)

        return files

    def parse_file(self, file_path: str) -> Optional[ArkTSFile]:
        """解析单个 ArkTS 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except (FileNotFoundError, IOError, PermissionError):
            return None

        if not content.strip():
            return None

        line_count = content.count('\n') + 1

        # 提取导入
        imports = self._extract_imports(content)

        # 提取类
        classes = self._extract_classes(content, file_path)

        return ArkTSFile(
            path=file_path,
            classes=classes,
            imports=imports,
            line_count=line_count
        )

    def _extract_imports(self, content: str) -> List[Dict]:
        """提取导入语句"""
        imports = []
        for match in self.RE_IMPORT.finditer(content):
            source = match.group(1)
            # 提取导入的具体内容
            import_str = match.group(0)
            items = []
            if '{' in import_str:
                items_str = import_str[import_str.index('{') + 1:import_str.index('}')]
                items = [item.strip() for item in items_str.split(',')]
            elif 'import' in import_str and 'from' in import_str:
                # default import
                parts = import_str.split()
                if len(parts) >= 2:
                    items = [parts[1]]

            imports.append({
                'source': source,
                'items': items,
                'full': match.group(0)
            })
        return imports

    def _extract_classes(self, content: str, file_path: str) -> List[ArkTSClass]:
        """提取所有类/struct定义"""
        classes = []

        # 查找 class 定义
        for match in self.RE_CLASS.finditer(content):
            class_name = match.group(1)
            parent_class = match.group(2)

            # 找到类体的开始位置
            class_start = match.end()
            # 跳过泛型参数
            depth = 0
            i = class_start
            while i < len(content):
                ch = content[i]
                if ch == '<':
                    depth += 1
                elif ch == '>':
                    depth -= 1
                elif ch == '{' and depth == 0:
                    real_class_start = i
                    break
                i += 1
            else:
                continue

            class_body = self._extract_block(content, real_class_start)

            # 检查是否是组件
            is_component = self._is_component(content, match.start())
            is_entry = '@Entry' in content[max(0, match.start() - 200):match.start()]

            # 提取装饰器
            decorators = self._extract_decorators(content, match.start())

            # 提取方法
            methods = self._extract_methods_fast(class_body, class_name)

            classes.append(ArkTSClass(
                name=class_name,
                file_path=file_path,
                is_component=is_component,
                is_entry=is_entry,
                parent_class=parent_class,
                decorators=decorators,
                methods=methods
            ))

        # 查找 struct 定义
        for match in self.RE_STRUCT.finditer(content):
            struct_name = match.group(1)

            # 找到 struct 体的开始位置
            struct_start = match.end()
            try:
                brace_pos = content.index('{', struct_start)
            except ValueError:
                continue

            struct_body = self._extract_block(content, brace_pos)

            # 检查是否是组件
            is_component = self._is_component(content, match.start())
            is_entry = '@Entry' in content[max(0, match.start() - 200):match.start()]

            # 提取装饰器
            decorators = self._extract_decorators(content, match.start())

            # 提取方法
            methods = self._extract_methods_fast(struct_body, struct_name)

            classes.append(ArkTSClass(
                name=struct_name,
                file_path=file_path,
                is_component=is_component,
                is_entry=is_entry,
                decorators=decorators,
                methods=methods
            ))

        return classes

    def _is_component(self, content: str, pos: int) -> bool:
        """检查是否是组件（前面有@Component装饰器）"""
        before = content[max(0, pos - 500):pos]
        return '@Component' in before or '@Entry' in before

    def _extract_decorators(self, content: str, pos: int) -> List[str]:
        """提取类/方法前面的装饰器"""
        decorators = []
        before = content[max(0, pos - 500):pos]

        # 查找所有 @装饰器
        for match in re.finditer(r'@(\w+)(?:\([^)]*\))?', before):
            decorators.append(match.group(1))

        return decorators

    def _extract_block(self, content: str, start: int) -> str:
        """从 start 位置提取一个 {} 块的内容"""
        depth = 0
        i = start
        in_string = False
        string_char = None
        in_line_comment = False
        in_block_comment = False

        while i < len(content):
            ch = content[i]

            # 处理注释
            if in_line_comment:
                if ch == '\n':
                    in_line_comment = False
                i += 1
                continue
            if in_block_comment:
                if ch == '*' and i + 1 < len(content) and content[i + 1] == '/':
                    in_block_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if not in_string:
                if ch == '/' and i + 1 < len(content):
                    if content[i + 1] == '/':
                        in_line_comment = True
                        i += 2
                        continue
                    if content[i + 1] == '*':
                        in_block_comment = True
                        i += 2
                        continue

            # 处理字符串
            if in_string:
                if ch == '\\':
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
                i += 1
                continue
            else:
                if ch in ('"', "'", '`'):
                    in_string = True
                    string_char = ch
                    i += 1
                    continue

            # 处理大括号
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return content[start:i]

            i += 1

        return content[start:]

    def _find_non_code_ranges(self, content: str) -> List[Tuple[int, int]]:
        """找出所有字符串和注释的范围"""
        ranges = []
        i = 0
        n = len(content)

        while i < n:
            ch = content[i]

            # 单行注释
            if ch == '/' and i + 1 < n and content[i + 1] == '/':
                start = i
                i += 2
                while i < n and content[i] != '\n':
                    i += 1
                ranges.append((start, i))
                continue

            # 多行注释
            if ch == '/' and i + 1 < n and content[i + 1] == '*':
                start = i
                i += 2
                while i < n - 1 and not (content[i] == '*' and content[i + 1] == '/'):
                    i += 1
                i += 2
                ranges.append((start, i))
                continue

            # 字符串（单引号、双引号）
            if ch in ('"', "'"):
                string_char = ch
                start = i
                i += 1
                while i < n:
                    if content[i] == '\\':
                        i += 2
                        continue
                    if content[i] == string_char:
                        i += 1
                        break
                    i += 1
                ranges.append((start, i))
                continue

            # 模板字符串（反引号），${...} 中的代码不算非代码
            if ch == '`':
                start = i
                i += 1
                while i < n:
                    if content[i] == '\\':
                        i += 2
                        continue
                    if content[i] == '`':
                        i += 1
                        break
                    # ${...} 插值中的代码是可执行代码
                    if content[i] == '$' and i + 1 < n and content[i + 1] == '{':
                        # 先记录模板字符串文字部分
                        ranges.append((start, i))
                        i += 2  # 跳过 ${
                        # 跳过插值内容（括号平衡）
                        brace_depth = 1
                        while i < n and brace_depth > 0:
                            if content[i] == '{':
                                brace_depth += 1
                            elif content[i] == '}':
                                brace_depth -= 1
                            elif content[i] in ('"', "'", '`'):
                                # 跳过插值中的嵌套字符串
                                inner_char = content[i]
                                i += 1
                                while i < n:
                                    if content[i] == '\\':
                                        i += 2
                                        continue
                                    if content[i] == inner_char:
                                        break
                                    i += 1
                            i += 1
                        # 插值结束，继续模板字符串
                        start = i  # 下一部分模板字符串的起始位置
                        continue
                    i += 1
                # 记录最后的模板字符串部分
                if start < i:
                    ranges.append((start, i))
                continue

            i += 1

        return ranges

    def _is_in_range(self, pos: int, ranges: List[Tuple[int, int]]) -> bool:
        """检查位置是否在非代码范围内"""
        for start, end in ranges:
            if start <= pos < end:
                return True
        return False

    def _extract_methods_fast(self, class_body: str, class_name: str) -> List[ArkTSMethod]:
        """从类体中提取所有方法 - 优化版本"""
        methods = []

        # 预计算非代码区域
        non_code_ranges = self._find_non_code_ranges(class_body)

        # 正则匹配所有方法声明位置
        method_pattern = re.compile(
            r'(?<![.\w])'
            r'((?:(?:public|private|protected|static|async|override|abstract)\s+)*)'
            r'(\w+)'
            r'\s*(?:<[^>]*>)?\s*\('
        )

        all_matches = list(method_pattern.finditer(class_body))
        processed_end = 0

        for match in all_matches:
            pos = match.start()

            if pos < processed_end:
                continue

            if self._is_in_range(pos, non_code_ranges):
                continue

            modifiers = match.group(1).strip() if match.group(1) else ''
            method_name = match.group(2)

            if method_name in self.keywords or method_name in self.arkts_ui_components:
                continue

            # 找到参数列表的右括号
            paren_start = match.end() - 1
            paren_depth = 0
            paren_end = paren_start
            for k in range(paren_start, len(class_body)):
                ch = class_body[k]
                if ch == '(':
                    paren_depth += 1
                elif ch == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        paren_end = k
                        break
            if paren_depth != 0:
                continue

            params_str = class_body[paren_start + 1:paren_end]

            # 快速检查：看后面是什么字符
            after_paren = class_body[paren_end + 1:].lstrip()

            # 提取返回类型和判断方法类型
            return_type = 'void'
            is_abstract = False
            has_body = False
            body_start = -1
            body_end = -1

            if after_paren.startswith(':'):
                # 有返回类型，需要跳过
                # 简化处理：找到第一个 { 或 ; 在顶层
                depth = 0
                k = paren_end + 1
                while k < len(class_body):
                    ch = class_body[k]
                    if ch in '<([':
                        depth += 1
                    elif ch in ')]>' and not (ch == '>' and k > 0 and class_body[k-1] == '='):
                        depth -= 1
                    elif depth == 0:
                        if ch == '{':
                            # 检查是否是对象字面量类型
                            # 简化：如果 { 前面是 : 或 =>，可能是返回类型
                            # 否则是方法体
                            prev = class_body[max(0, k-10):k].strip()
                            if prev.endswith('=>') or prev.endswith(':'):
                                # 可能是对象字面量返回类型，需要更复杂的处理
                                # 简化：假设对象字面量类型很少，直接当作方法体
                                pass
                            has_body = True
                            body_start = k
                            break
                        elif ch == ';':
                            is_abstract = True
                            body_end = k
                            break
                    k += 1
            elif after_paren.startswith('{'):
                has_body = True
                body_start = paren_end + 1 + after_paren.index('{')
            elif after_paren.startswith(';'):
                is_abstract = True
                body_end = paren_end + 1 + after_paren.index(';')
            else:
                continue

            # 提取参数
            params = self._parse_params(params_str)

            # 提取方法体
            method_body = ''
            if has_body and body_start >= 0:
                method_body = self._extract_block(class_body, body_start)
                processed_end = body_start + len(method_body)
            elif is_abstract and body_end >= 0:
                processed_end = body_end + 1
            else:
                continue

            # 提取方法调用
            called_methods = self._extract_method_calls(method_body, class_name, non_code_ranges)

            # 提取嵌套组件（如果是 build 方法）
            nested_components = []
            if method_name == 'build':
                nested_components = self._extract_nested_components(method_body, non_code_ranges)

            methods.append(ArkTSMethod(
                name=method_name,
                class_name=class_name,
                return_type=return_type,
                params=params,
                decorators=self._extract_decorators(class_body, pos),
                called_methods=called_methods,
                nested_components=nested_components
            ))

        return methods

    def _parse_params(self, params_str: str) -> List[Dict]:
        """解析参数列表"""
        params = []
        if not params_str.strip():
            return params

        # 简单的参数解析
        depth = 0
        current_param = ''

        for ch in params_str:
            if ch in '<([{':
                depth += 1
                current_param += ch
            elif ch in '>)]}':
                depth -= 1
                current_param += ch
            elif ch == ',' and depth == 0:
                if current_param.strip():
                    param_info = self._parse_single_param(current_param.strip())
                    params.append(param_info)
                current_param = ''
            else:
                current_param += ch

        if current_param.strip():
            param_info = self._parse_single_param(current_param.strip())
            params.append(param_info)

        return params

    def _parse_single_param(self, param_str: str) -> Dict:
        """解析单个参数"""
        # 处理默认值
        if '=' in param_str:
            parts = param_str.split('=', 1)
            name_type = parts[0].strip()
            default_value = parts[1].strip()
        else:
            name_type = param_str
            default_value = None

        # 处理可选标记
        if name_type.endswith('?'):
            name_type = name_type[:-1]
            optional = True
        else:
            optional = False

        # 分离名称和类型
        if ':' in name_type:
            parts = name_type.split(':', 1)
            name = parts[0].strip()
            param_type = parts[1].strip()
        else:
            name = name_type
            param_type = 'any'

        return {
            'name': name,
            'type': param_type,
            'optional': optional,
            'default': default_value
        }

    def _extract_method_calls(self, method_body: str, current_class: str, non_code_ranges: List[Tuple[int, int]]) -> List[Tuple[str, str, str, str]]:
        """从方法体中提取所有方法调用"""
        calls = []
        seen = set()

        for match in self.RE_METHOD_CALL.finditer(method_body):
            if self._is_in_range(match.start(), non_code_ranges):
                continue

            target_class = match.group(1) or current_class
            method_name = match.group(2)

            # 过滤内置方法
            if method_name in {'log', 'warn', 'error', 'then', 'catch', 'forEach', 'map', 'filter'}:
                continue

            key = (current_class, method_name, target_class, method_name)
            if key not in seen:
                seen.add(key)
                calls.append((method_name, target_class, method_name, target_class))

        return calls

    def _extract_nested_components(self, build_body: str, non_code_ranges: List[Tuple[int, int]]) -> List[str]:
        """从 build 方法中提取嵌套的自定义组件"""
        components = []
        seen = set()

        for match in self.RE_COMPONENT_USAGE.finditer(build_body):
            if self._is_in_range(match.start(), non_code_ranges):
                continue

            comp_name = match.group(1)

            if comp_name in self.arkts_ui_components:
                continue

            if comp_name not in seen:
                seen.add(comp_name)
                components.append(comp_name)

        return components


class CodeKnowledgeGraph:
    """代码知识图谱"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                line_count INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classes (
                name TEXT,
                file_path TEXT,
                is_component INTEGER,
                is_entry INTEGER,
                parent_class TEXT,
                decorators TEXT,
                PRIMARY KEY (name, file_path)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS methods (
                name TEXT,
                class_name TEXT,
                file_path TEXT,
                return_type TEXT,
                params TEXT,
                decorators TEXT,
                PRIMARY KEY (name, class_name, file_path)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS method_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller TEXT,
                caller_class TEXT,
                callee TEXT,
                callee_class TEXT,
                file_path TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS component_nesting (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_component TEXT,
                child_component TEXT,
                file_path TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                target TEXT,
                items TEXT
            )
        ''')

        self.conn.commit()

    def build(self, project_path: str):
        """构建知识图谱"""
        parser = ArkTSParser()
        files = parser.parse_project(project_path)

        for arkts_file in files:
            self._insert_file(arkts_file)

        print(f"\n📊 知识图谱构建完成！")
        print(f"   📁 文件数: {len(files)}")
        print(f"   📦 类/组件数: {sum(len(f.classes) for f in files)}")
        print(f"   🔧 方法数: {sum(sum(len(c.methods) for c in f.classes) for f in files)}")
        print(f"   🔗 调用关系数: {sum(sum(sum(len(m.called_methods) for m in c.methods) for c in f.classes) for f in files)}")
        print(f"   💾 数据库已保存到: {self.db_path}")

    def _insert_file(self, arkts_file: ArkTSFile):
        """插入文件数据"""
        cursor = self.conn.cursor()

        # 插入文件
        cursor.execute(
            'INSERT OR REPLACE INTO files (path, line_count) VALUES (?, ?)',
            (arkts_file.path, arkts_file.line_count)
        )

        # 插入导入
        for imp in arkts_file.imports:
            cursor.execute(
                'INSERT INTO imports (source, target, items) VALUES (?, ?, ?)',
                (imp['source'], arkts_file.path, ','.join(imp['items']))
            )

        # 插入类和方法
        for cls in arkts_file.classes:
            cursor.execute(
                '''INSERT OR REPLACE INTO classes
                   (name, file_path, is_component, is_entry, parent_class, decorators)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (cls.name, arkts_file.path, int(cls.is_component), int(cls.is_entry),
                 cls.parent_class or '', ','.join(cls.decorators))
            )

            for method in cls.methods:
                cursor.execute(
                    '''INSERT OR REPLACE INTO methods
                       (name, class_name, file_path, return_type, params, decorators)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (method.name, cls.name, arkts_file.path, method.return_type,
                     str(method.params), ','.join(method.decorators))
                )

                # 插入方法调用
                for caller_method, caller_class, callee_method, callee_class in method.called_methods:
                    cursor.execute(
                        '''INSERT INTO method_calls
                           (caller, caller_class, callee, callee_class, file_path)
                           VALUES (?, ?, ?, ?, ?)''',
                        (method.name, cls.name, callee_method, callee_class, arkts_file.path)
                    )

                # 插入组件嵌套关系
                for child in method.nested_components:
                    cursor.execute(
                        '''INSERT INTO component_nesting
                           (parent_component, child_component, file_path)
                           VALUES (?, ?, ?)''',
                        (cls.name, child, arkts_file.path)
                    )

        self.conn.commit()

    def execute_sql(self, sql: str) -> List[Dict]:
        """执行 SQL 查询"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            return [{'error': str(e)}]

    def get_schema(self) -> Dict:
        """获取数据库 schema"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        cursor = self.conn.cursor()
        stats = {}

        for table in ['files', 'classes', 'methods', 'method_calls', 'component_nesting']:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            stats[table] = cursor.fetchone()[0]

        return stats

    def close(self):
        """关闭数据库连接"""
        self.conn.close()


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法: python arkts_code_graph.py <项目路径> [数据库路径]")
        sys.exit(1)

    project_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else 'code_graph.db'

    graph = CodeKnowledgeGraph(db_path)
    graph.build(project_path)
    graph.close()
