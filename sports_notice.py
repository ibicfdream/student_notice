"""运动会观看通知按开、闭幕仪式拆分，观赛说明不另建任务。"""
import re
import unicodedata
from datetime import date


def extract_sports_ceremonies(source: str, reference: date) -> list[dict] | None:
    from extractor import DATE, MISSING, extract_notice, extract_time_details
    text = unicodedata.normalize('NFKC', source).replace(',', '，')
    if '运动会' not in text or not re.search(r'观赛|观看', text):
        return None
    matches = list(re.finditer(r'(?:举行|举办)(开幕式|闭幕式)', text))
    if not matches:
        return None
    year = re.search(r'(20\d{2})年[^\n。]{0,20}运动会', text)
    event_reference = date(int(year[1]), 1, 1) if year else reference
    shared = re.search(r'(?<!时间)地点\s*(?:均为|均在|为|在|[:：])\s*([^，。；;\n]+)', text)
    location = shared[1].strip() if shared else MISSING
    viewing = re.search(r'观赛安排\s*[:：]\s*([^。]+)', text)
    rows = []
    lower = 0
    for match in matches:
        dates = list(DATE.finditer(text, lower, match.start()))
        # 没有本场日期时不借用上一仪式的日期。
        if not dates:
            return None
        expression = text[dates[-1].start():match.end()]
        normalized = re.sub(r'(上午|下午|晚上|中午|凌晨)\s*约', r'约\1', expression)
        row = extract_notice('事项：观看运动会' + match[1], event_reference)
        row.update(extract_time_details('活动时间：' + normalized, event_reference))
        row.update(task='观看运动会' + match[1], time_role='活动开始', time_kind='event',
                   submit_method='现场观看', method_role='参与方式', location=location,
                   source_text=source, source_segment=expression, time_expression=expression,
                   category='活动实践', category_candidates=['活动实践'],
                   category_matches={'活动实践': ['运动会']})
        if viewing:
            row['requirements'] = viewing[1].strip()
        if '约' in expression:
            row['time_note'] = '原文为约定时刻，暂按所述时间生成提醒，实际开始时间请核对现场安排。'
        rows.append(row)
        lower = match.end()
    return rows
