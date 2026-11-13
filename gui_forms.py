"""图形界面的草稿校验；不依赖窗口，便于验证保存流程。"""
from copy import deepcopy
from datetime import datetime

from categories import CHOICES
from extractor import MISSING
from main import normalize_time_input
from reminders import enrich

TIME_FIELDS = ('deadline', 'start_time', 'end_time')


def prepare_record(original: dict, values: dict) -> dict:
    """在副本上应用人工编辑，保留原文与识别依据。"""
    record = deepcopy(original)
    for key, value in values.items():
        value = (value or '').strip()
        if key in TIME_FIELDS:
            value = normalize_time_input(value) if value and value != MISSING else MISSING
        record[key] = value or MISSING
    if record['task'] == MISSING:
        raise ValueError('请填写事项名称')
    if record['category'] not in CHOICES:
        raise ValueError('请选择有效分类')
    if record['deadline'] != original.get('deadline'):
        for key in ('deadline_boundary', 'deadline_note', 'deadline_inferred',
                    'reference_required', 'weekday_conflict'):
            record.pop(key, None)
    pairs = [('start_time', 'deadline'), ('deadline', 'end_time')]
    for first, last in pairs:
        a, b = record.get(first), record.get(last)
        if a not in (None, '', MISSING) and b not in (None, '', MISSING):
            # 日期粒度不补造时刻，同日先后关系留给用户核对。
            if len(a) == 10 or len(b) == 10:
                invalid = a[:10] > b[:10]
            else:
                invalid = datetime.fromisoformat(a) > datetime.fromisoformat(b)
            if invalid:
                raise ValueError('结束/截止时间不能早于开始时间')
    return enrich(record)
