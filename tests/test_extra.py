import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from core import open_document, SplitError, PasswordRequired
from extra_core import (parse_page_selection, delete_pages, rotate_pages, extract_text,
                        encrypt_document, decrypt_document, images_to_pdf)


class ExtraTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / '中文 原件.pdf'
        c = Canvas(str(self.source))
        for i in range(1, 5):
            c.setPageSize((200 + i, 300))
            c.drawString(20, 220, f'PAGE {i}')
            c.showPage()
        c.save()
        self.doc = open_document(self.source)
        self.original = self.source.read_bytes()

    def tearDown(self):
        self.assertEqual(self.source.read_bytes(), self.original)
        self.temp.cleanup()

    def test_parse(self):
        self.assertEqual(parse_page_selection('4，1, 2-3,2', 4), [1,2,3,4])

    def test_parse_invalid(self):
        for text in ('', '0', '5', '3-1', '1,', 'x', '1-3-4', '-1', '1.2'):
            with self.subTest(text=text), self.assertRaises(SplitError):
                parse_page_selection(text, 4)

    def test_delete(self):
        result = delete_pages(self.doc, [2,2,4], self.root)
        r = PdfReader(result)
        self.assertEqual([int(p.mediabox.width) for p in r.pages], [201,203])
        self.assertEqual(len(self.doc.reader.pages), 4)

    def test_delete_all_or_invalid(self):
        for pages in ([1,2,3,4], [], [0], [True], [5], ['2']):
            with self.subTest(pages=pages), self.assertRaises(SplitError):
                delete_pages(self.doc, pages, self.root)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_rotate_source_immutable_and_repeat(self):
        for _ in range(2):
            target = rotate_pages(self.doc, [2,4], 270, self.root)
            self.assertEqual([p.rotation for p in PdfReader(target).pages], [0,270,0,270])
            self.assertEqual([p.rotation for p in self.doc.reader.pages], [0,0,0,0])

    def test_rotate_invalid(self):
        for angle in (0, 45, -90, 360, True, '90'):
            with self.subTest(angle=angle), self.assertRaises(SplitError):
                rotate_pages(self.doc, [1], angle, self.root)

    def test_extract_text(self):
        target = extract_text(self.doc, self.root, '文字.txt')
        content = target.read_text(encoding='utf-8')
        for i in range(1,5):
            self.assertIn(f'PAGE {i}', content)
            self.assertIn(f'第 {i} 页', content)
        self.assertEqual(target.suffix, '.txt')

    def test_extract_blank(self):
        path = self.root / 'blank.pdf'
        writer = PdfWriter()
        writer.add_blank_page(100,100)
        writer.write(path)
        with self.assertRaisesRegex(SplitError, 'OCR'):
            extract_text(open_document(path), self.root)

    def test_encrypt_decrypt(self):
        encrypted = encrypt_document(self.doc, '测试密码-example', self.root)
        r = PdfReader(encrypted)
        self.assertTrue(r.is_encrypted)
        self.assertFalse(r.decrypt(''))
        self.assertFalse(r.decrypt('wrong'))
        with self.assertRaises(PasswordRequired):
            open_document(encrypted, 'wrong')
        unlocked = open_document(encrypted, '测试密码-example')
        result = decrypt_document(unlocked, self.root)
        self.assertFalse(PdfReader(result).is_encrypted)
        self.assertEqual([p.extract_text() for p in PdfReader(result).pages], [p.extract_text() for p in self.doc.reader.pages])

    def test_encrypt_invalid(self):
        for password in ('', '   ', None, 'x\0y', 'a'*128, '字'*43):
            with self.subTest(password=password), self.assertRaises(SplitError):
                encrypt_document(self.doc, password, self.root)

    def test_decrypt_unencrypted(self):
        with self.assertRaises(SplitError):
            decrypt_document(self.doc, self.root)

    def test_repeat_unique_outputs(self):
        a = delete_pages(self.doc, [1], self.root)
        b = delete_pages(self.doc, [1], self.root)
        self.assertNotEqual(a.parent, b.parent)
        self.assertTrue(a.exists())

    def test_invalid_filename(self):
        for name in ('../bad.pdf', 'NUL.pdf', 'CON.pdf', '', 'x?.pdf'):
            with self.subTest(name=name), self.assertRaises(SplitError):
                delete_pages(self.doc, [1], self.root, name)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_blank_output(self):
        with self.assertRaises(SplitError):
            rotate_pages(self.doc, [1], 90, '')

    def test_write_failure_cleanup(self):
        with patch.object(PdfWriter, 'write', side_effect=OSError('simulated')):
            with self.assertRaises(SplitError):
                delete_pages(self.doc, [1], self.root)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_progress_failure_cleanup(self):
        def broken(*a):
            raise RuntimeError('simulated')
        with self.assertRaises(SplitError):
            rotate_pages(self.doc, [1], 90, self.root, progress=broken)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_images_order_sizes_alpha_and_source(self):
        paths = []
        for i in (1,2):
            path = self.root / f'{i}.png'
            Image.new('RGBA', (i * 100, 100), (255,0,0,128)).save(path)
            paths.append(path)
        hashes = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
        target = images_to_pdf(paths[::-1], self.root, dpi=100)
        self.assertEqual([round(float(p.mediabox.width)) for p in PdfReader(target).pages], [144,72])
        self.assertEqual([hashlib.sha256(p.read_bytes()).digest() for p in paths], hashes)

    def test_images_invalid(self):
        for paths in ([], [self.source], [self.root/'missing.png']):
            with self.subTest(paths=paths), self.assertRaises(SplitError):
                images_to_pdf(paths, self.root)

    def test_images_animated_rejected(self):
        a,b = Image.new('RGB',(20,20),'red'), Image.new('RGB',(20,20),'blue')
        path = self.root/'animated.webp'
        a.save(path,save_all=True,append_images=[b],format='WEBP')
        with self.assertRaisesRegex(SplitError,'动画'):
            images_to_pdf([path], self.root)
        a.close();b.close()

    def test_images_exif(self):
        path = self.root/'orientation.jpg'
        image = Image.new('RGB',(100,200),'red')
        exif = image.getexif();exif[274]=6
        image.save(path, exif=exif)
        result = images_to_pdf([path],self.root,dpi=100)
        page = PdfReader(result).pages[0]
        self.assertEqual((round(float(page.mediabox.width)),round(float(page.mediabox.height))), (144,72))

    def test_images_failure_cleanup(self):
        path = self.root/'image.png'
        Image.new('RGB',(10,10),'red').save(path)
        with patch.object(Image.Image, 'save',side_effect=OSError('simulated')):
            with self.assertRaises(SplitError):
                images_to_pdf([path],self.root)
        self.assertEqual(set(self.root.iterdir()), {self.source,path})

if __name__ == '__main__':
    unittest.main()
