"""按需导入 OCR，纯文本模式不需要安装依赖。"""
import json
import os
import re
from pathlib import Path
from course_table import render_course_table


def join_ocr_lines(data: dict) -> str:
    """按文字框接合同段折行；标题、字段和段落间隔保留。"""
    texts = data.get('rec_texts', [])
    boxes = data.get('rec_boxes', [])
    if len(boxes) != len(texts) or not texts:
        return '\n'.join(texts)
    right_edge = max(box[2] for box in boxes)
    boundary = re.compile(
        r'^\s*(?:【|\[|(?:[一二三四五六七八九十]+|\d+)[、.．]|'
        r'[\u4e00-\u9fff]{2,10}[：:])'
    )
    paragraphs = []
    for index, raw in enumerate(texts):
        line = raw.strip()
        if not line:
            continue
        merge = False
        if index and paragraphs:
            previous = texts[index - 1].strip()
            left, top, right, bottom = boxes[index - 1]
            x1, y1, x2, y2 = boxes[index]
            height = max(bottom - top, y2 - y1, 1)
            merge = (
                0 <= y1 - bottom <= height * 0.9
                and abs(x1 - left) <= height * 2
                and right_edge - right <= height * 2
                and not boundary.match(line)
                and (not boundary.match(previous)
                     or re.match(r'^\s*(?:[一二三四五六七八九十]+|\d+)[、.．][^：:\n]+[：:]\s*\S', previous))
                and not re.search(r'[。！？!?；;]$', previous)
            )
        if merge:
            # 英文单词之间保留空格，中文折行直接接合。
            separator = ' ' if re.search(r'[A-Za-z]$', paragraphs[-1]) and re.match(r'[A-Za-z]', line) else ''
            paragraphs[-1] += separator + line
        else:
            paragraphs.append(line)
    return '\n'.join(paragraphs)


def recognize(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f'图片不存在：{path}')
    try:
        os.environ.setdefault(
            'PADDLE_PDX_CACHE_HOME',
            str(Path(__file__).resolve().parent / '.ocr-models' / 'paddlex'),
        )
        from paddleocr import PaddleOCR
        # 当前 Windows CPU 组合的 oneDNN 加速会触发不支持的算子。
        model = PaddleOCR(lang='ch', use_doc_orientation_classify=False,
                          use_doc_unwarping=False, use_textline_orientation=False,
                          enable_mkldnn=False)
        lines = []
        for result in model.predict(input=str(path)):
            data = result.json
            if isinstance(data, str):
                data = json.loads(data)
            payload = data.get('res', data)
            table = render_course_table(payload)
            lines.append(table if table is not None else join_ocr_lines(payload))
        text = '\n'.join(lines)
    except ImportError as exc:
        raise ValueError('OCR 依赖缺失，请按 README 安装 PaddleOCR 所需依赖') from exc
    except Exception as exc:
        raise ValueError(f'OCR 失败，请检查模型及图片：{exc}') from exc
    if not text.strip():
        raise ValueError('未识别到文字，请换用清晰截图或直接粘贴文本')
    return text
