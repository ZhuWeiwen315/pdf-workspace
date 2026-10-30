"""Best-effort local PDF to editable DOCX, without OCR or external services.

Text lines and ruled tables are reconstructed; images remain images. This is not
an exact-layout conversion engine. PDF and Word have different layout models.
"""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import shutil
import tempfile
import pdfplumber
from docx import Document as WordDocument
from docx.enum.section import WD_SECTION_START
from docx.shared import Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pypdf import PdfWriter
from core import SplitError


@dataclass(frozen=True)
class WordResult:
    path: Path
    pages: int
    editable_pages: int
    image_only_pages: int
    tables: int
    images: int
    reference_pages: int = 0

    @property
    def summary(self):
        note = f'已转换 {self.pages} 页，其中 {self.editable_pages} 页含可编辑文字。'
        if self.image_only_pages:
            note += f' {self.image_only_pages} 页没有可提取文字，已保留为图片，需 OCR 才能编辑其中的文字。'
        if self.reference_pages:
            note += f' 另在文末附了 {self.reference_pages} 页原页参考图，以保留未重建的矢量图或表格内图片；参考图中的内容不可编辑。'
        return note + ' Word 页数可能变化；双栏、公式和复杂表格请对照原 PDF 检查。'


def clean_text(value):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', str(value or ''))


def validate_docx_filename(filename):
    filename = filename.strip()
    if not filename or re.search(r'[<>:"/\\|?*\x00-\x1f]', filename):
        raise SplitError('请输入有效的 Word 文件名，不能含路径或 Windows 禁用字符。')
    if not filename.lower().endswith('.docx'):
        filename += '.docx'
    stem = filename[:-5]
    if not stem or stem.endswith((' ', '.')) or len(filename) > 100:
        raise SplitError('Word 文件名过长或无效（最多 100 个字符）。')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}
    if stem.split('.')[0].upper() in reserved:
        raise SplitError('该文件名是 Windows 保留名称。')
    return filename


def _payload(doc):
    if not doc.reader.is_encrypted:
        return doc.data
    # Reuse the already unlocked in-memory snapshot. No password saved to disk.
    writer = PdfWriter()
    writer.clone_document_from_reader(doc.reader)
    stream = BytesIO()
    writer.write(stream)
    writer.close()
    return stream.getvalue()


def _inside(obj, bbox):
    x = (obj['x0'] + obj['x1']) / 2
    y = (obj['top'] + obj['bottom']) / 2
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def _section(section, width, height):
    # Word permits at most 22-inch pages. Large source pages scale down.
    scale = min(1.0, 1584.0 / max(width, height))
    width, height = width * scale, height * scale
    margin = min(36.0, width * .07, height * .07)
    section.page_width = Pt(width)
    section.page_height = Pt(height)
    section.left_margin = section.right_margin = Pt(margin)
    section.top_margin = section.bottom_margin = Pt(margin)
    section.header_distance = section.footer_distance = Pt(0)
    return scale, margin, width - 2*margin, height - 2*margin


def _format_run(run, word, scale=1):
    name = str(word.get('fontname', ''))
    text = run.text
    font = '宋体' if any('\u3400' <= c <= '\u9fff' for c in text) else ('Times New Roman' if 'Times' in name else 'Arial')
    run.font.name = font
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
    run.font.size = Pt(max(6, min(48, float(word.get('size', 11)) * scale)))
    run.bold = any(token in name.lower() for token in ['bold', 'black', 'heavy'])
    run.italic = any(token in name.lower() for token in ['italic', 'oblique'])


def _line_events(words):
    lines = []
    for word in sorted(words, key=lambda w: (round(w['top'], 1), w['x0'])):
        if not lines or abs(word['top'] - lines[-1][0]['top']) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [(min(w['top'] for w in line), min(w['x0'] for w in line), 'text', sorted(line,key=lambda w:w['x0'])) for line in lines]


def _add_text(output, words, scale, margin, body_width):
    paragraph = output.add_paragraph()
    fmt = paragraph.paragraph_format
    fmt.space_before = fmt.space_after = Pt(0)
    fmt.keep_with_next = False
    fmt.line_spacing = 1.0
    indent = max(0, min(words[0]['x0'] * scale - margin, body_width * .7))
    fmt.left_indent = Pt(indent)
    previous = None
    for word in words:
        text = clean_text(word['text'])
        if not text:
            continue
        if previous:
            # Avoid injecting spaces between contiguous Chinese glyphs.
            left_cjk = '\u3400' <= previous['text'][-1:] <= '\u9fff'
            right_cjk = '\u3400' <= text[:1] <= '\u9fff'
            if not (left_cjk and right_cjk):
                paragraph.add_run(' ')
        run = paragraph.add_run(text)
        _format_run(run, word, scale)
        previous = word


def _add_table(output, data, bbox, scale, body_width):
    rows, cols = len(data), max((len(row) for row in data), default=0)
    if not rows or not cols:
        return
    table = output.add_table(rows=rows, cols=cols)
    table.style = 'Table Grid'
    table.autofit = False
    width = min(body_width, (bbox[2] - bbox[0]) * scale)
    for column in table.columns:
        column.width = Pt(width/cols)
    for i, row in enumerate(data):
        for j, value in enumerate(row):
            cell = table.cell(i,j)
            cell.width = Pt(width/cols)
            cell.text = clean_text(value)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(0)
                for run in paragraph.runs:
                    _format_run(run, {'size':10}, scale)
    # Prevent a row from splitting across Word pages where possible.
    for row in table.rows:
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))


def _image_bytes(page, bbox=None):
    # Bound raster memory: longest page edge <= 2400 px, maximum 144 DPI.
    resolution = min(144, 2400 * 72 / max(page.width, page.height))
    target = page if bbox is None else page.crop(bbox)
    image = target.to_image(resolution=resolution, antialias=True).original
    stream = BytesIO()
    image.save(stream, format='PNG')
    stream.seek(0)
    return stream


def _add_image(output, stream, width, height, body_width, body_height):
    factor = min(1.0, body_width/max(width,1), (body_height-18)/max(height,1))
    paragraph = output.add_paragraph()
    paragraph.paragraph_format.space_before = paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    paragraph.add_run().add_picture(stream, width=Pt(width*factor), height=Pt(height*factor))


def convert_pdf_to_docx(doc, output_dir, filename='转换结果.docx', progress=None):
    """Convert unlocked Document snapshot, preserving source and existing files.

    Entirely non-text PDFs are rejected instead of falsely claiming editable OCR.
    Non-text pages in a mixed PDF are copied as images and reported explicitly.
    """
    if not str(output_dir).strip() or not Path(output_dir).is_dir():
        raise SplitError('请选择存在的输出目录。')
    filename = validate_docx_filename(filename)
    folder = None
    try:
        with pdfplumber.open(BytesIO(_payload(doc))) as pdf:
            has_text = [any(clean_text(c.get('text','')).strip() for c in page.chars) for page in pdf.pages]
            if not any(has_text):
                raise SplitError('未找到可提取的文字。这可能是扫描件或文字已转为轮廓；本版不提供 OCR，不能生成可编辑文字。')
            output = WordDocument()
            output.core_properties.title = doc.path.stem
            output.core_properties.author = ''
            output.core_properties.last_modified_by = ''
            output.styles['Normal'].font.name = '宋体'
            output.styles['Normal'].font.size = Pt(11)
            output.styles['Normal'].paragraph_format.space_after = Pt(0)
            table_count = image_count = image_only = 0
            reference_indices = []
            for index, page in enumerate(pdf.pages):
                section = output.sections[0] if index == 0 else output.add_section(WD_SECTION_START.NEW_PAGE)
                scale, margin, body_width, body_height = _section(section,page.width,page.height)
                if not has_text[index]:
                    if page.images or page.curves or page.rects or page.lines:
                        _add_image(output,_image_bytes(page),page.width*scale,page.height*scale,body_width,body_height)
                        image_only += 1
                        image_count += 1
                    else:
                        output.add_paragraph('')
                    if progress: progress(index+1,len(pdf.pages))
                    continue
                tables = []
                for table in page.find_tables():
                    data = table.extract()
                    if data and len(data) >= 2 and max(map(len,data),default=0) >= 2 and any(str(cell or '').strip() for row in data for cell in row):
                        tables.append((table.bbox,data))
                # Some graphics cannot be represented as editable Word objects.
                # Preserve a reference rendering rather than silently discarding them.
                has_unhandled_vectors = any(not any(_inside(obj,bbox) for bbox,_ in tables)
                    for obj in page.curves + page.rects + page.lines)
                has_table_images = any(any(_inside(img,bbox) for bbox,_ in tables) for img in page.images)
                if has_unhandled_vectors or has_table_images:
                    reference_indices.append(index)
                words = page.extract_words(x_tolerance=2,y_tolerance=3,extra_attrs=['fontname','size'])
                words = [w for w in words if not any(_inside(w,bbox) for bbox,_ in tables)]
                events = _line_events(words)
                for bbox,data in tables:
                    events.append((bbox[1],bbox[0],'table',(bbox,data)))
                seen = set()
                for item in page.images:
                    bbox=(max(0,item['x0']),max(0,item['top']),min(page.width,item['x1']),min(page.height,item['bottom']))
                    if bbox[2]-bbox[0]<2 or bbox[3]-bbox[1]<2 or bbox in seen:
                        continue
                    if any(_inside(item,table_bbox) for table_bbox,_ in tables):
                        continue
                    seen.add(bbox)
                    events.append((bbox[1],bbox[0],'image',bbox))
                for top,left,kind,value in sorted(events,key=lambda e:(e[0],e[1])):
                    if kind=='text':
                        _add_text(output,value,scale,margin,body_width)
                    elif kind=='table':
                        bbox,data=value
                        _add_table(output,data,bbox,scale,body_width)
                        table_count+=1
                    else:
                        _add_image(output,_image_bytes(page,value),(value[2]-value[0])*scale,(value[3]-value[1])*scale,body_width,body_height)
                        image_count+=1
                if progress: progress(index+1,len(pdf.pages))
                page.close()
            for index in reference_indices:
                page=pdf.pages[index]
                section=output.add_section(WD_SECTION_START.NEW_PAGE)
                scale,margin,body_width,body_height=_section(section,page.width,page.height)
                paragraph=output.add_paragraph(f'原 PDF 第 {index+1} 页参考图（图片内容不可编辑）')
                paragraph.paragraph_format.space_after=Pt(6)
                _add_image(output,_image_bytes(page),page.width*scale,page.height*scale,body_width,body_height-35)
            folder=Path(tempfile.mkdtemp(prefix='word_',dir=Path(output_dir).resolve()))
            target=folder/filename
            output.save(target)
            return WordResult(target,len(pdf.pages),sum(has_text),image_only,table_count,image_count,len(reference_indices))
    except Exception as exc:
        if folder is not None:
            try: shutil.rmtree(folder)
            except OSError:
                raise SplitError(f'转换失败，部分输出可能仍在 {folder}：{exc}') from exc
        if isinstance(exc,SplitError):raise
        raise SplitError(f'PDF 转 Word 失败：{exc}') from exc
