"""通用编号阶段与动作拆分；时间只绑定本动作或明确共享的动作。"""
import re
from datetime import date

SECTION = re.compile(r'^[ \t]*(?:[一二三四五六七八九十]+|\d+)[、.．][ \t]*([^\n:：]+)(?:[:：][ \t]*([^\n]*))?', re.MULTILINE)
RELATIVE = re.compile(r'((?:答辩|审核|审批|审查)(?:通过|结束|完成))后\s*([一二三四五六七八九十\d]+)\s*个?(工作日|天|日)内')
ACTION = re.compile(r'上传|提交|补交|送交|发送|报送|填报|组建|选题|核对|修改|领取|转递|交至|交到|交给|参加|登记|办理')


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
    pieces = re.split(r'[，,]|\+(?=(?:纸质|电子|系统|上传|提交))|(?=同时(?:上传|提交|发送|报送))', sentence)
    actions = []
    pending = ''
    for piece in pieces:
        piece = piece.strip()
        if not piece:
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
    from extractor import DATE, URL, MISSING, extract_notice, extract_time_details, _event_interval
    from categories import classify
    from task_names import concise_task, content_lines

    headings = list(SECTION.finditer(text))
    if len(headings) < 2:
        return None
    title = text[:headings[0].start()].strip()
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
        body = ((heading[2] or '') + '\n' + text[heading.end():end]).strip()
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
        common_match = re.search(r'(?:统一截止时间|统一提交期限|统一办理期限)\s*[:：为]?\s*([^。；;\n]+)', body)
        common_time = extract_time_details('截止时间：' + common_match[1], reference) if common_match else heading_time
        section_rows = []
        sentences = [part.strip(' 。；;\n') for part in re.split(r'[。；;\n]+', body) if part.strip()]
        for sentence in sentences:
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
                row = base(stage, action)
                platforms = re.findall(r'(?:登录|登陆|进入|至|到)\s*([\u4e00-\u9fffA-Za-z0-9]{1,24}(?:系统|平台))', action)
                row['submit_method'] = '；'.join(dict.fromkeys(platforms)) or row['submit_method']
                if re.search(r'系统|填报', action) and not re.search(r'纸质|纸版', action):
                    if len(shared_urls) == 1 and not platforms:
                        row['submit_method'] = '系统：' + shared_urls[0]
                address = re.search(r'(?:至|交到|到|前往|送至|送交)\s*([^，。；;]*?(?:(?:中心|办公室|学工办|教务处)(?:\s*\([^)]*\))?|[楼馆]\s*[A-Za-z]?\d{2,4}(?:室)?))', action)
                row['location'] = address[1].strip() if address else MISSING
                if '组建' in action or '选题' in action:
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
                    name = '上传终稿PDF' if '终稿' in action else '上传电子版论文' if '论文' in body else '上传去向证明材料' if '去向' in body else '上传材料'
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
                section_rows.append(row)
                previous_row = row
        # 未支持的章节也保留，避免只展示已识别动作而漏掉整个阶段。
        if not section_rows and body:
            row = base(stage, body)
            row['task'] = name_prefix + '—办理事项' if dated_heading else stage
            row['time_note'] = '本阶段动作未能可靠拆分，请对照原文核对。'
            section_rows.append(row)
        records.extend(section_rows)
    return records or None
