# 单文件便携版：维护者构建与验证

用户只需下载已验证的 `PDFWorkspace.exe`。无需安装 Python、Conda、pip，也不用 BAT。
关闭程序后可将这个单文件移到桌面、其他普通本地目录再运行；不会依赖原源码目录。
**这不是现有 onedir EXE：旧版单独复制 EXE 仍然不能运行。**

## 当前状态

此副本是新打包方案，Windows CI 尚未运行，不是已经验证的 Windows 成品。
Linux 回归和脚本审查不等于 Windows DLL/GUI 验证。需要下列 CI 全部通过后才能交付 EXE。

## 可复核构建流程

- `.github/workflows/windows-portable.yml` 使用 GitHub-hosted `windows-2022`、官方 setup-python 提供的 CPython 3.12.10 x64；不是用户的 Conda。
- 官方 Actions 固定提交 SHA；全部运行/打包依赖在 `requirements-windows-build.lock` 固定版本及 Windows wheel SHA256。
- 用 `--only-binary=:all: --require-hashes` 安装，随后 `pip check` 和完整回归。
- `build_portable.py` 明确拒绝非 Windows x64/指定 Python/Conda。构建 `--onefile --windowed --noupx`。
- 保留标准 Tkinter hook，显式收集 TkDnD、PDFium及其原生库、DOCX模板和 ReportLab。
- 先收集第三方许可与 Python/Tcl/Tk notice，再嵌入单EXE。GUI“关于→导出第三方许可证”可以随时查看；也可运行 `PDFWorkspace.exe --export-licenses NEW_DIRECTORY`。不能覆盖已有目录。
- 构建输出含源码 commit、依赖清单、锁文件和EXE SHA256。固定输入有助重复构建/审计，但 runner 镜像更新、打包时间信息意味着**不承诺位级完全一致的 EXE**。

开发者可在相同 Windows CPython 环境执行：

```powershell
python -m pip install --only-binary=:all: --require-hashes -r requirements-windows-build.lock
python -m pip check
python -m unittest discover -s tests -v
python build_portable.py --output portable-dist
python verify_portable.py portable-dist/PDFWorkspace.exe portable-dist/reports
```

`--output` 必须是新目录，防止覆盖已有文件。普通用户不用执行这些命令。

## 必须通过的冻结程序测试

`verify_portable.py` **仅复制 EXE** 到“Desktop Copy”和“中文路径 与空格”两个新目录，
从无关工作目录启动；子进程 PATH 仅留 Windows/System32，移除 Python/Conda/Tcl环境变量。
每次运行真正的 `PDFWorkspace.exe --self-test REPORT_JSON`，超时/非零/报告失败均阻止成功制品上传。
自检包含完整界面初始化、TkDnD 原生包加载、PDFium真正渲染、DOCX可编辑文字、AES密码、
全部14种PDF功能的合成文件操作和原件字节不变，以及内嵌许可证导出。
**TkDnD 加载不代表真实鼠标拖放手势已经测试；Windows人工拖放和用户系统验收仍须单独进行。**
CI 主机有Python，但测试EXE的路径被清理；这不是物理“从未安装Python”的干净虚拟机。

## GitHub 权限与发布

仅需要现有仓库的 workflow 写入/触发权限和启用 Actions；工作流本身只有 `contents: read`，
不需要用户创建 PAT、提供密码或新增长期密钥。先在 `portable-exe` 分支审查，推送才会触发。
成功产物是 Actions artifact，不自动创建 Release、不改主分支、不自动发布签名文件。
后续公开 Release 应由维护者确认验证结果后发布；artifact 有保留期限。

## 边界与安全

- 每次启动会把内嵌运行库解压到系统临时目录，退出通常清理；不是反复下载/安装依赖。
- 需要正常可写/可执行的 TEMP 和磁盘空间；崩溃可能遗留临时目录。网络盘、极长路径、企业阻止临时执行等不保证。
- 不需要管理员权限，不建议管理员运行 onefile。
- 未购买/配置代码签名证书，所以 Windows SmartScreen 或安全软件可能提示未知发布者；不能保证无误报，也不要关闭杀毒软件或下载第三方 DLL。
- 移动 EXE 不移动用户的 PDF/DOCX 输出。移动后旧桌面快捷方式可能失效，需要重新创建。
- 本方案无安装器、注册表安装项或自动更新。若以后提供安装版，安装目录不能任意搬动后还保证快捷方式/卸载正常。
- 支持目标为 Windows x64；不承诺 Windows 7、32位或所有 ARM系统。
