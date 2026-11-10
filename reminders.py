"""计算提醒计划，不发送消息或创建系统定时任务。"""
from datetime import datetime, timedelta

STRATEGIES = {
    '课程学业': (('提前3天', 72), ('截止前2小时', 2)),
    '竞赛科研': (('提前5天', 120), ('提前1天', 24)),
    '活动实践': (('提前1天', 24),),
    '行政事务': (('提前3天', 72), ('截止前2小时', 2)),
    '就业实习': (('提前7天', 168), ('提前1天', 24)),
    '生活服务': (('提前1天', 24),),
}


def plan(category: str, deadline: str) -> tuple[list[dict], str]:
    strategy = STRATEGIES.get(category)
    if not strategy:
        return [], '该分类尚未设置提醒策略'
    try:
        date_only = len(deadline) == 10
        fmt = '%Y-%m-%d' if date_only else '%Y-%m-%d %H:%M'
        stamp = datetime.strptime(deadline, fmt)
    except (ValueError, TypeError):
        return [], '事件时间未确定，暂不生成提醒'
    reminders = []
    skipped = False
    for label, hours in strategy:
        if date_only and hours % 24:
            skipped = True
            continue
        reminders.append({'label': label, 'time': (stamp - timedelta(hours=hours)).strftime(fmt)})
    return reminders, '缺少具体时刻，未生成截止前2小时提醒' if skipped else ''


def enrich(record: dict) -> dict:
    """派生提醒始终按当前分类和时间重算，避免手动修改后的旧计划残留。"""
    from categories import UNCATEGORIZED
    record.setdefault('category', UNCATEGORIZED)
    if record.get('time_kind') in ('relative', 'approximate') and record['deadline'] == '未提及':
        record['reminder_times'] = []
        record['reminder_note'] = ('需确认触发日期和工作日日历，暂不生成具体日期提醒'
                                   if record['time_kind'] == 'relative'
                                   else '只有预计公布时间，暂不生成精确日期提醒')
        if record.get('reference_required'):
            record['reminder_note'] = '缺少通知发布时间，暂不生成相对日期提醒'
        elif record.get('weekday_conflict'):
            record['reminder_note'] = '日期与原文星期存在冲突，暂不生成提醒'
        return record
    record['reminder_times'], record['reminder_note'] = plan(record['category'], record['deadline'])
    if record.get('time_role', '').endswith('开始'):
        for reminder in record['reminder_times']:
            if reminder['label'] == '截止前2小时':
                reminder['label'] = '开始前2小时'
        record['reminder_note'] = record['reminder_note'].replace('截止前2小时', '开始前2小时')
    return record
