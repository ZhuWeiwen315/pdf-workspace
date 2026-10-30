from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from docx import Document as Docx
from pypdf import PdfReader, PdfWriter
from core import SplitError, open_document
from word_export import convert_pdf_to_docx, clean_text

class WordTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.source=self.folder/'原始 文字.pdf'
        c=canvas.Canvas(str(self.source),pagesize=(500,700))
        c.setFont('Helvetica-Bold',18);c.drawString(45,650,'Heading')
        c.setFont('Helvetica',11);c.drawString(45,620,'Hello editable world')
        c.showPage();c.drawString(45,650,'Second page');c.save()
        self.doc=open_document(self.source)
    def tearDown(self):self.tmp.cleanup()
    def convert(self,doc=None,name='result.docx'):
        return convert_pdf_to_docx(doc or self.doc,self.folder,name)
    def all_text(self,path):return '\n'.join(p.text for p in Docx(path).paragraphs)
    def scan(self,path,mixed=False):
        c=canvas.Canvas(str(path),pagesize=(500,700))
        if mixed:
            c.drawString(45,650,'Editable page');c.showPage()
        image=Image.new('RGB',(200,200),'navy')
        c.drawImage(ImageReader(image),20,20,width=460,height=660)
        c.save()
    def test_text_is_editable(self):
        result=self.convert();word=Docx(result.path)
        self.assertIn('Hello editable world',self.all_text(result.path))
        self.assertEqual(len(word.inline_shapes),0)
        self.assertEqual(result.editable_pages,2)
    def test_page_size_and_sections(self):
        word=Docx(self.convert().path)
        self.assertEqual(len(word.sections),2)
        self.assertAlmostEqual(word.sections[0].page_width.pt,500,places=1)
        self.assertAlmostEqual(word.sections[0].page_height.pt,700,places=1)
    def test_font_weight(self):
        word=Docx(self.convert().path)
        heading=next(r for p in word.paragraphs for r in p.runs if r.text=='Heading')
        self.assertTrue(heading.bold);self.assertAlmostEqual(heading.font.size.pt,18)
    def test_source_protected_and_repeat(self):
        before=self.source.read_bytes();a=self.convert();b=self.convert()
        self.assertNotEqual(a.path,b.path);self.assertTrue(a.path.exists())
        self.assertEqual(self.source.read_bytes(),before)
    def test_encrypted(self):
        writer=PdfWriter();writer.append(self.doc.reader);writer.encrypt('word-test',algorithm='AES-256')
        path=self.folder/'locked.pdf';writer.write(path)
        result=self.convert(open_document(path,'word-test'))
        self.assertIn('Hello editable world',self.all_text(result.path))
    def test_scanned_rejected(self):
        path=self.folder/'scan.pdf';self.scan(path);before=set(self.folder.iterdir())
        with self.assertRaisesRegex(SplitError,'OCR'):self.convert(open_document(path))
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_mixed_scanned_reported(self):
        path=self.folder/'mixed.pdf';self.scan(path,True)
        result=self.convert(open_document(path))
        self.assertEqual(result.image_only_pages,1);self.assertEqual(result.editable_pages,1)
        self.assertEqual(len(Docx(result.path).inline_shapes),1)
        self.assertIn('OCR',result.summary)
    def test_image_retained(self):
        path=self.folder/'image.pdf';c=canvas.Canvas(str(path),pagesize=(500,700))
        c.drawString(45,650,'Picture below');c.drawImage(ImageReader(Image.new('RGB',(50,50),'red')),45,500,100,100);c.save()
        result=self.convert(open_document(path))
        self.assertEqual(result.images,1);self.assertEqual(len(Docx(result.path).inline_shapes),1)
    def test_vector_reference_preserved(self):
        path=self.folder/'vector.pdf';c=canvas.Canvas(str(path),pagesize=(500,700))
        c.drawString(45,650,'Vector diagram');c.setFillColorRGB(1,0,0);c.circle(200,500,60,fill=1);c.save()
        result=self.convert(open_document(path))
        self.assertEqual(result.reference_pages,1)
        self.assertEqual(len(Docx(result.path).inline_shapes),1)
        self.assertIn('参考图',result.summary)
        self.assertIn('Vector diagram',self.all_text(result.path))
    def test_chinese(self):
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        path=self.folder/'chinese.pdf';c=canvas.Canvas(str(path),pagesize=(500,700))
        c.setFont('STSong-Light',14);c.drawString(45,650,'中文转换测试');c.save()
        self.assertIn('中文转换测试',self.all_text(self.convert(open_document(path)).path))
    def test_table_editable(self):
        path=self.folder/'table.pdf';c=canvas.Canvas(str(path),pagesize=(500,700))
        c.drawString(45,650,'Table')
        for y in [600,570,540]:c.line(45,y,245,y)
        for x in [45,145,245]:c.line(x,540,x,600)
        for text,x,y in [('Name',50,580),('Score',150,580),('Alice',50,550),('95',150,550)]:c.drawString(x,y,text)
        c.save();result=self.convert(open_document(path));word=Docx(result.path)
        self.assertEqual(result.tables,1)
        self.assertEqual(word.tables[0].cell(1,0).text,'Alice')
        self.assertEqual(word.tables[0].cell(1,1).text,'95')
    def test_invalid_names(self):
        before=set(self.folder.iterdir())
        for name in ['', '../bad.docx','CON.docx','x?y.docx']:
            with self.subTest(name=name),self.assertRaises(SplitError):self.convert(name=name)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_invalid_output(self):
        with self.assertRaises(SplitError):convert_pdf_to_docx(self.doc,'')
    def test_save_failure_cleanup(self):
        before=set(self.folder.iterdir())
        with patch('docx.document.Document.save',side_effect=OSError('disk full')):
            with self.assertRaises(SplitError):self.convert()
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_progress(self):
        events=[];convert_pdf_to_docx(self.doc,self.folder,progress=lambda n,t:events.append((n,t)))
        self.assertEqual(events,[(1,2),(2,2)])
    def test_snapshot(self):
        self.source.write_bytes(b'external change')
        self.assertIn('Hello editable world',self.all_text(self.convert().path))
        self.assertEqual(self.source.read_bytes(),b'external change')
    def test_control_characters(self):self.assertEqual(clean_text('a\x00b\uffffc'),'abc')

if __name__=='__main__':unittest.main()
