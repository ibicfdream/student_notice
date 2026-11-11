import unittest
from datetime import date

from extractor import extract_notices


class CompetitionRegistrationTests(unittest.TestCase):
    def notice(self, label):
        return ('近期市教委将举办第二届北京市大学生“人工智能+”创新大赛，现将有关事项通知如下：\n'
                '一、大赛主旨\n培养实践能力，引导大学生参加创新实践。\n'
                '二、赛题设置\n设置11道赛题，包括机器人足球、论文研究等内容。\n'
                '三、' + label + '\n'
                '1.本次大赛采用团队形式参赛，每支参赛队伍学生人数3-5名，每名学生仅可参与1支队伍，每支队伍仅限参加1个赛题。\n'
                '2.本届大赛报名、资料上传等工作统一通过大赛官网（https://www.bjai-edu.cn）线上报送。\n'
                '3.各参赛队伍须于2026年11月7日前通过大赛报名系统完成初始报名，按要求填写参赛赛题、队伍成员和指导教师等信息。'
                '报名信息提交后，不得变更赛题、队伍成员和指导教师及其排列顺序。')

    def test_registration_is_independent_of_section_names_and_wrapping(self):
        for label in ('参赛说明', '参赛须知', '操作指引', '报名流程'):
            plain = self.notice(label)
            wrapped = '\n'.join(plain[index:index + 19] for index in range(0, len(plain), 19))
            for source in (plain, wrapped):
                with self.subTest(label=label, wrapped=source == wrapped):
                    rows = extract_notices(source, date(2026, 1, 1))
                    self.assertEqual(len(rows), 1)
                    row = rows[0]
                    self.assertIn('人工智能+创新大赛报名', row['task'])
                    self.assertEqual(row['deadline'], '2026-11-06')
                    self.assertIn('https://www.bjai-edu.cn', row['submit_method'])
                    self.assertEqual(row['category'], '竞赛科研')
                    self.assertIn('3-5名', row['requirements'])
                    self.assertIn('不得变更', row['requirements'])
                    self.assertEqual(row['source_text'], source)

    def test_conflicting_registration_deadlines_are_not_guessed(self):
        source = self.notice('参赛说明') + '\n本科生须于2026年11月8日前完成系统报名。'
        row = extract_notices(source, date(2026, 1, 1))[0]
        self.assertEqual(row['deadline'], '未提及')
        self.assertIn('多个报名截止', row['time_note'])
