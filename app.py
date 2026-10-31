"""Local PDF workspace: sidebar navigation, splitting and merging."""
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinterdnd2 import DND_FILES, TkinterDnD
from core import Part, SplitError, PasswordRequired, even_parts, open_document, split_document, validate_parts, merge_documents, page_move_order, compact_page_order, reorder_document

BG = '#ffffff'
SIDE = '#f7f7f8'
INK = '#202123'
MUTED = '#6b6d73'
LINE = '#e6e7eb'
ACCENT = '#202123'


class App:
    def __init__(self, root):
        self.root = root
        self.doc = None
        self.busy = False
        self.rows = []
        self.merge_docs = []
        self.reorder_doc = None
        self.word_doc = None
        self.word_output = tk.StringVar()
        self.word_name = tk.StringVar(value="转换结果.docx")
        self.word_info = tk.StringVar(value="尚未选择文件")
        self.word_notice = tk.StringVar(value="转换结果将在这里显示。")
        self.mode = 'split'
        self.messages = queue.Queue()
        self.tool_buttons = []
        self.image_paths = []
        self.tools = {}
        specs = {
            'delete': ('删除页面','移除选定页，保留其余页面。','删除页面.pdf','删除页面不是安全涂黑，不能用于隐去页面内的敏感文字。'),
            'rotate': ('旋转页面','按顺时针方向旋转选定页面。','旋转页面.pdf','角度是在原有旋转角度基础上增加。'),
            'text': ('提取文字','把 PDF 的文字层导出为 UTF-8 文本。','提取文字.txt','不提供 OCR；扫描页无法提取文字，复杂阅读顺序可能需要整理。TXT 不受原密码保护。'),
            'encrypt': ('设置密码','为另存的 PDF 设置打开密码。','加密文件.pdf','使用 AES-256。请妥善记住密码；遗忘后本工具不能恢复。'),
            'decrypt': ('移除密码','用已知密码打开后，另存为无密码 PDF。','移除密码.pdf','只支持你已知密码的文件，不提供破解。输出文件将不再受密码保护。'),
            'images_pdf': ('图片转 PDF','把多张图片按顺序合成为一份 PDF。','图片合成.pdf','支持 PNG/JPEG/BMP/WebP 单帧图片，透明区域变白，可能重编码，并非无损归档。'),
            'pdf_images': ('PDF 转图片','把选定页面导出为 PNG 或 JPEG。','','这是页面渲染，不是提取原始图片；页数较多会占用较多磁盘空间，图片不受原密码保护。'),
            'compress': ('压缩 PDF','压缩内容流，不降低图片分辨率。','压缩文件.pdf','不保证文件变小；已压缩的文件可能保持原大小或变大。完成后会显示前后大小。'),
            'watermark': ('添加水印','给选定页面加上半透明文字水印。','水印文件.pdf','水印不是安全涂黑，可被 PDF 编辑器移除；也可能覆盖页面内容。'),
            'numbers': ('添加页码','在选定页面底部中央添加页码。','页码文件.pdf','按原始物理页序编号：起始值为 1 时，选第 3 页会标为 3。可能覆盖原有页脚。')
        }
        for key,(title,description,filename,note) in specs.items():
            self.tools[key] = dict(title=title,description=description,note=note,doc=None,
                info=tk.StringVar(value='尚未选择文件'),output=tk.StringVar(),name=tk.StringVar(value=filename),
                pages=tk.StringVar(value='1'),angle=tk.StringVar(value='90'),dpi=tk.StringVar(value='150'),
                format=tk.StringVar(value='PNG'),text=tk.StringVar(value='仅供参考'),start=tk.StringVar(value='1'),
                password=tk.StringVar(),confirm=tk.StringVar())
        self.output = tk.StringVar()
        self.merge_output = tk.StringVar()
        self.merge_name = tk.StringVar(value='合并文档.pdf')
        self.reorder_output = tk.StringVar()
        self.reorder_name = tk.StringVar(value='调整顺序.pdf')
        self.reorder_info = tk.StringVar(value='尚未选择文件')
        self.move_m = tk.StringVar(value='1')
        self.move_n = tk.StringVar(value='1')
        self.move_t = tk.StringVar(value='2')
        self.move_position = tk.StringVar(value='before')
        self.order_preview = tk.StringVar(value='选择 PDF 后，填写要移动的页码。')
        self.count = tk.StringVar(value='2')
        self.info = tk.StringVar(value='尚未选择文件')
        self.merge_info = tk.StringVar(value='0 个文件 · 0 页')
        self.status = tk.StringVar(value='就绪 · 所有文件在本机处理')
        root.title('PDF 工作台 1.4.0')
        root.geometry('1100x790')
        root.minsize(990, 730)
        root.configure(bg=BG)
        root.option_add('*Font', ('Microsoft YaHei UI', 10))
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Microsoft YaHei UI', 10), background=BG, foreground=INK)
        style.configure('TFrame', background=BG)
        style.configure('TLabel', background=BG, foreground=INK)
        style.configure('Muted.TLabel', foreground=MUTED, font=('Microsoft YaHei UI', 9))
        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 24, 'bold'))
        style.configure('Section.TLabel', font=('Microsoft YaHei UI', 11, 'bold'))
        style.configure('TButton', padding=(13, 8), background='#f4f4f5', borderwidth=0, relief='flat')
        style.map('TButton', background=[('active', '#e9e9ed'), ('disabled', '#f5f5f5')], foreground=[('disabled', '#b1b1b5')])
        style.configure('Primary.TButton', background=ACCENT, foreground='white', padding=(22,10))
        style.map('Primary.TButton', background=[('active','#3e3f43'),('disabled','#aaaab0')], foreground=[('disabled','#eeeeee')])
        style.configure('TEntry', fieldbackground='white', bordercolor=LINE, padding=6)
        style.configure('TSpinbox', fieldbackground='white', bordercolor=LINE, padding=6)
        style.configure('Treeview', rowheight=42, fieldbackground=BG, background=BG, borderwidth=0)
        style.configure('Treeview.Heading', background='#f7f7f8', foreground=MUTED, relief='flat', padding=(8,10))
        style.map('Treeview', background=[('selected','#e8e8ed')], foreground=[('selected',INK)])
        style.configure('Horizontal.TProgressbar', background='#5b8f78', troughcolor='#eeeeef', borderwidth=0, thickness=4)
        sidebar = tk.Frame(root, bg=SIDE, width=205)
        sidebar.pack(side='left', fill='y'); sidebar.pack_propagate(False)
        tk.Label(sidebar, text='PDF 工作台', bg=SIDE, fg=INK, font=('Microsoft YaHei UI',15,'bold')).pack(anchor='w', padx=22, pady=(28,4))
        tk.Label(sidebar, text='简单处理每一页', bg=SIDE, fg=MUTED, font=('Microsoft YaHei UI',9)).pack(anchor='w', padx=22)
        nav_host=tk.Frame(sidebar,bg=SIDE);nav_host.pack(fill='both',expand=True,pady=(20,0))
        nav_canvas=tk.Canvas(nav_host,bg=SIDE,highlightthickness=0,width=188,height=200)
        nav_bar=ttk.Scrollbar(nav_host,orient='vertical',command=nav_canvas.yview)
        nav_canvas.configure(yscrollcommand=nav_bar.set)
        nav_bar.pack(side='right',fill='y');nav_canvas.pack(side='left',fill='both',expand=True)
        nav_frame=tk.Frame(nav_canvas,bg=SIDE)
        nav_window=nav_canvas.create_window((0,0),window=nav_frame,anchor='nw')
        nav_frame.bind('<Configure>',lambda e:nav_canvas.configure(scrollregion=nav_canvas.bbox('all')))
        nav_canvas.bind('<Configure>',lambda e:nav_canvas.itemconfigure(nav_window,width=e.width))
        self.nav = {}
        groups=[('文档整理',[('split','PDF 分离'),('merge','PDF 合并'),('reorder','调整顺序'),('delete','删除页面'),('rotate','旋转页面')]),
                ('格式转换',[('word','PDF 转 Word'),('text','提取文字'),('pdf_images','PDF 转图片'),('images_pdf','图片转 PDF')]),
                ('保护与修饰',[('encrypt','设置密码'),('decrypt','移除密码'),('compress','压缩 PDF'),('watermark','添加水印'),('numbers','添加页码')])]
        for group,items in groups:
            tk.Label(nav_frame,text=group,bg=SIDE,fg='#8c8d94',font=('Microsoft YaHei UI',9)).pack(anchor='w',padx=22,pady=(13,6))
            for key,title in items:
                button=tk.Button(nav_frame,text='  '+title,anchor='w',relief='flat',bd=0,padx=10,pady=10,cursor='hand2',bg=SIDE,fg=INK,activebackground='#e9e9ed',command=lambda k=key:self.show_page(k))
                button.pack(fill='x',padx=9,pady=2);self.nav[key]=button
        def scroll_navigation(event):
            x,y=event.x_root,event.y_root
            if not (nav_host.winfo_rootx()<=x<nav_host.winfo_rootx()+nav_host.winfo_width() and nav_host.winfo_rooty()<=y<nav_host.winfo_rooty()+nav_host.winfo_height()):return
            number=getattr(event,'num',None);delta=getattr(event,'delta',0)
            direction=-1 if number==4 or delta>0 else (1 if number==5 or delta<0 else 0)
            if direction:
                nav_canvas.yview_scroll(direction*3,'units');return 'break'
        for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
            root.bind_all(sequence,scroll_navigation,add='+')
        bottom=tk.Frame(sidebar,bg=SIDE); bottom.pack(side='bottom',fill='x',padx=22,pady=25)
        tk.Label(bottom,text='●  本地处理',bg=SIDE,fg='#468366',font=('Microsoft YaHei UI',9)).pack(anchor='w')
        tk.Label(bottom,text='文件不上传 · 原件不改动\n版本 1.4.0',bg=SIDE,fg=MUTED,justify='left',font=('Microsoft YaHei UI',9)).pack(anchor='w',pady=(7,0))
        tk.Frame(root,bg=LINE,width=1).pack(side='left',fill='y')
        main=ttk.Frame(root,padding=(30,24,30,18)); main.pack(side='left',fill='both',expand=True)
        self.pages={}
        page_host=ttk.Frame(main); page_host.pack(fill='both',expand=True)
        page_host.columnconfigure(0,weight=1); page_host.rowconfigure(0,weight=1)
        for key in ['split','merge','reorder','word']+list(self.tools):
            frame=ttk.Frame(page_host); frame.grid(row=0,column=0,sticky='nsew'); self.pages[key]=frame
        self.build_split(self.pages['split'])
        self.build_merge(self.pages['merge'])
        self.build_reorder(self.pages['reorder'])
        self.build_word(self.pages['word'])
        for key in self.tools:self.build_tool(self.pages[key],key)
        for variable in (self.move_m,self.move_n,self.move_t,self.move_position):
            variable.trace_add('write',self.refresh_order_preview)
        self.progress=ttk.Progressbar(main,mode='determinate'); self.progress.pack(fill='x',pady=(14,9))
        ttk.Label(main,textvariable=self.status,style='Muted.TLabel',wraplength=760).pack(anchor='w')
        root.drop_target_register(DND_FILES); root.dnd_bind('<<Drop>>',self.on_drop)
        self.show_page('split')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100,self.poll)

    def header(self,parent,title,description):
        ttk.Label(parent,text=title,style='Title.TLabel').pack(anchor='w')
        ttk.Label(parent,text=description,style='Muted.TLabel').pack(anchor='w',pady=(8,23))

    def drop_area(self,parent,text,command):
        box=tk.Label(parent,text=text,bg='#fafafa',fg=MUTED,height=4,bd=1,relief='solid',highlightthickness=0,cursor='hand2',font=('Microsoft YaHei UI',11))
        box.pack(fill='x'); box.bind('<Button-1>',lambda e:command()); return box

    def output_row(self,parent,variable,command):
        row=ttk.Frame(parent); row.pack(fill='x',pady=(9,0))
        ttk.Entry(row,textvariable=variable).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='选择位置',command=command).pack(side='left',padx=(9,0))

    def build_split(self,parent):
        self.header(parent,'PDF 分离','把一份文档，整理成你需要的几份。')
        self.drop=self.drop_area(parent,'拖入一个 PDF 文件\n或点击这里选择文件',self.choose)
        ttk.Label(parent,textvariable=self.info,style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(10,19))
        controls=ttk.Frame(parent); controls.pack(fill='x',pady=(0,12))
        ttk.Label(controls,text='设置页码范围',style='Section.TLabel').pack(side='left')
        ttk.Button(controls,text='+ 增加一份',command=self.add).pack(side='right')
        ttk.Button(controls,text='均分生成',command=self.generate).pack(side='right',padx=9)
        ttk.Label(controls,text='份').pack(side='right')
        ttk.Spinbox(controls,from_=1,to=9999,textvariable=self.count,width=4).pack(side='right',padx=7)
        ttk.Label(controls,text='分成').pack(side='right')
        ttk.Label(parent,text='包含起止页 · 从 1 开始计数 · 支持重复范围或跳过页面',style='Muted.TLabel').pack(anchor='w',pady=(0,8))
        host=ttk.Frame(parent); host.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(host,highlightthickness=0,height=130,bg=BG)
        bar=ttk.Scrollbar(host,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set); bar.pack(side='right',fill='y'); self.canvas.pack(side='left',fill='both',expand=True)
        self.range_frame=ttk.Frame(self.canvas)
        self.window=self.canvas.create_window((0,0),window=self.range_frame,anchor='nw')
        self.range_frame.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.window,width=e.width))
        self.canvas.bind('<MouseWheel>',self.scroll)
        ttk.Separator(parent).pack(fill='x',pady=15)
        ttk.Label(parent,text='输出位置',style='Section.TLabel').pack(anchor='w')
        self.output_row(parent,self.output,self.choose_output)
        footer=ttk.Frame(parent); footer.pack(fill='x',pady=(14,0))
        ttk.Label(footer,text='每次新建结果文件夹，不覆盖原文件。',style='Muted.TLabel').pack(side='left')
        self.run_button=ttk.Button(footer,text='开始分离  →',style='Primary.TButton',command=self.run); self.run_button.pack(side='right')

    def build_merge(self,parent):
        self.header(parent,'PDF 合并','按你指定的顺序，把多份文档合为一份。')
        self.merge_drop=self.drop_area(parent,'拖入多个 PDF 文件\n或点击这里添加文件',self.choose_merge)
        toolbar=ttk.Frame(parent); toolbar.pack(fill='x',pady=(18,10))
        ttk.Label(toolbar,text='合并顺序',style='Section.TLabel').pack(side='left')
        ttk.Label(toolbar,textvariable=self.merge_info,style='Muted.TLabel').pack(side='left',padx=13)
        ttk.Button(toolbar,text='+ 添加文件',command=self.choose_merge).pack(side='right')
        host=ttk.Frame(parent); host.pack(fill='both',expand=True)
        self.merge_tree=ttk.Treeview(host,columns=('order','name','pages'),show='headings',selectmode='browse',height=4)
        for col,title,width,anchor in [('order','顺序',60,'center'),('name','文件名称',420,'w'),('pages','页数',70,'center')]:
            self.merge_tree.heading(col,text=title);self.merge_tree.column(col,width=width,anchor=anchor,stretch=(col=='name'))
        self.merge_tree.pack(side='left',fill='both',expand=True)
        bar=ttk.Scrollbar(host,orient='vertical',command=self.merge_tree.yview);bar.pack(side='right',fill='y');self.merge_tree.configure(yscrollcommand=bar.set)
        actions=ttk.Frame(parent); actions.pack(fill='x',pady=(9,0))
        for text,func in [('上移',lambda:self.move_merge(-1)),('下移',lambda:self.move_merge(1)),('移除',self.remove_merge),('清空',self.clear_merge)]:
            ttk.Button(actions,text=text,command=func).pack(side='left',padx=(0,7))
        ttk.Label(actions,text='从上到下依次合并',style='Muted.TLabel').pack(side='right')
        ttk.Separator(parent).pack(fill='x',pady=15)
        name_row=ttk.Frame(parent);name_row.pack(fill='x')
        ttk.Label(name_row,text='输出文件名',style='Section.TLabel').pack(side='left')
        ttk.Entry(name_row,textvariable=self.merge_name,width=30).pack(side='right',fill='x',expand=True,padx=(18,0))
        self.output_row(parent,self.merge_output,self.choose_merge_output)
        footer=ttk.Frame(parent);footer.pack(fill='x',pady=(14,0))
        ttk.Label(footer,text='输出不保留密码保护或有效数字签名。',style='Muted.TLabel').pack(side='left')
        self.merge_button=ttk.Button(footer,text='开始合并  →',style='Primary.TButton',command=self.run_merge);self.merge_button.pack(side='right')

    def build_reorder(self,parent):
        self.header(parent,'调整顺序','移动一页或一段页面，其他页面保持原来的相对顺序。')
        self.reorder_drop=self.drop_area(parent,'拖入一个 PDF 文件\n或点击这里选择文件',self.choose_reorder)
        ttk.Label(parent,textvariable=self.reorder_info,style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(10,22))
        ttk.Label(parent,text='移动哪些页面？',style='Section.TLabel').pack(anchor='w')
        row=ttk.Frame(parent);row.pack(fill='x',pady=(12,18))
        for label,var in [('从第 m 页',self.move_m),('到第 n 页',self.move_n)]:
            ttk.Label(row,text=label).pack(side='left',padx=(0,10))
            ttk.Entry(row,textvariable=var,width=7).pack(side='left',padx=(0,22))
        ttk.Label(row,text='m = n 时移动单页',style='Muted.TLabel').pack(side='left')
        target=ttk.Frame(parent);target.pack(fill='x',pady=(0,17))
        ttk.Label(target,text='插入到原始第 t 页').pack(side='left',padx=(0,10))
        ttk.Entry(target,textvariable=self.move_t,width=7).pack(side='left',padx=(0,20))
        ttk.Radiobutton(target,text='之前',variable=self.move_position,value='before').pack(side='left',padx=(0,14))
        ttk.Radiobutton(target,text='之后',variable=self.move_position,value='after').pack(side='left')
        ttk.Label(parent,text='m、n、t 均为原始 PDF 页码。t 不能位于 m 到 n 内。',style='Muted.TLabel').pack(anchor='w',pady=(0,14))
        preview=tk.Frame(parent,bg='#f7f7f8',padx=18,pady=14)
        preview.pack(fill='both',expand=True)
        tk.Label(preview,text='调整后的原始页码顺序',bg='#f7f7f8',fg=MUTED,font=('Microsoft YaHei UI',9)).pack(anchor='w')
        tk.Label(preview,textvariable=self.order_preview,bg='#f7f7f8',fg=INK,font=('Microsoft YaHei UI',12),justify='left',wraplength=690).pack(anchor='w',pady=(10,0))
        ttk.Separator(parent).pack(fill='x',pady=15)
        row=ttk.Frame(parent);row.pack(fill='x')
        ttk.Label(row,text='输出文件名',style='Section.TLabel').pack(side='left')
        ttk.Entry(row,textvariable=self.reorder_name).pack(side='left',fill='x',expand=True,padx=(18,0))
        self.output_row(parent,self.reorder_output,lambda:self.pick_folder(self.reorder_output))
        footer=ttk.Frame(parent);footer.pack(fill='x',pady=(14,0))
        ttk.Label(footer,text='输出不保留密码保护或有效数字签名。',style='Muted.TLabel').pack(side='left')
        self.reorder_button=ttk.Button(footer,text='确认并导出  →',style='Primary.TButton',command=self.run_reorder)
        self.reorder_button.pack(side='right')

    def choose_reorder(self):
        if self.busy:return
        path=filedialog.askopenfilename(title='选择要调整顺序的 PDF',filetypes=[('PDF 文件','*.pdf')])
        if path:self.load_reorder(path)

    def load_reorder(self,path):
        if self.busy:return
        if self.reorder_doc and not messagebox.askyesno('更换文件','更换文件会重置移动规则，是否继续？'):return
        doc=self.read_pdf(path)
        if doc is None:return
        self.reorder_doc=doc
        self.reorder_info.set(f'{doc.path.name}  ·  {doc.pages} 页')
        self.reorder_drop.configure(text='文件已就绪\n点击或拖入其他 PDF 可更换')
        self.reorder_output.set(str(doc.path.parent))
        self.move_m.set('1');self.move_n.set('1');self.move_t.set('2');self.move_position.set('before')
        self.refresh_order_preview()
        self.status.set('文件已加载 · 所有输入均按原始 PDF 的物理页序计数')

    def read_move_rule(self):
        if self.reorder_doc is None:raise SplitError('请先选择 PDF。')
        try:m,n,t=int(self.move_m.get()),int(self.move_n.get()),int(self.move_t.get())
        except ValueError:raise SplitError('m、n、t 都必须是整数。')
        position=self.move_position.get()
        order=page_move_order(self.reorder_doc.pages,m,n,t,position)
        return m,n,t,position,order

    def refresh_order_preview(self,*args):
        if self.reorder_doc is None:return
        try:
            m,n,t,position,order=self.read_move_rule()
            preview=compact_page_order(order)
            if order==list(range(1,self.reorder_doc.pages+1)):
                preview+='\n当前规则不会改变页面顺序。'
            self.order_preview.set(preview)
        except SplitError as exc:self.order_preview.set(str(exc))

    def run_reorder(self):
        if self.busy:return
        try:
            m,n,t,position,order=self.read_move_rule()
            if not self.reorder_output.get().strip() or not Path(self.reorder_output.get()).is_dir():raise SplitError('请选择存在的输出文件夹。')
        except SplitError as exc:messagebox.showerror('检查移动规则',str(exc));return
        where='之前' if position=='before' else '之后'
        preview=compact_page_order(order)
        no_change='\n注意：当前规则不会改变页面顺序。' if order==list(range(1,self.reorder_doc.pages+1)) else ''
        if not messagebox.askyesno('确认页面顺序',f'把原始第 {m} 到 {n} 页移到原始第 {t} 页{where}。\n\n调整后的原始页码顺序：\n{preview}{no_change}\n\n确认导出？'):return
        doc,output,name=self.reorder_doc,self.reorder_output.get(),self.reorder_name.get()
        self.start_job(lambda cb:[reorder_document(doc,m,n,t,position,output,name,cb)],'调整顺序')

    def build_word(self,parent):
        self.header(parent,'PDF 转 Word','把文字型 PDF 转成可编辑的 Word 文档，在本机完成。')
        self.word_drop=self.drop_area(parent,'拖入一个 PDF 文件\n或点击这里选择文件',self.choose_word)
        ttk.Label(parent,textvariable=self.word_info,style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(10,22))
        card=tk.Frame(parent,bg='#f7f7f8',padx=20,pady=18);card.pack(fill='x')
        tk.Label(card,text='转换前请了解',bg='#f7f7f8',fg=INK,font=('Microsoft YaHei UI',11,'bold')).pack(anchor='w')
        tk.Label(card,text='• 文字和识别到的表格可编辑，图片仍是图片。\n• 尽量保留字号、页面大小和内容顺序，不保证排版完全一致。\n• 不提供 OCR：纯扫描件会提示无法提取文字。\n• 双栏、公式、复杂表格、页眉页脚可能需要手动整理。\n• 未重建的矢量图或表格内图片会附原页参考图。\n• 输出不保留原文件的密码保护或数字签名。',bg='#f7f7f8',fg=MUTED,justify='left',wraplength=690,font=('Microsoft YaHei UI',10)).pack(anchor='w',pady=(12,0))
        result=ttk.Frame(parent);result.pack(fill='both',expand=True,pady=(18,0))
        ttk.Label(result,text='转换情况',style='Section.TLabel').pack(anchor='w')
        ttk.Label(result,textvariable=self.word_notice,style='Muted.TLabel',wraplength=730,justify='left').pack(anchor='w',pady=(10,0))
        ttk.Separator(parent).pack(fill='x',pady=15)
        row=ttk.Frame(parent);row.pack(fill='x')
        ttk.Label(row,text='Word 文件名',style='Section.TLabel').pack(side='left')
        ttk.Entry(row,textvariable=self.word_name).pack(side='left',fill='x',expand=True,padx=(18,0))
        self.output_row(parent,self.word_output,lambda:self.pick_folder(self.word_output))
        footer=ttk.Frame(parent);footer.pack(fill='x',pady=(14,0))
        ttk.Label(footer,text='另存为 .docx，保留原始 PDF。',style='Muted.TLabel').pack(side='left')
        self.word_button=ttk.Button(footer,text='转换为 Word  →',style='Primary.TButton',command=self.run_word)
        self.word_button.pack(side='right')

    def choose_word(self):
        if self.busy:return
        path=filedialog.askopenfilename(title='选择要转换的 PDF',filetypes=[('PDF 文件','*.pdf')])
        if path:self.load_word(path)

    def load_word(self,path):
        if self.busy:return
        doc=self.read_pdf(path)
        if doc is None:return
        self.word_doc=doc;self.word_info.set(f'{doc.path.name}  ·  {doc.pages} 页')
        self.word_output.set(str(doc.path.parent));self.word_name.set(doc.path.stem[:80]+'.docx')
        self.word_drop.configure(text='文件已就绪\n点击或拖入其他 PDF 可更换')
        self.word_notice.set('已加载。转换时会检查文字；纯扫描件需要额外的 OCR 工具。')
        self.status.set('文件已加载 · 文档越大转换越慢，请等待完成后再关闭')

    def run_word(self):
        if self.busy:return
        if self.word_doc is None:messagebox.showinfo('先选择 PDF','请先选择要转换的 PDF。');return
        if not self.word_output.get().strip() or not Path(self.word_output.get()).is_dir():
            messagebox.showerror('选择输出位置','请选择存在的输出文件夹。');return
        doc,output,name=self.word_doc,self.word_output.get(),self.word_name.get()
        self.word_notice.set('正在提取文字和表格，转换不会上传文件。')
        def operation(cb):
            from word_export import convert_pdf_to_docx
            result=convert_pdf_to_docx(doc,output,name,cb)
            self.messages.put(('word_notice',result.summary))
            return [result.path]
        self.start_job(operation,'PDF 转 Word')

    def build_tool(self,parent,key):
        data=self.tools[key]
        self.header(parent,data['title'],data['description'])
        choose=(self.choose_images if key=='images_pdf' else lambda:self.choose_tool(key))
        drop_text='拖入多张图片，或点击这里添加' if key=='images_pdf' else '拖入一个 PDF 文件\n或点击这里选择文件'
        self.drop_area(parent,drop_text,choose)
        ttk.Label(parent,textvariable=data['info'],style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(10,18))
        config=ttk.Frame(parent);config.pack(fill='x')
        def entry(label,variable,width=24,show=None):
            row=ttk.Frame(config);row.pack(fill='x',pady=(0,10))
            ttk.Label(row,text=label,width=13).pack(side='left')
            widget=ttk.Entry(row,textvariable=variable,width=width,show=show or '')
            widget.pack(side='left',fill='x',expand=True)
        def choice(label,variable,values):
            row=ttk.Frame(config);row.pack(fill='x',pady=(0,10))
            ttk.Label(row,text=label,width=13).pack(side='left')
            ttk.Combobox(row,textvariable=variable,values=values,state='readonly',width=18).pack(side='left')
        if key in ('delete','rotate','pdf_images','watermark','numbers'):
            entry('页码（1,3-5）',data['pages'])
        if key=='rotate':choice('顺时针旋转',data['angle'],('90','180','270'))
        if key=='pdf_images':
            choice('图片格式',data['format'],('PNG','JPEG'));entry('DPI（36–300）',data['dpi'])
        if key=='watermark':entry('水印文字',data['text'])
        if key=='numbers':entry('原第 1 页编号',data['start'])
        if key=='encrypt':
            entry('新密码',data['password'],show='*');entry('再次输入',data['confirm'],show='*')
        if key=='images_pdf':
            entry('DPI（36–600）',data['dpi'])
            self.image_list=tk.Listbox(config,height=5,selectmode='browse',bg=BG,fg=INK,relief='solid',bd=1,exportselection=False)
            self.image_list.pack(fill='x')
            controls=ttk.Frame(config);controls.pack(fill='x',pady=(7,0))
            for label,command in [('+ 添加',self.choose_images),('上移',lambda:self.move_image(-1)),('下移',lambda:self.move_image(1)),('移除',self.remove_image),('清空',self.clear_images)]:
                ttk.Button(controls,text=label,command=command).pack(side='left',padx=(0,7))
        note=ttk.Frame(parent);note.pack(fill='both',expand=True,pady=(15,0))
        ttk.Label(note,text=data['note'],style='Muted.TLabel',wraplength=730,justify='left').pack(anchor='w')
        ttk.Label(note,text='所有输出均写入新文件夹，不修改原件。',style='Muted.TLabel').pack(anchor='w',pady=(10,0))
        if key not in ('encrypt','images_pdf','pdf_images','text'):
            ttk.Label(note,text='生成的 PDF 不保留密码保护；数字签名不会保持有效。',style='Muted.TLabel').pack(anchor='w',pady=(6,0))
        ttk.Separator(parent).pack(fill='x',pady=15)
        if key!='pdf_images':
            row=ttk.Frame(parent);row.pack(fill='x')
            ttk.Label(row,text='输出文件名',style='Section.TLabel').pack(side='left')
            ttk.Entry(row,textvariable=data['name']).pack(side='left',fill='x',expand=True,padx=(18,0))
        self.output_row(parent,data['output'],lambda:self.pick_folder(data['output']))
        button=ttk.Button(parent,text=data['title']+'  →',style='Primary.TButton',command=lambda:self.run_tool(key))
        button.pack(anchor='e',pady=(14,0));self.tool_buttons.append(button)

    def choose_tool(self,key):
        if self.busy:return
        path=filedialog.askopenfilename(title='选择 PDF',filetypes=[('PDF 文件','*.pdf')])
        if path:self.load_tool(key,path)

    def load_tool(self,key,path):
        if self.busy:return
        doc=self.read_pdf(path)
        if doc is None:return
        data=self.tools[key];data['doc']=doc
        data['info'].set(f'{doc.path.name}  ·  {doc.pages} 页')
        data['output'].set(str(doc.path.parent))
        data['pages'].set('1' if key=='delete' or doc.pages==1 else f'1-{doc.pages}')
        data['password'].set('');data['confirm'].set('')
        self.status.set('文件已加载 · 请检查选项后导出')

    def choose_images(self):
        if self.busy:return
        paths=filedialog.askopenfilenames(title='选择图片',filetypes=[('图片','*.png *.jpg *.jpeg *.bmp *.webp')])
        if paths:self.add_image_paths(paths)

    def add_image_paths(self,paths):
        if self.busy:return
        from PIL import Image
        added=0
        for raw in paths:
            path=Path(raw).resolve()
            if path in self.image_paths:continue
            try:
                with Image.open(path) as img:
                    if img.format not in ('PNG','JPEG','BMP','WEBP') or getattr(img,'n_frames',1)!=1:
                        raise ValueError('请选择单帧 PNG/JPEG/BMP/WebP 图片。')
                if len(self.image_paths)>=100:raise ValueError('每次最多添加 100 张图片。')
            except Exception as exc:
                messagebox.showerror('无法添加图片',f'{path.name}\n{exc}');continue
            self.image_paths.append(path);added+=1
            if not self.tools['images_pdf']['output'].get():self.tools['images_pdf']['output'].set(str(path.parent))
        self.refresh_images();self.status.set(f'已添加 {added} 张图片 · 请检查排序')

    def refresh_images(self,selected=None):
        self.image_list.delete(0,'end')
        for i,path in enumerate(self.image_paths,1):self.image_list.insert('end',f'{i:02d}  {path.name}')
        self.tools['images_pdf']['info'].set(f'{len(self.image_paths)} 张图片 · 按列表从上到下合成')
        if selected is not None and self.image_paths:
            index=min(selected,len(self.image_paths)-1);self.image_list.selection_set(index);self.image_list.see(index)

    def move_image(self,delta):
        if self.busy:return
        selected=self.image_list.curselection()
        if not selected:return
        i=selected[0];j=i+delta
        if 0<=j<len(self.image_paths):
            self.image_paths[i],self.image_paths[j]=self.image_paths[j],self.image_paths[i];self.refresh_images(j)

    def remove_image(self):
        if self.busy:return
        selected=self.image_list.curselection()
        if selected:
            index=selected[0];self.image_paths.pop(index);self.refresh_images(index)

    def clear_images(self):
        if self.busy:return
        if self.image_paths and messagebox.askyesno('清空图片列表','仅移出列表，不删除原图片，是否继续？'):
            self.image_paths.clear();self.refresh_images()

    def run_tool(self,key):
        if self.busy:return
        import extra_core as extra
        import pdf_more as more
        data=self.tools[key];doc=data['doc'];output=data['output'].get();name=data['name'].get()
        if key!='images_pdf' and doc is None:messagebox.showinfo('先选择 PDF','请先选择一个 PDF。');return
        try:
            if not output.strip() or not Path(output).is_dir():raise SplitError('请选择存在的输出文件夹。')
            pages=extra.parse_page_selection(data['pages'].get(),doc.pages) if key in ('delete','rotate','pdf_images','watermark','numbers') else None
            if key=='delete':operation=lambda cb:[extra.delete_pages(doc,pages,output,name,cb)]
            elif key=='rotate':
                angle=int(data['angle'].get());operation=lambda cb:[extra.rotate_pages(doc,pages,angle,output,name,cb)]
            elif key=='text':operation=lambda cb:[extra.extract_text(doc,output,name,cb)]
            elif key=='encrypt':
                password=data['password'].get()
                if password!=data['confirm'].get():raise SplitError('两次输入的密码不一致。')
                if not password.strip():raise SplitError('请输入非空的新密码。')
                operation=lambda cb:[extra.encrypt_document(doc,password,output,name,cb)]
            elif key=='decrypt':operation=lambda cb:[extra.decrypt_document(doc,output,name,cb)]
            elif key=='images_pdf':
                paths=list(self.image_paths);dpi=int(data['dpi'].get())
                operation=lambda cb:[extra.images_to_pdf(paths,output,name,cb,dpi=dpi)]
            elif key=='pdf_images':
                dpi=int(data['dpi'].get());fmt=data['format'].get()
                operation=lambda cb:more.render_document(doc,output,pages=pages,image_format=fmt,dpi=dpi,progress=cb)
            elif key=='compress':
                def operation(cb):
                    path=more.compress_document(doc,output,name,cb)
                    self.messages.put(('job_note',f'原始大小：{len(doc.data):,} 字节\n输出大小：{path.stat().st_size:,} 字节\n流压缩不保证变小；请检查输出。'))
                    return [path]
            elif key=='watermark':
                text=data['text'].get();operation=lambda cb:[more.watermark_document(doc,output,text,name,pages=pages,progress=cb)]
            elif key=='numbers':
                start=int(data['start'].get());operation=lambda cb:[more.number_pages(doc,output,name,pages=pages,start_number=start,progress=cb)]
        except ValueError as exc:
            messagebox.showerror('检查输入',str(exc) if isinstance(exc,SplitError) else '请输入有效整数。');return
        self.start_job(operation,data['title'])

    def show_page(self,mode):
        if self.busy:return
        self.mode=mode; self.pages[mode].tkraise()
        for key,button in self.nav.items():button.configure(bg='#e7e7eb' if key==mode else SIDE, font=('Microsoft YaHei UI',10,'bold' if key==mode else 'normal'))

    def scroll(self,event): self.canvas.yview_scroll(-int(event.delta/120),'units')

    def read_pdf(self,path):
        password=None
        while True:
            try:return open_document(path,password)
            except PasswordRequired as exc:
                password=simpledialog.askstring('PDF 密码',f'{Path(path).name}\n{exc}',show='*',parent=self.root)
                if password is None:return None
            except SplitError as exc:
                messagebox.showerror('无法打开',f'{Path(path).name}\n{exc}');return None

    def choose(self):
        if self.busy:return
        path=filedialog.askopenfilename(title='选择 PDF',filetypes=[('PDF 文件','*.pdf')])
        if path:self.load(path)

    def on_drop(self,event):
        if self.busy:return
        paths=self.root.tk.splitlist(event.data)
        if self.mode=='merge':self.add_merge_paths(paths)
        elif self.mode=='images_pdf':self.add_image_paths(paths)
        elif self.mode in self.tools:
            if len(paths)!=1:messagebox.showwarning('请选择一个文件','此功能一次只处理一个 PDF。')
            else:self.load_tool(self.mode,paths[0])
        elif self.mode=='word':
            if len(paths)!=1:messagebox.showwarning('请选择一个文件','PDF 转 Word 一次只处理一个 PDF。')
            else:self.load_word(paths[0])
        elif self.mode=='reorder':
            if len(paths)!=1:messagebox.showwarning('请选择一个文件','调整顺序一次只处理一个 PDF。')
            else:self.load_reorder(paths[0])
        elif len(paths)!=1:messagebox.showwarning('请选择一个文件','分离一次处理一个 PDF；多个文件可以在“PDF 合并”中添加。')
        else:self.load(paths[0])

    def load(self,path):
        if self.busy:return
        if self.doc and not messagebox.askyesno('更换文件','更换 PDF 将重新生成页码范围，是否继续？'):return
        doc=self.read_pdf(path)
        if doc is None:return
        self.doc=doc;self.info.set(f'{doc.path.name}  ·  {doc.pages} 页')
        self.drop.configure(text='文件已就绪\n点击或拖入其他 PDF 可更换')
        self.output.set(str(doc.path.parent));self.count.set(str(min(2,doc.pages)))
        self.generate(confirm=False);self.progress['value']=0
        self.status.set('文件已加载 · 导出不保留密码保护或有效数字签名')

    def generate(self,confirm=True):
        if self.busy:return
        if not self.doc:messagebox.showinfo('先选择 PDF','请先拖入或选择一个 PDF。');return
        try:parts=even_parts(self.doc.pages,int(self.count.get()))
        except ValueError:messagebox.showerror('份数无效',f'请填写 1 到 {self.doc.pages} 之间的整数。');return
        if confirm and self.rows and not messagebox.askyesno('重新生成','这会替换当前填写的页码范围，是否继续？'):return
        for row in self.rows:row[0].destroy()
        self.rows.clear()
        for part in parts:self.add(part)
        self.status.set('范围已生成 · 你可以继续修改每份的起止页')

    def add(self,part=None):
        if self.busy:return
        if not self.doc:messagebox.showinfo('先选择 PDF','请先选择 PDF。');return
        part=part or Part(1,self.doc.pages)
        frame=ttk.Frame(self.range_frame,padding=(0,6));frame.pack(fill='x')
        label=ttk.Label(frame,width=9);label.pack(side='left')
        a,b=tk.StringVar(value=str(part.start)),tk.StringVar(value=str(part.end))
        ttk.Entry(frame,textvariable=a,width=7).pack(side='left',padx=(0,10))
        ttk.Label(frame,text='至',style='Muted.TLabel').pack(side='left')
        ttk.Entry(frame,textvariable=b,width=7).pack(side='left',padx=10)
        ttk.Label(frame,text='页',style='Muted.TLabel').pack(side='left')
        row=(frame,label,a,b)
        ttk.Button(frame,text='移除',command=lambda:self.remove(row)).pack(side='right',padx=5)
        self.rows.append(row);self.renumber()

    def remove(self,row):
        if self.busy:return
        row[0].destroy();self.rows.remove(row);self.renumber()

    def renumber(self):
        for i,row in enumerate(self.rows,1):row[1].configure(text=f'第 {i} 份')
        self.count.set(str(len(self.rows)))

    def choose_output(self):self.pick_folder(self.output)
    def choose_merge_output(self):self.pick_folder(self.merge_output)
    def pick_folder(self,var):
        if self.busy:return
        path=filedialog.askdirectory(title='选择输出位置',initialdir=var.get() or None)
        if path:var.set(path)

    def choose_merge(self):
        if self.busy:return
        paths=filedialog.askopenfilenames(title='添加 PDF 文件',filetypes=[('PDF 文件','*.pdf')])
        if paths:self.add_merge_paths(paths)

    def add_merge_paths(self,paths):
        if self.busy:return
        added=skipped=0
        for path in paths:
            if Path(path).resolve() in [doc.path for doc in self.merge_docs]:skipped+=1;continue
            doc=self.read_pdf(path)
            if doc is None:skipped+=1;continue
            self.merge_docs.append(doc);added+=1
            if not self.merge_output.get():self.merge_output.set(str(doc.path.parent))
        self.refresh_merge()
        self.status.set(f'已添加 {added} 个文件'+(f' · {skipped} 个重复、取消或无效文件未加入' if skipped else '')+' · 请检查列表顺序')

    def refresh_merge(self,selected=None):
        self.merge_tree.delete(*self.merge_tree.get_children())
        for i,doc in enumerate(self.merge_docs):self.merge_tree.insert('', 'end',iid=str(i),values=(f'{i+1:02d}',doc.path.name,doc.pages))
        self.merge_info.set(f'{len(self.merge_docs)} 个文件 · {sum(d.pages for d in self.merge_docs)} 页')
        if selected is not None and self.merge_docs:
            iid=str(min(selected,len(self.merge_docs)-1));self.merge_tree.selection_set(iid);self.merge_tree.see(iid)

    def move_merge(self,delta):
        if self.busy:return
        selected=self.merge_tree.selection()
        if not selected:return
        index=int(selected[0]);dest=index+delta
        if 0<=dest<len(self.merge_docs):
            self.merge_docs[index],self.merge_docs[dest]=self.merge_docs[dest],self.merge_docs[index];self.refresh_merge(dest)

    def remove_merge(self):
        if self.busy:return
        selected=self.merge_tree.selection()
        if selected:
            index=int(selected[0]);self.merge_docs.pop(index);self.refresh_merge(index)

    def clear_merge(self):
        if self.busy:return
        if self.merge_docs and messagebox.askyesno('清空列表','移除列表中的全部文件？不会删除原文件。'):
            self.merge_docs.clear();self.refresh_merge()

    def run(self):
        if self.busy:return
        if not self.doc:messagebox.showinfo('先选择 PDF','请先选择 PDF。');return
        try:
            parts=[Part(int(row[2].get()),int(row[3].get())) for row in self.rows]
            validate_parts(parts,self.doc.pages)
            if not self.output.get().strip() or not Path(self.output.get()).is_dir():raise SplitError('请选择存在的输出文件夹。')
        except ValueError as exc:messagebox.showerror('检查范围',str(exc) if isinstance(exc,SplitError) else '页码必须是整数。');return
        doc,output=self.doc,self.output.get()
        self.start_job(lambda cb:split_document(doc,parts,output,cb),'分离')

    def run_merge(self):
        if self.busy:return
        if len(self.merge_docs)<2:messagebox.showinfo('添加文件','请至少添加两个 PDF。');return
        docs,output,name=list(self.merge_docs),self.merge_output.get(),self.merge_name.get()
        self.start_job(lambda cb:[merge_documents(docs,output,name,cb)],'合并')

    def lock_inputs(self,locked):
        if locked:
            self.locked_inputs=[]
            def visit(widget):
                if isinstance(widget,(ttk.Entry,ttk.Spinbox,ttk.Radiobutton)) and not widget.instate(['disabled']):
                    widget.state(['disabled']);self.locked_inputs.append(widget)
                for child in widget.winfo_children():visit(child)
            for page in self.pages.values():visit(page)
        else:
            for widget in getattr(self,'locked_inputs',[]):widget.state(['!disabled'])
            self.locked_inputs=[]

    def start_job(self,operation,label):
        self.busy=True;self.job_label=label;self.job_note='';self.lock_inputs(True)
        for button in self.tool_buttons:button.state(['disabled'])
        self.run_button.state(['disabled']);self.merge_button.state(['disabled']);self.reorder_button.state(['disabled']);self.word_button.state(['disabled'])
        self.progress['value']=0;self.status.set(f'正在{label}，使用已确认的设置，请稍候…')
        def work():
            try:
                paths=operation(lambda n,total:self.messages.put(('progress',n/total*95)))
                self.messages.put(('done',paths))
            except Exception as exc:self.messages.put(('error',str(exc)))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,value=self.messages.get_nowait()
                if kind=='progress':self.progress['value']=value;continue
                if kind=='word_notice':self.word_notice.set(value);continue
                if kind=='job_note':self.job_note=value;continue
                for button in self.tool_buttons:button.state(['!disabled'])
                self.busy=False;self.lock_inputs(False);self.run_button.state(['!disabled']);self.merge_button.state(['!disabled']);self.reorder_button.state(['!disabled']);self.word_button.state(['!disabled'])
                if self.job_label=='设置密码':
                    self.tools['encrypt']['password'].set('');self.tools['encrypt']['confirm'].set('')
                if kind=='error':
                    self.status.set('未完成 · 请检查错误提示')
                    if self.job_label=='PDF 转 Word':self.word_notice.set(value)
                    messagebox.showerror('处理失败',value)
                else:
                    self.progress['value']=100
                    self.status.set(f'{self.job_label}完成 · 已保存 {len(value)} 个文件 · {value[0].parent}')
                    result_text=self.word_notice.get() if self.job_label=='PDF 转 Word' else (self.job_note or f'成功导出 {len(value)} 个文件。')
                    if messagebox.askyesno('处理完成',f'{result_text}\n\n{value[0].parent}\n\n现在打开结果文件夹吗？'):
                        if sys.platform=='win32':
                            try:os.startfile(value[0].parent)
                            except OSError as exc:messagebox.showwarning('无法打开文件夹',f'文件已导出，请手动打开结果目录。\n{exc}')
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def close(self):
        if self.busy:messagebox.showinfo('正在导出','请等待本次导出完成后再关闭。');return
        self.root.destroy()


def main():
    root=TkinterDnD.Tk();App(root);root.mainloop()

if __name__=='__main__':main()
