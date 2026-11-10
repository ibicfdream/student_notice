"""不依赖第三方库的通知规则提取器。"""
import re
import unicodedata
from datetime import date, datetime

MISSING = "未提及"
DATE = re.compile(r"(?<!\d)(?:(?P<y>20\d{2})\s*[年/.-]\s*)?(?P<m>\d{1,2})\s*[月/.-]\s*(?P<d>\d{1,2})(?:\s*[日号])?(?!\d)")
CLOCK = re.compile(r"(?P<period>上午|下午|晚上|中午|凌晨)?\s*(?P<h>\d{1,2})\s*(?::\s*(?P<minute>\d{1,2})|[点时](?P<cnminute>\d{1,2})?\s*分?)(?!\d)")


def extract_time(text: str, reference: date) -> str:
    semester = re.search(r"(20\d{2})\s*-\s*(20\d{2})\s*-\s*([12])\s*学期", text)
    candidates = []
    for match in DATE.finditer(text):
        # 防止把学年 2024-2025-2 的末尾误当作月日。
        if semester and match.start() < semester.end() and match.end() > semester.start():
            continue
        year = int(match['y']) if match['y'] else (int(semester[2] if semester[3] == '2' else semester[1]) if semester else reference.year)
        following = text[match.end():]
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
        end = bool(re.search(r"截止|截至|最[迟晚]", before) or re.search(r"截止|截至|结束|之前|前(?:提交|完成|报送|报名|$)", clause))
        start = bool(re.search(r"开始|启动|举行|举办|(?:活动|会议|考试|讲座|报到|面试|集合|上课|比赛)(?:时间|日期)|定于|将于", before + clause))
        # 无事件语义的日期可能只是聊天时间戳或通知落款，不自动填入。
        if end or start:
            candidates.append((2 if end else 1, match.start(), value.strftime('%Y-%m-%d %H:%M') if clock else value.strftime('%Y-%m-%d')))
    if candidates:
        return max(candidates, key=lambda x: (x[0], -x[1]))[2]
    return MISSING


def extract_notice(source: str, reference: date | None = None) -> dict:
    text = unicodedata.normalize('NFKC', source).replace(',', '，')
    flat = re.sub(r'\s+', ' ', text).strip()
    if not flat:
        raise ValueError('通知内容不能为空')
    task = MISSING
    explicit = re.search(r'(?:事项|任务|主题|标题)\s*[:：]\s*([^\n。；;]+)', text)
    known = re.search(r'选课补退选|补退选|奖学金申请|助学金申请|职业规划大赛|合唱队员招募|材料提交|考试报名|课程报名|志愿者招募|班会|讲座|会议', flat)
    if explicit:
        task = explicit[1].strip()
    elif known:
        task = known[0]
    else:
        title = re.sub(r'【[^】]*】|\[[^\]]*\]', '', flat)
        title = re.sub(r'^关于|的通知$', '', title)
        title = re.split(r'将于|请|于(?=\s*\d)|[，。；;]', title)[0].strip()
        if title:
            task = title[:40]
    methods = []
    for pattern in (
        r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',
        r'https?://[^\s，。；;<>]+',
        r'[\u4e00-\u9fffA-Za-z0-9]{0,16}(?:系统|平台|小程序)',
        r'问卷星|腾讯文档|金山文档|群接龙|群内接龙|纸质(?:版)?|现场提交|电子邮件|邮箱',
    ):
        for item in re.findall(pattern, flat):
            item = re.split(r'登录|登陆|进入|通过|请|同学|在|到', item)[-1]
            if item and item not in methods:
                methods.append(item)
    place = re.search(r'(?:地点|地址)\s*[:：为]?\s*([^，。；;\n]+)', text)
    if not place:
        place = re.search(r'(?:在|到|至)\s*([^，。；;\n]{1,25}?(?:教室|会议室|报告厅|礼堂|体育馆|办公室|[楼馆]\s*\d{2,4}(?:室)?))', text)
    return dict(task=task, deadline=extract_time(text, reference or date.today()),
                submit_method='；'.join(methods) or MISSING,
                location=place[1].strip() if place else MISSING, source_text=source)
