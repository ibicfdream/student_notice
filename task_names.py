"""事项名称只保留主题/动作；日期、地点和人群条件另行归属。"""
import re

METADATA_LABELS = {'时间', '地点', '地址', '截止时间', '活动时间', '报名时间', '提交方式', '报名方式', '参与方式', '注意事项', '通知', '提醒'}
KNOWN = re.compile(r'大学生创新创业训练计划项目(?:申报)?|创新创业训练计划项目(?:申报)?|大创项目(?:申报)?|选课补退选|补退选|奖学金申请|助学金申请|职业规划大赛|合唱队员招募|材料提交|考试报名|课程报名|志愿者招募|体测补测|体测|补测|实习分享会|班会|讲座|会议')
TIME_HINT = re.compile(r'今天|明天|后天|(?:下|本|这)?(?:周|星期|礼拜)[一二三四五六日天]|\d{1,2}\s*(?:月|日|点|时|:)')
EVENT_HINT = re.compile(r'体测|补测|补考|考试|面试|班会|讲座|会议|分享会|宣讲会|培训|座谈|活动|大赛|运动会|晚会|画展')


def content_lines(text: str) -> list[str]:
    """转发人和群聊包装不是通知主题；保留后续真正的标题和正文。"""
    lines = []
    text = re.sub(r'【([^】]+)】', lambda match: '【' + match[1].replace('\n', '') + '】', text)
    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r'@(?:所有人|全体成员)', '', line).strip()
        if not line:
            continue
        if re.match(r'^(?:转发(?:自)?|转自|来自).{0,30}?(?:[:：]|[<＜]{2,})', line):
            continue
        lines.append(line)
    return lines


def brief_subject(text: str) -> str | None:
    """识别“体测补测：时间地点……”这种简短主题，而非任意冒号前缀。"""
    line = next(iter(content_lines(text)), '')
    line = re.sub(r'【[^】]*】|\[[^\]]*\]|@\S+\s*', '', line).strip()
    match = re.match(r'([^:：，。；;\n]{2,24})\s*[:：]', line)
    if not match:
        return None
    subject = re.sub(r'^[^\w\u4e00-\u9fff]+', '', match[1]).strip()
    if subject in METADATA_LABELS or TIME_HINT.search(subject) or re.search(r'必须|不用|请于|同学|截止', subject):
        return None
    return subject


def concise_task(text: str, missing: str) -> str:
    heading = next(iter(content_lines(text)), '')
    recruitment_title = re.fullmatch(r'【([^】]*(?:招募|招新)[^】]*)】', heading)
    if recruitment_title:
        title = recruitment_title[1].strip(' ！!。')
        if '合唱比赛' in title and re.search(r'(?:招募|招收|招)\s*合唱队员', text):
            title = re.sub(r'(?:招募|招新)(?:通知)?$', '', title)
            return title + '招募合唱队员'
        return title.removesuffix('通知').strip()
    activity_title = re.fullmatch(r'【([^】]*(?:活动|讲座|会议|培训)[^】]*通知)】', heading)
    if activity_title:
        return activity_title[1].removesuffix('通知').strip()
    explicit = re.search(r'(?:^|[\n。；;])\s*(?:事项|任务|主题|标题)\s*[:：]\s*([^\n。；;]+)', text)
    if explicit:
        # 即使显式标题把时间等写在同一行，也只取首个主题分句。
        value = re.split(r'[，。；;]', explicit[1], maxsplit=1)[0].strip()
        timing = TIME_HINT.search(value)
        if timing:
            value = value[:timing.start()].strip()
        if value == '材料提交':
            block = re.split(r'\n\s*\n', text)[0]
            relevant = re.sub(r'(?:咨询|答疑)[^。；;\n]*', '', block)
            objects = set(re.findall(r'奖学金|助学金', relevant))
            if len(objects) == 1:
                return next(iter(objects)) + value
        return value or missing
    named_activity = re.search(r'新生风采大赛|风采大赛|歌手大赛|运动会|晚会|画展|社团招新', text)
    if named_activity:
        return named_activity[0]
    subject = brief_subject(text)
    if subject:
        return subject
    # 材料提交是动作，业务对象须从当前内容块补齐；多个对象时不猜测。
    # 只在确有提交材料语义时归纳，不能把咨询/背景中的对象当作任务。
    blocks = re.split(r'\n\s*\n', text)
    material_tasks = []
    for block in blocks:
        if not re.search(r'材料提交|(?:提交|报送|递交|交至|交到|送交)[^。；;\n]{0,30}材料|材料[^。；;\n]{0,30}(?:提交|报送|递交|交至|交到|送交)', block):
            continue
        relevant = re.sub(r'(?:咨询|答疑)[^。；;\n]*', '', block)
        objects = set(re.findall(r'奖学金|助学金', relevant))
        if len(objects) == 1:
            material_tasks.append(next(iter(objects)) + '材料提交')
    if len(set(material_tasks)) == 1:
        return material_tasks[0]
    known = KNOWN.search(text)
    if known:
        return known[0]
    title = next(iter(content_lines(text)), '')
    title = re.sub(r'【[^】]*】|\[[^\]]*\]', '', title).strip()
    title = re.sub(r'^关于(?:举办|开展)?|的通知$', '', title)
    title = re.split(r'将于|请|于(?=\s*\d)|[:：，。；;]', title)[0].strip()
    # 无法归纳主题时宁可待核对，不用时间/人群句子冒充事项名称。
    if not title or TIME_HINT.search(title) or re.search(r'同学|必须|不用|无需|田径场|操场', title):
        return missing
    return title[:40]


def short_venue(text: str) -> str | None:
    venue = r'([\u4e00-\u9fffA-Za-z0-9]{0,25}(?:田径场|操场|运动场|篮球场|足球场|体育馆|活动中心|报告厅|招聘大厅|大厅|礼堂|教室|会议室|办公室|[楼馆]\s*[A-Za-z]?\d{2,4}(?:室)?))'
    standalone = re.search(r'(?:^|[，。；;\n])\s*(?:地点\s*[:：]?|在|到)?\s*' + venue + r'\s*(?=$|[，。；;\n])', text)
    if standalone:
        if not TIME_HINT.search(standalone[1]):
            return standalone[1]
    located = re.search(r'(?:地点\s*[:：]|在)\s*' + venue, text)
    return located[1] if located else None


def fitness_conditions(text: str) -> dict:
    details = {}
    if re.search(r'体测|补测', text):
        if re.search(r'没过|未通过|未达标|不合格', text):
            details.update(prerequisite='体测未通过', optional=False)
        if re.search(r'(?<!没)(?<!未)(?:过的|已通过(?:的)?|已达标(?:的)?)(?:同学)?(?:不用|无需|不必)(?:来|参加)?', text):
            details['excluded_audience'] = '体测已通过者无需参加'
        clauses = [part.strip() for part in re.split(r'[，。；;\n]', text)
                   if re.search(r'没过|未通过|未达标|不合格|必须来|不用来|无需参加', part)]
        if clauses:
            details['requirements'] = '；'.join(clauses)
    return details
