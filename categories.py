"""基于关键词的可解释分类；规则顺序只用于展示，不用于强行打破平局。"""
import re

CULTURAL_ACTIVITIES = ('风采大赛', '歌手大赛', '运动会', '晚会', '画展', '社团招新')
RULES = {
    '课程学业': ('选课', '考试', '成绩', '补考', '调停课', '体测', '补测', '讲座', '课程论文', '期末论文', '毕业论文', '学位论文', '答辩', '学分'),
    '竞赛科研': ('挑战杯', '大创', '创新创业训练计划', '竞赛', '职业规划大赛', '期刊论文', '会议论文', '科研论文'),
    '活动实践': ('社团', '志愿', '实践', '文化节', '招新', '合唱', '演出', '文艺', '体育', '篮球', '足球', *CULTURAL_ACTIVITIES),
    '就业实习': ('宣讲', '宣讲会', '招聘', '实习', '简历', 'offer', '就业', '毕业去向', '去向登记', '去向落实'),
    '行政事务': ('奖学金', '助学金', '学籍', '宿舍', '证明', '评优', '请假', '盖章', '档案', '调档函', '住宿申请', '入住申请', '退宿申请', '调宿申请'),
    '生活服务': ('医保', '体检', '图书馆', '校园卡', '食堂', '维修', '报修', '保修', '检修'),
}
UNCATEGORIZED = '其它类别'
CHOICES = (*RULES, UNCATEGORIZED)


def paper_context(context: str) -> str | None:
    course = bool(re.search(r'(?:课程|马原|马克思主义基本原理|专业课|期末|毕业(?:生)?|学位)[^。；;\n]{0,16}论文', context))
    research = bool(re.search(
        r'(?:期刊|学术会议|会议|科研(?:项目)?|研究项目|课题|比赛|竞赛|挑战杯|大创)[^。；;\n]{0,24}论文'
        r'|论文[^。；;\n]{0,24}(?:期刊|学术会议|会议投稿|科研项目|比赛|竞赛|投稿|发表)', context))
    if course != research:
        return '课程学业' if course else '竞赛科研'
    return None


def classify(text: str, task: str = '') -> dict:
    folded_text, folded_task = text.casefold(), task.casefold()
    matches = {category: [word for word in words if word.casefold() in folded_text or word.casefold() in folded_task]
               for category, words in RULES.items()}
    matches = {key: words for key, words in matches.items() if words}
    primary = task.strip() or next((line.strip() for line in text.splitlines() if line.strip()), '')
    paper_category = None
    if '论文' in primary:
        paper_category = paper_context(primary) or paper_context(text)
        if paper_category:
            matches.setdefault(paper_category, []).append('论文用途语境')
    # 事项名较全文更集中；标题只命中一类时优先该类。
    title_hits = [category for category, words in RULES.items() if any(word.casefold() in folded_task for word in words)]
    candidates = list(matches)
    # 主事项的动作比“宿舍”等地点词更具体，不能单靠关键词数量决定。
    dorm_admin = any(word in primary for word in ('宿舍申请', '宿舍分配', '宿舍调换', '宿舍调整', '住宿申请', '入住申请', '退宿申请', '调宿申请'))
    service_action = any(word in primary for word in ('维修', '报修', '保修', '检修'))
    cultural_event = (any(word in primary for word in CULTURAL_ACTIVITIES)
                      or (not title_hits and any(word in text for word in CULTURAL_ACTIVITIES)))
    if dorm_admin and '行政事务' in matches:
        category = '行政事务'
    elif '实习证明' in primary:
        category = '就业实习'
    elif service_action:
        category = '生活服务'
    elif cultural_event:
        # 文体活动主题优先于举办地点中的“招聘大厅”等背景词。
        category = '活动实践'
    elif paper_category:
        category = paper_category
    elif len(title_hits) == 1:
        category = title_hits[0]
    elif matches:
        highest = max(map(len, matches.values()))
        winners = [key for key, words in matches.items() if len(words) == highest]
        category = winners[0] if len(winners) == 1 else UNCATEGORIZED
    else:
        category = UNCATEGORIZED
    return dict(category=category, category_candidates=candidates, category_matches=matches)
