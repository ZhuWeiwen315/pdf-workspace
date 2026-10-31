"""Headless tests of actual GUI operation dispatch; native layout is separate QA."""
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter
from core import open_document
from app import App

class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value

class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        path=self.folder/'source.pdf';c=canvas.Canvas(str(path),pagesize=(300,400))
        for n in range(1,4):c.drawString(30,350,f'Page {n}');c.showPage()
        c.save();self.doc=open_document(path)
        self.app=App.__new__(App);self.app.busy=False;self.app.messages=queue.Queue()
        self.data={'doc':self.doc,'output':Value(str(self.folder)),'name':Value('out.pdf'),'pages':Value('1'),'angle':Value('90'),'dpi':Value('72'),'format':Value('PNG'),'text':Value('TEST'),'start':Value('1'),'password':Value('new-password'),'confirm':Value('new-password'),'title':'Test'}
        self.results=None
        self.app.start_job=lambda op,label:setattr(self,'results',op(lambda n,t:None))
    def tearDown(self):self.tmp.cleanup()
    def run_key(self,key):
        self.app.tools={key:self.data};self.app.run_tool(key);return self.results
    def test_delete_dispatch(self):self.assertEqual(len(PdfReader(self.run_key('delete')[0]).pages),2)
    def test_rotate_dispatch(self):self.assertEqual(PdfReader(self.run_key('rotate')[0]).pages[0].rotation,90)
    def test_text_dispatch(self):
        self.data['name']=Value('out.txt');self.assertIn('Page 1',self.run_key('text')[0].read_text(encoding='utf-8'))
    def test_encrypt_dispatch(self):
        reader=PdfReader(self.run_key('encrypt')[0]);self.assertTrue(reader.is_encrypted);self.assertTrue(reader.decrypt('new-password'))
    def test_decrypt_dispatch(self):
        writer=PdfWriter();writer.append(self.doc.reader);writer.encrypt('known')
        path=self.folder/'locked.pdf';writer.write(path);self.data['doc']=open_document(path,'known')
        self.assertFalse(PdfReader(self.run_key('decrypt')[0]).is_encrypted)
    def test_images_dispatch(self):
        path=self.folder/'image.png';Image.new('RGB',(30,40),'red').save(path);self.app.image_paths=[path]
        self.assertEqual(len(PdfReader(self.run_key('images_pdf')[0]).pages),1)
    def test_pdf_images_dispatch(self):
        with Image.open(self.run_key('pdf_images')[0]) as image:self.assertEqual(image.size,(300,400))
    def test_compress_dispatch(self):
        path=self.run_key('compress')[0];self.assertTrue(path.exists());self.assertEqual(self.app.messages.get()[0],'job_note')
    def test_watermark_dispatch(self):self.assertIn('TEST',PdfReader(self.run_key('watermark')[0]).pages[0].extract_text())
    def test_number_dispatch(self):self.assertIn('1',PdfReader(self.run_key('numbers')[0]).pages[0].extract_text())
    def test_password_mismatch(self):
        self.data['confirm']=Value('different')
        with patch('app.messagebox.showerror') as error:self.run_key('encrypt');error.assert_called_once()
        self.assertIsNone(self.results)
    def test_invalid_pages(self):
        self.data['pages']=Value('99')
        with patch('app.messagebox.showerror') as error:self.run_key('delete');error.assert_called_once()
        self.assertIsNone(self.results)

if __name__=='__main__':unittest.main()
