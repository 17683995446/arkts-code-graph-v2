#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 code_graph.db 导出为 JSON，供可视化网站使用。
用法: python export_graph.py [数据库路径]
"""

import sqlite3
import json
import sys
from pathlib import Path

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "code_graph.db"
OUTPUT_PATH = DB_PATH.replace(".db", "_data.json")


def export(db_path: str, output_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    data = {}

    # 文件
    cur.execute("SELECT * FROM files ORDER BY path")
    data["files"] = [dict(r) for r in cur.fetchall()]

    # 类
    cur.execute("SELECT * FROM classes ORDER BY file_path, name")
    data["classes"] = [dict(r) for r in cur.fetchall()]

    # 方法
    cur.execute("SELECT * FROM methods ORDER BY class_name, name")
    data["methods"] = [dict(r) for r in cur.fetchall()]

    # 调用关系
    cur.execute("SELECT * FROM method_calls")
    data["method_calls"] = [dict(r) for r in cur.fetchall()]

    # 组件嵌套
    cur.execute("SELECT * FROM component_nesting")
    data["component_nesting"] = [dict(r) for r in cur.fetchall()]

    # 统计
    stats = {}
    for table in ["files", "classes", "methods", "method_calls", "component_nesting"]:
        cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
        stats[table] = cur.fetchone()["cnt"]

    cur.execute("SELECT COUNT(*) as cnt FROM classes WHERE is_component=1")
    stats["components"] = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) as cnt FROM classes WHERE is_entry=1")
    stats["entries"] = cur.fetchone()["cnt"]
    cur.execute("SELECT SUM(line_count) as cnt FROM files")
    stats["total_lines"] = cur.fetchone()["cnt"] or 0

    data["stats"] = stats

    conn.close()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已导出到: {output_path}")
    print(f"   文件: {stats['files']}  类: {stats['classes']}  方法: {stats['methods']}  调用: {stats['method_calls']}")


if __name__ == "__main__":
    export(DB_PATH, OUTPUT_PATH)
