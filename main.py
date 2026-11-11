"""学生通知 CLI：python main.py --help。"""
import argparse
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from extractor import MISSING, extract_notices
from ocr import recognize
from storage import append_many, load
from categories import CHOICES, UNCATEGORIZED
from reminders import enrich

LABELS = {'task': '事项', 'deadline': '时间', 'submit_method': '提交方式', 'location': '地点'}


def normalize_time_input(value: str) -> str:
    """手动日期可省略分钟；有小时才补:00，只有日期时保留日期精度。"""
    value = value.strip().replace('：', ':')
    match = re.fullmatch(r'(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T]+(\d{1,2})(?::(\d{1,2}))?)?', value)
    if not match:
        raise ValueError('日期时间格式无效')
    year, month, day = (int(match[index]) for index in (1, 2, 3))
    if match[4] is None:
        return date(year, month, day).isoformat()
    stamp = datetime(year, month, day, int(match[4]), int(match[5] or 0))
    return stamp.strftime('%Y-%m-%d %H:%M')


def confirm(record: dict, editing: bool = False) -> bool:
    """先展示完整草稿，按编号修改；仅确认后提交草稿。"""
    draft = record.copy()
    draft.setdefault('category', UNCATEGORIZED)
    items = [('task', '事项名称'), ('deadline', '截止/事件时间'),
             ('submit_method', '提交方式'), ('location', '事件地点'), ('category', '分类标签')]
    if draft.get('time_role'):
        items[1] = ('deadline', draft['time_role'] + '时间')
    if 'start_time' in draft:
        items.append(('start_time', '开始时间'))
    if 'end_time' in draft:
        items.append(('end_time', draft.get('end_time_label', '活动结束时间')))
    if 'service_hours' in draft:
        items.append(('service_hours', '每日服务时段'))
    if 'service_note' in draft:
        items.append(('service_note', '补充说明'))
    for key, label in (('time_expression', '原文时间安排'), ('prerequisite', '参加/办理条件'), ('excluded_audience', '无需参加人群'), ('consequence', '未办理后果'),
                       ('requirements', '要求')):
        if key in draft:
            items.append((key, label))
    if draft.get('method_role'):
        items[2] = ('submit_method', draft['method_role'])
    show_source = False
    category_confirmed = False
    while True:
        enrich(draft)
        if draft.get('deadline_boundary') == 'exclusive_date':
            items[1] = ('deadline', '最晚提交日期')
        else:
            items[1] = ('deadline', draft['time_role'] + '时间' if draft.get('time_role') else '截止/事件时间')
        if draft.get('time_kind') in ('relative', 'approximate'):
            items[1] = ('deadline', '具体提醒时间（待确认）' if draft['deadline'] == MISSING else '人工确认的提醒时间')
        print('\n========== 提取结果预览 ==========')
        if draft.get('stage'):
            print('所属阶段：' + draft['stage'])
        if draft.get('notice_subject'):
            print('通知主题：' + draft['notice_subject'])
        if draft.get('submission_group'):
            print('同组材料：' + draft['submission_group'])
        for number, (key, label) in enumerate(items, 1):
            value = draft[key]
            warning = ''
            if value == MISSING:
                warning = ' [待核对：信息缺失]'
            elif key in ('deadline', 'end_time', 'start_time'):
                try:
                    datetime.strptime(value, '%Y-%m-%d' if len(value) == 10 else '%Y-%m-%d %H:%M')
                    if len(value) == 10:
                        warning = ' [待核对：未提供具体时刻]'
                except ValueError:
                    warning = ' [待核对：时间格式异常]'
            elif key == 'category' and not category_confirmed:
                if value == UNCATEGORIZED:
                    warning = ' [待核对：未确定具体类别]'
                elif len(draft.get('category_candidates', [])) > 1:
                    warning = ' [待核对：命中多个类别]'
            if key == 'deadline' and draft.get('deadline_inferred'):
                warning += ' [待核对：沿用同组材料期限]'
            print(f'{number}. {label}：{value}{warning}')
        if draft.get('relative_date_expression'):
            basis = '指定参考日期' if draft.get('reference_source') == 'specified' else '当前北京时间日期'
            print(f"参考日期：{draft.get('reference_date', '未提及')}（{basis}）")
        print('\n提醒计划：')
        for reminder in draft['reminder_times']:
            print(f"  {reminder['label']}：{reminder['time']}")
        if draft['reminder_note']:
            print('  ' + draft['reminder_note'])
        if draft.get('time_note'):
            print('  [待核对] ' + draft['time_note'])
        if draft.get('extraction_note'):
            print('  [待核对] ' + draft['extraction_note'])
        if draft.get('deadline_note'):
            print('  时间说明：' + draft['deadline_note'])
        if draft.get('time_range_expression'):
            print('  原文时间范围：' + draft['time_range_expression'])
        print('\n原文来源：' + ('已展开' if show_source else '已折叠（输入 v 展开查看）'))
        if show_source:
            if draft.get('source_segment'):
                print('本事项对应语句：' + draft['source_segment'])
            print('完整通知：')
            print(draft['source_text'])
            evidence = draft.get('category_matches', {})
            if evidence:
                print('自动分类依据：' + '；'.join(f"{key}：{'、'.join(words)}" for key, words in evidence.items()))
        prompt = f'\n输入 1–{len(items)} 修改对应内容 / v 展开或收起原文 / '
        prompt += 'y 确认当前修改并返回总览 / n 放弃当前修改并返回：' if editing else 'y 全部确认保存 / n 放弃：'
        action = input(prompt).strip().lower()
        if action == 'y':
            record.update(draft)
            return True
        if action == 'n':
            return False
        if action == 'v':
            show_source = not show_source
            continue
        if action not in tuple(str(index) for index in range(1, len(items) + 1)):
            print(f'请输入 1–{len(items)}、v、y 或 n；保存请明确输入 y。')
            continue
        key, label = items[int(action) - 1]
        print(f'修改{label}，当前内容：{draft[key]}')
        if key == 'category':
            print('分类选项：' + ' / '.join(f'{i} {name}' for i, name in enumerate(CHOICES, 1)))
        elif key in ('deadline', 'end_time', 'start_time'):
            print('可输入日期、日期+小时或日期+时分；例如 2026-11-17 14 会保存为 2026-11-17 14:00。')
        while True:
            value = input('回车保留，输入新内容替换；输入“未提及”清空：').strip()
            if not value:
                break
            if key == 'category':
                if value.isdigit() and 1 <= int(value) <= len(CHOICES):
                    value = CHOICES[int(value) - 1]
                if value not in CHOICES:
                    print('请选择上方列出的分类编号或名称。')
                    continue
                category_confirmed = True
            elif key in ('deadline', 'end_time', 'start_time') and value != MISSING:
                try:
                    value = normalize_time_input(value)
                except ValueError:
                    print('时间无效，请检查日期及小时（0–23）、分钟（0–59）；支持 YYYY-MM-DD、YYYY-MM-DD HH 或 YYYY-MM-DD HH:MM。')
                    continue
            if key in ('deadline', 'start_time') and 'start_time' in draft:
                start = value if key == 'start_time' else draft['start_time']
                end = value if key == 'deadline' else draft['deadline']
                if start != MISSING and end != MISSING and datetime.fromisoformat(end) < datetime.fromisoformat(start):
                    print('截止时间不能早于开始时间；可先清空另一端再调整。')
                    continue
            if key in ('deadline', 'end_time') and 'end_time' in draft:
                start = value if key == 'deadline' else draft['deadline']
                end = value if key == 'end_time' else draft['end_time']
                if start != MISSING and end != MISSING:
                    if datetime.fromisoformat(end) < datetime.fromisoformat(start):
                        print('结束时间不能早于开始时间；可先将另一端设为“未提及”，再调整日期。')
                        continue
                draft['time_note'] = ''
            if key == 'deadline':
                draft['deadline_boundary'] = 'manual'
                draft['deadline_note'] = ''
                if draft.get('deadline_inferred'):
                    draft['deadline_inferred'] = False
                    draft['time_binding'] = 'manual'
                    draft['time_note'] = '该动作的时间已由用户单独修改。'
                if draft.get('time_kind') in ('relative', 'approximate'):
                    draft['time_note'] = ('具体提醒时间由用户确认，原文时间安排保留供核对。'
                                          if value != MISSING else '尚无确定提醒时间，请核对原文时间安排和触发条件。')
            draft[key] = value
            if key == 'time_expression' and draft.get('time_kind') == 'relative':
                draft['depends_on_event'] = '待重新确认'
                draft['relative_offset'] = None
                draft['time_note'] = '原文时间安排已修改，需重新确认触发条件。'
            break


def confirm_notices(records: list[dict]) -> bool:
    if len(records) == 1:
        return confirm(records[0])
    drafts = [row.copy() for row in records]
    show_source = False
    while True:
        print(f'\n========== 检测到 {len(drafts)} 个独立事项 ==========')
        for index, row in enumerate(drafts, 1):
            enrich(row)
            print(f"\n事项 {index}：{row['task']}")
            if row.get('stage'):
                print('  所属阶段：' + row['stage'])
            if row.get('notice_subject'):
                print('  通知主题：' + row['notice_subject'])
            label = '最晚提交日期' if row.get('deadline_boundary') == 'exclusive_date' else row.get('time_role', '截止/事件') + '时间'
            if row.get('time_kind') in ('relative', 'approximate'):
                label = '具体提醒时间（待确认）' if row['deadline'] == MISSING else '人工确认的提醒时间'
            print(f"  {label}：{row['deadline']}")
            if row.get('submission_group'):
                print('  同组材料：' + row['submission_group'])
            if row.get('deadline_inferred'):
                print('  [待核对：沿用同组材料期限，并非原文独立明示]')
            for key, title in (('time_expression', '原文时间安排'), ('prerequisite', '参加/办理条件'), ('excluded_audience', '无需参加人群'), ('consequence', '未办理后果'), ('requirements', '要求')):
                if row.get(key):
                    print(f'  {title}：{row[key]}')
            if 'start_time' in row:
                print('  开始时间：' + row['start_time'])
            if 'end_time' in row:
                print(f"  {row.get('end_time_label', '活动结束时间')}：{row['end_time']}")
            if row.get('service_hours'):
                print('  每日服务时段：' + row['service_hours'])
            if row.get('service_note'):
                print('  补充说明：' + row['service_note'])
            print(f"  {row.get('method_role', '提交方式')}：{row['submit_method']}")
            print(f"  事件地点：{row['location']}")
            print(f"  分类标签：{row['category']}")
            if any(row[key] == MISSING for key in LABELS):
                print('  [待核对：部分信息未提及]')
            for reminder in row['reminder_times']:
                print(f"  {reminder['label']}提醒：{reminder['time']}")
            if row['reminder_note']:
                print('  ' + row['reminder_note'])
            if row.get('time_note'):
                print('  [待核对] ' + row['time_note'])
            if row.get('extraction_note'):
                print('  [待核对] ' + row['extraction_note'])
            if row.get('deadline_note'):
                print('  时间说明：' + row['deadline_note'])
        if show_source:
            print('\n完整通知：\n' + drafts[0]['source_text'])
        action = input('\n输入事项编号查看/修改 / v 展开或收起原文 / y 全部确认保存 / n 全部放弃：').strip().lower()
        if action == 'y':
            for record, draft in zip(records, drafts):
                record.update(draft)
            return True
        if action == 'n':
            return False
        if action == 'v':
            show_source = not show_source
        elif action.isdigit() and 1 <= int(action) <= len(drafts):
            confirm(drafts[int(action) - 1], editing=True)
        else:
            print('请输入有效事项编号、v、y 或 n。')


def show_todos(path: Path, days: int | None, category: str | None = None) -> None:
    now = datetime.now()
    rows = []
    for row in load(path):
        if category and row['category'] != category:
            continue
        raw = row['deadline']
        try:
            # 日期型任务当天结束前不标为逾期，但存储时保留日期精度。
            start_of_day = time.min if 'end_time' in row else time.max
            stamp = datetime.combine(date.fromisoformat(raw), start_of_day) if len(raw) == 10 else datetime.strptime(raw, '%Y-%m-%d %H:%M')
        except ValueError:
            stamp = None
        if days is not None and (stamp is None or stamp > now + timedelta(days=days)):
            continue
        status = '时间待确认' if stamp is None else '已逾期' if stamp < now else '待办'
        if 'end_time' in row and stamp is not None:
            try:
                end_raw = row['end_time']
                end_stamp = datetime.combine(date.fromisoformat(end_raw), time.max) if len(end_raw) == 10 else datetime.strptime(end_raw, '%Y-%m-%d %H:%M')
                status = '待开始' if now < stamp else '进行中' if now <= end_stamp else '已结束'
            except ValueError:
                status = '结束时间待确认'
        prefix = '最晚提交日期 ' if row.get('deadline_boundary') == 'exclusive_date' else (row['time_role'] + ' ' if row.get('time_role') else '')
        display_time = prefix + raw
        if row.get('time_expression'):
            display_time += '（' + row['time_expression'] + '）'
        if row.get('start_time') and row['start_time'] != MISSING:
            display_time = row['start_time'] + ' 至 ' + display_time
        if row.get('end_time') and row['end_time'] != MISSING:
            display_time += ' 至 ' + row['end_time']
        if row.get('service_hours'):
            display_time += '（' + row['service_hours'] + '）'
        extra = (' | 补充说明：' + row['service_note']) if row.get('service_note') else ''
        if row.get('prerequisite'):
            extra += ' | 前置条件：' + row['prerequisite']
        if row.get('excluded_audience'):
            extra += ' | 无需参加人群：' + row['excluded_audience']
        if row.get('stage'):
            extra += ' | 阶段：' + row['stage']
        if row.get('deadline_inferred'):
            extra += ' | 期限沿用同组材料（待核对）'
        rows.append((stamp or datetime.max, f"[{status}][{row['category']}] {display_time} | {row['task']} | {row['submit_method']} | {row['location']}{extra}"))
    for _, line in sorted(rows, key=lambda item: item[0]):
        print(line)
    if not rows:
        print('暂无符合条件的待办。')


def show_reminders(path: Path) -> None:
    """输出全部计划，不将重复查看当成已经发送提醒。"""
    rows = []
    notes = []
    for row in load(path):
        for reminder in row['reminder_times']:
            rows.append((reminder['time'], f"{reminder['time']} | {row['category']} | {row['task']} | {reminder['label']}"))
        if row['reminder_note']:
            notes.append(f"{row['task']}：{row['reminder_note']}")
    print('提醒计划（仅输出，不会自动推送）：')
    for _, line in sorted(rows):
        print(line)
    for note in notes:
        print('提示：' + note)
    if not rows:
        print('暂无可生成的提醒。')


def main() -> int:
    parser = argparse.ArgumentParser(description='学生通知提取与待办管理（本地时间）')
    parser.add_argument('--file', type=Path, default=Path('todo_list.json'), help='JSON 保存路径')
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('add', help='输入通知、预览全部结果并按需修改确认')
    source = add.add_mutually_exclusive_group()
    source.add_argument('--text', help='直接传入通知文本')
    source.add_argument('--image', type=Path, help='通知截图')
    add.add_argument('--reference-date', '--notice-date', dest='reference_date', type=date.fromisoformat, help='通知发布时间/参考日期 YYYY-MM-DD；省略时按当前北京时间日期换算相对日期')
    listing = commands.add_parser('list', help='按时间输出所有已保存事项')
    listing.add_argument('--days', type=int, help='未来 N 天内及全部逾期事项，排除时间未知事项')
    listing.add_argument('--category', choices=CHOICES, help='按分类筛选')
    commands.add_parser('reminders', help='输出各分类对应的提醒计划，不自动推送')
    args = parser.parse_args()
    try:
        if args.command == 'list':
            if args.days is not None and args.days < 0:
                raise ValueError('--days 不能为负数')
            show_todos(args.file, args.days, args.category)
        elif args.command == 'reminders':
            show_reminders(args.file)
        else:
            if args.image:
                text = recognize(args.image)
            elif args.text is not None:
                text = args.text
            else:
                print('粘贴通知，可含多行；单独输入 END 结束：')
                lines = []
                while (line := input()).strip().upper() != 'END':
                    lines.append(line)
                text = '\n'.join(lines)
            records = extract_notices(text, args.reference_date)
            if confirm_notices(records):
                append_many(args.file, records)
                print(f'已保存 {len(records)} 条事项到 {args.file.resolve()}')
            else:
                print('已取消。')
        return 0
    except (ValueError, OSError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print('\n输入中断，未新增记录。', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
