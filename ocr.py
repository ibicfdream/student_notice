"""按需导入 OCR，纯文本模式不需要安装依赖。"""
import json
from pathlib import Path


def recognize(path: Path, engine: str, tesseract_cmd: str | None = None) -> str:
    if not path.is_file():
        raise ValueError(f'图片不存在：{path}')
    try:
        if engine == 'pytesseract':
            import pytesseract
            from PIL import Image, ImageOps
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            with Image.open(path) as image:
                text = pytesseract.image_to_string(ImageOps.exif_transpose(image).convert('RGB'), lang='chi_sim+eng')
        else:
            from paddleocr import PaddleOCR
            model = PaddleOCR(lang='ch', use_doc_orientation_classify=False,
                              use_doc_unwarping=False, use_textline_orientation=False)
            lines = []
            for result in model.predict(input=str(path)):
                data = result.json
                if isinstance(data, str):
                    data = json.loads(data)
                lines.extend(data.get('res', data).get('rec_texts', []))
            text = '\n'.join(lines)
    except ImportError as exc:
        raise ValueError(f'OCR 依赖缺失，请按 README 安装 {engine} 所需依赖') from exc
    except Exception as exc:
        raise ValueError(f'OCR 失败，请检查引擎、语言包及图片：{exc}') from exc
    if not text.strip():
        raise ValueError('未识别到文字，请换用清晰截图或直接粘贴文本')
    return text
