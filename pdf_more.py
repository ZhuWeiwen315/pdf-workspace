"""Local render/compress/overlay helpers; import alongside the existing core.py.

Input is an already unlocked core.Document snapshot. All outputs use a new folder.
No operation changes the source file. PDF outputs are not password-protected.
"""
from io import BytesIO
from pathlib import Path
import math
import shutil
import tempfile
from pypdf import PdfReader, PdfWriter
from core import SplitError, validate_output_filename


def _pages(doc, pages):
    values = list(range(1, doc.pages + 1)) if pages is None else list(pages)
    if not values or any(type(p) is not int or not 1 <= p <= doc.pages for p in values):
        raise SplitError('请选择有效的页码（从 1 开始）。')
    if len(set(values)) != len(values):
        raise SplitError('页码不能重复。')
    return values


def _folder(output_dir, prefix):
    if not str(output_dir).strip() or not Path(output_dir).is_dir():
        raise SplitError('请选择存在的输出目录。')
    return Path(tempfile.mkdtemp(prefix=prefix, dir=Path(output_dir).resolve()))


def _fail(folder, exc):
    try:
        shutil.rmtree(folder)
        detail = '未完成的输出已清理'
    except OSError:
        detail = f'部分输出可能仍在 {folder}，请检查后手动清理'
    raise SplitError(f'处理失败，{detail}：{exc}') from exc


def _snapshot(doc):
    writer = PdfWriter()
    try:
        writer.clone_document_from_reader(doc.reader)
        buffer = BytesIO()
        writer.write(buffer)
        return buffer.getvalue()
    finally:
        writer.close()


def render_document(doc, output_dir, pages=None, image_format='png', dpi=150,
                    jpeg_quality=90, progress=None):
    """Render chosen one-based pages. Returns list[Path] in supplied order.

    36–300 DPI, maximum 40 megapixels per page. Transparent areas become white.
    No OCR: resulting files are images. Runs one document at a time in the GUI.
    """
    import pypdfium2 as pdfium
    selected = _pages(doc, pages)
    fmt = str(image_format).lower()
    if fmt not in ('png', 'jpg', 'jpeg'):
        raise SplitError('图片格式只支持 PNG 或 JPEG。')
    if type(dpi) is not int or not 36 <= dpi <= 300:
        raise SplitError('分辨率应为 36 到 300 DPI 的整数。')
    if type(jpeg_quality) is not int or not 1 <= jpeg_quality <= 95:
        raise SplitError('JPEG 质量应为 1 到 95 的整数。')
    data = _snapshot(doc)
    folder = _folder(output_dir, 'images_')
    pdf = None
    try:
        pdf = pdfium.PdfDocument(data)
        result = []
        for index, number in enumerate(selected, 1):
            page = pdf[number - 1]
            bitmap = None
            try:
                w, h = page.get_size()
                scale = dpi / 72
                if not math.isfinite(w * h) or math.ceil(w * scale) * math.ceil(h * scale) > 40_000_000:
                    raise SplitError(f'第 {number} 页过大，请降低 DPI。')
                bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255))
                image = bitmap.to_pil().convert('RGB')
                try:
                    suffix = 'png' if fmt == 'png' else 'jpg'
                    path = folder / f'page_{number:04d}.{suffix}'
                    with path.open('xb') as stream:
                        options = {'dpi': (dpi, dpi)}
                        if suffix == 'jpg':
                            options['quality'] = jpeg_quality
                        image.save(stream, format='PNG' if suffix == 'png' else 'JPEG', **options)
                    result.append(path)
                finally:
                    image.close()
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
            if progress:
                progress(index, len(selected))
        return result
    except Exception as exc:
        _fail(folder, exc)
    finally:
        if pdf is not None:
            pdf.close()


def compress_document(doc, output_dir, filename='压缩.pdf', progress=None):
    """Compress page content streams only; no image downsampling or quality loss.

    Reduction is not guaranteed. Chooses the smaller of normalized baseline and
    compressed output, but normalization may still exceed original file size.
    """
    filename = validate_output_filename(filename)
    folder = _folder(output_dir, 'compressed_')
    writer = None
    try:
        baseline = _snapshot(doc)
        writer = PdfWriter(clone_from=BytesIO(baseline))
        for i, page in enumerate(writer.pages, 1):
            page.compress_content_streams(level=6)
            if progress:
                progress(i, doc.pages)
        buffer = BytesIO()
        writer.write(buffer)
        compressed = buffer.getvalue()
        target = folder / filename
        with target.open('xb') as stream:
            stream.write(compressed if len(compressed) < len(baseline) else baseline)
        return target
    except Exception as exc:
        _fail(folder, exc)
    finally:
        if writer is not None:
            writer.close()


def _finite(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise SplitError(f'{label}应在 {low} 到 {high} 之间。')


def _overlay(doc, output_dir, filename, pages, make_overlay, progress):
    selected = set(_pages(doc, pages))
    filename = validate_output_filename(filename)
    folder = _folder(output_dir, 'annotated_')
    writer = None
    try:
        writer = PdfWriter(clone_from=BytesIO(_snapshot(doc)))
        for number, page in enumerate(writer.pages, 1):
            if number in selected:
                # Normalize rotation so marks are aligned with the displayed page.
                page.transfer_rotation_to_content()
                overlay_bytes = make_overlay(page, number)
                page.merge_page(PdfReader(BytesIO(overlay_bytes)).pages[0])
            if progress:
                progress(number, doc.pages)
        target = folder / filename
        with target.open('xb') as stream:
            writer.write(stream)
        return target
    except Exception as exc:
        _fail(folder, exc)
    finally:
        if writer is not None:
            writer.close()


def watermark_document(doc, output_dir, text, filename='水印.pdf', pages=None,
                       font_size=36, opacity=0.2, angle=35, progress=None):
    """Center text watermark. Basic Chinese/Latin; not secure redaction.

    CJK uses the standard STSong-Light CID font; no third-party font is bundled.
    Other scripts/emoji are not supported. Existing PDF signatures are invalidated.
    """
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    if not isinstance(text, str) or not text.strip() or len(text) > 100 or any(ord(c) < 32 for c in text):
        raise SplitError('请输入 1 到 100 个字符的单行水印。')
    # Avoid silently missing unsupported emoji/complex-script glyphs.
    if any(not (32 <= ord(c) <= 126 or 0x3000 <= ord(c) <= 0x303f or 0x4e00 <= ord(c) <= 0x9fff or 0xff00 <= ord(c) <= 0xffef) for c in text):
        raise SplitError('水印目前支持常用简体汉字、英文、数字和基本标点。')
    _finite(font_size, 6, 200, '字号')
    _finite(opacity, 0.05, 1, '不透明度')
    _finite(angle, -180, 180, '角度')
    font = 'Helvetica'
    if any(ord(c) > 126 for c in text):
        font = 'STSong-Light'
        if font not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(font))
    def make(page, number):
        box = page.cropbox
        width, height = float(box.width), float(box.height)
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(float(page.mediabox.right), float(page.mediabox.top)))
        c.setFillAlpha(opacity)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.translate(float(box.left) + width / 2, float(box.bottom) + height / 2)
        c.rotate(angle)
        # Fit to the visible page to avoid clipping long text.
        text_width = pdfmetrics.stringWidth(text, font, font_size)
        size = min(font_size, font_size * (min(width, height) * 0.85) / max(text_width, 1))
        c.setFont(font, size)
        c.drawCentredString(0, -size * 0.3, text)
        c.save()
        return buffer.getvalue()
    return _overlay(doc, output_dir, filename, pages, make, progress)


def number_pages(doc, output_dir, filename='页码.pdf', pages=None, start_number=1,
                 font_size=11, progress=None):
    """Bottom-center numbers. Physical page 1 receives start_number.

    For a page subset, labels still reflect original physical page positions.
    """
    from reportlab.pdfgen import canvas
    if type(start_number) is not int or not 0 <= start_number <= 1_000_000:
        raise SplitError('起始编号应为 0 到 1000000 的整数。')
    _finite(font_size, 6, 36, '字号')
    def make(page, number):
        box = page.cropbox
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(float(page.mediabox.right), float(page.mediabox.top)))
        c.setFont('Helvetica', font_size)
        c.drawCentredString(float(box.left) + float(box.width) / 2,
                            float(box.bottom) + min(20, float(box.height) * .05),
                            str(start_number + number - 1))
        c.save()
        return buffer.getvalue()
    return _overlay(doc, output_dir, filename, pages, make, progress)
