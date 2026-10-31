"""Run inside the actual frozen EXE; synthetic files only, offline, bounded output."""
import json
from pathlib import Path
import tempfile
import traceback


def exercise_pdf_features(folder):
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader
    from PIL import Image
    from docx import Document as Docx
    from core import Part, open_document, split_document, merge_documents, reorder_document
    from extra_core import delete_pages, rotate_pages, extract_text, encrypt_document, decrypt_document, images_to_pdf
    from pdf_more import render_document, compress_document, watermark_document, number_pages
    from word_export import convert_pdf_to_docx
    source = folder / 'sample.pdf'
    c = canvas.Canvas(str(source), pagesize=(300,400))
    for page in range(1,4):
        c.drawString(30,350,'Page %d' % page); c.showPage()
    c.save()
    original = source.read_bytes()
    doc = open_document(source)
    assert len(split_document(doc,[Part(1,1),Part(2,3)],folder)) == 2
    assert len(PdfReader(merge_documents([doc,doc],folder)).pages) == 6
    moved = PdfReader(reorder_document(doc,1,1,3,'after',folder))
    assert 'Page 2' in moved.pages[0].extract_text()
    assert len(PdfReader(delete_pages(doc,[1],folder)).pages) == 2
    assert PdfReader(rotate_pages(doc,[1],90,folder)).pages[0].rotation == 90
    assert 'Page 1' in extract_text(doc,folder).read_text(encoding='utf-8')
    encrypted = encrypt_document(doc,'synthetic-test-password',folder)
    assert PdfReader(encrypted).is_encrypted
    assert not PdfReader(decrypt_document(open_document(encrypted,'synthetic-test-password'),folder)).is_encrypted
    png = folder / 'image.png'; Image.new('RGB',(30,40),'red').save(png)
    assert len(PdfReader(images_to_pdf([png],folder)).pages) == 1
    images = render_document(doc,folder,pages=[1],dpi=72)
    with Image.open(images[0]) as image:
        assert image.size == (300,400)
    assert len(PdfReader(compress_document(doc,folder)).pages) == 3
    assert 'WATERMARK' in PdfReader(watermark_document(doc,folder,'WATERMARK')).pages[0].extract_text()
    assert '1' in PdfReader(number_pages(doc,folder)).pages[0].extract_text()
    word = convert_pdf_to_docx(doc,folder)
    assert 'Page 1' in '\n'.join(p.text for p in Docx(word.path).paragraphs)
    assert source.read_bytes() == original
    return ['split','merge','reorder','delete','rotate','text','encrypt','decrypt',
            'images_pdf','pdf_images','compress','watermark','numbers','word','source_unchanged']


def run_self_test(report_path):
    result = {'ok':False,'checks':[],'native_drag_gesture_tested':False}
    root = None
    try:
        from tkinterdnd2 import TkinterDnD
        from app import App
        root = TkinterDnD.Tk(); root.withdraw()
        App(root); root.update()
        result['tkdnd_version'] = root.tk.call('package','present','tkdnd')
        result['checks'].append('tk_tkdnd_and_full_ui_initialized')
        root.destroy(); root = None
        with tempfile.TemporaryDirectory(prefix='pdfworkspace_smoke_') as temporary:
            result['checks'].extend(exercise_pdf_features(Path(temporary)))
            from portable_entry import export_licenses
            export_licenses(Path(temporary)/'notices')
            result['checks'].append('embedded_licenses_exported')
        result['ok'] = True
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if root is not None:
            root.destroy()
    # Exclusive creation prevents an explicit diagnostic argument overwriting user data.
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    return 0 if result['ok'] else 1
