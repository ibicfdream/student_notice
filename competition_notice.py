"""比赛报名按操作语义聚合，不把章节、赛题或评审介绍当作个人任务。"""
import re
from datetime import date

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
DOMAIN = re.compile(r'(?<![\w@.-])(?:[A-Za-z0-9-]+\.)+(?:com|net|cn)(?![\w.-])')
REGISTRATION = re.compile(r'报名(?:阶段|系统|截止|方式|时间|网址|平台)|(?:系统|线上|初始|完成|须|请|参赛)[^。；;]{0,24}报名|报名[^。；;]{0,160}(?:报送|提交|上传|官网|网址)')


def extract_competition_registration(source: str, text: str, reference: date) -> list[dict] | None:
    from extractor import DATE, URL, MISSING, extract_notice, extract_time_details
    from task_names import content_lines
    from categories import CULTURAL_ACTIVITIES
    lines = content_lines(text)
    first_section = re.search(r'(?m)^[ \t]*(?:[一二三四五六七八九十]+[、.．]|\([一二三四五六七八九十]+\))', text)
    introduction = (text[:first_section.start()] if first_section else '\n'.join(lines)[:500]).replace('\n', '')
    if not re.search(r'大赛|比赛|竞赛', introduction):
        return None
    # OCR 换行不应改变段落的语义；先按句末标点确定候选语句。
    paragraphs = [part.strip() for part in re.split(r'[。；;]', text.replace('\r', '').replace('\n', '')) if part.strip()]
    registration = [part for part in paragraphs if '报名' in part and REGISTRATION.search(part)]
    if not registration:
        return None
    # 材料命名与提交说明属于同一报名流程，不需要重复出现“完成报名”。
    related = [part for part in paragraphs if part in registration or re.search(r'报名材料|报名信息', part)]
    registration_text = '。'.join(related)

    if '职业规划大赛' in introduction:
        subject = '职业规划大赛'
    else:
        title = re.search(r'([^\n，。；;：:《》]{2,90}(?:大赛|比赛|竞赛))', introduction)
        if not title:
            return None
        subject = title[1].strip()
        subject = re.sub(r'^.*(?:举办|开展|组织)', '', subject)
        subject = re.sub(r'^关于', '', subject).strip('【】[]“”" ')
        subject = subject.replace('“', '').replace('”', '').replace('"', '')
    task = subject.removesuffix('报名') + '报名'
    row = extract_notice('事项：' + task, reference)

    deadlines = []
    for paragraph in registration:
        details = extract_time_details(paragraph, reference)
        if details['deadline'] != MISSING:
            deadlines.append((details, paragraph))
        elif re.search(r'报名(?:阶段|时间|期限|截止)', paragraph):
            # “即日起—某日”是报名窗口；取该标签内末日，不能取背景日期。
            window = re.search(r'报名(?:阶段|时间|期限|截止)[^。]{0,80}', paragraph)
            dates = list(DATE.finditer(window[0])) if window else []
            if dates:
                details = extract_time_details('报名截止时间：' + dates[-1][0], reference)
                deadlines.append((details, window[0]))
    unique = {details['deadline'] for details, _ in deadlines}
    notes = []
    if len(unique) == 1:
        details, evidence = deadlines[0]
        row.update(details)
        row['deadline_source'] = evidence
    else:
        row['deadline'] = MISSING
        notes.append('未找到明确报名截止日期' if not unique else '存在多个报名截止日期，无法唯一绑定，请核对对应赛道或批次')

    urls = list(dict.fromkeys(URL.findall(registration_text)))
    emails = list(dict.fromkeys(EMAIL.findall(registration_text)))
    email_domains = {email.split('@', 1)[1] for email in emails}
    domains = [value for value in DOMAIN.findall(registration_text)
               if value not in email_domains and not any(value in url for url in urls)]
    methods = []
    if urls or domains:
        methods.append('系统报名：' + '；'.join(dict.fromkeys(urls + domains)))
    if emails:
        methods.append('报名材料发送至邮箱：' + '；'.join(emails))
    if not methods and re.search(r'系统报名|报名系统', registration_text):
        methods.append('报名系统（具体网址未提及）')

    requirements = []
    for paragraph in paragraphs:
        relevant = paragraph in related or bool(re.search(r'(?:每支|每名|每位|各参赛)[^。]{0,40}(?:人数|仅|限|不得)', paragraph))
        if not relevant:
            continue
        for clause in re.split(r'[，,]', paragraph):
            clause = re.sub(r'^\s*(?:\d+[、.．]|\([一二三四五六七八九十]+\))\s*', '', clause).strip()
            if re.search(r'网址|https?://|@', clause):
                if '打包' in clause:
                    requirements.append('报名材料需打包')
                continue
            if DATE.search(clause) and '报名' in clause:
                continue
            if re.search(r'材料|压缩|命名|按要求|每支|每名|每位|人数|仅可|仅限|不得|不能|不可|操作流程|操作指南|队伍成员|指导教师', clause):
                requirements.append(clause)
    category = '活动实践' if any(word in subject for word in CULTURAL_ACTIVITIES) else '竞赛科研'
    row.update(task=task, stage='报名', notice_subject=subject, time_role='报名截止', time_kind='deadline',
               submit_method='；'.join(methods) or MISSING, source_text=source,
               source_segment=registration_text, category=category, category_candidates=[category],
               category_matches={category: ['比赛报名操作']})
    if requirements:
        row['requirements'] = '；'.join(dict.fromkeys(requirements))
    if notes:
        row['time_note'] = '；'.join(notes)
    return [row]
