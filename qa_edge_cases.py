r"""九组边缘案例验收；仅生成测试报告，不改写待办或生产规则。

运行：.venv\Scripts\python.exe qa_edge_cases.py
OCR 两组测试模拟识别后的文本框，不调用模型，不能衡量读图准确率。
"""
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from course_table import HEADER, render_course_table
from extractor import extract_notices
from ocr import join_ocr_lines
from reminders import enrich

REFERENCE = date(2026, 11, 11)
DIAGNOSES = {
    '申请与领卡地点不同': '通用多事项拆分的动作校验缺少“领取”，拆分后回退为整条通知；整条地点又选中了后面的图书馆，造成时间和地点串项。',
    '提交地点不能被咨询地点替换': '地点正则未区分“咨询地点”和“提交地点”，先匹配到后文“咨询地点”就覆盖了真正的交材料地址。',
}


def fields(rows, key):
    return [row.get(key) for row in rows]


def table_fixture():
    texts = list(HEADER) + [
        '11月20日', '9:00-11:00', '三教', '310', 'Python程序设计', '2学时', '张老师',
        '11月21日', '14:00-16:00', '理科楼', '208', '高等数学', '2学时',
    ]
    boxes = [[100 + index * 150, 0, 200 + index * 150, 20] for index in range(5)]
    boxes += [
        [110, 40, 180, 56], [110, 62, 200, 78], [260, 40, 300, 56], [260, 62, 300, 78],
        [405, 48, 495, 68], [560, 48, 600, 68], [710, 48, 750, 68],
        [110, 100, 180, 116], [110, 122, 200, 138], [260, 100, 300, 116],
        [260, 122, 300, 138], [410, 108, 480, 128], [560, 108, 600, 128],
    ]
    return {'rec_texts': list(reversed(texts)), 'rec_boxes': list(reversed(boxes))}


GROUPS = [
    ('1. 分类模糊与关键词冲突', [
        dict(name='课程论文引用科研材料', text='事项：马原课程论文提交\n请于11月20日18:00前上传至教学平台，可参考科研项目论文，作为本课程考核。',
             expected={'count': 1, 'category': ['课程学业'], 'deadline': ['2026-11-20 18:00']}),
        dict(name='竞赛论文含课程词', text='事项：竞赛论文提交\n挑战杯竞赛论文请于11月21日18:00前通过竞赛平台提交，可附课程项目成果。',
             expected={'count': 1, 'category': ['竞赛科研']}),
        dict(name='文体活动在招聘大厅', text='金秋相约\n新生风采大赛定于11月22日19:00举行。\n东区公主楼三楼招聘大厅',
             expected={'count': 1, 'category': ['活动实践'], 'task': ['新生风采大赛'], 'location': ['东区公主楼三楼招聘大厅']}),
        dict(name='实习证明与行政关键词', text='事项：提交实习证明\n11月23日17:00前将盖章后的实习证明上传就业系统。',
             expected={'count': 1, 'category': ['就业实习']}),
    ]),
    ('2. 时间缺失、模糊与非法日期', [
        dict(name='时间另行通知', text='事项：校园卡补办\n请携带身份证到学生服务中心101室补办校园卡，办理时间另行通知。',
             expected={'count': 1, 'deadline': ['未提及'], 'no_reminders': True}),
        dict(name='预计日期不是硬截止', text='事项：关注奖学金评审结果\n结果预计11月20日前后公布，具体以学院通知为准。',
             expected={'count': 1, 'deadline': ['未提及'], 'no_reminders': True}),
        dict(name='非法日期不能生成提醒', text='事项：材料提交\n请于2026年2月30日17:00前提交至教务系统。',
             expected={'count': 1, 'deadline': ['未提及'], 'no_reminders': True}),
    ]),
    ('3. 多地点及地点归属', [
        dict(name='申请与领卡地点不同', text='事项：校园卡补办\n11月18日12:00前到学生服务中心101室提交申请，11月20日16:00前到图书馆102室领取新卡。',
             expected={'count': 2, 'deadline': ['2026-11-18 12:00', '2026-11-20 16:00'],
                       'location_contains': ['学生服务中心101', '图书馆102']}),
        dict(name='提交地点不能被咨询地点替换', text='事项：奖学金材料提交\n11月18日12:00前将纸质材料交至行政楼205办公室。咨询地点：图书馆报告厅（不接收材料）。',
             expected={'count': 1, 'location': ['行政楼205办公室']}),
    ]),
    ('4. 多事项及时间、渠道和条件绑定', [
        dict(name='核对、纠错、提交各有时间', text=(
            '事项：学生信息办理\n一、信息核对：11月16日-11月18日登录学生系统核对信息，有误者于11月19日17:00前到行政楼108室现场修改。\n'
            '二、材料提交：11月20日18:00前上传材料至学生系统，纸质版交至学院学工办。'),
             expected={'count': 4, 'deadline': ['2026-11-16', '2026-11-19 17:00', '2026-11-20 18:00', '2026-11-20 18:00'],
                       'first_end': '2026-11-18', 'condition_index': 1, 'condition': '个人信息有误', 'first_no_condition': True}),
        dict(name='同一报名窗口不能拆成两件事', text='事项：课程报名\n课程报名于11月16日09:00开始，11月20日18:00截止，请通过选课系统报名。',
             expected={'count': 1, 'start_time': ['2026-11-16 09:00'], 'deadline': ['2026-11-20 18:00'],
                       'reminder_times': [['2026-11-15 09:00', '2026-11-16 09:00', '2026-11-20 16:00']]}),
    ]),
    ('5. 模拟 OCR 断行恢复', [
        dict(name='动作词在行尾被截断', text='事项：课程论文提交\n请于11月19日18:00前上传到教学平台。',
             ocr=dict(rec_texts=['事项：课程论文提交', '请于11月19日18:00前上', '传到教学平台。'],
                      rec_boxes=[[2, 0, 350, 16], [2, 30, 610, 46], [2, 53, 240, 69]]),
             expected={'count': 1, 'category': ['课程学业'], 'deadline': ['2026-11-19 18:00'], 'equivalent_plain': True}),
        dict(name='编号阶段内月份和系统名断行', text=(
            '学生信息办理\n一、信息核对：请于11月16日-11月18日登录学生系统核对信息，有误者于11\n月19日\n17:00前到行政楼108室现场修改。\n'
            '二、材料提交：11月20日18:00前上传至学\n生系统，\n纸质版交至学院学工办。'),
             expected={'count': 4, 'deadline': ['2026-11-16', '2026-11-19 17:00', '2026-11-20 18:00', '2026-11-20 18:00']}),
    ]),
    ('6. 当前日期换算及原文留存', [
        dict(name='下周一', text='下周一下午两点有个实习分享会，想参加的群里接龙。', current=True,
             expected={'count': 1, 'deadline': ['2026-11-16 14:00'], 'reference_date': ['2026-11-11'], 'original_relative': '下周一'}),
        dict(name='后天没有具体时刻', text='后天参加班会，地点：教学楼201室。', current=True,
             expected={'count': 1, 'deadline': ['2026-11-13'], 'reference_date': ['2026-11-11'], 'original_relative': '后天', 'date_only_reminders': True}),
        dict(name='年末跨年', text='后天下午3点参加班会。', current=True, today='2026-12-31',
             expected={'count': 1, 'deadline': ['2027-01-02 15:00'], 'reference_date': ['2026-12-31'], 'original_relative': '后天'}),
        dict(name='指定参考日覆盖当前日', text='后天下午3点参加班会。', current=True, reference='2026-11-01',
             expected={'count': 1, 'deadline': ['2026-11-03 15:00'], 'reference_date': ['2026-11-01']}),
    ]),
    ('7. 模拟课程表坐标与缺失单元格', [
        dict(name='乱序文字框及第二行缺教师', text=('时间｜地点｜主题｜学时｜主讲教师\n'
             '11月20日09:00—11:00｜三教310｜Python程序设计｜2学时｜张老师\n'
             '11月21日14:00—16:00｜理科楼208｜高等数学｜2学时｜未提供'), table=True,
             expected={'count': 2, 'task': ['Python程序设计', '高等数学'],
                       'deadline': ['2026-11-20 09:00', '2026-11-21 14:00'],
                       'end_time': ['2026-11-20 11:00', '2026-11-21 16:00'],
                       'location': ['三教310', '理科楼208'], 'teacher': ['张老师', ''], 'category': ['课程学业', '课程学业'], 'warning_index': 1}),
    ]),
    ('8. 群消息与口语化条件', [
        dict(name='材料照片、纸质版及自愿分享会', text=(
            '@所有人 明天（周四）中午12点前把实习证明拍照发我微信。'
            '还没交的这周五之前交纸质版到经管楼507。'
            '另外下周三下午两点有个实习分享会，想参加的群里接龙。'),
             expected={'count': 3, 'deadline': ['2026-11-12 12:00', '2026-11-12', '2026-11-18 14:00'],
                       'method_contains': ['微信', '纸质', '群接龙'], 'optional_index': 2, 'no_mention_in_tasks': True}),
    ]),
    ('9. 复杂比赛报名聚合', [
        dict(name='赛题和组织介绍不是任务', text=(
            '关于第六届大学生智能制造创新大赛的通知\n'
            '一、赛事背景\n培养实践能力，赛题包括机器人足球和论文研究。\n'
            '二、赛题介绍\n共设置10个题目，每题另附评分说明；颁奖典礼定于12月1日举行。\n'
            '三、组委会工作\n组织教学研讨、招聘交流。\n'
            '四、选手须知\n每支参赛队伍学生人数3-5名，每名学生仅可参加1支队伍。'
            '本次报名与资料上传统一通过官网https://contest.example.com线上报送。'
            '参赛队伍须于2026年11月25日17:00前完成系统报名，同时将报名材料打包发送至team@example.como。'
            '报名材料命名为“学校-姓名-赛题”，报名信息提交后不得变更队伍成员。'),
             expected={'count': 1, 'deadline': ['2026-11-25 17:00'], 'category': ['竞赛科研'],
                       'method_contains_all': ['https://contest.example.com', 'team@example.com'],
                       'method_excludes': ['example.como'], 'requirements_contains': ['3-5名', '命名', '不得变更'],
                       'task_contains': ['智能制造创新大赛报名']}),
    ]),
]


def check(actual, expected, processed, case):
    failures = []
    def require(ok, message):
        if not ok:
            failures.append(message)
    require(len(actual) == expected['count'], f"事项数量：预期 {expected['count']}，实际 {len(actual)}")
    for key in ('task', 'category', 'deadline', 'location', 'start_time', 'end_time', 'teacher', 'reference_date'):
        if key in expected:
            require(fields(actual, key) == expected[key], f'{key}：预期 {expected[key]!r}，实际 {fields(actual, key)!r}')
    for key, field in (('location_contains', 'location'), ('method_contains', 'submit_method'), ('task_contains', 'task')):
        if key in expected:
            for index, value in enumerate(expected[key]):
                require(index < len(actual) and value in actual[index].get(field, ''), f'第{index+1}项 {field} 应含 {value}')
    if actual:
        first = actual[0]
        for value in expected.get('method_contains_all', []):
            require(value in first['submit_method'], f'提交方式缺少 {value}')
        for value in expected.get('method_excludes', []):
            require(value not in first['submit_method'], f'提交方式误含 {value}')
        for value in expected.get('requirements_contains', []):
            require(value in first.get('requirements', ''), f'要求缺少 {value}')
        if 'first_end' in expected:
            require(first.get('end_time') == expected['first_end'], '第一项范围结束时间错误')
        if expected.get('first_no_condition'):
            require(not first.get('prerequisite'), '第一项不应继承第二项的条件')
    for key, condition in (('warning_index', lambda r: bool(r.get('time_note'))),
                           ('optional_index', lambda r: r.get('optional') is True),
                           ('condition_index', lambda r: r.get('prerequisite') == expected.get('condition'))):
        if key in expected:
            index = expected[key]
            require(index < len(actual) and condition(actual[index]), f'第{index+1}项 {key} 不符合预期')
    for row in actual:
        require(row['source_text'] == processed, '原文未完整保留')
        if expected.get('no_reminders'):
            require(not row['reminder_times'], '未知时间不应生成提醒')
        if expected.get('date_only_reminders'):
            require(all(len(item['time']) == 10 for item in row['reminder_times']), '仅日期不能虚构小时提醒')
        if expected.get('original_relative'):
            require(expected['original_relative'] in row.get('time_expression', ''), '未保留原文相对时间')
        if expected.get('no_mention_in_tasks'):
            require('@所有人' not in row['task'], '群提醒混入事项名称')
    if 'reminder_times' in expected:
        values = [[item['time'] for item in row['reminder_times']] for row in actual]
        require(values == expected['reminder_times'], f'提醒计划错误：{values!r}')
    if expected.get('equivalent_plain'):
        plain = extract_notices(case['text'], REFERENCE)
        wanted = ('task', 'deadline', 'location', 'submit_method', 'category')
        require([{k:r.get(k) for k in wanted} for r in plain] == [{k:r.get(k) for k in wanted} for r in actual],
                '模拟OCR断行后的提取结果与纯文本不一致')
    return failures


def run():
    results = []
    for group, cases in GROUPS:
        for case in cases:
            processed = case['text']
            actual = []
            try:
                if case.get('ocr'):
                    processed = join_ocr_lines(case['ocr'])
                if case.get('table'):
                    processed = render_course_table(table_fixture())
                today = date.fromisoformat(case.get('today', REFERENCE.isoformat()))
                reference = date.fromisoformat(case['reference']) if case.get('reference') else (None if case.get('current') else REFERENCE)
                with patch('extractor.current_reference_date', return_value=today):
                    actual = [enrich(row) for row in extract_notices(processed, reference)]
                failures = check(actual, case['expected'], processed, case)
            except Exception as exc:
                failures = [f'{type(exc).__name__}: {exc}']
            results.append(dict(group=group, name=case['name'], original=case['text'], processed=processed,
                                expected=case['expected'], actual=actual, failures=failures))
    root = Path(__file__).resolve().parent
    (root / 'qa_edge_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    passed = sum(not result['failures'] for result in results)
    report = ['# 九组通知边缘测试报告', '', f'结果：{passed}/{len(results)} 子案例通过；{len(results)-passed} 个子案例失败。', '',
              '参考日固定为北京时间 2026-11-11；跨年案例单独固定日期。全部测试不写入待办文件，也不发送提醒。', '',
              '第5、7组为模拟 OCR 文本/坐标测试，不调用 PaddleOCR，不衡量图片文字识别准确率。', '']
    for group, _ in GROUPS:
        report += ['## ' + group, '']
        for result in (r for r in results if r['group'] == group):
            report += ['### ' + result['name'] + ('：失败' if result['failures'] else '：通过'), '',
                       '通知原文：', '', '```text', result['original'], '```', '',
                       '预期核对点：', '', '```json', json.dumps(result['expected'], ensure_ascii=False, indent=2), '```', '']
            if result['processed'] != result['original']:
                report += ['送入提取器的模拟 OCR 文本：', '', '```text', result['processed'], '```', '']
            report += ['实际提取摘要：', '', '```json', json.dumps([
                {k: row.get(k) for k in ('task','deadline','end_time','location','submit_method','category','reference_date','time_expression','requirements')}
                for row in result['actual']], ensure_ascii=False, indent=2), '```', '']
            if result['failures']:
                report += ['发现的问题：', ''] + ['- ' + failure for failure in result['failures']] + ['']
                if result['name'] in DIAGNOSES:
                    report += ['代码核对后的原因：' + DIAGNOSES[result['name']], '']
    (root / 'qa_edge_report.md').write_text('\n'.join(report), encoding='utf-8')
    print(f'{passed}/{len(results)} cases passed; {len(results)-passed} failed')
    for group, _ in GROUPS:
        subset = [r for r in results if r['group'] == group]
        print(ascii(group), sum(not r['failures'] for r in subset), '/', len(subset))
    print('Reports: qa_edge_report.md, qa_edge_results.json')
    return 0 if passed == len(results) else 1


if __name__ == '__main__':
    raise SystemExit(run())
