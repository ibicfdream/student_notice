"""通用编号阶段与动作拆分；时间只绑定本动作或明确共享的动作。"""
import re
from datetime import date

SECTION = re.compile(r'^[ \t]*(?:(?:[一二三四五六七八九十]+|\d+)[、.．]|\((?:[一二三四五六七八九十]+|\d+)\))[ \t]*([^\n:：]+)(?:[:：][ \t]*([^\n]*))?', re.MULTILINE)
RELATIVE = re.compile(r'((?:答辩|审核|审批|审查)(?:通过|结束|完成))后\s*([一二三四五六七八九十\d]+)\s*个?(工作日|天|日)内')
ACTION = re.compile(r'上传|提交|补交|送交|发送|报送|填报|组建|选题|核对|修改|领取|转递|交至|交到|交给|参加|登记|办理|完成')


def parallel_materials(stage: str, action: str, previous: dict | None) -> bool:
    """仅推定同句同组的省略对象纸质版；不泛化为所有相邻动作共用期限。"""
    if not previous or previous.get('time_kind') != 'deadline':
        return False
    if not re.search(r'材料|归档|提交|报送', stage):
        return False
    if not re.search(r'上传|电子版', previous['source_segment']):
        return False
    if re.search(r'另行|另外|单独|补交|补充|待通知|随后', action):
        return False
    return bool(re.match(r'^(?:其|相应|对应|同一)?纸质(?:版)?(?:材料)?\s*(?:交至|交到|交给|送至|提交|报送)', action))


def split_actions(sentence: str) -> list[str]:
    """逗号只做候选切分；日期前缀附给下一动作，格式说明附给上一动作。"""
    pieces = re.split(r'[，,]|\+(?=(?:纸质|电子|系统|上传|提交))|(?=同时(?:上传|提交|发送|报送))|以及(?=参加)', sentence)
    actions = []
    pending = ''
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if re.fullmatch(r'完成章节学习后', piece):
            pending += ('，' if pending else '') + piece
            continue
        if ACTION.search(piece):
            actions.append((pending + ('，' if pending else '') + piece).strip())
            pending = ''
        elif re.search(r'\d+月\d+|后\s*[一二三四五六七八九十\d]+\s*个?(?:工作日|天|日)内', piece):
            pending += ('，' if pending else '') + piece
        elif actions:
            actions[-1] += '，' + piece
        else:
            pending += ('，' if pending else '') + piece
    if pending:
        if actions:
            actions[-1] += '，' + pending
        else:
            actions.append(pending)
    return actions


def extract_stages(source: str, text: str, whole: dict, reference: date) -> list[dict] | None:
    # 延迟导入：沿用同一个日期/日期前边界解析器，不重复实现时间规则。
    from extractor import DATE, URL, EMAIL_PERIOD, MISSING, extract_notice, extract_time_details, _event_interval
    from categories import classify
    from task_names import concise_task, content_lines

    # OCR 常把材料编号“1.”识别为“1，”；仅在明确材料清单中放宽，
    # 避免把普通正文中的逗号数字误当成任务阶段。
    checklist_intro = re.search(r'(?:提交|报送|递交|交齐)[^。\n]{0,12}(?:以下|下列|如下)材料[^\n]*\n', text)
    section_pattern = SECTION
    if checklist_intro:
        section_pattern = re.compile(SECTION.pattern.replace('[、.．]', '[、.．，,]'), re.MULTILINE)
    headings = list(section_pattern.finditer(text))
    if len(headings) < 2:
        return None
    title = text[:headings[0].start()].strip()
    # 编号可以列材料，也可以列阶段。先识别清单，避免把末项后的说明
    # 当成独立任务，丢失清单前统一给出的截止时间和提交对象。
    material_intro = re.search(r'(?:提交|报送|递交|交齐)[^。\n]{0,12}(?:以下|下列|如下)材料', title)
    material_list = material_intro and all(
        not DATE.search(heading[1]) and not ACTION.search(heading[1])
        and not heading[2]
        for heading in headings
    )
    if material_list:
        row = whole.copy()
        row.pop('stage', None)
        # 从清单引导句之后保留全文，第一项的编号完全损坏也不能静默丢弃。
        requirements_start = checklist_intro.end() if checklist_intro else headings[0].start()
        row['requirements'] = text[requirements_start:].strip()
        if checklist_intro and (requirements_start < headings[0].start()
                               or re.search(r'^\s*\d+[，,]', row['requirements'], re.MULTILINE)):
            row['time_note'] = '材料清单编号可能存在OCR误识别；已保留完整材料要求，请核对文字和符号。'
        row['task'] = concise_task(title, MISSING)
        recipient = re.search(r'(?:提交|报送|递交)[^。\n:：]{0,30}?(?:至|给|交到)\s*([^。\n:：，]+)', title)
        if recipient:
            paper = bool(re.search(r'打印|纸质|复印件', text))
            row['submit_method'] = ('纸质材料交' if paper else '材料交') + recipient[1].strip()
        return [row]
    notice_subject = concise_task(title, MISSING)
    clean_title = '\n'.join(content_lines(title))
    year = re.search(r'(20\d{2})\s*年(?!\s*\d{1,2}\s*月)', title)
    if year:
        reference = date(int(year[1]), 1, 1)
    classification = classify(text, clean_title)
    shared_urls = list(dict.fromkeys(URL.findall(text)))
    records = []

    def base(stage: str, segment: str) -> dict:
        row = extract_notice(segment, reference)
        row.update(source_text=source, source_segment=segment, stage=stage,
                   requirements=segment.strip(), notice_subject=notice_subject)
        row.update(classification)
        fixes = [match for match in EMAIL_PERIOD.finditer(source) if match[1] in row['submit_method']]
        if fixes:
            row['extraction_note'] = '；'.join(
                f'邮箱末尾 o 疑似句号：{match[0]} 暂按 {match[1]} 提取，请对照原图核对'
                for match in fixes)
        return row

    def set_relative(row: dict, relative) -> None:
        row.update(deadline=MISSING, deadline_boundary='relative', deadline_note='',
                   time_kind='relative', time_role='条件期限', time_expression=relative[0],
                   depends_on_event=relative[1], prerequisite=relative[1],
                   relative_offset={'value': int(relative[2]) if relative[2].isdigit() else relative[2],
                                    'unit': relative[3], 'relation': 'within_after'},
                   time_note='需确认实际触发日期；工作日需核对学校日历，暂不计算具体截止。')

    for index, heading in enumerate(headings):
        stage = heading[1].strip(' :：')
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = ((heading[2] or '') + text[heading.end():end]).strip()
        # 阶段标题已确定范围；段内单次换行只是排版，可能截断月份、
        # 系统名或条件句。句末标点和空段落仍作为边界，动作由标点拆分。
        body = re.sub(r'(?<=[^。；;！!？?\r\n])[ \t]*\r?\n[ \t]*(?![ \t]*\r?\n)', '', body)
        # OCR 排版换行可能落在“上\n传”等动作词中间；只接合已知词，
        # 不把所有独立行合并，以免混用不同动作的期限。
        for word in ACTION.pattern.split('|') + ['同时']:
            wrapped_word = r'[ \t]*\r?\n[ \t]*'.join(map(re.escape, word))
            body = re.sub(wrapped_word, word, body)
        body = re.sub(r'[ \t]*\r?\n[ \t]*(?=同时\s*(?:上传|提交|发送|报送))', '', body)
        body = re.sub(r'同时[ \t]*\r?\n[ \t]*(?=上传|提交|发送|报送)', '同时', body)
        heading_time = extract_time_details('截止时间：' + stage, reference) if DATE.match(stage) else None
        dated_heading = bool(heading_time and heading_time['deadline'] != MISSING)
        if dated_heading:
            # “1. 3月30日前：...”是带时间的编号安排，不是名为日期的阶段。
            body = stage + '，' + body
            if re.search(r'组建|选题|填报', body):
                stage = '组队选题与填报'
            elif '初稿' in body:
                stage = '初稿审核'
            elif '终稿' in body:
                stage = '终稿提交'
            else:
                stage = f'阶段{index + 1}'
        name_prefix = notice_subject if dated_heading and notice_subject != MISSING else stage
        stage_urls = list(dict.fromkeys(URL.findall(body)))
        if dated_heading and not stage_urls:
            stage_urls = shared_urls
        common_match = re.search(r'(?:统一截止时间|统一提交期限|统一办理期限)\s*[:：为]?\s*([^。；;\n]+)', body)
        common_time = extract_time_details('截止时间：' + common_match[1], reference) if common_match else heading_time
        section_rows = []
        sentences = [part.strip(' 。；;\n') for part in re.split(r'[。；;\n]+', body) if part.strip()]
        for sentence in sentences:
            # “材料包括……”描述前一提交事项的组成，不是另一次提交。
            composition = re.match(r'^(?:需(?:要)?|须)?(?:提交|上传|报送)的材料(?:包括|包含|为)[:：]?\s*(.+)$', sentence)
            if (composition and section_rows
                    and re.search(r'上传|提交|报送', section_rows[-1]['source_segment'])
                    and not DATE.search(composition[1])
                    and not ACTION.search(composition[1])
                    and not re.search(r'另行|另外|单独|分别', composition[1])):
                target = section_rows[-1]
                target['requirements'] += '。' + sentence
                target['source_segment'] += '。' + sentence
                continue
            dates = list(DATE.finditer(sentence))
            fuzzy = next((match for match in dates if re.match(r'\s*(?:前后|左右)', sentence[match.end():])), None)
            if fuzzy and re.search(r'结果|公布|发布', sentence):
                suffix = re.match(r'\s*(?:前后|左右)', sentence[fuzzy.end():])
                row = base(stage, sentence)
                row.update(task=name_prefix + '—关注结果公布', deadline=MISSING,
                           submit_method=MISSING, location=MISSING, time_kind='approximate',
                           time_role='预计公布', time_expression=sentence[fuzzy.start():fuzzy.end() + suffix.end()],
                           deadline_boundary='approximate', deadline_note='',
                           time_note='预计日期前后不是确定截止日期；待实际公布后核对。')
                section_rows.append(row)
                continue
            relative = RELATIVE.search(sentence)
            actions = split_actions(sentence)
            previous_row = None
            for action in actions:
                action = action.strip(' ，,')
                if not ACTION.search(action):
                    continue
                if (previous_row and re.search(r'上传|提交|报送', previous_row['source_segment'])
                        and re.match(r'^(?:经|经过|经由).*审核通过后(?:方可|才可|才能)参加', action)
                        and not DATE.search(action)):
                    previous_row['requirements'] += '，' + action
                    previous_row['source_segment'] += '，' + action
                    continue
                row = base(stage, action)
                platforms = re.findall(r'(?:登录|登陆|进入|至|到)\s*([\u4e00-\u9fffA-Za-z0-9]{1,24}(?:系统|平台))', action)
                row['submit_method'] = '；'.join(dict.fromkeys(platforms)) or row['submit_method']
                if re.search(r'系统|填报', action) and not re.search(r'纸质|纸版', action):
                    if len(stage_urls) == 1 and not platforms:
                        row['submit_method'] = '系统：' + stage_urls[0]
                address = re.search(r'(?:至|交到|到|前往|送至|送交)\s*([^，。；;]*?(?:(?:中心|办公室|学工办|教务处)(?:\s*\([^)]*\))?|[楼馆]\s*[A-Za-z]?\d{2,4}(?:室)?))', action)
                row['location'] = address[1].strip() if address else MISSING
                if '线上理论学习' in stage and '自测' in action:
                    row['task'] = name_prefix + '—完成章节自测'
                elif '线上理论学习' in stage and '综合测试' in action:
                    row['task'] = name_prefix + '—参加综合测试'
                elif '线上理论学习' in stage and '学习心得' in action:
                    row['task'] = name_prefix + '—提交学习心得'
                elif '线上理论学习' in stage and '课程' in action and '完成' in action:
                    row['task'] = name_prefix + '—完成线上课程'
                elif '个人自学' in stage and re.search(r'PPT', action, re.I):
                    row['task'] = name_prefix + '—制作并发送微党课PPT'
                elif '组建' in action or '选题' in action:
                    row.update(task=name_prefix + '—组建团队与选题', submit_method=MISSING)
                elif '填报' in action:
                    row['task'] = name_prefix + '—系统填报'
                elif '初稿' in action and re.search(r'提交|审核', action):
                    row.update(task=name_prefix + '—提交申报书初稿审核',
                               submit_method='交指导老师审核' if '指导老师' in action else row['submit_method'])
                elif re.search(r'纸质|纸版', action):
                    row.update(task=name_prefix + ('—提交纸质论文' if '论文' in body else '—提交纸质材料'),
                               submit_method='纸质提交', method_role='提交方式')
                elif '终稿' in action and '系统' in action:
                    row['task'] = name_prefix + '—系统终稿提交'
                elif '上传' in action:
                    name = '上传主题实践活动报告' if '主题实践活动报告' in action else '上传中期检查材料' if '中期检查材料' in action else '上传终稿PDF' if '终稿' in action else '上传电子版论文' if '论文' in body else '上传去向证明材料' if '去向' in body else '上传材料'
                    row['task'] = name_prefix + '—' + name
                elif '核对' in action:
                    row['task'] = name_prefix + '—核对个人信息'
                elif '修改' in action:
                    row.update(task=name_prefix + '—现场修改信息', submit_method='现场修改')
                elif '领取' in action:
                    row.update(task=name_prefix + ('—领取调档函' if '调档函' in action else '—领取材料'), submit_method='现场领取')
                elif '转递' in action:
                    row.update(task=name_prefix + '—办理档案转递', submit_method='集中办理档案转递')
                elif '参加' in action and '答辩' in action:
                    row.update(task=name_prefix + '—参加答辩', submit_method='参加答辩', method_role='参与方式')
                else:
                    row['task'] = name_prefix + '—办理事项'
                if '线上理论学习' in stage and row['submit_method'] == MISSING and len(stage_urls) == 1:
                    row['submit_method'] = '学习平台：' + stage_urls[0]
                action_dates = list(DATE.finditer(action))
                date_range = len(action_dates) >= 2 and bool(re.fullmatch(r'\s*(?:\([^)]*\)\s*)?[-~～—–至到]\s*', action[action_dates[0].end():action_dates[1].start()]))
                if date_range:
                    first_date = action_dates[0]
                    details, event_end, note = _event_interval(action[first_date.start():] if first_date else action, reference)
                    row.update(details)
                    role = '答辩' if '参加' in action and '答辩' in action else '核对' if '核对' in action else '转递' if '转递' in action else '办理'
                    row.update(time_kind='range', time_role=role + '开始', end_time=event_end,
                               end_time_label=role + '结束日期', time_range_expression=action,
                               time_note=note or '日期范围不代表具体预约时刻，请核对办理安排。')
                    if '另行通知' in action:
                        row['time_note'] = '仅给出日期范围；具体时间和地点待另行通知。'
                else:
                    row['time_kind'] = 'deadline'
                    if relative and row['deadline'] == MISSING:
                        set_relative(row, relative)
                    elif row['deadline'] == MISSING and common_time and common_time['deadline'] != MISSING:
                        row.update(common_time)
                        row['time_binding'] = 'stage_heading' if dated_heading and not common_match else 'stage_explicit_shared'
                        row['time_note'] = '使用本编号安排的共同期限，请核对。' if dated_heading and not common_match else '使用本阶段明确写出的统一期限，请核对。'
                    elif row['deadline'] == MISSING and action.startswith('同时') and previous_row and previous_row.get('time_kind') == 'deadline' and previous_row['deadline'] != MISSING:
                        for key in ('deadline', 'deadline_expression', 'deadline_boundary', 'deadline_note', 'time_role'):
                            if key in previous_row:
                                row[key] = previous_row[key]
                        row['time_binding'] = 'shared_explicit'
                        row['time_note'] = '依据“同时”共享上一动作的期限，请核对。'
                    elif row['deadline'] == MISSING and parallel_materials(stage, action, previous_row) and previous_row['deadline'] != MISSING:
                        for key in ('deadline', 'deadline_expression', 'deadline_boundary', 'deadline_note', 'time_role'):
                            if key in previous_row:
                                row[key] = previous_row[key]
                        group = previous_row['task'].replace('—上传', '—')
                        previous_row['submission_group'] = group
                        row.update(time_binding='parallel_material_inferred', deadline_inferred=True,
                                   deadline_source=previous_row['source_segment'], submission_group=group,
                                   time_note=f"同阶段同句的电子/纸质材料并列提交，推定共用 {row['deadline']}；纸质期限并非独立明示，请核对。")
                    elif row['deadline'] == MISSING:
                        row['time_note'] = '本动作未单独说明时间，不自动套用其它动作的期限。'
                if '导师审核通过' in action:
                    row['prerequisite'] = '导师审核通过'
                elif re.search(r'通过盲审|盲审通过', action):
                    row['prerequisite'] = '通过盲审'
                elif '有误者' in action:
                    row['prerequisite'] = '个人信息有误'
                elif '需调档函' in action:
                    row['prerequisite'] = '需要调档函'
                row.setdefault('time_binding', 'own_action' if row['deadline'] != MISSING else 'unresolved')
                if re.search(r'档案|调档函', row['task']):
                    row.update(classify(source, row['task']))
                section_rows.append(row)
                previous_row = row
        # 未支持的章节也保留，避免只展示已识别动作而漏掉整个阶段。
        if not section_rows and body:
            row = base(stage, body)
            row['task'] = name_prefix + '—办理事项' if dated_heading else stage
            row['time_note'] = '本阶段动作未能可靠拆分，请对照原文核对。'
            section_rows.append(row)
        # 环节内的整体完成要求可覆盖多个动作；不跨章节、不覆盖独立期限。
        collective = re.search(
            r'(?:所有课程|全部课程|本环节(?:所有|全部)?(?:任务|事项)?|本阶段(?:所有|全部)?(?:任务|事项)?)'
            r'[^。；;\n]{0,60}?(?:完成|截止)', body)
        collective_time = extract_time_details(collective[0], reference) if collective else None
        collective_source = collective[0] if collective else ''
        if not collective_time or collective_time['deadline'] == MISSING:
            explicit_rows = [row for row in section_rows
                             if row.get('time_kind') == 'deadline' and row['deadline'] != MISSING]
            if len({row['deadline'] for row in explicit_rows}) == 1:
                anchor = explicit_rows[0]
                collective_time = {key: anchor[key] for key in
                                   ('deadline', 'deadline_expression', 'deadline_boundary', 'deadline_note')
                                   if key in anchor}
                collective_source = anchor['source_segment']
        if collective_time and collective_time['deadline'] != MISSING:
            for row in section_rows:
                if (row['deadline'] == MISSING and row.get('time_kind') == 'deadline'
                        and not re.search(r'另行|单独|待通知|另定|随后|补交', row['source_segment'])):
                    row.update(collective_time)
                    row.update(time_binding='stage_collective', deadline_source=collective_source,
                               time_note=f'沿用本环节共同期限“{collective_source}”；本事项未单独给出期限，请核对。')
        records.extend(section_rows)
    return records or None
