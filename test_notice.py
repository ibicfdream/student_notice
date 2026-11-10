import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from extractor import extract_notice
from main import confirm
from storage import append, load


class NoticeTests(unittest.TestCase):
    def test_example(self):
        row = extract_notice('【教务处通知】2024-2025-2 学期选课补退选将于 3 月 12 日 12:00 结束，请未确认的同学登录教务系统完成操作，逾期不再受理。')
        self.assertEqual(row['task'], '选课补退选')
        self.assertEqual(row['deadline'], '2025-03-12 12:00')
        self.assertEqual(row['submit_method'], '教务系统')
        self.assertEqual(row['location'], '未提及')

    def test_deadline_priority(self):
        row = extract_notice('报名于3月1日09:00开始，截止3月12日18:00。', date(2025, 1, 1))
        self.assertEqual(row['deadline'], '2025-03-12 18:00')

    def test_date_precision(self):
        self.assertEqual(extract_notice('3月12日前提交材料', date(2025, 1, 1))['deadline'], '2025-03-12')

    def test_publication_is_not_event(self):
        for text in ('发布时间：2026年11月10日12:00\n请关注后续通知。',
                     '2026-11-10 12:00\n请关注后续通知。'):
            self.assertEqual(extract_notice(text)['deadline'], '未提及')
        row = extract_notice('发布时间：2026年11月10日12:00\n活动时间：2026年11月12日14:00')
        self.assertEqual(row['deadline'], '2026-11-12 14:00')
        row = extract_notice('发布时间：2026年11月10日12:00，11月13日18:00截止。', date(2026, 1, 1))
        self.assertEqual(row['deadline'], '2026-11-13 18:00')

    def test_cancel_keeps_original(self):
        row = extract_notice('选课补退选')
        original = row.copy()
        with patch('builtins.input', side_effect=['新事项', '', '', '', 'n']), patch('builtins.print'):
            self.assertFalse(confirm(row))
        self.assertEqual(row, original)

    def test_invalid_dates(self):
        for text in ('2025年2月30日12:00截止', '2025年3月12日25:00截止'):
            self.assertEqual(extract_notice(text)['deadline'], '未提及')

    def test_location_email(self):
        row = extract_notice('主题：项目申请\n地点：教学楼301室\n请发送到 student@example.edu，3月12日下午3点截止。', date(2025, 1, 1))
        self.assertEqual(row['deadline'], '2025-03-12 15:00')
        self.assertEqual(row['location'], '教学楼301室')
        self.assertIn('student@example.edu', row['submit_method'])

    def test_missing_and_empty(self):
        self.assertEqual(extract_notice('请关注后续消息')['deadline'], '未提及')
        with self.assertRaises(ValueError):
            extract_notice('   ')

    def test_storage_and_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            row = extract_notice('选课补退选')
            append(path, row)
            append(path, row)
            self.assertEqual(load(path), [row, row])
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                append(path, row)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')

    def test_edit_and_confirm(self):
        row = extract_notice('选课补退选')
        with patch('builtins.input', side_effect=['补选课程', '2025-02-30', '2025-03-12 18:00', '教务系统', '', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['task'], '补选课程')
        self.assertEqual(row['deadline'], '2025-03-12 18:00')
        self.assertEqual(row['submit_method'], '教务系统')
        self.assertEqual(row['source_text'], '选课补退选')

    def test_reedit_and_clear(self):
        row = extract_notice('选课补退选截止3月12日18:00')
        with patch('builtins.input', side_effect=['', '', '', '', 'e', '', '未提及', '', '', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['deadline'], '未提及')


if __name__ == '__main__':
    unittest.main()
