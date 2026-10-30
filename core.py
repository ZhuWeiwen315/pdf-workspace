"""Local PDF transformations. Page numbers are one-based, inclusive."""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import os
import re
import shutil
import tempfile
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject


class SplitError(ValueError):
    pass


class PasswordRequired(SplitError):
    pass


@dataclass(frozen=True)
class Part:
    start: int
    end: int


@dataclass
class Document:
    path: Path
    data: bytes
    reader: PdfReader

    @property
    def pages(self):
        return len(self.reader.pages)


def open_document(path, password=None):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() != '.pdf':
        raise SplitError('请选择一个有效的 PDF 文件。')
    try:
        data = path.read_bytes()
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            if password is None:
                raise PasswordRequired('该 PDF 需要密码。')
            if not reader.decrypt(password):
                raise PasswordRequired('密码不正确，请重试。')
        if not len(reader.pages):
            raise SplitError('此 PDF 没有可分离的页面。')
        return Document(path, data, reader)
    except SplitError:
        raise
    except Exception as exc:
        raise SplitError(f'无法读取 PDF：{exc}') from exc


def validate_parts(parts, page_count):
    if not parts:
        raise SplitError('请至少设置一份输出。')
    for i, part in enumerate(parts, 1):
        if type(part.start) is not int or type(part.end) is not int:
            raise SplitError(f'第 {i} 份的页码必须是整数。')
        if not 1 <= part.start <= part.end <= page_count:
            raise SplitError(f'第 {i} 份范围无效：请填写 1 到 {page_count}，起始页不能大于结束页。')


def even_parts(page_count, count):
    if type(count) is not int or count < 1 or count > page_count:
        raise SplitError(f'份数应为 1 到 {page_count} 之间的整数。')
    q, r = divmod(page_count, count)
    result, start = [], 1
    for i in range(count):
        end = start + q + (i < r) - 1
        result.append(Part(start, end))
        start = end + 1
    return result


def safe_stem(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).rstrip(' .')[:60]
    return name or 'document'


def split_document(doc, parts, output_dir, progress=None):
    """Write into a fresh directory; never overwrite an existing input/output.

    Incomplete output is removed if any part fails. The loaded source snapshot is
    used even if the original file is subsequently changed outside this program.
    """
    validate_parts(parts, doc.pages)
    if not str(output_dir).strip():
        raise SplitError('请选择输出目录。')
    parent = Path(output_dir).resolve()
    if not parent.is_dir():
        raise SplitError('输出目录不存在，请重新选择。')
    stem = safe_stem(doc.path.stem)
    folder = Path(tempfile.mkdtemp(prefix=stem + '_split_', dir=parent))
    try:
        total = sum(p.end - p.start + 1 for p in parts)
        done = 0
        paths = []
        for i, part in enumerate(parts, 1):
            writer = PdfWriter()
            # append preserves page objects/resources and reconstructs form fields.
            writer.append(doc.reader, pages=(part.start - 1, part.end), import_outline=False)
            writer.add_metadata({'/Producer': 'PDF Workspace 1.3'})
            target = folder / f'{stem}_{i:02d}_p{part.start}-{part.end}.pdf'
            with target.open('xb') as stream:
                writer.write(stream)
            writer.close()
            paths.append(target)
            done += part.end - part.start + 1
            if progress:
                progress(done, total)
        return paths
    except Exception as exc:
        try:
            shutil.rmtree(folder)
            cleanup = '未完成的输出已清理'
        except OSError:
            cleanup = f'部分输出可能仍位于 {folder}，请检查后手动清理'
        raise SplitError(f'分离失败，{cleanup}：{exc}') from exc


def validate_output_filename(filename):
    filename = filename.strip()
    if not filename or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename):
        raise SplitError('文件名不能为空，也不能包含路径或 Windows 不支持的字符。')
    if not filename.lower().endswith('.pdf'):
        filename += '.pdf'
    stem = filename[:-4]
    if not stem or stem.endswith((' ', '.')) or len(filename) > 100:
        raise SplitError('请使用不超过 100 个字符的有效文件名，名称末尾不要留空格或句点。')
    if stem.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}:
        raise SplitError('该名称是 Windows 保留名称，请换一个文件名。')
    return filename


def merge_documents(documents, output_dir, filename='merged.pdf', progress=None):
    """Merge in supplied order into a fresh output folder, never replacing files."""
    if len(documents) < 2:
        raise SplitError('请至少添加两个 PDF 文件。')
    if not str(output_dir).strip() or not Path(output_dir).is_dir():
        raise SplitError('请选择存在的输出目录。')
    filename = validate_output_filename(filename)
    parent = Path(output_dir).resolve()
    folder = Path(tempfile.mkdtemp(prefix='merged_', dir=parent))
    try:
        writer = PdfWriter()
        total = sum(doc.pages for doc in documents)
        done = 0
        for index, doc in enumerate(documents, 1):
            reader = doc.reader
            if reader.get_fields():
                # Work on a separate in-memory clone so repeated exports do not
                # mutate the loaded document. Prefix fields to prevent collisions.
                clone = PdfWriter()
                clone.clone_document_from_reader(reader)
                buffer = BytesIO()
                clone.write(buffer)
                clone.close()
                buffer.seek(0)
                reader = PdfReader(buffer)
                fields = reader.root_object['/AcroForm'].get('/Fields', [])
                for field_index, reference in enumerate(fields, 1):
                    field = reference.get_object()
                    old_name = str(field.get('/T', f'field{field_index}'))
                    field[NameObject('/T')] = TextStringObject(f'file{index:03d}_{old_name}')
            writer.append(reader, import_outline=False)
            done += doc.pages
            if progress: progress(done, total)
        writer.add_metadata({'/Producer': 'PDF Workspace 1.3'})
        target = folder / filename
        with target.open('xb') as stream:
            writer.write(stream)
        writer.close()
        return target
    except Exception as exc:
        try:
            shutil.rmtree(folder)
            cleanup = '未完成的输出已清理'
        except OSError:
            cleanup = f'部分输出可能仍位于 {folder}，请检查后手动清理'
        raise SplitError(f'合并失败，{cleanup}：{exc}') from exc


def page_move_order(page_count, m, n, t, position='before'):
    """Return one-based source-page order; t always refers to the original PDF."""
    if type(page_count) is not int or page_count < 2:
        raise SplitError('调整顺序至少需要 2 页 PDF。')
    if any(type(value) is not int for value in (m, n, t)):
        raise SplitError('m、n、t 都必须是整数。')
    if not 1 <= m <= n <= page_count:
        raise SplitError(f'移动范围必须满足 1 ≤ m ≤ n ≤ {page_count}。')
    if not 1 <= t <= page_count:
        raise SplitError(f'目标页 t 必须在 1 到 {page_count} 之间。')
    if m <= t <= n:
        raise SplitError('目标页 t 不能位于移动范围 m 到 n 内。')
    if position not in ('before', 'after'):
        raise SplitError('插入位置必须是目标页之前或之后。')
    remaining = list(range(1, m)) + list(range(n + 1, page_count + 1))
    offset = remaining.index(t) + (position == 'after')
    return remaining[:offset] + list(range(m, n + 1)) + remaining[offset:]


def compact_page_order(order):
    """Collapse consecutive increasing page numbers for a short readable preview."""
    if not order:
        return ''
    chunks = []
    start = end = order[0]
    for value in order[1:]:
        if value == end + 1:
            end = value
        else:
            chunks.append(str(start) if start == end else f'{start}–{end}')
            start = end = value
    chunks.append(str(start) if start == end else f'{start}–{end}')
    return ' → '.join(chunks)


def reorder_document(doc, m, n, t, position, output_dir, filename='调整顺序.pdf', progress=None):
    order = page_move_order(doc.pages, m, n, t, position)
    if not str(output_dir).strip() or not Path(output_dir).is_dir():
        raise SplitError('请选择存在的输出目录。')
    filename = validate_output_filename(filename)
    folder = Path(tempfile.mkdtemp(prefix='reordered_', dir=Path(output_dir).resolve()))
    try:
        writer = PdfWriter()
        writer.append(doc.reader, pages=[value - 1 for value in order], import_outline=False)
        writer.add_metadata({'/Producer': 'PDF Workspace 1.3'})
        target = folder / filename
        with target.open('xb') as stream:
            writer.write(stream)
        writer.close()
        if progress:
            progress(len(order), len(order))
        return target
    except Exception as exc:
        try:
            shutil.rmtree(folder)
            cleanup = '未完成的输出已清理'
        except OSError:
            cleanup = f'部分输出可能仍位于 {folder}，请检查后手动清理'
        raise SplitError(f'调整顺序失败，{cleanup}：{exc}') from exc
