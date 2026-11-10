"""群消息的相对日期、隐含材料和条件动作；缺少发布时间时不编造日期。"""
import re
from datetime import date, timedelta

WEEKDAY = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
RELATIVE_DATE = re.compile(r'(?<!下)(?:今天|明天|后天)(?:\s*\((?:周|星期|礼拜)[一二三四五六日天]\))?|(?<![下(])(?:这|本|下)?(?:周|星期|礼拜)[一二三四五六日天]')


def resolve_day(expression: str, reference: date) -> tuple[date, bool]:
    if expression.startswith(('今天', '明天', '后天')):
        offset = 0 if expression.startswith('今天') else 1 if expression.startswith('明天') else 2
        resolved = reference + timedelta(days=offset)
        annotated = re.search(r'\((?:周|星期|礼拜)([一二三四五六日天])\)', expression)
        return resolved, bool(annotated and WEEKDAY[annotated[1]] != resolved.weekday())
    weekday = WEEKDAY[expression[-1]]
    monday = reference - timedelta(days=reference.weekday())
    return monday + timedelta(days=weekday + (7 if expression.startswith('下') else 0)), False


def normalize_chinese_clock(text: str) -> str:
    digits = {'一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    def number(match):
        raw = match[1]
        if '十' in raw:
            left, right = raw.split('十', 1)
            value = (digits.get(left, 1) * 10) + digits.get(right, 0)
        else:
            value = digits.get(raw, 0)
        return str(value) + match[2]
    return re.sub(r'([一二两三四五六七八九十]{1,3})([点时])', number, text).replace('点半', '点30分')


def extract_colloquial(source: str, text: str, reference: date, reference_explicit: bool) -> list[dict] | None:
    from extractor import CLOCK, MISSING, extract_notice, extract_time_details
    from categories import classify
    from task_names import EVENT_HINT, brief_subject, short_venue, fitness_conditions

    markers = list(RELATIVE_DATE.finditer(text))
    if not markers:
        return None
    starts = []
    for index, marker in enumerate(markers):
        lower = markers[index - 1].end() if index else 0
        separators = list(re.finditer(r'[，。；;！!\n]', text[lower:marker.start()]))
        starts.append(lower + separators[-1].end() if separators else (0 if index == 0 else marker.start()))
    records = []
    material = ''
    anchor_conflict = reference_explicit and any(resolve_day(marker[0], reference)[1] for marker in markers)
    for index, marker in enumerate(markers):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        segment = text[starts[index]:end].strip(' ，。；;\n')
        local = RELATIVE_DATE.search(segment)
        if not local:
            return None
        row = extract_notice(segment, reference)
        row.update(source_text=source, source_segment=segment, requirements=segment)
        subject = brief_subject(segment)
        fitness = bool(re.search(r'体测|补测', segment))
        named_event = subject and EVENT_HINT.search(subject) and not re.search(r'提交|上传|报送|报名|缴费|登记', subject)
        activity = bool(fitness or named_event or re.search(r'分享会|宣讲会|讲座|会议|有个.*活动|参加.*活动', segment))
        if activity:
            event_name = re.search(r'(?:有个|有一场|举行|举办|参加)\s*([^，。；;\n]{1,25}?(?:分享会|宣讲会|讲座|会议|活动))', segment)
            name = event_name[1] if event_name else row['task'] if row['task'] != MISSING else '活动'
            task = subject or ('体测补测' if '体测' in segment and '补测' in segment else '体测' if fitness else '参加' + name)
            row.update(task=task, time_role='活动开始', method_role='参与方式', location=short_venue(segment) or MISSING)
            row['submit_method'] = '群接龙' if re.search(r'群.{0,5}接龙', segment) else MISSING
            if row['submit_method'] == MISSING and row['location'] != MISSING:
                row['submit_method'] = '现场参加'
            row.update(fitness_conditions(segment))
            if re.search(r'想参加|自愿|有兴趣|感兴趣', segment):
                row.update(prerequisite='自愿参加', optional=True)
        elif re.search(r'微信|发我|发给|拍照|纸质|交', segment):
            found = re.search(r'把\s*([^，。；;\n]{1,20}?)(?:拍照|扫描|发我|发给|发送)', segment)
            if found:
                material = found[1].strip()
            paper = bool(re.search(r'纸质|纸版', segment))
            row.update(task=('提交' + (material or '材料') + ('纸质版' if paper else '照片')),
                       time_role='提交截止', method_role='提交方式', location=MISSING)
            if paper:
                row['submit_method'] = '纸质提交'
                location = re.search(r'(?:到|交至|送至)\s*([^，。；;\n]{1,30}?(?:[楼馆]\s*[A-Za-z]?\d{2,4}(?:室)?|办公室|中心))', segment)
                if location:
                    row['location'] = location[1].strip()
                if not found and material:
                    row['material_inferred'] = True
            else:
                row['submit_method'] = '微信发送照片（发给通知发布者）' if '微信' in segment else row['submit_method']
            if material:
                row['submission_group'] = material + '提交'
            if re.search(r'没交的话|还没交|未提交|未交', segment):
                row['prerequisite'] = '前述材料尚未提交'
            consequence = re.search(r'(?:不然|否则)([^，。；;\n]+)', segment)
            if consequence:
                row['consequence'] = consequence[1]
        else:
            row['time_note'] = '已识别相对时间，但动作不明确，请对照原文核对。'

        resolved, conflict = resolve_day(local[0], reference)
        conflict = bool(conflict or anchor_conflict)
        tail = normalize_chinese_clock(segment[local.end():])
        clock = CLOCK.search(tail)
        prefix = segment[:local.start()]
        normalized = prefix + f'{resolved.year}年{resolved.month}月{resolved.day}日' + tail
        label = '活动时间：' if activity else '截止时间：'
        details = extract_time_details(label + normalized[len(prefix):], reference)
        expression_tail = tail[:clock.end()] if clock else ''
        after_clock = tail[clock.end():] if clock else tail
        before = re.match(r'\s*(?:之前|前(?!后))', after_clock)
        if before:
            expression_tail += before[0]
        row.update(details)
        row.update(time_expression=local[0] + expression_tail,
                   relative_date_expression=local[0], reference_date=reference.isoformat() if reference_explicit else MISSING,
                   reference_required=not reference_explicit, weekday_conflict=conflict,
                   time_kind='relative_date')
        notes = []
        if row['task'] == MISSING:
            notes.append('事项主题无法可靠识别，请手动填写，不使用整句代替。')
        if not reference_explicit:
            row.update(deadline=MISSING, deadline_note='', deadline_boundary='relative', time_kind='relative')
            notes.append('尚未指定通知发布时间；请用 --reference-date YYYY-MM-DD 或手动填写具体时间。')
        elif conflict:
            row.update(deadline=MISSING, deadline_note='', deadline_boundary='relative', time_kind='relative')
            notes.append(f'参考日期 {reference.isoformat()} 与通知中的星期标注不一致，所有相对时间需核对，不自动修正。')
        else:
            notes.append(f'相对日期按通知发布时间 {reference.isoformat()} 换算，请核对。')
        if row.get('material_inferred'):
            notes.append('纸质版按前文关联到同一材料，请核对。')
        row['time_note'] = ' '.join(notes)
        row.update(classify(segment, row['task']))
        records.append(row)
    return records
