from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter
from core import SplitError, open_document, page_move_order, compact_page_order, reorder_document

class RuleTests(unittest.TestCase):
    def test_block_later_before(self):self.assertEqual(page_move_order(5,2,3,5),[1,4,2,3,5])
    def test_block_later_after(self):self.assertEqual(page_move_order(5,2,3,5,'after'),[1,4,5,2,3])
    def test_block_earlier_before(self):self.assertEqual(page_move_order(5,4,5,2),[1,4,5,2,3])
    def test_block_earlier_after(self):self.assertEqual(page_move_order(5,4,5,2,'after'),[1,2,4,5,3])
    def test_single_to_front(self):self.assertEqual(page_move_order(5,5,5,1),[5,1,2,3,4])
    def test_single_to_end(self):self.assertEqual(page_move_order(5,1,1,5,'after'),[2,3,4,5,1])
    def test_adjacent_noop(self):
        self.assertEqual(page_move_order(5,2,3,4),[1,2,3,4,5])
        self.assertEqual(page_move_order(5,2,3,1,'after'),[1,2,3,4,5])
    def test_t_in_range(self):
        for t in [2,3,4]:
            with self.subTest(t=t),self.assertRaises(SplitError):page_move_order(5,2,4,t)
    def test_invalid_rules(self):
        for values in [(0,2,5),(3,2,5),(1,6,5),(1,2,0),(1,2,6),(1.5,2,5),(True,2,5)]:
            with self.subTest(values=values),self.assertRaises(SplitError):page_move_order(5,*values)
        with self.assertRaises(SplitError):page_move_order(5,1,2,5,'invalid')
        with self.assertRaises(SplitError):page_move_order(1,1,1,1)
    def test_exhaustive_invariants(self):
        for count in range(2,9):
            original=list(range(1,count+1))
            for m in original:
                for n in range(m,count+1):
                    for t in original:
                        if m<=t<=n:continue
                        for position in ['before','after']:
                            with self.subTest(count=count,m=m,n=n,t=t,position=position):
                                result=page_move_order(count,m,n,t,position)
                                self.assertEqual(sorted(result),original)
                                remaining=[i for i in original if not m<=i<=n]
                                self.assertEqual([i for i in result if not m<=i<=n],remaining)
                                block=list(range(m,n+1));start=result.index(m)
                                self.assertEqual(result[start:start+len(block)],block)
                                if position=='before':self.assertEqual(result[start+len(block)],t)
                                else:self.assertEqual(result[start-1],t)
    def test_compact_preview(self):
        self.assertEqual(compact_page_order([1,4,2,3,5]),'1 → 4 → 2–3 → 5')
        self.assertEqual(compact_page_order(list(range(1,10001))),'1–10000')
        self.assertEqual(compact_page_order([]),'')

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        writer=PdfWriter()
        for i in range(1,6):writer.add_blank_page(width=100+i,height=300)
        self.source=self.folder/'原始 文档.pdf';writer.write(self.source)
        self.doc=open_document(self.source)
    def tearDown(self):self.tmp.cleanup()
    def widths(self,path):return [int(p.mediabox.width) for p in PdfReader(path).pages]
    def test_export_matches_before_preview(self):
        path=reorder_document(self.doc,2,3,5,'before',self.folder)
        self.assertEqual(self.widths(path),[100+p for p in page_move_order(5,2,3,5)])
    def test_export_after(self):
        path=reorder_document(self.doc,2,3,5,'after',self.folder)
        self.assertEqual(self.widths(path),[101,104,105,102,103])
    def test_repeated_no_overwrite(self):
        original=self.source.read_bytes()
        a=reorder_document(self.doc,1,1,5,'after',self.folder,self.source.name)
        b=reorder_document(self.doc,1,1,5,'after',self.folder,self.source.name)
        self.assertNotEqual(a,b);self.assertTrue(a.exists())
        self.assertEqual(self.source.read_bytes(),original)
        self.assertEqual([int(p.mediabox.width) for p in self.doc.reader.pages],[101,102,103,104,105])
    def test_invalid_creates_nothing(self):
        before=set(self.folder.iterdir())
        with self.assertRaises(SplitError):reorder_document(self.doc,2,3,2,'before',self.folder)
        with self.assertRaises(SplitError):reorder_document(self.doc,2,3,5,'before',self.folder,'../bad.pdf')
        with self.assertRaises(SplitError):reorder_document(self.doc,2,3,5,'before','')
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_write_failure_cleanup(self):
        before=set(self.folder.iterdir())
        with patch('core.PdfWriter.write',side_effect=OSError('disk full')):
            with self.assertRaises(SplitError):reorder_document(self.doc,2,3,5,'before',self.folder)
        self.assertEqual(set(self.folder.iterdir()),before)
    def test_encrypted(self):
        writer=PdfWriter();writer.append(self.doc.reader);writer.encrypt('known')
        path=self.folder/'locked.pdf';writer.write(path)
        result=reorder_document(open_document(path,'known'),5,5,1,'before',self.folder)
        self.assertEqual(self.widths(result),[105,101,102,103,104]);self.assertFalse(PdfReader(result).is_encrypted)
    def test_progress(self):
        events=[]
        reorder_document(self.doc,2,3,5,'before',self.folder,progress=lambda n,t:events.append((n,t)))
        self.assertEqual(events,[(5,5)])

if __name__=='__main__':unittest.main()
