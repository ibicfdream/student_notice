"""图形界面的识别、编辑与保存回归，不启动真实窗口。"""
import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from extractor import extract_notices
from gui import NoticeWindow
from gui_forms import prepare_record
from storage import load


class GuiFlowTests(unittest.TestCase):
    def test_clear_date_invalidates_old_drafts_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            window = self.window(path)
            window.text.value = '奖学金申请明天18:00截止。'
            window.reference.value = '2026-11-13'
            asyncio.run(window.parse_text(None))
            self.assertTrue(window.drafts)
            window.clear_reference(None)
            self.assertEqual(window.reference.value, '')
            self.assertFalse(window.drafts)
            self.assertTrue(window.save_button.disabled)
            self.assertFalse(path.exists())

    def test_multiple_cards_keep_two_columns_and_editor_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            window = self.window(path)
            record = extract_notices('奖学金申请截止2026年12月1日。')[0]
            window.drafts = [dict(record, task=f'事项{i}') for i in range(1, 4)]
            window.render_records()
            self.assertEqual(len(window.results.controls), 2)
            self.assertEqual(len(window.results.controls[0].controls), 2)
            self.assertEqual(len(window.results.controls[1].controls), 2)
            window.editors[1]['task'].value = '第二栏修改'
            asyncio.run(window.save(None))
            self.assertEqual([r['task'] for r in load(path)], ['事项1', '第二栏修改', '事项3'])

    def test_optional_reference_uses_default_date(self):
        with tempfile.TemporaryDirectory() as directory:
            window = self.window(Path(directory) / 'todos.json')
            self.assertEqual(window.reference.value, '')
            window.text.value = '奖学金申请明天18:00截止。'
            with patch('extractor.current_reference_date', return_value=date(2026, 11, 13)):
                asyncio.run(window.parse_text(None))
            self.assertTrue(window.drafts)
            self.assertEqual(window.drafts[0]['deadline'], '2026-11-14 18:00')

    def test_optional_reference_rejects_invalid_nonempty_dates(self):
        with tempfile.TemporaryDirectory() as directory:
            window = self.window(Path(directory) / 'todos.json')
            window.text.value = '奖学金申请明天截止。'
            for raw in ('2026-02-30', '20261113'):
                window.reference.value = raw
                asyncio.run(window.parse_text(None))
                self.assertFalse(window.drafts)
                self.assertIn('发布日期无效', window.status.value)

    def window(self, path):
        page = SimpleNamespace(window=SimpleNamespace(), add=lambda *a: None,
                               update=lambda: None)
        return NoticeWindow(page, path)

    def test_text_edit_save_and_no_double_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            window = self.window(path)
            source = '奖学金申请截止2026年12月1日18:00，请登录学生服务平台提交。'
            window.text.value = source
            window.reference.value = '2026-11-11'
            asyncio.run(window.parse_text(None))
            self.assertTrue(window.drafts)
            self.assertFalse(path.exists())
            window.editors[0]['task'].value = '修改后的申请'
            window.editors[0]['deadline'].value = '2026-12-02 9'
            asyncio.run(window.save(None))
            rows = load(path)
            self.assertEqual(rows[0]['task'], '修改后的申请')
            self.assertEqual(rows[0]['deadline'], '2026-12-02 09:00')
            self.assertEqual(rows[0]['source_text'], source)
            asyncio.run(window.save(None))
            self.assertEqual(len(load(path)), len(rows))

    def test_invalid_time_does_not_write_and_keeps_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            window = self.window(path)
            window.text.value = '奖学金申请截止2026年12月1日18:00。'
            asyncio.run(window.parse_text(None))
            window.editors[0]['deadline'].value = '2026-02-30'
            asyncio.run(window.save(None))
            self.assertFalse(path.exists())
            self.assertTrue(window.drafts)
            self.assertIn('保存失败', window.status.value)

    def test_ocr_failure_does_not_leave_old_results(self):
        with tempfile.TemporaryDirectory() as directory:
            window = self.window(Path(directory) / 'todos.json')
            window.text.value = '奖学金申请截止2026年12月1日。'
            asyncio.run(window.parse_text(None))
            window.image_path = Path('example.png')
            with patch('gui.recognize', side_effect=ValueError('模拟识别失败')):
                asyncio.run(window.parse_image(None))
            self.assertFalse(window.drafts)
            self.assertTrue(window.save_button.disabled)

    def test_ocr_result_uses_same_confirmation_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            window = self.window(path)
            window.image_path = Path('example.png')
            source = '奖学金申请截止2026年12月1日。'
            with patch('gui.recognize', return_value=source):
                asyncio.run(window.parse_image(None))
            self.assertEqual(window.text.value, source)
            self.assertFalse(window.drafts)
            self.assertTrue(window.save_button.disabled)
            self.assertEqual(window.image_step.value, '请点击“识别正文”提取信息')
            asyncio.run(window.parse_text(None))
            self.assertTrue(window.drafts)
            self.assertFalse(path.exists())
            window.clear_results(None)
            self.assertFalse(path.exists())

    def test_edit_does_not_mutate_extraction(self):
        original = extract_notices('奖学金申请4月1日前提交。', date(2026, 1, 1))[0]
        edited = prepare_record(original, {'deadline': '2026-04-05'})
        self.assertEqual(original['deadline_boundary'], 'exclusive_date')
        self.assertNotIn('deadline_boundary', edited)
        self.assertEqual(edited['deadline'], '2026-04-05')


if __name__ == '__main__':
    unittest.main()
