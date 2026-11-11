"""海报中相邻的活动标题、独立日期和邀请地点，不将宣传引语当任务。"""
import re
from datetime import date


def extract_poster_event(source: str, reference: date) -> list[dict] | None:
    from extractor import DATE, CLOCK, MISSING, extract_notice, extract_time_details
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    title_indexes = [index for index, line in enumerate(lines)
                     if re.search(r'(?:文化节|艺术节|科技节|体育节)开幕式', line)]
    if len(title_indexes) != 1:
        return None
    index = title_indexes[0]
    heading = lines[index]
    match = re.search(r'([\u4e00-\u9fff]{0,12}(?:文化节|艺术节|科技节|体育节)开幕式)', heading)
    task = match[1]
    if index + 1 < len(lines) and re.match(r'^暨.{1,20}(?:游园会|活动|演出)$', lines[index + 1]):
        task += lines[index + 1]
    title_year = re.search(r'(20\d{2})年', heading)
    event_reference = date(int(title_year[1]), 1, 1) if title_year else reference
    candidates = []
    for position, line in enumerate(lines):
        # 只用标题邻近的独立日期行，不把标题的“10·25”品牌标识当日期。
        if abs(position - index) > 5:
            continue
        stamp = DATE.match(line)
        if not stamp:
            continue
        suffix = line[stamp.end():].strip()
        if suffix and not re.fullmatch(r'(?:上午|中午|下午|晚上|凌晨)(?:\s*\d{1,2}(?:[:：]\d{2}|[点时](?:\d{1,2}分?)?))?|\d{1,2}(?:[:：]\d{2}|[点时](?:\d{1,2}分?)?)', suffix):
            continue
        if position and re.search(r'发布|推送|更新|落款', lines[position - 1]):
            continue
        candidates.append(line)
    if len(candidates) != 1:
        return None
    expression = candidates[0]
    row = extract_notice('事项：' + task, event_reference)
    row.update(extract_time_details('活动时间：' + expression, event_reference))
    locations = []
    for line in lines[index + 1:]:
        place = re.match(r'^在\s*(.+(?:广场|场馆|礼堂|报告厅|体育馆))(?:等你|等候|举行|举办|集合|见面)?[！!。]*$', line)
        if place:
            locations.append(place[1])
    row.update(task=task, time_role='活动开始', time_kind='event',
               time_expression=expression, location=locations[0] if len(locations) == 1 else MISSING,
               submit_method='现场参加', method_role='参与方式',
               source_text=source, source_segment='\n'.join(lines[max(index - 2, 0):]),
               requirements='\n'.join(lines[index:]), reference_date=event_reference.isoformat())
    period = re.search(r'上午|中午|下午|晚上|凌晨', expression)
    notes = []
    if period and not CLOCK.search(expression):
        notes.append(f'原文时间为“{expression}”，仅明确{period[0]}，未给出具体时刻，不自动补成整点')
    if title_year and not re.match(r'20\d{2}年', expression):
        notes.append(f'日期年份沿用活动标题中的{title_year[1]}年')
    if notes:
        row['time_note'] = '；'.join(notes)
    return [row]
