import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from extractor import extract_notice, extract_notices
from main import confirm, confirm_notices, show_todos, normalize_time_input
from storage import append, append_many, load
from categories import RULES, classify
from reminders import plan, enrich


class NoticeTests(unittest.TestCase):
    INNOVATION_NOTICE = ('转发自辅导员：\n转发自学院通知 <<<\n【重要】2025年大学生创新创业训练计划项目申报\n'
                         '1. 3月30日前：团队组建+选题，在系统（http://cxcy.school.edu.cn）填报\n'
                         '2. 4月15日前：提交申报书初稿给指导老师审核\n'
                         '3. 4月30日前：系统终稿提交+纸质版交至教务处（行政楼201）\n'
                         '请各班班长通知到每位同学，逾期系统关闭 <<<')

    def test_innovation_subject_not_date_and_forwarding_wrapper(self):
        rows = extract_notices(self.INNOVATION_NOTICE, date(2026, 1, 1))
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(row['notice_subject'], '大学生创新创业训练计划项目申报')
            self.assertTrue(row['task'].startswith('大学生创新创业训练计划项目申报—'))
            self.assertNotIn('月', row['task'])
            self.assertNotIn('转发', row['task'])
            self.assertNotIn('日前', row['stage'])
            self.assertEqual(row['category'], '竞赛科研')
        self.assertEqual([row['deadline'] for row in rows], ['2025-03-29', '2025-03-29', '2025-04-14', '2025-04-29', '2025-04-29'])
        self.assertIn('组建团队与选题', rows[0]['task'])
        self.assertIn('系统填报', rows[1]['task'])
        self.assertEqual(rows[1]['submit_method'], '系统：http://cxcy.school.edu.cn')
        self.assertIn('初稿审核', rows[2]['task'])
        self.assertEqual(rows[2]['submit_method'], '交指导老师审核')
        self.assertIn('系统终稿提交', rows[3]['task'])
        self.assertEqual(rows[3]['submit_method'], '系统：http://cxcy.school.edu.cn')
        self.assertEqual(rows[4]['submit_method'], '纸质提交')
        self.assertEqual(rows[4]['location'], '教务处(行政楼201)')
        self.assertEqual(rows[4]['time_binding'], 'stage_heading')

    def test_project_subject_also_available_without_stage_parsing(self):
        row = extract_notice(self.INNOVATION_NOTICE, date(2026, 1, 1))
        self.assertEqual(row['task'], '大学生创新创业训练计划项目申报')
        self.assertEqual(row['category'], '竞赛科研')

    def test_forwarded_generic_title_is_not_sender(self):
        row = extract_notice('转发自辅导员：\n转发自学院通知 <<<\n【重要】学生服务问卷调查\n请关注后续通知。')
        self.assertEqual(row['task'], '学生服务问卷调查')

    def test_manual_time_accepts_hour_without_minutes(self):
        examples = {
            '2026-11-17 14': '2026-11-17 14:00',
            '2026-11-17 2': '2026-11-17 02:00',
            '2026-11-17 14:30': '2026-11-17 14:30',
            '2026-11-17 14：30': '2026-11-17 14:30',
            '2026-11-17': '2026-11-17',
            '2026-1-7 9': '2026-01-07 09:00',
            '2026-11-17T14': '2026-11-17 14:00',
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_time_input(value), expected)
        for value in ('2026-11-17 25', '2026-02-30 14', '2026-11-17 14:60', '14'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_time_input(value)

    def test_manual_hour_applies_to_both_range_endpoints(self):
        row = extract_notices(self.FITNESS_NOTICE)[0]
        row['end_time'] = '未提及'
        with patch('builtins.input', side_effect=['2', '2026-11-17 14', '6', '2026-11-17 16', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['deadline'], '2026-11-17 14:00')
        self.assertEqual(row['end_time'], '2026-11-17 16:00')

    FITNESS_NOTICE = '体测补测：下周二下午2点，田径场。没过的同学必须来，过的不用来。'

    def test_brief_fitness_fields_belong_to_their_own_places(self):
        row = extract_notices(self.FITNESS_NOTICE, date(2026, 11, 10))[0]
        self.assertEqual(row['task'], '体测补测')
        self.assertEqual(row['deadline'], '2026-11-17 14:00')
        self.assertEqual(row['time_role'], '活动开始')
        self.assertEqual(row['location'], '田径场')
        self.assertEqual(row['submit_method'], '现场参加')
        self.assertEqual(row['prerequisite'], '体测未通过')
        self.assertEqual(row['excluded_audience'], '体测已通过者无需参加')
        self.assertEqual(row['category'], '课程学业')
        for extra in ('下周', '2点', '田径场', '同学'):
            self.assertNotIn(extra, row['task'])
        self.assertNotIn('下周二', row['requirements'])
        self.assertNotIn('田径场', row['requirements'])

    def test_brief_fitness_without_reference_still_has_clean_name(self):
        row = extract_notices(self.FITNESS_NOTICE)[0]
        self.assertEqual(row['task'], '体测补测')
        self.assertEqual(row['deadline'], '未提及')
        self.assertEqual(row['location'], '田径场')
        self.assertEqual(row['prerequisite'], '体测未通过')

    def test_brief_subject_and_absolute_date(self):
        row = extract_notices('体测补测：2026年11月17日14:00，田径场。没过的同学必须来，过的不用来。')[0]
        self.assertEqual(row['task'], '体测补测')
        self.assertEqual(row['deadline'], '2026-11-17 14:00')
        self.assertEqual(row['location'], '田径场')
        self.assertEqual(row['excluded_audience'], '体测已通过者无需参加')
        row = extract_notices('社团面试：下周二下午两点，学生活动中心。', date(2026, 11, 10))[0]
        self.assertEqual(row['task'], '社团面试')
        self.assertNotIn('下周', row['task'])
        self.assertEqual(row['location'], '学生活动中心')

    def test_unknown_task_does_not_copy_time_and_location(self):
        row = extract_notices('下周二下午2点，田径场。请留意通知。', date(2026, 11, 10))[0]
        self.assertEqual(row['task'], '未提及')

    CHAT_NOTICE = ('📢 @所有人 明天（周四）中午12点前把实习证明拍照发我微信，'
                   '没交的话这周五之前必须交纸质版到经管楼507，不然实习学分不给录。'
                   '另外下周三下午2点有个实习分享会，想参加的在群里接龙')

    def test_colloquial_three_independent_tasks(self):
        rows = extract_notices(self.CHAT_NOTICE, date(2026, 11, 11))
        self.assertEqual(len(rows), 3)
        photo, paper, meeting = rows
        self.assertEqual(photo['task'], '提交实习证明照片')
        self.assertEqual(photo['deadline'], '2026-11-12 12:00')
        self.assertIn('微信', photo['submit_method'])
        self.assertEqual(photo['location'], '未提及')
        self.assertEqual(paper['task'], '提交实习证明纸质版')
        self.assertEqual(paper['deadline'], '2026-11-12')
        self.assertEqual(paper['submit_method'], '纸质提交')
        self.assertEqual(paper['location'], '经管楼507')
        self.assertEqual(paper['prerequisite'], '前述材料尚未提交')
        self.assertIn('实习学分不给录', paper['consequence'])
        self.assertTrue(paper['material_inferred'])
        self.assertEqual(photo['submission_group'], paper['submission_group'])
        self.assertEqual(meeting['task'], '参加实习分享会')
        self.assertEqual(meeting['deadline'], '2026-11-18 14:00')
        self.assertEqual(meeting['time_role'], '活动开始')
        self.assertEqual(meeting['submit_method'], '群接龙')
        self.assertEqual(meeting['location'], '未提及')
        self.assertTrue(meeting['optional'])
        self.assertTrue(all(row['category'] == '就业实习' for row in rows))

    def test_colloquial_requires_notice_date(self):
        rows = extract_notices(self.CHAT_NOTICE)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual(row['deadline'], '未提及')
            self.assertTrue(row['reference_required'])
            self.assertEqual(enrich(row)['reminder_times'], [])
            self.assertIn('通知发布时间', row['reminder_note'])

    def test_colloquial_weekday_conflict_blocks_relative_dates(self):
        rows = extract_notices(self.CHAT_NOTICE, date(2026, 11, 10))
        for row in rows:
            self.assertEqual(row['deadline'], '未提及')
            self.assertTrue(row['weekday_conflict'])
            self.assertEqual(enrich(row)['reminder_times'], [])

    def test_colloquial_chinese_clock_and_week_boundaries(self):
        from colloquial import resolve_day
        row = extract_notices('明天下午两点有个实习分享会，想参加的在群里接龙', date(2026, 11, 11))[0]
        self.assertEqual(row['deadline'], '2026-11-12 14:00')
        self.assertEqual(resolve_day('下周三', date(2026, 12, 31))[0], date(2027, 1, 6))
        self.assertEqual(resolve_day('这周五', date(2026, 11, 15))[0], date(2026, 11, 13))
        self.assertEqual(resolve_day('后天', date(2024, 2, 28))[0], date(2024, 3, 1))

    def test_colloquial_manual_time_and_saved_conditions(self):
        rows = extract_notices(self.CHAT_NOTICE)
        with patch('builtins.input', side_effect=['2', '2026-11-12 12:00', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(rows[0]))
        self.assertTrue(rows[0]['reminder_times'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append_many(path, rows)
            saved = load(path)
            self.assertEqual(saved[1]['prerequisite'], '前述材料尚未提交')
            self.assertEqual(saved[2]['submit_method'], '群接龙')
            self.assertEqual(saved[0]['deadline'], '2026-11-12 12:00')

    GRADUATION_NOTICE = ('【教务处】关于2025届毕业生毕业去向登记及去向落实材料提交的通知\n'
                         '一、信息核对：请于4月10日-4月15日登录就业系统核对个人信息，有误者于4月15日17:00前持身份证至就业指导中心（行政楼108）现场修改。\n'
                         '二、材料提交：签约/升学/创业等去向证明材料请于5月20日17:00前上传至就业系统，纸质版交至学院学工办。\n'
                         '三、档案转递：6月10日-6月20日集中办理档案转递，需调档函的同学请于5月30日前到行政楼108领取。')

    def test_generic_inline_stages_and_six_graduation_actions(self):
        rows = extract_notices(self.GRADUATION_NOTICE, date(2025, 1, 1))
        self.assertEqual(len(rows), 6)
        check, correction, upload, paper, transfer, letter = rows
        self.assertEqual([row['stage'] for row in rows], ['信息核对', '信息核对', '材料提交', '材料提交', '档案转递', '档案转递'])
        self.assertEqual(check['deadline'], '2025-04-10')
        self.assertEqual(check['end_time'], '2025-04-15')
        self.assertEqual(check['submit_method'], '就业系统')
        self.assertEqual(check['location'], '未提及')
        self.assertEqual(correction['deadline'], '2025-04-15 17:00')
        self.assertEqual(correction['prerequisite'], '个人信息有误')
        self.assertIn('身份证', correction['requirements'])
        self.assertEqual(correction['location'], '就业指导中心(行政楼108)')
        self.assertEqual(upload['deadline'], '2025-05-20 17:00')
        self.assertEqual(upload['submit_method'], '就业系统')
        self.assertEqual(upload['location'], '未提及')
        self.assertEqual(paper['deadline'], '2025-05-20 17:00')
        self.assertEqual(paper['time_binding'], 'parallel_material_inferred')
        self.assertTrue(paper['deadline_inferred'])
        self.assertEqual(paper['submission_group'], upload['submission_group'])
        self.assertEqual(paper['location'], '学院学工办')
        self.assertEqual(paper['submit_method'], '纸质提交')
        self.assertEqual(transfer['deadline'], '2025-06-10')
        self.assertEqual(transfer['end_time'], '2025-06-20')
        self.assertEqual(letter['deadline'], '2025-05-29')
        self.assertEqual(letter['location'], '行政楼108')
        self.assertEqual(letter['prerequisite'], '需要调档函')
        self.assertTrue(all(row['category'] == '就业实习' for row in rows))

    def test_inline_and_newline_stage_formats_equivalent(self):
        inline = extract_notices(self.GRADUATION_NOTICE, date(2025, 1, 1))
        separated = extract_notices(self.GRADUATION_NOTICE.replace('信息核对：', '信息核对\n').replace('材料提交：', '材料提交\n').replace('档案转递：', '档案转递\n'), date(2025, 1, 1))
        fields = ('stage', 'task', 'deadline', 'submit_method', 'location')
        self.assertEqual([[row[key] for key in fields] for row in inline], [[row[key] for key in fields] for row in separated])

    def test_stage_explicit_shared_deadline_only(self):
        rows = extract_notices('事项：项目材料办理\n一、材料提交：请于5月20日17:00前上传材料，同时提交纸质版至学院学工办。\n二、领取：请于5月22日12:00前到行政楼108领取。', date(2025, 1, 1))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['deadline'], '2025-05-20 17:00')
        self.assertEqual(rows[1]['deadline'], '2025-05-20 17:00')
        self.assertEqual(rows[1]['time_binding'], 'shared_explicit')
        self.assertEqual(rows[2]['deadline'], '2025-05-22 12:00')

    def test_parallel_material_own_deadline_has_priority(self):
        source = self.GRADUATION_NOTICE.replace('纸质版交至学院学工办', '纸质版于5月21日12:00前交至学院学工办')
        paper = extract_notices(source, date(2025, 1, 1))[3]
        self.assertEqual(paper['deadline'], '2025-05-21 12:00')
        self.assertEqual(paper['time_binding'], 'own_action')
        self.assertFalse(paper.get('deadline_inferred', False))

    def test_parallel_material_does_not_cross_sentence_or_stage(self):
        for source in (
            '材料办理\n一、提交材料：请于5月20日17:00前上传材料至就业系统。纸质版交至学院学工办。\n二、其它：请咨询负责人。',
            '材料办理\n一、电子提交：请于5月20日17:00前上传材料至就业系统。\n二、纸质提交：纸质版交至学院学工办。',
            '材料办理\n一、提交材料：请于5月20日17:00前上传材料至就业系统，纸质版交至学院学工办，时间另行通知。\n二、其它：请咨询负责人。',
            '材料办理\n一、提交材料：请于5月20日17:00前上传材料至就业系统，随后补交纸质版至学院学工办。\n二、其它：请咨询负责人。',
        ):
            with self.subTest(source=source):
                rows = extract_notices(source, date(2025, 1, 1))
                paper = next(row for row in rows if row['submit_method'] == '纸质提交')
                self.assertEqual(paper['deadline'], '未提及')
                self.assertFalse(paper.get('deadline_inferred', False))

    def test_parallel_material_can_override_and_persists(self):
        rows = extract_notices(self.GRADUATION_NOTICE, date(2025, 1, 1))
        paper = rows[3]
        self.assertEqual(enrich(paper)['reminder_times'], enrich(rows[2])['reminder_times'])
        with patch('builtins.input', side_effect=['2', '2025-05-21 12:00', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(paper))
        self.assertFalse(paper['deadline_inferred'])
        self.assertEqual(paper['time_binding'], 'manual')
        self.assertEqual(rows[2]['deadline'], '2025-05-20 17:00')
        self.assertEqual(paper['deadline'], '2025-05-21 12:00')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append_many(path, rows)
            self.assertEqual(load(path)[3]['time_binding'], 'manual')

    def test_unknown_stage_is_preserved(self):
        rows = extract_notices('办理安排\n一、信息核对：4月10日-4月15日登录就业系统核对信息。\n二、其它说明：特殊情况请咨询负责人。', date(2025, 1, 1))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['stage'], '其它说明')
        self.assertIn('咨询负责人', rows[1]['source_segment'])
        self.assertIn('未能可靠拆分', rows[1]['time_note'])

    def test_stage_common_deadline_scope_and_own_time_priority(self):
        source = ('项目办理\n一、材料提交：统一截止时间：5月20日17:00。上传材料至就业系统，纸质版交至学院学工办。'
                  '请于5月19日12:00前到行政楼108领取回执。\n二、后续办理：提交补充材料。')
        rows = extract_notices(source, date(2025, 1, 1))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]['deadline'], '2025-05-20 17:00')
        self.assertEqual(rows[1]['deadline'], '2025-05-20 17:00')
        self.assertEqual(rows[1]['time_binding'], 'stage_explicit_shared')
        self.assertEqual(rows[2]['deadline'], '2025-05-19 12:00')
        self.assertEqual(rows[3]['deadline'], '未提及')

    THESIS_NOTICE = ('【研究生院】关于2025届毕业生论文盲审及答辩安排的通知\n'
                     '一、论文盲审\n'
                     '3月30日前，导师审核通过的同学登录研究生管理系统上传终稿PDF（≤20MB），命名格式：学号姓名论文题目。盲审结果预计4月15日前后公布。\n'
                     '二、答辩安排\n'
                     '通过盲审的同学请于4月20日-4月30日期间参加答辩，具体时间地点由导师另行通知。\n'
                     '三、材料归档\n'
                     '答辩通过后3个工作日内，提交纸质版论文3本至学院教务办公室（理科楼A201），同时上传电子版至图书馆学位论文系统。')

    def test_thesis_stages_and_independent_actions(self):
        rows = extract_notices(self.THESIS_NOTICE, date(2025, 1, 1))
        self.assertEqual(len(rows), 5)
        upload, result, defense, paper, electronic = rows
        self.assertEqual([row['stage'] for row in rows], ['论文盲审', '论文盲审', '答辩安排', '材料归档', '材料归档'])
        self.assertEqual(upload['deadline'], '2025-03-29')
        self.assertEqual(upload['prerequisite'], '导师审核通过')
        self.assertEqual(upload['submit_method'], '研究生管理系统')
        self.assertIn('20MB', upload['requirements'])
        self.assertIn('命名格式', upload['requirements'])
        self.assertEqual(result['time_kind'], 'approximate')
        self.assertEqual(result['time_expression'], '4月15日前后')
        self.assertEqual(result['deadline'], '未提及')
        self.assertEqual(defense['deadline'], '2025-04-20')
        self.assertEqual(defense['end_time'], '2025-04-30')
        self.assertEqual(defense['location'], '未提及')
        self.assertEqual(defense['prerequisite'], '通过盲审')
        self.assertEqual(paper['submit_method'], '纸质提交')
        self.assertIn('3本', paper['requirements'])
        self.assertIn('学院教务办公室', paper['location'])
        self.assertIn('理科楼A201', paper['location'])
        self.assertEqual(electronic['submit_method'], '图书馆学位论文系统')
        self.assertEqual(electronic['location'], '未提及')
        self.assertTrue(all(row['category'] == '竞赛科研' for row in rows))

    def test_thesis_relative_deadline_not_calculated_from_planned_end(self):
        rows = extract_notices(self.THESIS_NOTICE, date(2025, 1, 1))
        for row in rows[-2:]:
            self.assertEqual(row['deadline'], '未提及')
            self.assertEqual(row['time_kind'], 'relative')
            self.assertEqual(row['depends_on_event'], '答辩通过')
            self.assertEqual(row['relative_offset']['unit'], '工作日')
            self.assertEqual(row['time_expression'], '答辩通过后3个工作日内')
            self.assertEqual(enrich(row)['reminder_times'], [])
        self.assertEqual(enrich(rows[1])['reminder_times'], [])

    def test_approximate_date_not_exact_deadline(self):
        for sentence in ('结果预计4月15日前后公布。', '结果于4月15日左右公布。'):
            self.assertEqual(extract_notice(sentence, date(2025, 1, 1))['deadline'], '未提及')

    def test_thesis_metadata_persists_and_manual_reminder_date(self):
        rows = extract_notices(self.THESIS_NOTICE, date(2025, 1, 1))
        paper = rows[-2]
        with patch('builtins.input', side_effect=['2', '2025-05-08', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(paper))
        self.assertEqual(paper['deadline'], '2025-05-08')
        self.assertTrue(paper['reminder_times'])
        self.assertEqual(paper['time_expression'], '答辩通过后3个工作日内')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append_many(path, rows)
            saved = load(path)
            self.assertEqual(len(saved), 5)
            self.assertEqual(saved[-1]['relative_offset']['unit'], '工作日')
            self.assertEqual(saved[1]['time_kind'], 'approximate')
            self.assertEqual(saved[-2]['deadline'], '2025-05-08')

    REPAIR_NOTICE = ('【后勤集团】关于学生宿舍空调维修的通知\n'
                     '3月18日至3月22日每天9:00-17:00，后勤维修组将在各宿舍楼值班，接受空调报修登记。'
                     '同学可前往本楼宿管阿姨处登记，或拨打报修热线：010-87654321。紧急故障可随时联系。')

    def test_repair_actual_notice_window_and_channels(self):
        rows = extract_notices(self.REPAIR_NOTICE, date(2026, 1, 1))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['deadline'], '2026-03-18')
        self.assertEqual(row['end_time'], '2026-03-22')
        self.assertEqual(row['service_hours'], '每天9:00-17:00')
        self.assertEqual(row['time_role'], '维修开始')
        self.assertEqual(row['end_time_label'], '维修结束时间')
        self.assertEqual(row['location'], '各宿舍楼')
        self.assertEqual(row['submit_method'], '本楼宿管阿姨处登记；报修热线：010-87654321')
        self.assertEqual(row['service_note'], '紧急故障可随时联系')
        self.assertEqual(row['category'], '生活服务')
        self.assertEqual(enrich(row)['reminder_times'], [{'label': '提前1天', 'time': '2026-03-17'}])

    def test_repair_category_priority_and_dorm_administration(self):
        for task in ('学生宿舍空调维修', '宿舍设备报修', '后勤维修', '宿舍空调保修', '宿舍水电检修'):
            self.assertEqual(classify(task, task)['category'], '生活服务')
        for task in ('宿舍申请', '宿舍分配', '宿舍调换', '调宿申请'):
            self.assertEqual(classify(task + '，维修记录作为附件', task)['category'], '行政事务')
        self.assertEqual(classify('奖学金申请通知，宿舍维修不影响申请', '奖学金申请')['category'], '行政事务')

    def test_repair_date_range_variants(self):
        for span in ('4月1日至5日', '4月1日至4月5日', '4月1日—4月5日'):
            row = extract_notice('空调维修通知\n维修时间：' + span, date(2026, 1, 1))
            self.assertEqual(row['deadline'], '2026-04-01')
            self.assertEqual(row['end_time'], '2026-04-05')
        row = extract_notice('维修时间：4月1日9:00-17:00', date(2026, 1, 1))
        self.assertEqual(row['deadline'], '2026-04-01 09:00')
        self.assertEqual(row['end_time'], '2026-04-01 17:00')

    def test_repair_hotline_no_number_and_registration_place(self):
        row = extract_notice('空调维修通知，同学可到宿管阿姨处登记，或拨打保修热线。')
        self.assertIn('宿管阿姨处登记', row['submit_method'])
        self.assertIn('保修热线（号码未提及）', row['submit_method'])
        self.assertEqual(row['location'], '未提及')

    def test_repair_range_edit_and_status(self):
        row = extract_notices(self.REPAIR_NOTICE, date(2026, 1, 1))[0]
        with patch('builtins.input', side_effect=['7', '每天10:00-16:00', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['service_hours'], '每天10:00-16:00')
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 3, 20, 12, 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append(path, row)
            with patch('main.datetime', FixedDatetime), patch('builtins.print') as output:
                show_todos(path, None)
            shown = '\n'.join(str(call.args[0]) for call in output.call_args_list if call.args)
            self.assertIn('[进行中]', shown)
            self.assertIn('2026-03-18 至 2026-03-22', shown)

    RECRUITMENT_NOTICE = ('【就业指导中心】字节跳动2025届春季校园招聘宣讲会\n'
                          '时间：3月22日（周六）19:00-21:00\n地点：图书馆报告厅\n'
                          '面向人群：2025届毕业生（本科/硕士/博士）\n'
                          '参与方式：无需报名，直接到场即可。现场可投递简历（纸质版），建议携带多份。\n'
                          '网申通道：https://job.bytedance.com/campus（截止4月15日）')

    def test_recruitment_activity_and_online_channels(self):
        onsite, online = extract_notices(self.RECRUITMENT_NOTICE, date(2026, 1, 1))
        self.assertEqual(onsite['deadline'], '2026-03-22 19:00')
        self.assertEqual(onsite['end_time'], '2026-03-22 21:00')
        self.assertEqual(onsite['time_role'], '活动开始')
        self.assertEqual(onsite['location'], '图书馆报告厅')
        self.assertIn('无需报名', onsite['submit_method'])
        self.assertIn('直接到场', onsite['submit_method'])
        self.assertIn('纸质版', onsite['submit_method'])
        self.assertNotIn('https://', onsite['submit_method'])
        self.assertEqual(online['deadline'], '2026-04-15')
        self.assertEqual(online['time_role'], '网申截止')
        self.assertEqual(online['location'], '未提及')
        self.assertNotIn('end_time', online)
        self.assertEqual(online['submit_method'], '网申通道：https://job.bytedance.com/campus')
        self.assertNotIn('纸质', online['submit_method'])
        self.assertEqual(onsite['category'], '就业实习')
        self.assertEqual(online['category'], '就业实习')
        self.assertEqual(enrich(onsite)['reminder_times'][0]['time'], '2026-03-15 19:00')
        self.assertEqual(enrich(online)['reminder_times'][0]['time'], '2026-04-08')

    def test_recruitment_online_missing_deadline_not_borrowed(self):
        source = self.RECRUITMENT_NOTICE.replace('（截止4月15日）', '')
        onsite, online = extract_notices(source, date(2026, 1, 1))
        self.assertEqual(onsite['deadline'], '2026-03-22 19:00')
        self.assertEqual(online['deadline'], '未提及')
        self.assertEqual(enrich(online)['reminder_times'], [])

    def test_recruitment_explicit_year_and_online_deadline_field(self):
        source = self.RECRUITMENT_NOTICE.replace('2025届春季', '2025年春季').replace('（截止4月15日）', '\n网申截止时间：4月15日17:00')
        onsite, online = extract_notices(source, date(2026, 1, 1))
        self.assertEqual(onsite['deadline'], '2025-03-22 19:00')
        self.assertEqual(online['deadline'], '2025-04-15 17:00')
        self.assertEqual(online['submit_method'], '网申通道：https://job.bytedance.com/campus')

    def test_url_does_not_include_deadline_parentheses(self):
        row = extract_notice('网申通道：https://example.edu/apply（截止4月15日）', date(2026, 1, 1))
        self.assertEqual(row['submit_method'], 'https://example.edu/apply')

    VOLUNTEER_NOTICE = ('【学生会】“春日市集”校园文化节志愿者招募\n'
                        '招募人数：30人\n报名时间：即日起至3月20日\n'
                        '报名方式：扫描附件二维码填写问卷，或前往大学生活动中心105现场报名\n'
                        '活动地点：学校中心广场\n活动时间：3月28日 14:00-18:00\n'
                        '志愿服务时长可录入第二课堂系统。')

    def test_registration_and_event_roles(self):
        registration, event = extract_notices(self.VOLUNTEER_NOTICE, date(2026, 1, 1))
        self.assertEqual(registration['deadline'], '2026-03-20')
        self.assertEqual(registration['time_role'], '报名截止')
        self.assertIn('问卷', registration['submit_method'])
        self.assertIn('现场报名', registration['submit_method'])
        self.assertNotIn('第二课堂', registration['submit_method'])
        self.assertEqual(registration['location'], '大学生活动中心105')
        self.assertEqual(event['deadline'], '2026-03-28 14:00')
        self.assertEqual(event['end_time'], '2026-03-28 18:00')
        self.assertEqual(event['time_role'], '活动开始')
        self.assertEqual(event['submit_method'], '未提及')
        self.assertEqual(event['location'], '学校中心广场')
        self.assertEqual(event['category'], '活动实践')
        self.assertEqual(enrich(registration)['reminder_times'][0]['time'], '2026-03-19')
        self.assertEqual(enrich(event)['reminder_times'][0]['time'], '2026-03-27 14:00')

    def test_clock_range_is_not_month_day(self):
        for separator in ('-', '~', '～', '—', '至'):
            row = extract_notice(f'活动时间：3月28日14:00{separator}18:00', date(2026, 1, 1))
            self.assertEqual(row['deadline'], '2026-03-28 14:00')
        self.assertEqual(extract_notice('报名时间：即日起至3月20日', date(2026, 1, 1))['deadline'], '2026-03-20')

    def test_labeled_registration_date_range_and_cross_day_event(self):
        rows = extract_notices('事项：春日市集志愿者招募\n报名时间：2025年3月10日至3月20日\n'
                               '活动时间：2025年3月28日14:00至3月29日18:00', date(2026, 1, 1))
        self.assertEqual(rows[0]['deadline'], '2025-03-20')
        self.assertEqual(rows[1]['deadline'], '2025-03-28 14:00')
        self.assertEqual(rows[1]['end_time'], '2025-03-29 18:00')

    def test_activity_end_edit_and_persistence(self):
        event = extract_notices(self.VOLUNTEER_NOTICE, date(2026, 1, 1))[1]
        with patch('builtins.input', side_effect=['6', '2026-03-28 13:00', '2026-03-28 19:00', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(event))
        self.assertEqual(event['end_time'], '2026-03-28 19:00')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append(path, event)
            self.assertEqual(load(path)[0]['end_time'], '2026-03-28 19:00')
            self.assertEqual(load(path)[0]['time_role'], '活动开始')
    MULTI_NOTICE = ('【团委】关于举办2025年“挑战杯”大学生课外学术科技作品竞赛院级选拔赛的通知\n'
                    '参赛团队请于3月25日17:00前将申报书（PDF版）发送至邮箱 xiaoming@school.edu.cn，'
                    '邮件主题须命名为“挑战杯+团队名+负责人姓名”。'
                    '纸质版材料一式三份于3月26日12:00前交至文科楼302办公室王老师处。逾期不予受理。')

    def test_multi_deadlines_bound_to_actions(self):
        rows = extract_notices(self.MULTI_NOTICE, date(2026, 11, 10))
        self.assertEqual(len(rows), 2)
        first, second = rows
        self.assertEqual(first['deadline'], '2025-03-25 17:00')
        self.assertEqual(second['deadline'], '2025-03-26 12:00')
        self.assertIn('申报书电子版', first['task'])
        self.assertIn('纸质材料', second['task'])
        self.assertIn('xiaoming@school.edu.cn', first['submit_method'])
        self.assertNotIn('纸质', first['submit_method'])
        self.assertNotIn('xiaoming', second['submit_method'])
        self.assertIn('纸质', second['submit_method'])
        self.assertEqual(first['location'], '未提及')
        self.assertEqual(second['location'], '文科楼302办公室')
        self.assertEqual(first['category'], '竞赛科研')
        self.assertEqual(second['source_text'], self.MULTI_NOTICE)
        self.assertNotIn('xiaoming', second['source_segment'])

    def test_start_end_stays_one_task(self):
        rows = extract_notices('考试报名于3月1日09:00开始，截止3月12日18:00。', date(2025, 1, 1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['deadline'], '2025-03-12 18:00')

    def test_two_deadlines_in_one_sentence(self):
        rows = extract_notices('报名截止3月12日18:00，缴费请于3月13日12:00前完成。', date(2025, 1, 1))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['deadline'], '2025-03-12 18:00')
        self.assertEqual(rows[1]['deadline'], '2025-03-13 12:00')

    def test_before_send_and_handover_time(self):
        for action in ('前将申报书发送至邮箱', '前交至教学楼', '前递交材料'):
            self.assertEqual(extract_notice('3月25日17:00' + action, date(2025, 1, 1))['deadline'], '2025-03-25 17:00')

    def test_batch_edit_and_cancel_are_atomic(self):
        rows = extract_notices(self.MULTI_NOTICE)
        original = [row.copy() for row in rows]
        with patch('builtins.input', side_effect=['2', '1', '纸质版申报材料提交', 'y', 'n']), patch('builtins.print'):
            self.assertFalse(confirm_notices(rows))
        self.assertEqual(rows, original)
        with patch('builtins.input', side_effect=['2', '1', '纸质版申报材料提交', 'y', 'y']), patch('builtins.print'):
            self.assertTrue(confirm_notices(rows))
        self.assertEqual(rows[1]['task'], '纸质版申报材料提交')
        self.assertEqual(rows[0]['task'], original[0]['task'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'todos.json'
            append_many(path, rows)
            self.assertEqual(len(load(path)), 2)
            content = path.read_text(encoding='utf-8')
            bad = rows[0].copy()
            bad['category'] = '错误分类'
            with self.assertRaises(ValueError):
                append_many(path, [rows[0], bad])
            self.assertEqual(path.read_text(encoding='utf-8'), content)

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
        self.assertEqual(extract_notice('3月12日前提交材料', date(2025, 1, 1))['deadline'], '2025-03-11')

    def test_before_date_excludes_day_with_weekday(self):
        for expression in ('4月1日（周一）前', '4月1日(星期一)前', '4月1日之前', '4月1日前'):
            with self.subTest(expression=expression):
                row = extract_notice('请于' + expression + '提交材料。', date(2024, 1, 1))
                self.assertEqual(row['deadline'], '2024-03-31')
                self.assertEqual(row['deadline_boundary'], 'exclusive_date')
                self.assertIn('不含 2024-04-01', row['deadline_note'])
                self.assertIn('前', row['deadline_expression'])

    def test_before_date_handles_month_year_and_leap_day(self):
        for expression, expected in (('2025年1月1日前', '2024-12-31'),
                                     ('2024年3月1日前', '2024-02-29'),
                                     ('2025年3月1日前', '2025-02-28')):
            self.assertEqual(extract_notice(expression + '提交材料')['deadline'], expected)

    def test_before_clock_and_inclusive_date_not_shifted(self):
        for expression in ('4月1日17:00前提交', '4月1日（周一）17:00前提交'):
            self.assertEqual(extract_notice(expression, date(2024, 1, 1))['deadline'], '2024-04-01 17:00')
        for expression in ('截至4月1日', '截止时间：4月1日', '报名时间：即日起至4月1日'):
            self.assertEqual(extract_notice(expression, date(2024, 1, 1))['deadline'], '2024-04-01')

    def test_before_date_reminders_and_manual_override(self):
        row = extract_notice('奖学金申请请于2024年4月1日（周一）前提交材料。')
        self.assertEqual(enrich(row)['reminder_times'][0]['time'], '2024-03-28')
        with patch('builtins.input', side_effect=['2', '2024-04-01 17:00', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['deadline'], '2024-04-01 17:00')
        self.assertEqual(row['deadline_note'], '')
        self.assertEqual(row['deadline_boundary'], 'manual')

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
        with patch('builtins.input', side_effect=['1', '新事项', 'n']), patch('builtins.print'):
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
            self.assertEqual(load(path), [enrich(row.copy()), enrich(row.copy())])
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                append(path, row)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')

    def test_edit_and_confirm(self):
        row = extract_notice('选课补退选')
        with patch('builtins.input', side_effect=['1', '补选课程', '2', '2025-02-30', '2025-03-12 18:00', '3', '教务系统', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['task'], '补选课程')
        self.assertEqual(row['deadline'], '2025-03-12 18:00')
        self.assertEqual(row['submit_method'], '教务系统')
        self.assertEqual(row['source_text'], '选课补退选')

    def test_reedit_and_clear(self):
        row = extract_notice('选课补退选截止3月12日18:00')
        with patch('builtins.input', side_effect=['2', '', '2', '未提及', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['deadline'], '未提及')

    def test_all_category_keywords(self):
        for category, words in RULES.items():
            for word in words:
                with self.subTest(category=category, keyword=word):
                    self.assertEqual(classify(word)['category'], category)

    def test_ambiguous_and_unknown(self):
        row = classify('考试与实习通知')
        self.assertEqual(row['category'], '其它类别')
        self.assertEqual(set(row['category_candidates']), {'课程学业', '就业实习'})
        self.assertEqual(classify('请关注后续消息')['category'], '其它类别')
        self.assertEqual(classify('考试报名，请携带实习证明', '考试报名')['category'], '课程学业')

    def test_reminder_strategies(self):
        expected = {
            '课程学业': ['2026-12-07 18:00', '2026-12-10 16:00'],
            '竞赛科研': ['2026-12-05 18:00', '2026-12-09 18:00'],
            '活动实践': ['2026-12-09 18:00'],
            '行政事务': ['2026-12-07 18:00', '2026-12-10 16:00'],
            '就业实习': ['2026-12-03 18:00', '2026-12-09 18:00'],
            '生活服务': ['2026-12-09 18:00'],
        }
        for category, times in expected.items():
            self.assertEqual([item['time'] for item in plan(category, '2026-12-10 18:00')[0]], times)
        reminders, note = plan('行政事务', '2026-12-10')
        self.assertEqual([item['time'] for item in reminders], ['2026-12-07'])
        self.assertIn('2小时', note)
        self.assertEqual(plan('课程学业', '2026-12-10'),
                         ([{'label': '提前3天', 'time': '2026-12-07'}],
                          '缺少具体时刻，未生成截止前2小时提醒'))
        self.assertEqual(plan('生活服务', '2026-12-10'), ([{'label': '提前1天', 'time': '2026-12-09'}], ''))
        self.assertEqual(plan('课程学业', '未提及')[0], [])

    def test_category_edit_recomputes_reminders(self):
        row = extract_notice('选课截止2026年12月10日18:00')
        with patch('builtins.input', side_effect=['5', '无效分类', '5', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['category'], '行政事务')
        self.assertEqual(row['reminder_times'][-1]['time'], '2026-12-10 16:00')

    def test_preview_all_before_first_input_and_direct_save(self):
        row = extract_notice('选课截止2026年12月10日18:00')
        original = row.copy()
        with patch('builtins.print') as output:
            def answer(prompt):
                shown = '\n'.join(str(call.args[0]) for call in output.call_args_list if call.args)
                for label in ('1. 事项名称', '2. 截止/事件时间', '3. 提交方式', '4. 事件地点', '5. 分类标签'):
                    self.assertIn(label, shown)
                self.assertNotIn(original['source_text'], [call.args[0] for call in output.call_args_list if call.args])
                return 'y'
            with patch('builtins.input', side_effect=answer) as reader:
                self.assertTrue(confirm(row))
            self.assertEqual(reader.call_count, 1)
        self.assertEqual(row['task'], original['task'])

    def test_source_toggle_and_invalid_menu(self):
        row = extract_notice('选课截止2026年12月10日18:00')
        with patch('builtins.input', side_effect=['', '9', 'v', 'v', 'y']), patch('builtins.print') as output:
            self.assertTrue(confirm(row))
        shown = [call.args[0] for call in output.call_args_list if call.args]
        self.assertEqual(shown.count(row['source_text']), 1)
        self.assertTrue(any('信息缺失' in str(line) for line in shown))

    def test_edit_date_recomputes_plan_and_edit_location(self):
        row = extract_notice('医保办理截止2026年12月10日18:00')
        with patch('builtins.input', side_effect=['2', '2026-12-12 14:00', '4', '学生服务中心', 'y']), patch('builtins.print'):
            self.assertTrue(confirm(row))
        self.assertEqual(row['location'], '学生服务中心')
        self.assertEqual(row['reminder_times'][0]['time'], '2026-12-11 14:00')

    def test_old_json_compatible(self):
        import json
        old = dict(task='选课', deadline='未提及', submit_method='未提及', location='未提及', source_text='选课')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.json'
            original = json.dumps([old], ensure_ascii=False)
            path.write_text(original, encoding='utf-8')
            self.assertEqual(load(path)[0]['category'], '其它类别')
            self.assertEqual(path.read_text(encoding='utf-8'), original)

    def test_legacy_category_name(self):
        import json
        old = dict(task='其他通知', deadline='未提及', submit_method='未提及',
                   location='未提及', source_text='其他通知', category='未分类')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.json'
            original = json.dumps([old], ensure_ascii=False)
            path.write_text(original, encoding='utf-8')
            self.assertEqual(load(path)[0]['category'], '其它类别')
            self.assertEqual(path.read_text(encoding='utf-8'), original)


if __name__ == '__main__':
    unittest.main()
