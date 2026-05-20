#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArkTS → SQLite 代码知识图谱 (DEBUG版本，带日志)
================================================
"""

import os
import re
import sqlite3
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# 调试日志开关
DEBUG = True
LOG_LEVEL = 2  # 0=ERROR, 1=WARN, 2=INFO, 3=DEBUG

def log(level: int, msg: str, *args):
    """打印日志"""
    if DEBUG and level <= LOG_LEVEL:
        prefix = ['ERROR', 'WARN', 'INFO', 'DEBUG'][level]
        print(f"[{prefix}] {msg}", *args, file=sys.stderr)

# ============================================================
# 数据模型
# ============================================================

@dataclass
class ArkTSMethod:
    """方法信息"""
    name: str
    return_type: str = "void"
    params: list = field(default_factory=list)
    called_methods: list = field(default_factory=list)
    nested_components: list = field(default_factory=list)
    decorators: list = field(default_factory=list)

@dataclass
class ArkTSClass:
    """类/组件信息"""
    name: str
    file_path: str
    is_component: bool = False
    is_entry: bool = False
    decorators: list = field(default_factory=list)
    methods: list = field(default_factory=list)
    parent_class: Optional[str] = None

@dataclass
class ArkTSFile:
    """文件信息"""
    path: str
    line_count: int = 0
    classes: list = field(default_factory=list)

# ============================================================
# ArkTS 解析器（DEBUG版本）
# ============================================================

class ArkTSParser:
    """纯 Python 实现的 ArkTS 源码解析器（带调试日志）"""

    RE_DECORATOR = re.compile(r'@(\w+)(?:\s*\(([^)]*)\))?')
    RE_CLASS = re.compile(r'\bclass\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?')
    RE_STRUCT = re.compile(r'\bstruct\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?')
    RE_METHOD = re.compile(r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*([\w<>\[\],\s]+))?')
    RE_METHOD_CALL = re.compile(r'(?:this\.|(\w+)\.)(\w+)\s*\(')
    RE_CHAIN_CALL = re.compile(r'(?:(?:\)|\])\s*\??\.|(\w+)\s*\?\.)\s*(\w+)\s*\(')
    RE_COMPONENT_USAGE = re.compile(r'(?:^|[\s(<,;])([A-Z]\w+)\s*(?:\(|{|>)')
    RE_IMPORT = re.compile(r'import\s+(?:type\s+)?(?:\{([^}]+)\}|(\w+))(?:\s*,\s*(?:\{([^}]+)\}|(\w+)))?\s+from\s+[\'"]([^\'"]+)[\'"]')

    LIFECYCLE_METHODS = {
        'build', 'aboutToAppear', 'aboutToDisappear',
        'onPageShow', 'onPageHide', 'onBackPress',
        'onReady', 'onShow', 'onHide', 'onDestroy',
        'onForeground', 'onBackground', 'onCreate', 'onWindowStageCreate',
    }

    COMMON_COMPONENTS = {
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

    def __init__(self):
        log(2, "ArkTSParser 初始化完成")

    def parse_file(self, file_path: str) -> ArkTSFile:
        """解析单个文件"""
        log(2, f"开始解析文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            log(0, f"读取文件失败: {file_path}, 错误: {e}")
            return ArkTSFile(path=file_path, line_count=0, classes=[])

        line_count = len(content.split('\n'))
        log(3, f"文件行数: {line_count}")

        classes = []
        
        # 预计算非代码区域
        non_code_ranges = self._find_non_code_ranges(content)
        
        # 查找类声明
        for match in self.RE_CLASS.finditer(content):
            # 跳过非代码区域（字符串、注释）中的匹配
            if self._is_in_range(match.start(), non_code_ranges):
                log(3, f"跳过非代码区域的类声明: {match.group(1)} at pos {match.start()}")
                continue
            log(3, f"找到类声明: {match.group(1)} at pos {match.start()}")
            cls = self._parse_class(match, content, file_path)
            if cls:
                classes.append(cls)
                log(2, f"成功解析类: {cls.name}, 方法数: {len(cls.methods)}")

        # 查找 struct 声明
        for match in self.RE_STRUCT.finditer(content):
            # 跳过非代码区域（字符串、注释）中的匹配
            if self._is_in_range(match.start(), non_code_ranges):
                log(3, f"跳过非代码区域的struct声明: {match.group(1)} at pos {match.start()}")
                continue
            log(3, f"找到struct声明: {match.group(1)} at pos {match.start()}")
            cls = self._parse_struct(match, content, file_path)
            if cls:
                classes.append(cls)
                log(2, f"成功解析struct: {cls.name}, 方法数: {len(cls.methods)}")

        log(2, f"文件解析完成: {file_path}, 共 {len(classes)} 个类/组件")
        return ArkTSFile(path=file_path, line_count=line_count, classes=classes)

    def _parse_class(self, match, content: str, file_path: str) -> Optional[ArkTSClass]:
        """解析类"""
        class_name = match.group(1)
        parent_class = match.group(2)
        
        log(3, f"_parse_class: name={class_name}, parent={parent_class}")

        # 查找类体
        class_start = match.end()
        brace_start = content.find('{', class_start)
        if brace_start == -1:
            log(1, f"类 {class_name} 未找到类体开始")
            return None

        class_body = self._extract_block(content, brace_start)
        if not class_body:
            log(1, f"类 {class_name} 无法提取类体")
            return None

        log(3, f"类 {class_name} 体长度: {len(class_body)}")

        # 提取装饰器
        decorators = self._extract_decorators(content, match.start())
        log(3, f"类 {class_name} 装饰器: {decorators}")

        # 提取方法
        methods = self._extract_methods(class_body, class_name)
        log(2, f"类 {class_name} 提取到 {len(methods)} 个方法")

        return ArkTSClass(
            name=class_name,
            file_path=file_path,
            is_component=False,
            is_entry='@Entry' in decorators,
            decorators=decorators,
            methods=methods,
            parent_class=parent_class
        )

    def _parse_struct(self, match, content: str, file_path: str) -> Optional[ArkTSClass]:
        """解析 struct（组件）"""
        struct_name = match.group(1)
        parent_class = match.group(2)
        
        log(3, f"_parse_struct: name={struct_name}, parent={parent_class}")

        # 查找 struct 体
        struct_start = match.end()
        brace_start = content.find('{', struct_start)
        if brace_start == -1:
            log(1, f"struct {struct_name} 未找到体开始")
            return None

        struct_body = self._extract_block(content, brace_start)
        if not struct_body:
            log(1, f"struct {struct_name} 无法提取体")
            return None

        log(3, f"struct {struct_name} 体长度: {len(struct_body)}")

        # 提取装饰器（包括 struct 前的装饰器）
        decorators = self._extract_decorators(content, match.start())
        log(3, f"struct {struct_name} 装饰器: {decorators}")

        # 提取方法
        methods = self._extract_methods(struct_body, struct_name)
        log(2, f"struct {struct_name} 提取到 {len(methods)} 个方法")

        return ArkTSClass(
            name=struct_name,
            file_path=file_path,
            is_component='@Component' in decorators,
            is_entry='@Entry' in decorators,
            decorators=decorators,
            methods=methods,
            parent_class=parent_class
        )

    def _extract_block(self, content: str, start: int) -> str:
        """提取匹配的代码块（从 { 开始到对应的 }）"""
        log(3, f"_extract_block: start={start}")
        
        if start >= len(content) or content[start] != '{':
            log(1, f"_extract_block: 起始位置不是 {{")
            return ""

        depth = 0
        in_string = False
        string_char = None
        in_template_expr = False
        template_expr_depth = 0

        for i in range(start, len(content)):
            ch = content[i]

            # 处理字符串
            if not in_template_expr:
                if ch in ('"', "'") and not in_string:
                    in_string = True
                    string_char = ch
                    continue
                elif ch == string_char and in_string:
                    # 检查是否是转义
                    backslash_count = 0
                    j = i - 1
                    while j >= 0 and content[j] == '\\':
                        backslash_count += 1
                        j -= 1
                    if backslash_count % 2 == 0:  # 非转义
                        in_string = False
                        string_char = None
                    continue

            # 处理模板字符串
            if not in_string:
                if ch == '`' and not in_template_expr:
                    in_template_expr = True
                    continue
                elif ch == '`' and in_template_expr and template_expr_depth == 0:
                    in_template_expr = False
                    continue
                elif ch == '$' and in_template_expr and i + 1 < len(content) and content[i + 1] == '{':
                    template_expr_depth += 1
                    continue
                elif ch == '}' and in_template_expr and template_expr_depth > 0:
                    template_expr_depth -= 1
                    continue

            # 处理大括号
            if not in_string and not in_template_expr:
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        result = content[start:i + 1]
                        log(3, f"_extract_block: 提取完成，长度={len(result)}")
                        return result

        log(1, "_extract_block: 未找到匹配的 }，返回剩余内容")
        return content[start:]

    def _find_non_code_ranges(self, content: str) -> list:
        """查找所有非代码区域（字符串、注释）"""
        log(3, "_find_non_code_ranges: 开始查找")
        ranges = []
        i = 0
        while i < len(content):
            if content[i:i+2] == '//':
                start = i
                end = content.find('\n', i)
                if end == -1:
                    end = len(content)
                ranges.append((start, end))
                i = end
            elif content[i:i+2] == '/*':
                start = i
                end = content.find('*/', i + 2)
                if end == -1:
                    end = len(content)
                else:
                    end += 2
                ranges.append((start, end))
                i = end
            elif content[i] in ('"', "'", '`'):
                start = i
                char = content[i]
                i += 1
                while i < len(content):
                    if content[i] == char:
                        backslash_count = 0
                        j = i - 1
                        while j >= 0 and content[j] == '\\':
                            backslash_count += 1
                            j -= 1
                        if backslash_count % 2 == 0:
                            ranges.append((start, i + 1))
                            i += 1
                            break
                    i += 1
            else:
                i += 1
        log(3, f"_find_non_code_ranges: 找到 {len(ranges)} 个非代码区域")
        return ranges

    def _is_in_range(self, pos: int, ranges: list) -> bool:
        for start, end in ranges:
            if start <= pos < end:
                return True
        return False

    def _extract_decorators(self, content: str, pos: int) -> list:
        """提取装饰器"""
        decorators = []
        lines_before = content[:pos].split('\n')
        for line in reversed(lines_before):
            stripped = line.strip()
            if not stripped or stripped.startswith('//') or stripped.startswith('*'):
                continue
            if stripped.startswith('@'):
                match = self.RE_DECORATOR.match(stripped)
                if match:
                    decorators.append(f"@{match.group(1)}")
            else:
                break
        return list(reversed(decorators))

    def _extract_methods(self, class_body: str, class_name: str) -> list:
        """从类体中提取所有方法"""
        log(3, f"_extract_methods: class={class_name}, body_len={len(class_body)}")
        
        methods = []
        keywords = {
            'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break',
            'continue', 'return', 'new', 'typeof', 'instanceof',
            'in', 'of', 'class', 'extends', 'implements', 'import', 'export',
            'from', 'as', 'try', 'catch', 'finally', 'throw', 'async', 'await',
            'function', 'const', 'let', 'var', 'static', 'private', 'public',
            'protected', 'abstract', 'override', 'super', 'this',
            'true', 'false', 'null', 'undefined', 'void', 'type', 'interface',
            'enum', 'namespace', 'module', 'declare', 'require',
        }
        arkts_ui_components = self.COMMON_COMPONENTS

        non_code_ranges = self._find_non_code_ranges(class_body)

        method_pattern = re.compile(
            r'(?<![.\w])'
            r'((?:(?:public|private|protected|static|async|override|abstract)\s+)*)'
            r'(\w+)'
            r'\s*(?:<[^>]*>)?\s*\('
        )

        all_matches = list(method_pattern.finditer(class_body))
        log(3, f"_extract_methods: 找到 {len(all_matches)} 个潜在方法匹配")
        
        processed_end = 0

        for idx, match in enumerate(all_matches):
            pos = match.start()

            if pos < processed_end:
                log(3, f"  匹配 {idx}: pos={pos} < processed_end={processed_end}, 跳过")
                continue

            if self._is_in_range(pos, non_code_ranges):
                log(3, f"  匹配 {idx}: pos={pos} 在非代码区域, 跳过")
                continue

            modifiers = match.group(1).strip() if match.group(1) else ''
            method_name = match.group(2)

            log(3, f"  匹配 {idx}: name={method_name}, modifiers={modifiers}, pos={pos}")

            if method_name in keywords or method_name in arkts_ui_components:
                log(3, f"    -> 关键字或UI组件, 跳过")
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
                log(3, f"    -> 括号不匹配, 跳过")
                continue

            params_str = class_body[paren_start + 1:paren_end]
            log(3, f"    -> params_str={repr(params_str[:50])}")

            # 提取返回类型
            rest = class_body[paren_end + 1:].lstrip()
            return_type = 'void'
            if rest.startswith(':'):
                type_start = 1
                angle_depth = 0
                for j in range(type_start, len(rest)):
                    ch = rest[j]
                    if ch == '<':
                        angle_depth += 1
                    elif ch == '>':
                        if j > 0 and rest[j - 1] == '=':
                            pass
                        elif angle_depth > 0:
                            angle_depth -= 1
                    elif ch == '{' and angle_depth == 0:
                        return_type = rest[type_start:j].strip() or 'void'
                        break
                    elif ch == ';' and angle_depth == 0:
                        return_type = rest[type_start:j].strip() or 'void'
                        break
                    elif ch == '\n' and angle_depth == 0:
                        remaining_after_nl = rest[j + 1:].lstrip()
                        if remaining_after_nl.startswith('<'):
                            continue
                        return_type = rest[type_start:j].strip() or 'void'
                        break
                    elif angle_depth == 0 and j > type_start:
                        remaining = rest[j:].lstrip()
                        if remaining and (remaining[0] == '}'):
                            return_type = rest[type_start:j].strip() or 'void'
                            break
                        if remaining and re.match(r'(?:(?:public|private|protected|static|async|override|abstract)\s+)?\w+\s*\(', remaining):
                            return_type = rest[type_start:j].strip() or 'void'
                            break
                else:
                    return_type = rest[type_start:].strip() or 'void'

            log(3, f"    -> return_type={repr(return_type[:50])}")

            # 检查是抽象方法还是普通方法
            after_paren = class_body[paren_end + 1:].lstrip()
            after_type = ''
            if after_paren.startswith(':'):
                angle_depth = 0
                k = paren_end + 1
                while k < len(class_body):
                    ch = class_body[k]
                    if ch == '<':
                        angle_depth += 1
                    elif ch == '>':
                        if k > 0 and class_body[k - 1] == '=':
                            pass
                        elif angle_depth > 0:
                            angle_depth -= 1
                    elif ch == '{' and angle_depth == 0:
                        brace_depth = 1
                        bk = k + 1
                        found_close = False
                        while bk < len(class_body) and brace_depth > 0:
                            if class_body[bk] == '{':
                                brace_depth += 1
                            elif class_body[bk] == '}':
                                brace_depth -= 1
                                if brace_depth == 0:
                                    found_close = True
                            bk += 1
                        if found_close and bk < len(class_body):
                            rest_after = class_body[bk:].lstrip()
                            if rest_after.startswith('{'):
                                k = bk
                                continue
                        after_type = '{'
                        break
                    elif ch == ';' and angle_depth == 0:
                        after_type = ';'
                        break
                    elif ch == '\n' and angle_depth == 0:
                        remaining_after_nl = class_body[k + 1:].lstrip()
                        if remaining_after_nl.startswith('<'):
                            k += 1
                            continue
                        after_type = ''
                        break
                    elif angle_depth == 0 and k > paren_end + 1:
                        remaining = class_body[k:].lstrip()
                        if remaining and remaining[0] == '}':
                            after_type = ''
                            break
                        if remaining and re.match(r'(?:(?:public|private|protected|static|async|override|abstract)\s+)?\w+\s*\(', remaining):
                            after_type = ''
                            break
                    k += 1
                else:
                    after_type = ''
            else:
                after_type = after_paren[0] if after_paren else ''

            is_abstract = after_type == ';'
            if not is_abstract and after_type == '':
                if 'abstract' in modifiers:
                    is_abstract = True
                else:
                    rest_after_paren = class_body[paren_end + 1:].lstrip()
                    if rest_after_paren.startswith(':'):
                        colon_idx = rest_after_paren.index(':')
                        after_colon = rest_after_paren[colon_idx + 1:].lstrip()
                        ret_start_in_after = after_colon.find(return_type)
                        if ret_start_in_after >= 0:
                            spaces_before = len(rest_after_paren[colon_idx + 1:]) - len(after_colon)
                            ret_end_abs = colon_idx + 1 + spaces_before + ret_start_in_after + len(return_type)
                            after_ret = rest_after_paren[ret_end_abs:].lstrip()
                            if after_ret and (after_ret[0] == '}' or
                                re.match(r'(?:(?:public|private|protected|static|async|override|abstract)\s+)?\w+\s*\(', after_ret)):
                                is_abstract = True

            has_body = after_type == '{'

            # 提取参数列表
            params = self._parse_params(params_str)
            log(3, f"    -> params={params}")

            # 提取方法体
            method_body = ''
            if has_body:
                try:
                    brace_pos = class_body.index('{', paren_end)
                    method_body = self._extract_block(class_body, brace_pos)
                    processed_end = brace_pos + len(method_body)
                except ValueError:
                    log(1, f"    -> 未找到方法体开始")
                    continue
            elif is_abstract:
                if after_type == ';':
                    semi_pos = class_body.index(';', paren_end)
                    processed_end = semi_pos + 1
                else:
                    rest = class_body[paren_end + 1:].lstrip()
                    if rest.startswith(':'):
                        nl_pos = class_body.find('\n', paren_end + 1)
                        processed_end = nl_pos if nl_pos > 0 else paren_end + 1
                    else:
                        processed_end = paren_end + 1
            else:
                log(3, f"    -> 既不是抽象方法也没有方法体, 跳过")
                continue

            # 提取方法调用
            called_methods = self._extract_method_calls(method_body, class_name)
            log(3, f"    -> called_methods={called_methods}")

            # 提取嵌套组件
            nested_components = []
            if method_name == 'build':
                nested_components = self._extract_nested_components(method_body)
                log(3, f"    -> nested_components={nested_components}")

            # 提取方法装饰器
            decorators = []
            preceding = class_body[:pos]
            lines_before = preceding.split('\n')
            for line in reversed(lines_before):
                stripped = line.strip()
                if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                    continue
                if stripped.startswith('@'):
                    dec_match = self.RE_DECORATOR.match(stripped)
                    if dec_match:
                        after_dec = stripped[dec_match.end():].strip()
                        if not after_dec:
                            decorators.append(dec_match.group(1))
                        else:
                            break
                elif stripped.startswith('export') or stripped.startswith('default'):
                    continue
                else:
                    break

            method = ArkTSMethod(
                name=method_name,
                return_type=return_type,
                params=params,
                called_methods=called_methods,
                nested_components=nested_components,
                decorators=decorators
            )
            methods.append(method)
            log(2, f"  ✓ 成功提取方法: {method_name}")

        log(2, f"_extract_methods: 共提取 {len(methods)} 个方法")
        return methods

    def _parse_params(self, params_str: str) -> list:
        """解析参数列表"""
        log(3, f"_parse_params: input={repr(params_str[:50])}")
        
        params = []
        if not params_str.strip():
            return params

        angle_depth = 0
        bracket_depth = 0
        brace_depth = 0
        square_depth = 0
        current = ''
        
        for ch in params_str:
            if ch == '<':
                angle_depth += 1
                current += ch
            elif ch == '>':
                if angle_depth > 0:
                    angle_depth -= 1
                current += ch
            elif ch == '(':
                bracket_depth += 1
                current += ch
            elif ch == ')':
                if bracket_depth > 0:
                    bracket_depth -= 1
                current += ch
            elif ch == '{':
                brace_depth += 1
                current += ch
            elif ch == '}':
                if brace_depth > 0:
                    brace_depth -= 1
                current += ch
            elif ch == '[':
                square_depth += 1
                current += ch
            elif ch == ']':
                if square_depth > 0:
                    square_depth -= 1
                current += ch
            elif ch == ',' and angle_depth == 0 and bracket_depth == 0 and brace_depth == 0 and square_depth == 0:
                param = current.strip()
                if param:
                    params.append(self._parse_single_param(param))
                current = ''
            else:
                current += ch

        param = current.strip()
        if param:
            params.append(self._parse_single_param(param))

        log(3, f"_parse_params: 输出 {len(params)} 个参数")
        return params

    def _parse_single_param(self, param_str: str) -> dict:
        """解析单个参数"""
        depth = 0
        eq_pos = -1
        for i, ch in enumerate(param_str):
            if ch in '<([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            elif ch == '=' and depth == 0:
                eq_pos = i
                break

        if eq_pos >= 0:
            name_type = param_str[:eq_pos].strip()
        else:
            name_type = param_str

        depth = 0
        colon_pos = -1
        for i, ch in enumerate(name_type):
            if ch in '<([{':
                depth += 1
            elif ch in ')]}':
                depth -= 1
            elif ch == ':' and depth == 0:
                colon_pos = i
                break

        if colon_pos >= 0:
            name = name_type[:colon_pos].strip()
            param_type = name_type[colon_pos + 1:].strip()
        else:
            name = name_type
            param_type = 'any'

        if name.startswith('...'):
            name = name[3:]
        if name.endswith('?'):
            name = name[:-1]

        return {'name': name, 'type': param_type}

    def _extract_method_calls(self, method_body: str, current_class: str) -> list:
        """提取方法调用"""
        log(3, f"_extract_method_calls: body_len={len(method_body)}, class={current_class}")
        
        calls = []
        seen = set()
        non_code_ranges = self._find_non_code_ranges(method_body)

        builtins = {
            'log', 'warn', 'error', 'debug', 'trace',
            'then', 'catch', 'finally', 'toString', 'valueOf',
            'hasOwnProperty', 'forEach', 'map', 'filter', 'reduce',
            'find', 'findIndex', 'some', 'every', 'includes',
            'indexOf', 'lastIndexOf', 'push', 'pop', 'shift', 'unshift',
            'splice', 'slice', 'concat', 'join', 'reverse', 'sort',
            'flat', 'flatMap', 'fill', 'copyWithin', 'entries', 'keys',
            'values', 'length', 'charAt', 'charCodeAt', 'startsWith',
            'endsWith', 'replace', 'replaceAll', 'search', 'match',
            'matchAll', 'split', 'substring', 'substr', 'trim',
            'trimStart', 'trimEnd', 'padStart', 'padEnd', 'repeat',
            'toLowerCase', 'toUpperCase', 'toFixed', 'toPrecision',
            'parseInt', 'parseFloat', 'isNaN', 'isFinite',
            'bind', 'call', 'apply', 'assign', 'defineProperty',
            'getPrototypeOf', 'setPrototypeOf', 'freeze', 'seal',
            'preventExtensions', 'isFrozen', 'isSealed',
            'stringify', 'abs', 'ceil', 'floor', 'round', 'max',
            'min', 'random', 'sqrt', 'pow', 'sign', 'trunc', 'cbrt',
            'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
            'addEventListener', 'removeEventListener', 'dispatchEvent',
            'querySelector', 'querySelectorAll', 'getElementById',
            'getElementsByClassName', 'getElementsByTagName',
            'setAttribute', 'getAttribute', 'removeAttribute',
            'createElement', 'createTextNode', 'appendChild',
            'removeChild', 'insertBefore', 'replaceChild',
            'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
            'requestAnimationFrame', 'cancelAnimationFrame',
            'encodeURI', 'decodeURI', 'encodeURIComponent', 'decodeURIComponent',
            'btoa', 'atob',
        }

        # 第一轮：this.method() 和 ClassName.method()
        for match in self.RE_METHOD_CALL.finditer(method_body):
            if self._is_in_range(match.start(), non_code_ranges):
                continue

            target_class = match.group(1) or current_class
            method_name = match.group(2)

            if method_name in builtins:
                continue

            key = (method_name, target_class)
            if key not in seen:
                seen.add(key)
                calls.append(key)

        # 第二轮：链式调用
        for match in self.RE_CHAIN_CALL.finditer(method_body):
            if self._is_in_range(match.start(), non_code_ranges):
                continue

            opt_target = match.group(1)
            method_name = match.group(2)

            if method_name in builtins:
                continue

            target_class = opt_target or current_class
            key = (method_name, target_class)
            if key not in seen:
                seen.add(key)
                calls.append(key)

        log(3, f"_extract_method_calls: 找到 {len(calls)} 个调用")
        return calls

    def _extract_nested_components(self, build_body: str) -> list:
        """提取嵌套组件"""
        log(3, f"_extract_nested_components: body_len={len(build_body)}")
        
        components = []
        seen = set()
        non_code_ranges = self._find_non_code_ranges(build_body)

        for match in self.RE_COMPONENT_USAGE.finditer(build_body):
            if self._is_in_range(match.start(), non_code_ranges):
                continue

            comp_name = match.group(1)

            if comp_name in self.COMMON_COMPONENTS:
                continue

            ts_keywords = {
                'If', 'ForEach', 'LazyForEach', 'While', 'Switch', 'For',
                'Else', 'ElseIf', 'True', 'False', 'Null', 'Undefined',
                'This', 'Super', 'New', 'Return', 'Type', 'Interface',
                'Enum', 'Class', 'Extends', 'Implements', 'Import',
                'Export', 'Default', 'From', 'As', 'Is', 'KeyOf',
                'Infer', 'Readonly', 'Partial', 'Required', 'Pick',
                'Omit', 'Record', 'Exclude', 'Extract', 'NonNullable',
                'ReturnType', 'InstanceType', 'Parameters', 'ConstructorParameters',
                'Promise', 'Array', 'Object', 'String', 'Number', 'Boolean',
                'Symbol', 'BigInt', 'Function', 'Undefined', 'Null',
                'Void', 'Never', 'Any', 'Unknown', 'Map', 'Set',
                'WeakMap', 'WeakSet', 'Date', 'RegExp', 'Error',
                'Response', 'Request', 'Headers', 'FormData', 'URL',
                'URLSearchParams', 'AbortController', 'AbortSignal',
                'Iterable', 'Iterator', 'AsyncIterable', 'AsyncIterator',
                'Generator', 'AsyncGenerator', 'ArrayBuffer', 'SharedArrayBuffer',
                'DataView', 'Int8Array', 'Uint8Array', 'Uint8ClampedArray',
                'Int16Array', 'Uint16Array', 'Int32Array', 'Uint32Array',
                'Float32Array', 'Float64Array', 'BigInt64Array', 'BigUint64Array',
            }

            if comp_name in ts_keywords:
                continue

            if comp_name not in seen:
                seen.add(comp_name)
                components.append(comp_name)

        log(3, f"_extract_nested_components: 找到 {len(components)} 个组件: {components}")
        return components


class CodeKnowledgeGraph:
    """代码知识图谱"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._init_tables()
        log(2, f"CodeKnowledgeGraph 初始化: {db_path}")

    def _init_tables(self):
        """初始化数据库表"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                is_component BOOLEAN DEFAULT 0,
                is_entry BOOLEAN DEFAULT 0,
                parent_class TEXT,
                UNIQUE(name, file_path)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                return_type TEXT DEFAULT 'void',
                params TEXT,
                decorators TEXT,
                UNIQUE(name, class_name)
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS method_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller TEXT NOT NULL,
                callee TEXT NOT NULL,
                caller_class TEXT NOT NULL,
                callee_class TEXT NOT NULL
            )
        ''')
        
        self.conn.commit()

    def build(self, project_path: str):
        """构建知识图谱"""
        log(2, f"开始构建知识图谱: {project_path}")
        
        parser = ArkTSParser()
        project_path = Path(project_path)
        
        # 收集所有 .ets 和 .ts 文件
        files = []
        for ext in ['.ets', '.ts']:
            files.extend(project_path.rglob(f'*{ext}'))
        
        log(2, f"找到 {len(files)} 个源文件")
        
        # 解析所有文件
        for file_path in files:
            try:
                result = parser.parse_file(str(file_path))
                self._save_file(result)
            except Exception as e:
                log(0, f"解析文件失败: {file_path}, 错误: {e}")
        
        log(2, "知识图谱构建完成")

    def _save_file(self, file_result: ArkTSFile):
        """保存文件解析结果到数据库"""
        for cls in file_result.classes:
            # 保存类
            self.cursor.execute('''
                INSERT OR REPLACE INTO classes (name, file_path, is_component, is_entry, parent_class)
                VALUES (?, ?, ?, ?, ?)
            ''', (cls.name, file_result.path, cls.is_component, cls.is_entry, cls.parent_class))
            
            # 保存方法
            for method in cls.methods:
                params_json = str(method.params)
                decorators_json = str(method.decorators)
                
                self.cursor.execute('''
                    INSERT OR REPLACE INTO methods (name, class_name, return_type, params, decorators)
                    VALUES (?, ?, ?, ?, ?)
                ''', (method.name, cls.name, method.return_type, params_json, decorators_json))
                
                # 保存方法调用
                for callee, callee_class in method.called_methods:
                    self.cursor.execute('''
                        INSERT INTO method_calls (caller, callee, caller_class, callee_class)
                        VALUES (?, ?, ?, ?)
                    ''', (method.name, callee, cls.name, callee_class))
        
        self.conn.commit()

    def execute_sql(self, sql: str) -> list:
        """执行 SQL 查询"""
        self.cursor.execute(sql)
        columns = [desc[0] for desc in self.cursor.description] if self.cursor.description else []
        rows = self.cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def close(self):
        """关闭数据库连接"""
        self.conn.close()
        log(2, "数据库连接已关闭")


# ============================================================
# 主程序入口
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='ArkTS 代码知识图谱解析器 (DEBUG模式)')
    parser.add_argument('project_path', help='ArkTS 项目路径')
    parser.add_argument('-o', '--output', default='code_graph.db', help='输出数据库文件')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细日志输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        LOG_LEVEL = 3
    
    graph = CodeKnowledgeGraph(args.output)
    graph.build(args.project_path)
    graph.close()
    
    print(f"知识图谱已保存到: {args.output}")
