import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from core import Part, SplitError, PasswordRequired, even_parts, open_document, safe_stem, split_document, validate_parts

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / '测试 文档 {原稿}.pdf'
        writer = PdfWriter()
        for i in range(7): writer.add_blank_page(width=200+i, height=300+i)
        writer.write(self.source)
        self.doc = open_document(self.source)

    def tearDown(self): self.temp.cleanup()

    def test_page_count(self): self.assertEqual(self.doc.pages, 7)
    def test_single_page(self):
        paths = split_document(self.doc, [Part(3, 3)], self.folder)
        reader = PdfReader(paths[0]); self.assertEqual(len(reader.pages), 1)
        self.assertEqual(float(reader.pages[0].mediabox.width), 202)
    def test_ranges_and_order(self):
        paths = split_document(self.doc, [Part(5,7), Part(1,2), Part(2,3)], self.folder)
        self.assertEqual([len(PdfReader(p).pages) for p in paths], [3,2,2])
        self.assertEqual([float(PdfReader(p).pages[0].mediabox.width) for p in paths], [204,200,201])
    def test_no_overwrite(self):
        before = self.source.read_bytes()
        a = split_document(self.doc, [Part(1,7)], self.folder)
        b = split_document(self.doc, [Part(1,7)], self.folder)
        self.assertNotEqual(a, b)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertTrue(a[0].exists())
    def test_invalid_ranges(self):
        for parts in [[], [Part(0,1)], [Part(2,1)], [Part(1,8)], [Part(-1,3)], [Part(1.2,3)], [Part(True,2)]]:
            with self.subTest(parts=parts), self.assertRaises(SplitError): validate_parts(parts,7)
    def test_even_ranges(self): self.assertEqual(even_parts(7,3), [Part(1,3),Part(4,5),Part(6,7)])
    def test_one_per_page(self): self.assertEqual(even_parts(7,7), [Part(i,i) for i in range(1,8)])
    def test_even_invalid(self):
        for x in [0,8,-1,1.5,True]:
            with self.subTest(x=x), self.assertRaises(SplitError): even_parts(7,x)
    def test_non_pdf(self):
        path=self.folder/'x.txt'; path.write_text('hello')
        with self.assertRaises(SplitError): open_document(path)
    def test_corrupt_pdf(self):
        path=self.folder/'bad.pdf'; path.write_bytes(b'%PDF-1.7\ngarbage')
        with self.assertRaises(SplitError): open_document(path)
    def test_missing_file(self):
        with self.assertRaises(SplitError): open_document(self.folder/'none.pdf')
    def test_empty_document(self):
        path=self.folder/'empty.pdf'; PdfWriter().write(path)
        with self.assertRaises(SplitError): open_document(path)
    def test_missing_output_dir(self):
        with self.assertRaises(SplitError): split_document(self.doc,[Part(1,1)],self.folder/'none')
    def test_password(self):
        writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.encrypt('secret')
        path=self.folder/'locked.pdf'; writer.write(path)
        for password in [None,'wrong']:
            with self.subTest(password=password), self.assertRaises(PasswordRequired): open_document(path,password)
        doc=open_document(path,'secret')
        paths=split_document(doc,[Part(1,1)],self.folder)
        self.assertFalse(PdfReader(paths[0]).is_encrypted)
    def test_snapshot(self):
        self.source.write_bytes(b'changed externally')
        paths=split_document(self.doc,[Part(1,2)],self.folder)
        self.assertEqual(len(PdfReader(paths[0]).pages),2)
        self.assertEqual(self.source.read_bytes(),b'changed externally')
    def test_cleanup_failure(self):
        before=set(self.folder.iterdir())
        with patch('core.PdfWriter.write',side_effect=OSError('disk full')):
            with self.assertRaises(SplitError): split_document(self.doc,[Part(1,1)],self.folder)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_progress(self):
        events=[]
        split_document(self.doc,[Part(1,2),Part(3,7)],self.folder,lambda n,t: events.append((n,t)))
        self.assertEqual(events,[(2,7),(7,7)])
    def test_text_content_preserved(self):
        writer=PdfWriter()
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        for word in ['FIRST', 'SECOND', 'THIRD']:
            page=writer.add_blank_page(width=300,height=400)
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
            content=DecodedStreamObject(); content.set_data(f'BT /F1 12 Tf 50 100 Td ({word}) Tj ET'.encode())
            page[NameObject('/Contents')]=content
        path=self.folder/'text.pdf'; writer.write(path)
        outputs=split_document(open_document(path),[Part(2,3),Part(1,1)],self.folder)
        self.assertEqual([p.extract_text() for p in PdfReader(outputs[0]).pages],['SECOND','THIRD'])
        self.assertEqual(PdfReader(outputs[1]).pages[0].extract_text(),'FIRST')
    def test_empty_output(self):
        with self.assertRaises(SplitError): split_document(self.doc,[Part(1,1)],'')
    def test_rotation_crop(self):
        writer=PdfWriter(); page=writer.add_blank_page(width=300,height=400)
        page.rotate(90); page.cropbox.lower_left=(10,20)
        path=self.folder/'rotated.pdf'; writer.write(path)
        paths=split_document(open_document(path),[Part(1,1)],self.folder)
        page=PdfReader(paths[0]).pages[0]
        self.assertEqual(page.rotation,90); self.assertEqual(tuple(page.cropbox.lower_left),(10,20))
    def test_invalid_range_no_outputs(self):
        before=set(self.folder.iterdir())
        with self.assertRaises(SplitError): split_document(self.doc,[Part(1,99)],self.folder)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_safe_name(self): self.assertEqual(safe_stem('a<b:c*?'), 'a_b_c__')

if __name__ == '__main__': unittest.main()
