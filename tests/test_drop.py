import tkinter as tk
import unittest

class DropTests(unittest.TestCase):
    def test_tcl_paths_spaces_unicode_braces(self):
        interp=tk.Tcl()
        paths=('C:/测试 文件/{报告}.pdf', 'C:/another folder/test.pdf')
        # TkDnD returns a Tcl list, not a space-separated string.
        tcl_list=interp.call('list',*paths)
        self.assertEqual(interp.splitlist(tcl_list),paths)

if __name__ == '__main__': unittest.main()
