"""JSON 持久化；损坏文件报错，避免覆盖原始数据。单进程使用。"""
import json
import os
import tempfile
from pathlib import Path

FIELDS = ('task', 'deadline', 'submit_method', 'location', 'source_text')


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list) or any(not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in FIELDS) for row in data):
        raise ValueError('待办文件格式错误：应为包含五个字符串字段的对象列表')
    return data


def append(path: Path, notice: dict) -> None:
    records = load(path)
    records.append(notice)
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
