"""不依赖第三方库的通知规则提取器。"""
import re
import unicodedata
from datetime import date, datetime, timedelta
from categories import classify
from task_names import EVENT_HINT, brief_subject, concise_task, short_venue, fitness_conditions

MISSING = "未提及"
DATE = re.compile(r"(?<!\d)(?<!\d:)(?:(?P<y>20\d{2})\s*[年/.-]\s*)?(?P<m>\d{1,2})\s*[月/.-]\s*(?P<d>\d{1,2})(?:\s*[日号])?(?!\d)")
CLOCK = re.compile(r"(?P<period>上午|下午|晚上|中午|凌晨)?\s*(?P<h>\d{1,2})\s*(?::\s*(?P<minute>\d{1,2})|[点时](?P<cnminute>\d{1,2})?\s*分?)(?!\d)")
BEFORE_DATE = re.compile(r'^\s*(?:\(\s*(?:周|星期|礼拜)[一二三四五六日天1-7]\s*\)\s*)?(?:之前|前(?!后|往|夕))')
URL = re.compile(r'https?://[^\s，。；;<>（）()“”"‘’]+')


def _time_candidates(text: str, reference: date) -> list[tuple[int, int, str]]:
    semester = re.search(r"(20\d{2})\s*-\s*(20\d{2})\s*-\s*([12])\s*学期", text)
    # 标题中的“2025年挑战杯”可为无年份日期提供上下文；排除完整日期。
    heading = next((line.strip() for line in text.splitlines() if line.strip()), '')
    title_year = re.search(r'(20\d{2})\s*年(?!\s*\d{1,2}\s*月)', heading)
    context_year = int(title_year[1]) if title_year else reference.year
    candidates = []
    for match in DATE.finditer(text):
        # 防止把学年 2024-2025-2 的末尾误当作月日。
        if semester and match.start() < semester.end() and match.end() > semester.start():
            continue
        year = int(match['y']) if match['y'] else (int(semester[2] if semester[3] == '2' else semester[1]) if semester else context_year)
        following = text[match.end():]
        if re.match(r'\s*(?:前后|左右)', following):
            # 模糊预计日期不作为单点截止或精确开始时间。
            continue
        clause = re.split(r"[，。；;\n]", following, maxsplit=1)[0]
        next_date = DATE.search(clause)
        if next_date:
            clause = clause[:next_date.start()]
        clock = CLOCK.search(clause)
        try:
            value = datetime(year, int(match['m']), int(match['d']))
            if clock:
                hour = int(clock['h'])
                if clock['period'] in ('下午', '晚上', '中午') and hour < 12:
                    hour += 12
                if clock['period'] == '凌晨' and hour == 12:
                    hour = 0
                value = value.replace(hour=hour, minute=int(clock['minute'] or clock['cnminute'] or 0))
        except ValueError:
            continue
        before = re.split(r"[，。；;\n]", text[:match.start()])[-1][-16:]
        # 同一句包含多个日期时，只看前一个日期之后的局部标签。
        previous_dates = list(DATE.finditer(text[:match.start()]))
        if previous_dates:
            before = before[-min(len(before), match.start() - previous_dates[-1].end()):] if match.start() > previous_dates[-1].end() else ''
        if re.search(r'发布(?:时间|日期)?|发送(?:时间|日期)?|推送(?:时间|日期)?|更新(?:时间|日期)?|落款|发文(?:时间|日期)?', before):
            continue
        # 以日期前后的局部措辞评分，避免把开始时间误判为截止。
        registration_end = bool(re.search(r'报名(?:时间|日期)[^\n。；;]*?(?:至|到)', before))
        exclusive_date = BEFORE_DATE.match(clause) if not clock else None
        clock_deadline = BEFORE_DATE.match(clause[clock.end():]) if clock else None
        end = bool(clock_deadline or exclusive_date or registration_end or re.search(r"截止|截至|最[迟晚]", before) or re.search(r"截止|截至|结束|之前|前(?:\s*(?:将|把|提交|完成|报送|报名|发送|交至|交到|交给|送交|递交|缴费)|\s*$)", clause))
        start = bool(re.search(r"开始|启动|举行|举办|(?:活动|会议|考试|讲座|报到|面试|集合|上课|比赛)(?:时间|日期)|定于|将于", before + clause))
        # 无事件语义的日期可能只是聊天时间戳或通知落款，不自动填入。
        if end or start:
            if exclusive_date:
                value -= timedelta(days=1)
            candidates.append((2 if end else 1, match.start(), value.strftime('%Y-%m-%d %H:%M') if clock else value.strftime('%Y-%m-%d')))
    return candidates


def extract_time(text: str, reference: date) -> str:
    candidates = _time_candidates(text, reference)
    if candidates:
        return max(candidates, key=lambda x: (x[0], -x[1]))[2]
    return MISSING


def extract_time_details(text: str, reference: date, position: int | None = None) -> dict:
    """保留自然语言时间依据，明确日期前不包含该日；供预览和持久化使用。"""
    candidates = _time_candidates(text, reference)
    if position is not None:
        candidates = [item for item in candidates if item[1] == position]
    details = dict(deadline=MISSING, deadline_expression='', deadline_boundary='unspecified', deadline_note='')
    if not candidates:
        return details
    _, position, deadline = max(candidates, key=lambda item: (item[0], -item[1]))
    match = DATE.match(text, position)
    suffix = BEFORE_DATE.match(text[match.end():]) if len(deadline) == 10 else None
    details['deadline'] = deadline
    if suffix:
        details['deadline_expression'] = text[match.start():match.end() + suffix.end()]
        details['deadline_boundary'] = 'exclusive_date'
        boundary = (date.fromisoformat(deadline) + timedelta(days=1)).isoformat()
        details['deadline_note'] = (f'原文“{details["deadline_expression"]}”按不含 {boundary} 当日处理；'
                                    f'最晚提交日期为 {deadline}，未指定具体时刻。')
    else:
        details['deadline_expression'] = match[0]
    return details


def extract_notice(source: str, reference: date | None = None) -> dict:
    text = unicodedata.normalize('NFKC', source).replace(',', '，')
    flat = re.sub(r'\s+', ' ', text).strip()
    if not flat:
        raise ValueError('通知内容不能为空')
    task = concise_task(text, MISSING)
    methods = []
    for pattern in (
        r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
        URL.pattern,
        r'[\u4e00-\u9fffA-Za-z0-9]{0,16}(?:系统|平台|小程序)',
        r'问卷星|腾讯文档|金山文档|群接龙|群内接龙|纸质(?:版)?|现场提交|电子邮件|邮箱',
    ):
        for item in re.findall(pattern, flat):
            item = re.split(r'登录|登陆|进入|通过|请|同学|在|到', item)[-1]
            if item and item not in methods:
                methods.append(item)
    place = re.search(r'(?:地点|地址)\s*[:：为]?\s*([^，。；;\n]+)', text)
    if not place:
        place = re.search(r'(?:在|到|至)\s*([^，。；;\n]{1,25}?(?:教室|会议室|报告厅|礼堂|体育馆|办公室|[楼馆]\s*\d{2,4}(?:\s*(?:会议室|办公室|教室|室))?))', text)
    record = dict(task=task, deadline=extract_time(text, reference or date.today()),
                submit_method='；'.join(methods) or MISSING,
                location=place[1].strip() if place else short_venue(text) or MISSING, source_text=source)
    record.update(classify(source, task))
    record.update(extract_time_details(text, reference or date.today()))
    subject = brief_subject(text)
    if subject and EVENT_HINT.search(subject) and not re.search(r'提交|上传|报送|报名|缴费|登记', subject):
        record.update(fitness_conditions(text))
        if record['submit_method'] == MISSING and record['location'] != MISSING:
            record.update(submit_method='现场参加', method_role='参与方式')
        first_date = DATE.search(text)
        candidates = _time_candidates(text, reference or date.today())
        if first_date and not any(candidate[0] == 2 for candidate in candidates):
            details, end, note = _event_interval(text[first_date.start():], reference or date.today())
            record.update(details)
            record['time_role'] = '活动开始'
            if end != MISSING:
                record.update(end_time=end, end_time_label='活动结束时间')
            if note:
                record['time_note'] = note
    if re.search(r'维修|报修|保修|检修', text):
        _repair_details(record, text, reference or date.today())
    return record


def _event_interval(event_value: str, reference: date) -> tuple[dict, str, str]:
    """共用的活动开始/结束解析；活动结束不作为提交截止。"""
    details = extract_time_details('活动时间：' + event_value, reference)
    event_start = details['deadline']
    event_end = MISSING
    event_dates = list(DATE.finditer(event_value))
    clocks = list(CLOCK.finditer(event_value))
    if len(event_dates) >= 2 and re.search(r'[-~～—–至到]', event_value[event_dates[0].end():event_dates[-1].start()]):
        end_reference = date(int(event_start[:4]), 1, 1) if event_start != MISSING else reference
        event_end = extract_time('活动时间：' + event_value[event_dates[-1].start():], end_reference)
    elif len(clocks) >= 2 and re.fullmatch(r'\s*[-~～—–至到]\s*', event_value[clocks[0].end():clocks[1].start()]):
        if event_start != MISSING:
            end_clock = clocks[1][0].strip()
            if clocks[0]['period'] and not clocks[1]['period']:
                end_clock = clocks[0]['period'] + end_clock
            event_end = extract_time('活动时间：' + event_start[:10] + ' ' + end_clock, reference)
    note = ''
    if event_end != MISSING and event_start != MISSING and event_end < event_start:
        event_end = MISSING
        note = '活动结束早于开始，可能跨日，请核对结束日期。'
    return details, event_end, note


def _repair_details(record: dict, text: str, reference: date) -> None:
    """维修窗口、每日服务时段和登记/电话渠道，不将窗口误作单点截止。"""
    methods = [] if record['submit_method'] == MISSING else [record['submit_method']]
    registration = re.findall(r'(?:本楼|各楼|本宿舍楼)?(?:宿管(?:阿姨|老师|员)?|宿舍管理员|楼管(?:阿姨|老师)?)(?:处|办公室|值班室)?(?:办理)?登记', text)
    methods.extend(registration)
    hotline_matches = list(re.finditer(r'((?:报修|保修|维修|服务)?热线|(?:报修|保修|维修)电话)\s*[:：]?\s*(?:为\s*)?([0-9][0-9\- ]{3,22}[0-9])?', text))
    for hotline in hotline_matches:
        number = (hotline[2] or '').strip()
        if len(re.sub(r'\D', '', number)) < 5:
            number = ''
        methods.append(hotline[1] + ('：' + number if number else '（号码未提及）'))
    explicit_method = re.search(r'(?:报修|保修|维修)(?:方式|渠道)\s*[:：]\s*([^\n。]+)', text)
    if explicit_method and not registration and not hotline_matches:
        methods.append(explicit_method[1].strip())
    if methods:
        record['submit_method'] = '；'.join(dict.fromkeys(methods))
        record['method_role'] = '报修方式'
    if record['location'] == MISSING:
        service_place = re.search(r'(?:在|到|至)(各宿舍楼|各学生宿舍楼|各栋宿舍楼|学生宿舍楼)(?:值班|进行|开展|提供|接受)', text)
        if service_place:
            record['location'] = service_place[1]
    emergency = re.search(r'紧急[^，。；;\n]{0,30}随时[^，。；;\n]*', text)
    if emergency:
        record['service_note'] = emergency[0]

    labeled = re.search(r'((?:报修|保修|维修|检修|维护|服务|受理)(?:时间|日期|时段|周期))\s*[:：为]?\s*([^\n。；;]+)', text)
    value = labeled[2].strip() if labeled else None
    if value is None:
        # 自由叙述仅接收带日期范围或明确时间段的维修句子。
        value = next((line.strip() for line in re.split(r'[\n。；;]', text)
                      if re.search(r'维修|报修|保修|检修', line) and DATE.search(line)
                      and re.search(r'至|到|[-~～—–]', line)), None)
    if value is None:
        return
    raw_value = value
    # 完整日期范围和同月省略月份写法，如4月1日至5日。
    short_range = re.compile(r'(?P<left>(?:20\d{2}年)?(?P<month>\d{1,2})月\d{1,2}日?)\s*(?P<sep>至|到|[-~～—–])\s*(?P<day>\d{1,2})日(?!\d)')
    value = short_range.sub(lambda match: f"{match['left']}{match['sep']}{match['month']}月{match['day']}日", value)
    daily = re.search(r'(?:每天|每日|每日服务时间|每天服务时间)\s*[:：]?\s*(.+)', value)
    if daily:
        record['service_hours'] = re.split(r'[，。；;\n]', daily[0], maxsplit=1)[0].strip(' ()')
        value = value[:daily.start()].strip(' ，，()')
    dates = list(DATE.finditer(value))
    clocks = list(CLOCK.finditer(value))
    is_range = (len(dates) >= 2 and bool(re.search(r'至|到|[-~～—–]', value[dates[0].end():dates[-1].start()]))) or (len(clocks) >= 2 and bool(re.fullmatch(r'\s*[-~～—–至到]\s*', value[clocks[0].end():clocks[1].start()])))
    if not is_range and not (daily and dates):
        if daily and not dates:
            record['time_note'] = '只有每日服务时段，缺少明确日期，暂不生成日期提醒。'
        return
    heading = next((line.strip() for line in text.splitlines() if line.strip()), '')
    title_year = re.search(r'(20\d{2})\s*年(?!\s*\d{1,2}\s*月)', heading)
    if title_year:
        reference = date(int(title_year[1]), 1, 1)
    details, end, note = _event_interval(value, reference)
    prefix = '报修受理' if labeled and re.search(r'报修|保修|受理', labeled[1]) else '维修'
    record.update(details)
    record.update(time_role=prefix + '开始', end_time=end, end_time_label=prefix + '结束时间',
                  time_range_expression=raw_value, time_note=note)
    if end == MISSING:
        record['time_note'] = note or '时间范围结束日期/时刻无法确定，请核对。'


def _onsite_and_online(source: str, text: str, whole: dict, reference: date) -> list[dict] | None:
    """就业通知中的现场活动、独立网申是两个通道，分别绑定时间和方式。"""
    if not re.search(r'宣讲|招聘|双选|就业', text):
        return None
    labels = list(re.finditer(r'(网申截止时间|网申截止|网申通道|网申地址|网申链接|活动时间|宣讲时间|招聘时间|活动地点|宣讲地点|参与方式|参加方式|面向人群|(?<![\u4e00-\u9fff])时间|(?<![\u4e00-\u9fff])地点)\s*[:：]', text))
    values = {}
    for index, label in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
        lines = text[label.end():end].strip().splitlines()
        values[label[1]] = lines[0].strip(' ，。；;') if lines else ''
    event_value = next((values[key] for key in ('活动时间', '宣讲时间', '招聘时间', '时间') if key in values), None)
    online_keys = ('网申通道', '网申地址', '网申链接', '网申截止时间', '网申截止')
    if event_value is None or not any(key in values for key in online_keys):
        return None
    heading = next((line.strip() for line in text.splitlines() if line.strip()), '')
    title_year = re.search(r'(20\d{2})\s*年(?!\s*\d{1,2}\s*月)', heading)
    # “2025届”仅指毕业届别，不把它当成活动年份。
    if title_year:
        reference = date(int(title_year[1]), 1, 1)
    event_details, event_end, time_note = _event_interval(event_value, reference)
    title = re.sub(r'【[^】]*】|\[[^\]]*\]', '', heading).strip() or whole['task']
    participation = values.get('参与方式') or values.get('参加方式') or MISSING
    onsite = whole.copy()
    onsite.update(event_details)
    onsite.update(task=title + '—现场参加', time_role='活动开始', end_time=event_end,
                  time_note=time_note, submit_method=participation,
                  method_role='参与方式', location=next((values[key] for key in ('活动地点', '宣讲地点', '地点') if values.get(key)), MISSING))
    onsite['source_segment'] = '\n'.join(f'{key}：{value}' for key, value in values.items() if key not in online_keys and key != '面向人群')
    online_segment = '\n'.join(f'{key}：{values[key]}' for key in online_keys if key in values)
    # 显式网申截止标签优先；没有截止语义时保留未提及，不借用活动时间。
    deadline_value = next((values[key] for key in ('网申截止时间', '网申截止') if key in values), None)
    online_details = extract_time_details('截止时间：' + deadline_value if deadline_value is not None else online_segment, reference)
    urls = list(dict.fromkeys(URL.findall(online_segment)))
    online = whole.copy()
    online.update(online_details)
    online.update(task=title + '—网申', time_role='网申截止', method_role='申请方式',
                  submit_method='网申通道：' + '；'.join(urls) if urls else '网申（具体网址未提及）',
                  location=MISSING, source_segment=online_segment)
    return [onsite, online]


def _registration_and_event(source: str, text: str, whole: dict, reference: date) -> list[dict] | None:
    """有明确字段标签时，分别关联报名信息和活动信息。"""
    labels = list(re.finditer(r'(报名截止时间|报名截止|报名时间|报名日期|报名方式|报名地点|活动时间|活动日期|活动地点|招募人数)\s*[:：]', text))
    values = {}
    for index, label in enumerate(labels):
        end = labels[index + 1].start() if index + 1 < len(labels) else len(text)
        # 跨行时下一普通段落不属于当前字段（例如服务时长说明）。
        value = text[label.end():end].strip().splitlines()
        values[label[1]] = value[0].strip(' ，。；;') if value else ''
    registration_value = next((values[key] for key in ('报名截止时间', '报名截止', '报名时间', '报名日期') if key in values), None)
    event_value = next((values[key] for key in ('活动时间', '活动日期') if key in values), None)
    if registration_value is None or event_value is None:
        return None
    heading = next((line.strip() for line in text.splitlines() if line.strip()), '')
    # 与通用时间解析器使用同一年的上下文推断规则。
    year = re.search(r'(20\d{2})\s*年(?!\s*\d{1,2}\s*月)', heading)
    semester = re.search(r'(20\d{2})\s*-\s*(20\d{2})\s*-\s*([12])\s*学期', text)
    if semester:
        reference = date(int(semester[2] if semester[3] == '2' else semester[1]), 1, 1)
    elif year:
        reference = date(int(year[1]), 1, 1)
    registration_dates = list(DATE.finditer(registration_value))
    # 报名区间取末日；首日带年份而末日未写年份时，继承首日年份。
    if registration_dates:
        first_year = registration_dates[0]['y']
        reg_reference = date(int(first_year), 1, 1) if first_year else reference
        reg_deadline = extract_time('截止时间：' + registration_value[registration_dates[-1].start():], reg_reference)
    else:
        reg_deadline = MISSING
    event_details, event_end, time_note = _event_interval(event_value, reference)
    event_start = event_details['deadline']
    title = re.sub(r'【[^】]*】|\[[^\]]*\]', '', heading).strip() or whole['task']
    registration = whole.copy()
    registration.update(task=title if title.endswith('报名') else title + '报名',
                        deadline=reg_deadline, time_role='报名截止',
                        submit_method=values.get('报名方式') or MISSING,
                        location=values.get('报名地点') or MISSING)
    registration.update(extract_time_details('截止时间：' + registration_value[registration_dates[-1].start():], reg_reference)
                        if registration_dates else dict(deadline=MISSING, deadline_expression='', deadline_boundary='unspecified', deadline_note=''))
    if registration['location'] == MISSING:
        onsite = re.search(r'(?:前往|到|在)\s*([^，。；;\n]{1,40}?)(?:现场报名|报名)', registration['submit_method'])
        if onsite:
            registration['location'] = onsite[1].strip()
    registration['source_segment'] = '\n'.join(f'{key}：{value}' for key, value in values.items() if key.startswith('报名'))
    event = whole.copy()
    event_title = re.sub(r'志愿者招募.*$', '', title).strip()
    event.update(task=(event_title + '—志愿服务活动') if '志愿' in text else event_title + '—参加活动',
                 deadline=event_start, end_time=event_end, time_role='活动开始',
                 submit_method=MISSING, location=values.get('活动地点') or MISSING,
                 time_note=time_note)
    event.update(event_details)
    event['source_segment'] = '\n'.join(f'{key}：{value}' for key, value in values.items() if key.startswith('活动'))
    return [registration, event]


def extract_notices(source: str, reference: date | None = None) -> list[dict]:
    """多次独立提交按时间和动作拆分；开始/截止组成的单一流程仍为一项。"""
    reference_explicit = reference is not None
    reference = reference or date.today()
    whole = extract_notice(source, reference)
    text = unicodedata.normalize('NFKC', source).replace(',', '，')
    from stages import extract_stages
    stages = extract_stages(source, text, whole, reference)
    if stages:
        return stages
    from colloquial import extract_colloquial
    colloquial = extract_colloquial(source, text, reference, reference_explicit)
    if colloquial:
        return colloquial
    channels = _onsite_and_online(source, text, whole, reference)
    if channels:
        return channels
    phases = _registration_and_event(source, text, whole, reference)
    if phases:
        return phases
    candidates = _time_candidates(text, reference)
    deadlines = [candidate for candidate in candidates if candidate[0] == 2]
    if len(deadlines) < 2:
        return [whole]
    starts = []
    for index, (_, position, _) in enumerate(deadlines):
        # 只在两个时间点之间找分句边界，保留本条时间前的动作对象。
        previous = deadlines[index - 1][1] if index else 0
        separators = list(re.finditer(r'[，。；;\n]', text[previous:position]))
        starts.append(previous + separators[-1].end() if separators else previous)
    records = []
    for index, (_, position, deadline) in enumerate(deadlines):
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        segment = text[starts[index]:end].strip(' ，。；;\n')
        # 没有分句边界时不硬拆，避免把两个日期强行绑定到同一句动作。
        if starts[index] > position or (index and starts[index] <= deadlines[index - 1][1]):
            return [whole]
        if not re.search(r'提交|发送|交至|交到|交给|送交|递交|报送|报名|缴费|完成', segment):
            return [whole]
        row = extract_notice(segment, reference)
        row.update(extract_time_details(text, reference, position=position))
        # 通知中的多个阶段继承同一通知主题和分类，但方法/地点只来自本段。
        context = '挑战杯院赛' if '挑战杯' in text and '院' in text else '挑战杯' if '挑战杯' in text else whole['task']
        if '纸质' in segment:
            action_name = '纸质材料提交'
        elif re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', segment):
            action_name = '申报书电子版提交' if '申报书' in segment else '电子材料提交'
        elif '报名' in segment:
            action_name = '报名'
        elif '缴费' in segment:
            action_name = '缴费'
        else:
            action_name = re.split(r'[，。；;\n]', segment)[0][:40]
        row['task'] = action_name if action_name in context else f'{context}—{action_name}'
        row['source_text'] = source
        row['source_segment'] = segment
        row['category'] = whole['category']
        row['category_candidates'] = whole['category_candidates']
        row['category_matches'] = whole['category_matches']
        records.append(row)
    return records
