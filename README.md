# 高校学生通知管理工具

Python 3.10+ 命令行程序。文本模式只用标准库，无须安装第三方依赖。所有通知经过人工确认后才写入 JSON；截图 OCR 可选择 pytesseract 或 PaddleOCR 3.x。

## 快速运行

先进入程序目录，以下命令均在此目录执行：

```powershell
cd D:\working\gpt\student_notice
python main.py add --text "【教务处通知】2024-2025-2 学期选课补退选将于 3 月 12 日 12:00 结束，请未确认的同学登录教务系统完成操作，逾期不再受理。"
```

预期提取结果：

```json
{
  "task": "选课补退选",
  "deadline": "2025-03-12 12:00",
  "submit_method": "教务系统",
  "location": "未提及",
  "source_text": "【教务处通知】2024-2025-2 学期选课补退选将于 3 月 12 日 12:00 结束，请未确认的同学登录教务系统完成操作，逾期不再受理。"
}
```

识别后依次核对“事项、时间、提交方式、地点”的内容。每项显示当前值，直接输入正确内容替换，直接回车保留原值，输入“未提及”清空。无需输入字段名。时间修改会校验日期合法性。

四项核对后会显示最终预览，输入 `y` 确认保存、`e` 再次修改、`n` 取消。只有最终确认才写入 JSON。原始 OCR 文字保留用于核对；修改的是提取后的内容。此功能用于新增记录保存前，不会修改已保存记录。

时间规则会排除带“发布时间、发送时间、更新日期、落款”等标记的日期。缺乏明确事件语义的日期（例如独立聊天时间戳）不再自动作为事件时间，而是显示“未提及”，请手动确认。复杂排版或 OCR 漏字仍可能影响判断。

也可多行粘贴：

```powershell
python main.py add
```

粘贴后另起一行输入 `END`。Ctrl+C 或输入中断会取消新增。

默认保存到**当前工作目录**的 `todo_list.json`，格式为对象数组，新增时追加记录。

指定文件、查看待办和查看未来七天及全部逾期事项：

```powershell
python main.py --file data/todo_list.json add --text "奖学金申请截止2026年12月1日18:00，请登录学生服务平台提交。"
python main.py list
python main.py list --days 7
python main.py --help
```

`--file` 放在子命令前。列表按时间排序；无时间的记录排在最后。`--days` 筛选排除无时间记录。列表仅展示，不会自动弹窗或发送消息。目前不提供完成状态管理和去重，每次确认都会新增一条。

## 可选 OCR 依赖

下列安装命令由你自行选择执行，纯文本使用不需要安装。建议先创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 方案一：pytesseract

```powershell
python -m pip install pytesseract Pillow
```

还必须安装 Tesseract OCR 原生程序及简体中文 `chi_sim`、英文 `eng` 语言包。仅安装 pip 包不包含 OCR 引擎。Windows 安装说明见 [Tesseract 官方文档](https://tesseract-ocr.github.io/tessdoc/Installation.html)。确保引擎在 PATH 中，或显式指定路径：

```powershell
python main.py add --image "截图.png" --ocr pytesseract --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

接口参考：[pytesseract](https://pypi.org/project/pytesseract/)。程序使用 `chi_sim+eng` 识别截图。

### 方案二：PaddleOCR 3.x

使用受 PaddlePaddle 支持的 Python 和操作系统版本；如安装提示没有匹配的 wheel，可另建 Python 3.10 或 3.11 环境。CPU 安装示例：

```powershell
python -m pip install paddlepaddle "paddleocr>=3,<4"
python main.py add --image "截图.png" --ocr paddleocr
```

适用安装方式以 [PaddlePaddle 官方安装说明](https://www.paddlepaddle.org.cn/install/quick) 为准。首次使用可能联网下载模型，后续识别在本机执行。代码使用 3.x 的 `predict()` 和结果 `json` 中的 `rec_texts`，不兼容 2.x 返回格式。参考 [PaddleOCR 官方 Python API](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md)。

OCR 识别出的文字会先展示并提取字段；识别错误可取消后粘贴修正文本，也可修改四个结构化字段。截图中有多条通知时请分别处理。

## 提取规则与边界

- 识别中文和常见数字日期，例如 `2025年3月12日12:00`、`2025-03-12 12:00`、`3 月 12 日下午3点`；截止/结束优先于开始/举行时间。
- 缺少年份时，优先从 `2024-2025-2 学期` 推断第二学期为 2025 年，第一学期为 2024 年；否则使用当前年份。可通过 `--reference-date 2025-01-01` 指定参考日期。跨年、特殊校历请人工修正。
- 只有日期时保存 `YYYY-MM-DD`，不虚构具体时刻；列表将该日期的当天结束视作逾期分界。有时刻时保存 `YYYY-MM-DD HH:MM`。均使用本机当地时间。
- 同级时间候选取文本中首项；无法确定的时间为“未提及”。暂不识别“明天”“下周五”、农历、只有时刻的通知和复杂跨日时间段。
- 事项优先显式标题，然后常见事项关键词，再从首句截取，最长 40 字。方法匹配平台、邮箱、网址、纸质和接龙等关键词；地点优先匹配“地点/地址”字段。
- 规则无法保证理解所有自然语言，提取结果必须人工确认；缺失字段为“未提及”。一个通知保存一个事项，复杂通知请拆分。
- JSON 使用临时文件原子替换；已有文件损坏会报错并保留原文件。当前仅支持单进程写入，不要让多个实例同时新增。

## 模块与验证

`main.py` 负责 CLI 和确认流程，`extractor.py` 负责规则，`ocr.py` 负责 OCR 适配，`storage.py` 负责持久化。GUI / Web 可直接复用提取、OCR 和存储函数。

运行标准库单元测试，无须安装测试框架：

```powershell
python -m unittest discover -v
```

测试覆盖样例、截止时间优先、日期精度、非法日期、地点邮箱、缺失字段、编辑确认及损坏文件保护。真实 OCR 需要安装所选引擎后另用截图验证。

## 扩展定时提醒

目前提供按时间筛选的待办输出，可让定时任务每天调用列表命令。

Windows：在“任务计划程序”中新建每天触发的任务；程序填写 Python 可执行文件的绝对路径，参数填写 `"D:\working\gpt\student_notice\main.py" --file "D:\working\gpt\student_notice\todo_list.json" list --days 7`。计划任务的控制台输出不等于桌面通知，需要另加通知模块或输出日志。

Linux/macOS 的 cron 示例（路径须替换为实际绝对路径）：

```cron
0 8 * * * /usr/bin/python3 /path/student_notice/main.py --file /path/student_notice/todo_list.json list --days 7 >> /path/student_notice/reminders.log 2>&1
```

后续可在 `show_todos()` 的筛选逻辑上增加桌面通知、邮件提醒，并在数据结构中加入 `id`、`completed`、`last_reminded_at`，避免已完成任务和重复提醒。若要支持并发写入，建议迁移到 SQLite。
