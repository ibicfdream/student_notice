"""Flet 桌面入口：导入通知 → 识别 → 核对 → 原子保存。"""
import argparse
import asyncio
from datetime import date
from pathlib import Path

import flet as ft

from categories import CHOICES
from extractor import MISSING, extract_notices
from gui_forms import prepare_record
from ocr import recognize
from storage import append_many

BASE = Path(__file__).resolve().parent


class NoticeWindow:
    def __init__(self, page: ft.Page, path: Path):
        self.page, self.path = page, path
        self.image_path = None
        self.drafts = []
        self.editors = []
        self.busy = False
        page.title = '高校学生通知管理工具'
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed='#25635C')
        page.bgcolor = '#CEDFD8'
        page.padding = 24
        page.window.width, page.window.height = 1180, 860
        self.text = ft.TextField(label='通知正文 / OCR 原文', multiline=True,
                                 min_lines=9, max_lines=16, text_size=16,
                                 hint_text='在这里粘贴群通知；截图识别后的文字也会显示在这里。')
        self.reference = ft.TextField(label='通知发布日期',
                                      value='',
                                      hint_text='YYYY-MM-DD',
                                      helper='需要时可填入通知发布日期，用于换算“明天、下周一”等日期。格式要求 YYYY-MM-DD。',
                                      helper_style=ft.TextStyle(size=14),
                                      helper_max_lines=3)
        self.text.on_change = self.source_changed
        self.reference.on_change = self.source_changed
        self.image_label = ft.Text('尚未选择截图', color='#65736E')
        self.image_step = ft.Text('', color='#C65D00', size=14,
                                  font_family='Microsoft YaHei',
                                  text_align=ft.TextAlign.CENTER, visible=False)
        self.image = ft.Image(src='', visible=False, height=170, fit=ft.BoxFit.CONTAIN)
        self.status = ft.Text('先导入通知，再识别并核对。', selectable=True)
        self.progress = ft.ProgressBar(visible=False)
        self.results = ft.Column(spacing=16,
                                 horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        self.pick_button = ft.Button('选择截图', icon=ft.Icons.IMAGE_OUTLINED,
                                     style=ft.ButtonStyle(text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')),
                                     on_click=self.pick_image)
        self.ocr_button = ft.Button('识别截图', on_click=self.parse_image, disabled=True,
                                    style=ft.ButtonStyle(text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')))
        self.parse_button = ft.Button('识别正文', icon=ft.Icons.AUTO_AWESOME,
                                      style=ft.ButtonStyle(text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')),
                                      on_click=self.parse_text)
        self.save_button = ft.Button('确认全部保存', icon=ft.Icons.SAVE_OUTLINED,
                                     style=ft.ButtonStyle(text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')),
                                     on_click=self.save, disabled=True)
        self.clear_button = ft.TextButton('放弃核对结果', on_click=self.clear_results,
                                         style=ft.ButtonStyle(text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')))
        self.clear_date_button = ft.TextButton('清空', on_click=self.clear_reference,
                                               style=ft.ButtonStyle(text_style=ft.TextStyle(
                                                   weight=ft.FontWeight.BOLD, font_family='Microsoft YaHei')))
        self.import_panel = ft.Column([
            ft.Text('01  导入通知', size=21, weight=ft.FontWeight.BOLD,
                    font_family='Microsoft YaHei'),
            ft.Text('粘贴正文，或选择一张清晰截图。'),
            ft.Row([self.pick_button, self.ocr_button], wrap=True,
                   alignment=ft.MainAxisAlignment.CENTER),
            self.image_step, self.text, self.parse_button, self.reference,
            ft.Row([self.clear_date_button], alignment=ft.MainAxisAlignment.END),
            self.image_label, self.image,
        ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        panel = lambda content: ft.Container(content=content, bgcolor='white',
                                             padding=22, border_radius=18)
        page.add(ft.Column([
            ft.Text('校园通知 · 轻松整理', size=30, weight=ft.FontWeight.BOLD),
            ft.Text('导入 → 识别 → 核对 → 保存', color='#65736E'),
            ft.Row([
                ft.Container(panel(self.import_panel), expand=1),
                ft.Container(panel(ft.Column([
                    ft.Text('02  核对与保存', size=21, weight=ft.FontWeight.BOLD,
                            font_family='Microsoft YaHei'),
                    ft.Text('结果仅供参考，请核对日期、参与条件和提交方式。'),
                    self.results,
                    ft.Row([self.save_button, self.clear_button], wrap=True,
                           alignment=ft.MainAxisAlignment.CENTER),
                ], spacing=16, horizontal_alignment=ft.CrossAxisAlignment.CENTER)),
                             expand=2),
            ], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            self.progress, self.status,
            ft.Text(f'保存位置：{path.resolve()}\n提醒目前仅生成计划，不会自动推送。',
                    size=12, color='#65736E', selectable=True),
        ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True))

    def message(self, text, error=False):
        self.status.value = text
        self.status.color = '#B42318' if error else '#25635C'
        self.page.update()

    def set_busy(self, value):
        self.busy = value
        self.import_panel.disabled = value
        self.results.disabled = value
        self.clear_button.disabled = value
        self.save_button.disabled = value or not self.drafts
        self.progress.visible = value
        self.page.update()

    def invalidate(self):
        self.drafts, self.editors = [], []
        self.results.controls.clear()
        self.save_button.disabled = True

    def source_changed(self, e):
        if self.drafts:
            self.invalidate()
            self.message('原文或发布日期已修改，请重新识别后核对。')

    def clear_reference(self, e):
        if self.busy:
            return
        if (self.reference.value or '').strip():
            self.reference.value = ''
            self.source_changed(e)
        else:
            self.reference.value = ''
        self.page.update()

    async def pick_image(self, e):
        files = await ft.FilePicker().pick_files(
            dialog_title='选择通知截图', allow_multiple=False,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=['png', 'jpg', 'jpeg', 'bmp', 'webp'])
        if not files:
            return
        if not files[0].path:
            self.message('此入口用于本地桌面，请选择本机图片。', True)
            return
        self.invalidate()
        self.image_path = Path(files[0].path)
        self.image_label.value = self.image_path.name
        self.image.src, self.image.visible = str(self.image_path), True
        self.ocr_button.disabled = False
        self.image_step.value = '截图已导入，请点击“识别截图”'
        self.image_step.visible = True
        self.message(self.image_step.value)

    async def parse_text(self, e):
        await self.parse(False)

    async def parse_image(self, e):
        await self.parse(True)

    async def parse(self, use_image):
        if self.busy:
            return
        try:
            raw_reference = '' if use_image else (self.reference.value or '').strip()
            reference = date.fromisoformat(raw_reference) if raw_reference else None
            if reference and reference.isoformat() != raw_reference:
                raise ValueError('日期格式须为 YYYY-MM-DD')
        except ValueError:
            self.message('发布日期无效，请填写 YYYY-MM-DD。', True)
            return
        self.invalidate()
        self.set_busy(True)
        try:
            if use_image:
                if self.image_path is None:
                    raise ValueError('请先选择截图')
                self.image_step.value = '正在识别截图，请等待'
                self.image_step.visible = True
                self.message(self.image_step.value)
                source = await asyncio.to_thread(recognize, self.image_path)
                self.text.value = source
                self.image_step.value = '请点击“识别正文”提取信息'
                self.message(self.image_step.value)
                return
            else:
                source = self.text.value or ''
            records = await asyncio.to_thread(extract_notices, source, reference)
            if not records:
                raise ValueError('没有提取到事项，请补充正文后重试')
            self.drafts = records
            self.render_records()
            if self.image_step.visible:
                self.image_step.value = '信息已提取，请在右侧核对后保存'
            self.message(f'已提取 {len(records)} 条事项。请逐条核对，确认后保存。')
        except Exception as exc:
            if use_image:
                self.image_step.value = '截图识别失败，请重试或粘贴正文'
                self.image_step.visible = True
            self.message(f'识别失败：{exc}', True)
        finally:
            self.set_busy(False)

    def render_records(self):
        self.results.controls.clear()
        self.editors = []
        cards = []
        extras = {'start_time': '开始时间', 'end_time': '结束时间',
                  'service_hours': '每日服务时段', 'service_note': '补充说明',
                  'prerequisite': '参加 / 前置条件', 'excluded_audience': '无需参加人群'}
        for index, record in enumerate(self.drafts, 1):
            controls = {}
            fields = {'task': '事项名称', 'deadline': record.get('time_role', '截止 / 事件时间'),
                      'submit_method': record.get('method_role', '提交 / 参与方式'),
                      'location': '地点',
                      **{k: v for k, v in extras.items() if k in record}}
            body = [ft.Text(f'事项 {index}', size=18, weight=ft.FontWeight.BOLD)]
            for key in ('notice_subject', 'stage', 'deadline_expression', 'deadline_note',
                        'time_expression', 'time_range_expression'):
                if record.get(key):
                    body.append(ft.Text(str(record[key]), color='#65736E', selectable=True))
            for key, label in fields.items():
                control = ft.TextField(label=label, value=record.get(key, MISSING),
                                       multiline=key in ('submit_method', 'service_note', 'prerequisite'))
                if key in ('deadline', 'start_time', 'end_time'):
                    control.helper = 'YYYY-MM-DD 或 YYYY-MM-DD HH:MM；未知可留空'
                controls[key] = control
                body.append(control)
            category = ft.Dropdown(label='分类', value=record['category'],
                                   options=[ft.DropdownOption(key=c, text=c) for c in CHOICES])
            controls['category'] = category
            body.append(category)
            if record.get('reminder_note'):
                body.append(ft.Text(record['reminder_note'], color='#936300'))
            body.append(ft.Text('保存时按核对后的时间和分类重新计算提醒。', size=12))
            self.editors.append(controls)
            cards.append(ft.Container(ft.Column(
                body, spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                                                       padding=16, bgcolor='#F5F8F7', border_radius=12))
        if len(cards) == 1:
            self.results.controls.append(cards[0])
        else:
            for offset in range(0, len(cards), 2):
                pair = cards[offset:offset + 2]
                for card in pair:
                    card.expand = 1
                if len(pair) == 1:
                    pair.append(ft.Container(expand=1))
                self.results.controls.append(ft.Row(
                    pair, spacing=16, vertical_alignment=ft.CrossAxisAlignment.START))

    async def save(self, e):
        if self.busy or not self.drafts:
            return
        self.set_busy(True)
        try:
            records = []
            for index, (draft, controls) in enumerate(zip(self.drafts, self.editors), 1):
                try:
                    records.append(prepare_record(draft, {k: c.value for k, c in controls.items()}))
                except ValueError as exc:
                    raise ValueError(f'事项 {index}：{exc}') from exc
            await asyncio.to_thread(append_many, self.path, records)
            self.invalidate()
            self.results.controls.append(ft.Text(f'✓ 已保存 {len(records)} 条事项', size=20, color='#25635C'))
            self.message(f'保存成功：{self.path.resolve()}。可以继续导入下一份通知。')
        except Exception as exc:
            self.message(f'保存失败：{exc}', True)
        finally:
            self.set_busy(False)

    def clear_results(self, e):
        self.invalidate()
        self.message('已放弃核对结果，没有写入待办文件。')


def main():
    parser = argparse.ArgumentParser(description='高校学生通知管理工具 · Flet 桌面版')
    parser.add_argument('--file', type=Path, default=BASE / 'todo_list.json')
    args = parser.parse_args()
    async def start(page: ft.Page):
        NoticeWindow(page, args.file)
    ft.run(start)


if __name__ == '__main__':
    main()
