"""Local PDF utilities. Page selections are one-based; originals are never changed.

No OCR, digital-signature preservation, PDF/A guarantee or secure redaction.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import secrets
import shutil
import tempfile

from pypdf import PdfWriter
from PIL import Image, ImageOps

from core import SplitError, validate_output_filename


def parse_page_selection(text, page_count):
    """Parse '1,3-5' (also Chinese comma); sorted unique original page numbers."""
    if type(page_count) is not int or page_count < 1:
        raise SplitError('PDF 页数无效。')
    if not isinstance(text, str) or not text.strip():
        raise SplitError('请输入页码，例如 1,3-5。')
    pages = set()
    for item in text.replace('，', ',').split(','):
        match = re.fullmatch(r'\s*([0-9]+)\s*(?:-\s*([0-9]+)\s*)?', item)
        if not match:
            raise SplitError('页码格式无效，请使用 1,3-5 这样的格式。')
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if not 1 <= first <= last <= page_count:
            raise SplitError(f'页码应在 1 到 {page_count} 之间，范围不能倒写。')
        pages.update(range(first, last + 1))
    return sorted(pages)


def _pages(pages, count):
    try:
        values = list(pages)
    except TypeError as exc:
        raise SplitError('请提供至少一个有效页码。') from exc
    if not values or any(type(p) is not int or not 1 <= p <= count for p in values):
        raise SplitError(f'请选择 1 到 {count} 之间的页码。')
    return sorted(set(values))


def _output(output_dir, filename, prefix, suffix='.pdf'):
    if not isinstance(output_dir, (str, Path)) or not str(output_dir).strip():
        raise SplitError('请选择输出目录。')
    parent = Path(output_dir).resolve()
    if not parent.is_dir():
        raise SplitError('输出目录不存在。')
    if not isinstance(filename, str):
        raise SplitError('请填写有效文件名。')
    if suffix == '.txt':
        # Reuse the Windows validation, including reserved device names.
        name = filename.strip()
        if name.lower().endswith('.txt'):
            name = name[:-4]
        name = validate_output_filename(name + '.pdf')[:-4] + '.txt'
    else:
        name = validate_output_filename(filename)
    try:
        folder = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    except OSError as exc:
        raise SplitError(f'无法创建输出文件夹：{exc}') from exc
    return folder, folder / name


def _failure(folder, operation, exc):
    try:
        shutil.rmtree(folder)
        cleanup = '未完成的输出已清理'
    except OSError:
        cleanup = f'请检查未完成的输出目录：{folder}'
    return SplitError(f'{operation}失败，{cleanup}：{exc}')


def _write(writer, output_dir, filename, prefix, operation, progress=None, total=1):
    folder, target = _output(output_dir, filename, prefix)
    try:
        with target.open('xb') as stream:
            writer.write(stream)
        if progress:
            progress(total, total)
        return target
    except Exception as exc:
        raise _failure(folder, operation, exc) from exc
    finally:
        writer.close()


def delete_pages(doc, pages, output_dir, filename='删除页面.pdf', progress=None):
    """Remove selected pages, retaining original order of all remaining pages."""
    selected = set(_pages(pages, doc.pages))
    if len(selected) == doc.pages:
        raise SplitError('不能删除全部页面，请至少保留一页。')
    writer = PdfWriter()
    try:
        writer.append(doc.reader, pages=[i for i in range(doc.pages) if i + 1 not in selected], import_outline=False)
        return _write(writer, output_dir, filename, 'deleted_', '删除页面', progress, doc.pages)
    finally:
        writer.close()


def rotate_pages(doc, pages, angle, output_dir, filename='旋转页面.pdf', progress=None):
    """Rotate selected pages clockwise by 90, 180 or 270 degrees, cumulatively."""
    selected = _pages(pages, doc.pages)
    if type(angle) is not int or angle not in (90, 180, 270):
        raise SplitError('旋转角度请选择顺时针 90、180 或 270 度。')
    writer = PdfWriter()
    try:
        writer.clone_document_from_reader(doc.reader)
        for page in selected:
            writer.pages[page - 1].rotate(angle)
        return _write(writer, output_dir, filename, 'rotated_', '旋转页面', progress, doc.pages)
    finally:
        writer.close()


def extract_text(doc, output_dir, filename='提取文字.txt', progress=None):
    """UTF-8 TXT with physical-page markers. No OCR or reading-order guarantee."""
    blocks = []
    found = False
    try:
        for i, page in enumerate(doc.reader.pages, 1):
            text = page.extract_text() or ''
            if text.strip():
                found = True
            blocks.append(f'===== 第 {i} 页 =====\n{text if text.strip() else "[本页未提取到文字，可能为扫描页或空白页；未进行 OCR]"}')
            if progress:
                progress(i, doc.pages)
    except Exception as exc:
        raise SplitError(f'提取文字失败：{exc}') from exc
    if not found:
        raise SplitError('未提取到文字，可能是扫描版或空白 PDF。本功能不含 OCR。')
    folder, target = _output(output_dir, filename, 'text_', suffix='.txt')
    try:
        with target.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write('\n\n'.join(blocks) + '\n')
        return target
    except Exception as exc:
        raise _failure(folder, '提取文字', exc) from exc


def encrypt_document(doc, password, output_dir, filename='加密文件.pdf', progress=None):
    """AES-256 password protection. Password is not persisted or logged.

    An independent random owner password prevents an empty owner password from
    becoming a bypass. No usage restrictions are represented as DRM guarantees.
    """
    if not isinstance(password, str) or not password or not password.strip():
        raise SplitError('请输入非空密码，建议使用至少 12 位的强密码。')
    if '\x00' in password or len(password.encode('utf-8')) > 127:
        raise SplitError('密码不能含空字符，UTF-8 编码后不得超过 127 字节。')
    writer = PdfWriter()
    try:
        writer.clone_document_from_reader(doc.reader)
        writer.encrypt(password, owner_password=secrets.token_urlsafe(32), algorithm='AES-256')
        return _write(writer, output_dir, filename, 'encrypted_', '加密 PDF', progress, doc.pages)
    finally:
        writer.close()


def decrypt_document(doc, output_dir, filename='解密文件.pdf', progress=None):
    """Save an already-unlocked encrypted Document without encryption.

    Use core.open_document(path, known_password) first. This is not cracking.
    """
    if not doc.reader.is_encrypted:
        raise SplitError('此 PDF 未加密，无需移除密码。')
    writer = PdfWriter()
    try:
        # Accessing doc.pages/clone requires successful decryption already.
        writer.clone_document_from_reader(doc.reader)
        return _write(writer, output_dir, filename, 'decrypted_', '移除 PDF 密码', progress, doc.pages)
    finally:
        writer.close()


def images_to_pdf(paths, output_dir, filename='图片合成.pdf', progress=None, dpi=150):
    """Single-frame PNG/JPEG/BMP/WebP images, one page each in supplied order.

    Transparency is composited onto white and EXIF orientation is applied.
    PDF page size derives from pixels / dpi. Pillow may recompress pixels;
    this is not a lossless archival or color-managed conversion.
    """
    if type(dpi) is not int or not 36 <= dpi <= 600:
        raise SplitError('图片分辨率必须为 36 到 600 之间的整数 DPI。')
    if not paths or len(paths) > 100:
        raise SplitError('请添加 1 到 100 张图片。')
    images = []
    pixel_count = 0
    folder = None
    try:
        for index, path in enumerate(paths, 1):
            path = Path(path)
            if not path.is_file():
                raise SplitError(f'图片不存在：{path.name}')
            with Image.open(BytesIO(path.read_bytes())) as raw:
                if raw.format not in {'PNG', 'JPEG', 'BMP', 'WEBP'}:
                    raise SplitError(f'不支持的图片类型：{path.name}。请选择 PNG/JPEG/BMP/WebP。')
                if getattr(raw, 'n_frames', 1) != 1:
                    raise SplitError(f'不支持动画或多帧图片：{path.name}')
                pixel_count += raw.width * raw.height
                if pixel_count > 100_000_000:
                    raise SplitError('图片总像素超过 1 亿，请分批转换或先缩小图片。')
                oriented = ImageOps.exif_transpose(raw)
                try:
                    if 'A' in oriented.getbands() or 'transparency' in oriented.info:
                        rgba = oriented.convert('RGBA')
                        converted = Image.new('RGB', rgba.size, 'white')
                        converted.paste(rgba, mask=rgba.getchannel('A'))
                        rgba.close()
                    else:
                        converted = oriented.convert('RGB')
                    images.append(converted)
                finally:
                    if oriented is not raw:
                        oriented.close()
            if progress:
                progress(index, len(paths))
        folder, target = _output(output_dir, filename, 'images_')
        with target.open('xb') as stream:
            images[0].save(stream, format='PDF', save_all=True, append_images=images[1:], resolution=dpi)
        return target
    except SplitError:
        if folder is not None:
            shutil.rmtree(folder, ignore_errors=True)
        raise
    except Exception as exc:
        if folder is not None:
            raise _failure(folder, '图片转 PDF', exc) from exc
        raise SplitError(f'无法读取图片：{exc}') from exc
    finally:
        for image in images:
            image.close()
