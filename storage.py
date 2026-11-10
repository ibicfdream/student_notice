"""JSON 持久化；损坏文件报错，避免覆盖原始数据。单进程使用。"""
import json
import os
import tempfile
from pathlib import Path
from categories import CHOICES, UNCATEGORIZED
from reminders import enrich

FIELDS = ('task', 'deadline', 'submit_method', 'location', 'source_text')


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list) or any(not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in FIELDS) for row in data):
        raise ValueError('待办文件格式错误：应为包含五个字符串字段的对象列表')
    for row in data:
        # 旧版记录只在内存补齐，不擅自重分类或改写原文件。
        row.setdefault('category', UNCATEGORIZED)
        if row['category'] == '未分类':
            row['category'] = UNCATEGORIZED
        if row['category'] not in CHOICES:
            raise ValueError('待办文件分类无效')
        enrich(row)
    return data


def append(path: Path, notice: dict) -> None:
    append_many(path, [notice])


def append_many(path: Path, notices: list[dict]) -> None:
    """一批事项一次原子写入，避免中途退出导致只保存一部分。"""
    records = load(path)
    for notice in notices:
        if notice.get('category', UNCATEGORIZED) not in CHOICES:
            raise ValueError('待办分类无效')
        records.append(enrich(notice.copy()))
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同目录临时文件 + 原子替换，降低写入中断损坏文件的风险。
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(records, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
