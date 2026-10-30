from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, DictionaryObject, ArrayObject, NumberObject, TextStringObject
from core import SplitError, open_document, merge_documents

class MergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.paths=[]
        for filename,widths in [('甲 文档.pdf',[101,102]),('乙 {文件}.pdf',[201,202,203])]:
            writer=PdfWriter()
            for w in widths:writer.add_blank_page(width=w,height=300)
            path=self.folder/filename;writer.write(path);self.paths.append(path)
        self.docs=[open_document(p) for p in self.paths]
    def tearDown(self):self.tmp.cleanup()
    def widths(self,path):return [float(p.mediabox.width) for p in PdfReader(path).pages]
    def test_merge_order(self):
        path=merge_documents(self.docs,self.folder,'合并 结果.pdf')
        self.assertEqual(self.widths(path),[101,102,201,202,203])
    def test_reversed_order(self):
        path=merge_documents(self.docs[::-1],self.folder)
        self.assertEqual(self.widths(path),[201,202,203,101,102])
    def test_duplicate_document_core(self):
        path=merge_documents([self.docs[0],self.docs[0]],self.folder)
        self.assertEqual(self.widths(path),[101,102,101,102])
    def test_no_overwrite_and_preserves_sources(self):
        source=[p.read_bytes() for p in self.paths]
        a=merge_documents(self.docs,self.folder,self.paths[0].name)
        b=merge_documents(self.docs,self.folder,self.paths[0].name)
        self.assertNotEqual(a,b);self.assertTrue(a.exists())
        self.assertEqual([p.read_bytes() for p in self.paths],source)
    def test_adds_pdf_extension(self):
        path=merge_documents(self.docs,self.folder,'结果')
        self.assertEqual(path.name,'结果.pdf')
    def test_invalid_names(self):
        before=set(self.folder.iterdir())
        for name in ['', ' ', '../escape.pdf','sub/out.pdf','a\\b.pdf','name?.pdf','CON.pdf','LPT1.pdf','.pdf','name..pdf','x'*101+'.pdf']:
            with self.subTest(name=name), self.assertRaises(SplitError):merge_documents(self.docs,self.folder,name)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_invalid_output(self):
        for path in ['',self.folder/'missing']:
            with self.subTest(path=path),self.assertRaises(SplitError):merge_documents(self.docs,path)
    def test_not_enough_documents(self):
        for docs in [[],self.docs[:1]]:
            with self.subTest(docs=docs),self.assertRaises(SplitError):merge_documents(docs,self.folder)
    def test_write_failure_cleanup(self):
        before=set(self.folder.iterdir())
        with patch('core.PdfWriter.write',side_effect=OSError('disk full')):
            with self.assertRaises(SplitError):merge_documents(self.docs,self.folder)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_progress(self):
        events=[]
        merge_documents(self.docs,self.folder,progress=lambda n,t:events.append((n,t)))
        self.assertEqual(events,[(2,5),(5,5)])
    def test_encrypted_input(self):
        writer=PdfWriter();writer.add_blank_page(width=401,height=300);writer.encrypt('secret')
        path=self.folder/'locked.pdf';writer.write(path)
        result=merge_documents([self.docs[0],open_document(path,'secret')],self.folder)
        self.assertEqual(self.widths(result),[101,102,401]);self.assertFalse(PdfReader(result).is_encrypted)
    def test_same_named_forms_are_isolated(self):
        docs=[]
        for i in range(2):
            writer=PdfWriter();page=writer.add_blank_page(width=100,height=100)
            field=DictionaryObject({NameObject('/Type'):NameObject('/Annot'),NameObject('/Subtype'):NameObject('/Widget'),NameObject('/FT'):NameObject('/Tx'),NameObject('/T'):TextStringObject('name'),NameObject('/V'):TextStringObject(f'Person {i}'),NameObject('/Rect'):ArrayObject([NumberObject(x) for x in [0,0,50,20]])})
            ref=writer._add_object(field)
            page[NameObject('/Annots')]=ArrayObject([ref])
            writer._root_object[NameObject('/AcroForm')]=DictionaryObject({NameObject('/Fields'):ArrayObject([ref])})
            path=self.folder/f'form{i}.pdf';writer.write(path);docs.append(open_document(path))
        result=merge_documents(docs,self.folder)
        fields=PdfReader(result).get_fields()
        self.assertEqual(fields['file001_name']['/V'],'Person 0')
        self.assertEqual(fields['file002_name']['/V'],'Person 1')
        self.assertIn('name',docs[0].reader.get_fields())
        self.assertNotIn('file001_name',docs[0].reader.get_fields())
        second=merge_documents(docs,self.folder)
        self.assertEqual(PdfReader(second).get_fields()['file002_name']['/V'],'Person 1')
    def test_snapshot(self):
        self.paths[0].write_bytes(b'changed after loading')
        result=merge_documents(self.docs,self.folder)
        self.assertEqual(self.widths(result),[101,102,201,202,203])
        self.assertEqual(self.paths[0].read_bytes(),b'changed after loading')

if __name__=='__main__':unittest.main()
