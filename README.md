# PDFWorkspace 1.4：单文件便携版

新版交付目标是 `PDFWorkspace.exe` 单文件，内置运行库，用户不需要 Python/Conda/BAT。
将已验证的新 EXE 关闭后移动到桌面或其他普通目录即可运行，不依赖原源码路径。
旧版 onedir 中的 EXE 不能单独移动；不要把新旧打包方式混用。

2026-10-31 的 [Windows CI 构建与验证](https://github.com/ZhuWeiwen315/pdf-workspace/actions/runs/41185582673) 已通过：Windows Server 2022 x64 / CPython 3.12.10，147 项回归、单文件 EXE 构建、两个搬移路径上的实际 EXE 自检全部成功。
已验证 EXE 来自源码提交 `0296905f8c9e9c83505a448d14842dfa99e85f91`，SHA256：`8536ef3d54113bce54bb7b88100e8538f6212c446b68df4086f1c758dfa781c4`。
双自检涵盖完整 UI 初始化、TkDnD 2.9.4 加载、14 项 PDF 功能、原件字节不变及内嵌许可证导出。
**未签名；真实鼠标拖放手势、高 DPI、所有用户系统和从未安装 Python 的干净虚拟机未全面验证。** CI 移除了子进程 PATH 中的 Python 和 Python/Conda/Tcl 环境变量，但主机本身安装了 Python。
完整构建、自检、许可及安全边界见 [PORTABLE_BUILD.md](PORTABLE_BUILD.md)。
原有14项PDF功能不变，详细使用说明见 README.txt。

---

# PDF 工作台 · PDF Workspace

一个基于 Python / Tkinter 的本地 PDF 工具箱。左侧分组选择功能，右侧操作，文件不上传，输出另存到新文件夹。

## 功能

- **文档整理**：PDF 分离、合并、页序调整、删除页面、旋转页面。
- **格式转换**：PDF 转 Word、提取文字、PDF 转 PNG/JPEG、图片转 PDF。
- **保护与修饰**：AES-256 打开密码、用已知密码移除保护、内容流压缩、文字水印、页码。

## 快速开始：普通用户

1. 打开[已验证构建](https://github.com/ZhuWeiwen315/pdf-workspace/actions/runs/41185582673)，在 **Artifacts** 下载 **PDFWorkspace-Windows-x64-portable**（下载可能需要登录 GitHub）。
2. 解压 ZIP，双击 `PDFWorkspace.exe`；无需安装 Python、Conda 或运行 BAT。只移动这个 EXE 即可，先关闭程序再移动。
3. 从左侧选择功能，拖入文件或点击选择，检查参数再导出。

此 Actions 下载有保留期限，目前到 **2026-11-30**；不是永久 Release。ZIP 内附构建清单、自检报告和日志，程序运行只需 EXE。未签名可能触发未知发布者提示，不要关闭安全软件。

## 源码运行：开发者

面向 Windows x64，建议 Python 3.12 或 3.13（最低 3.10），安装时保留 Tcl/Tk。

1. 下载并完整解压源码。
2. 双击 `start.bat`。启动器先检查 Python 3.10+ x64 / Tcl-Tk，再安装依赖；首次需要联网，依赖齐全后不再安装。旧的不兼容 `.venv` 保留不动。
3. 从左侧选择功能，拖入文件或点击选择，检查参数再导出。

**GitHub 的 Code → Download ZIP 是源码，不是上方 Actions 的预制 EXE 下载。** `build_exe.bat` 用于在 Windows 构建便携目录，不是日常启动入口。分发时保留整个 `dist/PDFWorkspace` 和其中的第三方许可证目录。

升级时可将新源码覆盖到旧程序目录，保留 `.venv`。v1.3 增加 Word、图像和水印依赖，首次升级会补装这些组件。

## Python 3.9 启动失败修复

如果日志包含 `cp39-cp39-win_amd64`，当前使用的是 Python 3.9。`pdfplumber 0.11.9` 固定依赖的 `pdfminer.six 20251230` 要求 **Python >=3.10**，仅升级旧 pip 无法解决。

1. 安装官方 **Python 3.13 或 3.12 Windows 64-bit**，保留 Tcl/Tk 与 Python Launcher。
2. 将本版全部文件更新到程序目录（包括新增 `bootstrap.py`），无需删除 `.venv` 或卸载 3.9。
3. 双击 `start.bat`。它自动发现解释器，优先 3.13/3.12；兼容环境复用，否则安全另建 `.venv-py313` 等目录。

找不到兼容 Python 时会停止，不会反复下载失败。`diagnose.bat` 可生成只读环境诊断；不安装任何内容。启动器只在需要时更新所选环境的旧 pip，不修改系统默认 Python 或镜像。构建脚本也使用同一版本检查，并使用独立 `.build-env-py...`。

## 页序调整规则

`m–n` 是原始 PDF 中要移动的连续范围（含两端）；`m=n` 表示单页。`t` 始终是原始页码，不是移除后重新编号的页码。可选插到 `t` 之前或之后，默认之前，且 `t` 不得位于 `[m,n]` 内。

原序列 `1,2,3,4,5`，输入 `m=2,n=3,t=5`：

- 之前：`1,4,2,3,5`
- 之后：`1,4,5,2,3`

界面显示新页序，并在导出前要求确认。

## 重要限制

- **PDF 转 Word 是基础内容重建，不是精确版式还原**。文字/规则表格可编辑，图片仍为图片；双栏、公式、复杂表格可能需要整理。
- **没有 OCR**。全扫描文档会拒绝生成伪“可编辑文字”；混合文档的无字页保留为图片并提示。未重建的矢量图/表格内图片会附原页参考图。
- 流压缩不降低图片分辨率，也不保证文件变小。
- 水印、删页不是安全涂黑。输出改写会影响数字签名；除设置密码外，输出不保留原 PDF 的密码保护。
- 大文件会消耗内存与磁盘，重要文档请对照原件抽查。

完整步骤与参数见 [使用说明](README.txt)，验证范围见 [测试记录](TEST_REPORT.txt)。

## 开发与测试

```sh
python -m pip install -r requirements.txt
python app.py
python -m unittest discover -s tests -v
```

v1.4：147 项自动化测试在 Linux 和 Windows CI 均通过；Windows 冻结 EXE 的双路径搬移自检通过。原功能此前在 Linux 桌面完成真实拖放及部分导出检查。Windows CI 自检不等同于人工鼠标拖放、高 DPI 或所有 Windows 用户设备的全面验收。

## 依赖许可

源码不捆绑第三方库。PDF 转 Word 使用 pdfplumber / python-docx / PDFium，不使用 PyMuPDF。第三方组件保留各自许可证，尤其 PDFium 的原生依赖不能一概按 MIT 描述。详见 [第三方说明](THIRD_PARTY_NOTICES.txt)。构建脚本会收集当前安装版本的许可证，分发前应核查实际产物。

## 项目许可证

本项目源码使用 [MIT License](LICENSE)。第三方依赖遵循各自许可证，项目 MIT 许可不会覆盖或取代第三方声明。
