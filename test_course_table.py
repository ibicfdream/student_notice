import tempfile
import unittest
from datetime import date
from pathlib import Path

from course_table import HEADER, render_course_table
from extractor import extract_notices
from reminders import enrich
from storage import append_many, load


class CourseTableTests(unittest.TestCase):
    def fixture(self):
        texts = list(HEADER)
        boxes = [[100 + i * 150, 0, 200 + i * 150, 20] for i in range(5)]
        # 以主题和教师的读取顺序打乱，仍须依坐标绑定，不能依输入顺序配对。
        texts += ['10月31日', '9:00-11:00', '三教', '310', '党章', '2学时', '吕佳',
                  '10月31日', '14:00-16:00', '党的性质', '2学时', '赵少华']
        boxes += [[110, 40, 180, 56], [110, 62, 200, 78], [260, 40, 300, 56], [260, 62, 300, 78],
                  [410, 48, 480, 68], [560, 48, 600, 68], [710, 48, 750, 68],
                  [110, 100, 180, 116], [110, 122, 200, 138], [410, 108, 480, 128],
                  [560, 108, 600, 128], [710, 108, 750, 128]]
        return dict(rec_texts=list(reversed(texts)), rec_boxes=list(reversed(boxes)))

    def test_geometry_keeps_rows_and_does_not_borrow_missing_room(self):
        text = render_course_table(self.fixture())
        rows = extract_notices(text, date(2026, 1, 1))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['task'], '党章')
        self.assertEqual(rows[0]['location'], '三教310')
        self.assertEqual(rows[0]['teacher'], '吕佳')
        self.assertEqual(rows[0]['deadline'], '2026-10-31 09:00')
        self.assertEqual(rows[0]['end_time'], '2026-10-31 11:00')
        self.assertEqual(rows[1]['task'], '党的性质')
        self.assertEqual(rows[1]['location'], '未提及')
        self.assertEqual(rows[1]['teacher'], '赵少华')
        self.assertEqual(rows[1]['deadline'], '2026-10-31 14:00')
        self.assertEqual(rows[1]['end_time'], '2026-10-31 16:00')
        self.assertEqual([r['time'] for r in enrich(rows[0])['reminder_times']],
                         ['2026-10-30 09:00', '2026-10-31 09:00', '2026-10-31 09:00'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'courses.json'
            append_many(path, rows)
            saved = load(path)
            self.assertEqual(saved[1]['teacher'], '赵少华')
            self.assertEqual(saved[1]['end_time'], '2026-10-31 16:00')

    def test_plain_ocr_is_not_forced_into_table(self):
        self.assertIsNone(render_course_table(dict(rec_texts=['活动时间：10月31日'], rec_boxes=[[0, 0, 100, 20]])))
        self.assertIsNone(render_course_table(dict(rec_texts=list(HEADER))))

    def test_wide_topic_fragments_do_not_move_into_hours_column(self):
        texts = list(HEADER) + ['11月1日', '14:00-16:00', '三教310', '根本方向', '——习', '近平新时代', '2学时', '王冬梅']
        boxes = [[179, 80, 223, 110], [296, 80, 341, 110], [480, 80, 523, 110],
                 [663, 80, 707, 110], [747, 80, 817, 110],
                 [168, 301, 232, 329], [149, 330, 253, 349], [298, 302, 340, 332],
                 [374, 305, 584, 322], [598, 304, 631, 324], [381, 330, 621, 347],
                 [658, 312, 710, 341], [753, 312, 812, 341]]
        row = extract_notices(render_course_table(dict(rec_texts=texts, rec_boxes=boxes)))[0]
        self.assertEqual(row['task'], '根本方向——习近平新时代')
        self.assertEqual(row['course_hours'], '2学时')

    def test_malformed_table_does_not_silently_shift_columns(self):
        with self.assertRaises(ValueError):
            extract_notices('\t'.join(HEADER) + '\n10月31日\t党章')
