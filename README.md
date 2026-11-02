# PDF 工作台 1.4 · Windows 单文件便携版

本分支给普通用户下载使用；完整开发源码在 [main 分支](https://github.com/ZhuWeiwen315/pdf-workspace/tree/main)。

## 下载与启动
1. [直接下载 PDFWorkspace.exe](https://github.com/ZhuWeiwen315/pdf-workspace/raw/refs/heads/exe/PDFWorkspace.exe)。
   也可点击仓库中的 PDFWorkspace.exe，再点击 Download raw file；不要把网页另存为 EXE。
2. 下载完成后双击运行，不需要安装 Python、Conda、pip，也不需要 BAT。
3. 关闭程序后可将这一个 EXE 移到桌面或其他普通本地目录；不依赖原源码目录。
4. 左侧选择功能，拖入 PDF 或点击选择文件，检查参数后导出；输出另存，注意保留原件。

文件大小：44,859,673 字节（约 42.8 MiB）。
SHA256：`8536ef3d54113bce54bb7b88100e8538f6212c446b68df4086f1c758dfa781c4`

PowerShell 可核对：
```powershell
Get-FileHash .\PDFWorkspace.exe -Algorithm SHA256
```

## 功能
分离、合并、调整页序、删除页、旋转页、PDF 转 Word、提取文字、PDF 转图片、图片转 PDF、设置密码、移除已知密码、内容流压缩、文字水印、页码。详细规则见 [源码使用说明](https://github.com/ZhuWeiwen315/pdf-workspace/blob/main/README.txt)。

## 验证与限制
本文件来自源码提交 `0296905f8c9e9c83505a448d14842dfa99e85f91`：
[Windows CI 验证记录](https://github.com/ZhuWeiwen315/pdf-workspace/actions/runs/41185582673)。
Windows Server 2022 x64 / CPython 3.12.10：147 项回归通过，实际 EXE 仅复制到含空格及中文路径，清除 Python/Conda/Tcl 环境变量后，两次自检通过完整界面初始化、TkDnD 加载、14 项功能、原件不变和许可证导出。
真实鼠标拖放手势、高 DPI、所有用户系统和从未安装 Python 的干净机器未全面测试。

- 目标是 Windows x64，不保证 Windows 7、32 位或全部 ARM 系统。
- **未做代码签名**，SmartScreen/安全软件可能提示未知发布者；不要关闭安全软件，不要下载随机 DLL，不要以管理员身份运行。
- 每次启动将内嵌运行库解压到系统临时目录；不是重新联网下载或安装依赖。需要可写、可执行的 TEMP 和足够磁盘空间。
- PDF 转 Word 是基础内容重建，不是精确排版还原；不含 OCR。重要文件请抽查结果。
- 水印和删页不是安全涂黑；修改文件会影响数字签名。压缩不保证变小。
- 移动 EXE 不会移动已导出的文档，旧快捷方式可能需要重建。

## 许可证
项目源码采用 [MIT License](https://github.com/ZhuWeiwen315/pdf-workspace/blob/main/LICENSE)，第三方组件遵循各自许可证，不能一概视为 MIT。
EXE 已内嵌项目、Python/Tcl/Tk、TkDnD、PDFium 及其他已收集的第三方许可。
打开程序的 **关于 → 导出第三方许可证** 可查看；也可执行：
```powershell
.\PDFWorkspace.exe --export-licenses .\PDFWorkspace_Licenses
```
目标必须为不存在的新目录，程序不会覆盖已有目录。分发时保留内嵌许可，不要移除相关声明。
