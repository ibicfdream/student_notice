"""基于关键词的可解释分类；规则顺序只用于展示，不用于强行打破平局。"""
RULES = {
    '课程学业': ('选课', '考试', '成绩', '补考', '调停课', '体测', '补测'),
    '竞赛科研': ('挑战杯', '大创', '创新创业训练计划', '竞赛', '论文', '讲座'),
    '活动实践': ('社团', '志愿', '实践', '文化节', '招新'),
    '就业实习': ('宣讲', '招聘', '实习', '简历', '就业', '毕业去向', '去向登记', '去向落实', '档案转递', '调档函'),
    '行政事务': ('奖学金', '助学金', '学籍', '宿舍', '证明', '住宿申请', '入住申请', '退宿申请', '调宿申请'),
    '生活服务': ('医保', '体检', '图书馆', '校园卡', '食堂', '维修', '报修', '保修', '检修'),
}
UNCATEGORIZED = '其它类别'
CHOICES = (*RULES, UNCATEGORIZED)


def classify(text: str, task: str = '') -> dict:
    matches = {category: [word for word in words if word in text or word in task]
               for category, words in RULES.items()}
    matches = {key: words for key, words in matches.items() if words}
    # 事项名较全文更集中；标题只命中一类时优先该类。
    title_hits = [category for category, words in RULES.items() if any(word in task for word in words)]
    candidates = list(matches)
    # 主事项的动作比“宿舍”等地点词更具体，不能单靠关键词数量决定。
    primary = task.strip() or next((line.strip() for line in text.splitlines() if line.strip()), '')
    dorm_admin = any(word in primary for word in ('宿舍申请', '宿舍分配', '宿舍调换', '宿舍调整', '住宿申请', '入住申请', '退宿申请', '调宿申请'))
    service_action = any(word in primary for word in ('维修', '报修', '保修', '检修'))
    if dorm_admin and '行政事务' in matches:
        category = '行政事务'
    elif '实习证明' in primary:
        category = '就业实习'
    elif service_action:
        category = '生活服务'
    elif len(title_hits) == 1:
        category = title_hits[0]
    elif matches:
        highest = max(map(len, matches.values()))
        winners = [key for key, words in matches.items() if len(words) == highest]
        category = winners[0] if len(winners) == 1 else UNCATEGORIZED
    else:
        category = UNCATEGORIZED
    return dict(category=category, category_candidates=candidates, category_matches=matches)
