# pdf-workspace

A local desktop PDF toolkit for splitting, merging, and reordering pages.

**PDF 工作台 1.2**：左侧选择功能，右侧操作文件。日常 PDF 处理仅在本机进行，不上传文件，导出时不覆盖原文件。

## 功能

- **PDF 分离**：自定义份数及每份的起止页码，也可先均分再修改。
- **PDF 合并**：拖入或选择多个文件，上移/下移调整合并顺序。
- **调整顺序**：移动单页或连续的 m–n 页到原始第 t 页之前/之后，预览页序后确认导出。

所有页码均从 1 开始，指 PDF 的物理页面顺序。调整顺序时，t 不能位于 m–n 内；m=n 表示单页。原顺序 `1,2,3,4,5,6`，将 `2–3` 插入原第 `5` 页之后，结果是 `1,4,5,2,3,6`。

## Windows 启动

1. 安装 Python 3.10 或更新版本（带 Tcl/Tk），保留 Python Launcher 或将 Python 加入 PATH。
2. 下载或克隆本仓库，完整解压到普通文件夹。
3. 双击 `start.bat`。首次会建立本目录下的 `.venv` 并从 PyPI 下载依赖；后续依赖正常时直接启动。
4. 不要以管理员身份启动，避免 Windows 权限隔离阻止拖放。

日常启动请用 `start.bat`，不是 `build_exe.bat`。从旧版本升级时，关闭程序、备份旧代码，再更新源码与脚本，保留已有 `.venv` 可避免重复安装相同依赖。

## 构建 EXE

在 Windows 上双击 `build_exe.bat`。构建成功后运行 `dist\PDFWorkspace\PDFWorkspace.exe`，分发时保留整个 `dist\PDFWorkspace` 文件夹。

**目前提供源码，不提供已经验证的 Windows EXE。Windows 实机启动、Windows 原生拖放与 EXE 打包尚未验证。** 不要为了运行未签名程序关闭系统安全功能。

## 测试

在已安装依赖的环境中运行：

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py core.py
```

v1.2 在 Linux 上通过 54 项自动化测试，并完成实际桌面拖放、分离、合并和页序调整验证。详细记录及未验证项目见 [TEST_REPORT.txt](TEST_REPORT.txt)。Linux 测试不等于 Windows 实机验证。

## 使用限制

- 加密 PDF 需输入已知密码；输出不保留密码保护。
- 拆分、合并或重排后，原数字签名不会保持有效，请保留原件。
- 书签不复制；复杂表单脚本、XFA、附件、跨页链接和 PDF/A 合规不保证。
- 合并时普通表单字段名加前缀以避免冲突，依赖字段名称的脚本可能需要调整。
- 输入以载入时的文件快照为准，主要保存在内存，不适合超大 PDF。

完整操作规则、升级说明及故障排查见 [README.txt](README.txt)。

## 许可

本项目源码以 [MIT License](LICENSE) 发布。第三方依赖不因此变为 MIT；参见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
