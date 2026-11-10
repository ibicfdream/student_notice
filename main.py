"""学生通知 CLI：python main.py --help。"""
import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

from extractor import MISSING, extract_notice
from ocr import recognize
from storage import append, load

LABELS = {'task': '事项', 'deadline': '时间', 'submit_method': '提交方式', 'location': '地点'}


def confirm(record: dict) -> bool:
    print('\n原文：\n' + record['source_text'])
    print('逐项核对提取内容：直接回车保留，输入正确内容替换，输入“未提及”清空。')
    print('时间格式：YYYY-MM-DD 或 YYYY-MM-DD HH:MM；请核对年份和事件时间。')
    draft = record.copy()
    while True:
        for key, label in LABELS.items():
            while True:
                value = input(f'{label}【{draft[key]}】\n正确内容（回车保留）：').strip()
                if not value:
                    break
                if key == 'deadline' and value != MISSING:
                    try:
                        fmt = '%Y-%m-%d %H:%M' if ' ' in value else '%Y-%m-%d'
                        value = datetime.strptime(value, fmt).strftime(fmt)
                    except ValueError:
                        print('时间无效，请重新输入 YYYY-MM-DD 或 YYYY-MM-DD HH:MM。')
                        continue
                draft[key] = value
                break
        print('\n最终预览：')
        for key, label in LABELS.items():
            print(f'{label}：{draft[key]}')
        while True:
            action = input('确认保存？y 保存 / e 继续修改 / n 取消：').strip().lower()
            if action == 'y':
                record.update(draft)
                return True
            if action == 'n':
                return False
            if action == 'e':
                break
            print('请输入 y、e 或 n。')


def show_todos(path: Path, days: int | None) -> None:
    now = datetime.now()
    rows = []
    for row in load(path):
        raw = row['deadline']
        try:
            # 日期型任务当天结束前不标为逾期，但存储时保留日期精度。
            stamp = datetime.combine(date.fromisoformat(raw), time.max) if len(raw) == 10 else datetime.strptime(raw, '%Y-%m-%d %H:%M')
        except ValueError:
            stamp = None
        if days is not None and (stamp is None or stamp > now + timedelta(days=days)):
            continue
        status = '时间待确认' if stamp is None else '已逾期' if stamp < now else '待办'
        rows.append((stamp or datetime.max, f"[{status}] {raw} | {row['task']} | {row['submit_method']} | {row['location']}"))
    for _, line in sorted(rows, key=lambda item: item[0]):
        print(line)
    if not rows:
        print('暂无符合条件的待办。')


def main() -> int:
    parser = argparse.ArgumentParser(description='学生通知提取与待办管理（本地时间）')
    parser.add_argument('--file', type=Path, default=Path('todo_list.json'), help='JSON 保存路径')
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('add', help='输入通知并逐条确认')
    source = add.add_mutually_exclusive_group()
    source.add_argument('--text', help='直接传入通知文本')
    source.add_argument('--image', type=Path, help='通知截图')
    add.add_argument('--ocr', choices=['pytesseract', 'paddleocr'], default='pytesseract')
    add.add_argument('--tesseract-cmd', help='Tesseract 可执行文件完整路径')
    add.add_argument('--reference-date', type=date.fromisoformat, default=date.today(), help='缺少年份时使用的参考日期 YYYY-MM-DD')
    listing = commands.add_parser('list', help='按时间输出所有已保存事项')
    listing.add_argument('--days', type=int, help='未来 N 天内及全部逾期事项，排除时间未知事项')
    args = parser.parse_args()
    try:
        if args.command == 'list':
            if args.days is not None and args.days < 0:
                raise ValueError('--days 不能为负数')
            show_todos(args.file, args.days)
        else:
            if args.image:
                text = recognize(args.image, args.ocr, args.tesseract_cmd)
            elif args.text is not None:
                text = args.text
            else:
                print('粘贴通知，可含多行；单独输入 END 结束：')
                lines = []
                while (line := input()) != 'END':
                    lines.append(line)
                text = '\n'.join(lines)
            record = extract_notice(text, args.reference_date)
            if confirm(record):
                append(args.file, record)
                print(f'已保存到 {args.file.resolve()}')
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
