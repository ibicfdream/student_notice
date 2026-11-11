"""课程表的坐标行列恢复与逐课提取，不跨行补齐缺失单元格。"""
import re
from datetime import date
from statistics import median

HEADER = ('时间', '地点', '主题', '学时', '主讲教师')
ALIASES = {'时间': '时间', '上课时间': '时间', '地点': '地点', '教室': '地点',
           '主题': '主题', '课程名称': '主题', '学时': '学时', '主讲教师': '主讲教师',
           '教师': '主讲教师', '培训类型': '培训类型'}
DATE_CELL = re.compile(r'(?:20\d{2}年)?\d{1,2}月\d{1,2}[日号]?')


def _cell_text(items: list[tuple[str, list]]) -> str:
    if not items:
        return ''
    height = median(max(box[3] - box[1], 1) for _, box in items)
    lines = []
    for text, box in sorted(items, key=lambda item: (item[1][1] + item[1][3]) / 2):
        center = (box[1] + box[3]) / 2
        if not lines or abs(center - lines[-1][0]) > height * 0.6:
            lines.append((center, []))
        lines[-1][1].append((box[0], text.strip()))
    return ''.join(text for _, line in lines for _, text in sorted(line))


def render_course_table(data: dict) -> str | None:
    """仅识别具备课程表表头和坐标的布局，否则返回普通 OCR 流程。"""
    texts, boxes = data.get('rec_texts', []), data.get('rec_boxes', [])
    if not texts or len(texts) != len(boxes):
        return None
    entries = [(text, box) for text, box in zip(texts, boxes) if text.strip()]
    candidates = [(ALIASES[text.strip()], box) for text, box in entries if text.strip() in ALIASES]
    headers = {}
    for name, box in candidates:
        headers.setdefault(name, box)
    if not {'时间', '地点', '主题'} <= headers.keys():
        return None
    header_height = median(box[3] - box[1] for box in headers.values())
    header_y = median((box[1] + box[3]) / 2 for box in headers.values())
    if any(abs((box[1] + box[3]) / 2 - header_y) > header_height for box in headers.values()):
        return None
    columns = sorted(headers, key=lambda name: (headers[name][0] + headers[name][2]) / 2)
    centers = [(headers[name][0] + headers[name][2]) / 2 for name in columns]
    def column(box):
        x = (box[0] + box[2]) / 2
        name = columns[min(range(len(centers)), key=lambda index: abs(centers[index] - x))]
        # 主题列通常远宽于学时列；不能把靠右的标题碎片按表头中心距
        # 分到学时列。学时表头左沿之前仍属于主题的右侧空间。
        if (name == '学时' and '主题' in headers
                and headers['主题'][2] < x < headers['学时'][0]):
            name = '主题'
        return name
    body = [(text, box) for text, box in entries if box[1] > header_y + header_height / 2]
    anchors = sorted([box for text, box in body
                      if column(box) == '时间' and DATE_CELL.fullmatch(re.sub(r'\s+', '', text))],
                     key=lambda box: box[1])
    if not anchors:
        return None
    # 行边界从本行日期上沿稍向上扩展，容纳同一行内不同高度的文字。
    starts = [box[1] - (box[3] - box[1]) * 0.45 for box in anchors]
    title = '\n'.join(text for text, box in entries if box[3] < header_y - header_height / 2)
    result = [title, '\t'.join(HEADER)]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else float('inf')
        cells = {name: [] for name in HEADER}
        for text, box in body:
            y = (box[1] + box[3]) / 2
            name = column(box)
            if start <= y < end and name in cells:
                cells[name].append((text, box))
        result.append('\t'.join(_cell_text(cells[name]).replace('\t', ' ') for name in HEADER))
    return '\n'.join(line for line in result if line)


def extract_course_table(source: str, reference: date) -> list[dict] | None:
    from extractor import MISSING, extract_notice, _event_interval
    lines = source.splitlines()
    header = '\t'.join(HEADER)
    if header not in lines:
        return None
    start = lines.index(header)
    rows = []
    for line in lines[start + 1:]:
        values = line.split('\t')
        if len(values) != len(HEADER):
            raise ValueError('课程表行列不完整，请核对该行，未保存数据')
        stamp, location, topic, hours, teacher = values
        details, end, note = _event_interval(stamp, reference)
        row = extract_notice('事项：' + (topic or MISSING), reference)
        requirements = '；'.join(f'{name}：{value}' for name, value in zip(HEADER, values) if value)
        row.update(details)
        row.update(task=topic or MISSING, end_time=end, time_role='课程开始',
                   end_time_label='课程结束时间', time_kind='range',
                   location=location or MISSING, submit_method='现场上课', method_role='参与方式',
                   category='课程学业', category_candidates=['课程学业'], category_matches={'课程学业': ['课程表']},
                   source_text=source, source_segment=requirements, requirements=requirements,
                   course_hours=hours, teacher=teacher, reference_date=reference.isoformat(),
                   time_expression=stamp)
        warnings = [note] if note else []
        if not topic or not location or not teacher or row['deadline'] == MISSING or end == MISSING:
            warnings.append('本行有单元格缺失或时间不完整，未沿用邻行内容，请核对')
        if not re.search(r'20\d{2}年', stamp):
            warnings.append(f'原表未写年份，按参考年份 {reference.year} 处理，请核对')
        if warnings:
            row['time_note'] = '；'.join(warnings)
        rows.append(row)
    if not rows:
        raise ValueError('课程表没有可提取的课程行，请核对图片')
    return rows
