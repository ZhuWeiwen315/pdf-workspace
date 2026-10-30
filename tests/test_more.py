import unittest
import tempfile
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import RectangleObject
from PIL import Image
from reportlab.pdfgen import canvas
from core import open_document, SplitError
from pdf_more import render_document, compress_document, watermark_document, number_pages

class MoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / '中文 test.pdf'
        c = canvas.Canvas(str(self.path), pagesize=(300, 400), pageCompression=0)
        for i in range(1, 4):
            c.drawString(30, 300, f'PAGE {i}')
            c.rect(30, 50, 40, 40, fill=1)
            c.showPage()
        c.save()
        self.original = self.path.read_bytes()
        self.doc = open_document(self.path)
    def tearDown(self):
        self.assertEqual(self.path.read_bytes(), self.original)
        self.tmp.cleanup()
    def test_png_dimensions_order(self):
        paths = render_document(self.doc, self.root, pages=[3, 1], dpi=144)
        self.assertEqual([x.name for x in paths], ['page_0003.png','page_0001.png'])
        with Image.open(paths[0]) as im:
            self.assertEqual(im.size,(600,800))
    def test_jpeg(self):
        paths=render_document(self.doc,self.root,pages=[1],image_format='jpeg')
        with Image.open(paths[0]) as im:
            self.assertEqual(im.format,'JPEG')
    def test_bad_render_args(self):
        for kw in [dict(pages=[]),dict(pages=[0]),dict(pages=[True]),dict(pages=[1,1]),dict(dpi=1000),dict(dpi=True),dict(image_format='bmp'),dict(jpeg_quality=100)]:
            with self.subTest(kw=kw),self.assertRaises(SplitError):
                render_document(self.doc,self.root,**kw)
    def test_compress_preserves_text_and_pixels(self):
        output=compress_document(self.doc,self.root)
        reader=PdfReader(output)
        self.assertEqual(len(reader.pages),3)
        self.assertEqual([p.extract_text() for p in reader.pages],[p.extract_text() for p in self.doc.reader.pages])
        a=render_document(self.doc,self.root,dpi=72)
        b=render_document(open_document(output),self.root,dpi=72)
        for x,y in zip(a,b):
            with Image.open(x) as ix,Image.open(y) as iy:
                self.assertEqual(ix.tobytes(),iy.tobytes())
    def test_watermark_subset(self):
        output=watermark_document(self.doc,self.root,'SAMPLE',pages=[2])
        pages=PdfReader(output).pages
        self.assertNotIn('SAMPLE',pages[0].extract_text())
        self.assertIn('SAMPLE',pages[1].extract_text())
        self.assertNotIn('SAMPLE',pages[2].extract_text())
        self.assertNotIn('SAMPLE',self.doc.reader.pages[1].extract_text())
    def test_chinese_watermark(self):
        output=watermark_document(self.doc,self.root,'内部资料')
        self.assertIn('内部资料',PdfReader(output).pages[0].extract_text())
        self.assertEqual(len(render_document(open_document(output),self.root,pages=[1])),1)
    def test_bad_watermark_args(self):
        for kw in [dict(text=''),dict(text='😀'),dict(text='a\nb'),dict(text='abc',opacity=0),dict(text='abc',font_size=float('nan')),dict(text='abc',angle=360)]:
            with self.subTest(kw=kw),self.assertRaises(SplitError):
                watermark_document(self.doc,self.root,**kw)
    def test_page_numbers(self):
        output=number_pages(self.doc,self.root,pages=[2,3],start_number=8)
        pages=PdfReader(output).pages
        self.assertNotIn('\n8',pages[0].extract_text())
        self.assertIn('\n9',pages[1].extract_text())
        self.assertIn('\n10',pages[2].extract_text())
    def test_rotated_cropbox(self):
        writer=PdfWriter(clone_from=self.path)
        writer.pages[0].rotate(90)
        writer.pages[1].cropbox=RectangleObject([20,30,250,350])
        path=self.root/'rotated.pdf'
        writer.write(path)
        doc=open_document(path)
        output=number_pages(doc,self.root)
        before=render_document(doc,self.root,dpi=72)
        after=render_document(open_document(output),self.root,dpi=72)
        for a,b in zip(before,after):
            with Image.open(a) as ia,Image.open(b) as ib:
                self.assertEqual(ia.size,ib.size)
                self.assertNotEqual(ia.tobytes(),ib.tobytes())
        self.assertEqual(doc.reader.pages[0].rotation,90)
    def test_repeat_isolation(self):
        a=number_pages(self.doc,self.root)
        b=number_pages(self.doc,self.root)
        self.assertNotEqual(a.parent,b.parent)
        self.assertEqual(PdfReader(a).pages[0].extract_text(),PdfReader(b).pages[0].extract_text())
    def test_encrypted_unlocked(self):
        w=PdfWriter(clone_from=self.path)
        w.encrypt('test-only',algorithm='AES-256')
        path=self.root/'locked.pdf';w.write(path)
        doc=open_document(path,'test-only')
        self.assertEqual(len(render_document(doc,self.root,pages=[1])),1)
        for fn in [compress_document,number_pages]:
            out=fn(doc,self.root)
            self.assertFalse(PdfReader(out).is_encrypted)
            self.assertEqual(len(PdfReader(out).pages),3)
    def test_invalid_filename_and_path(self):
        for fn in [compress_document,number_pages]:
            for kw in [dict(filename='../bad.pdf'),dict(filename='CON.pdf')]:
                with self.assertRaises(SplitError):fn(self.doc,self.root,**kw)
            with self.assertRaises(SplitError):fn(self.doc,'')
    def test_cleanup_on_write_failure(self):
        before=set(self.root.iterdir())
        with patch.object(PdfWriter,'write',side_effect=OSError('fake failure')):
            with self.assertRaises(SplitError):number_pages(self.doc,self.root)
        self.assertEqual(set(self.root.iterdir()),before)
    def test_cleanup_on_render_progress_failure(self):
        before=set(self.root.iterdir())
        def bad(*_):raise OSError('fake callback failure')
        with self.assertRaises(SplitError):render_document(self.doc,self.root,progress=bad)
        self.assertEqual(set(self.root.iterdir()),before)

if __name__=='__main__':unittest.main()
