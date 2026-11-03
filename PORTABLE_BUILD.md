# 单文件便携版：维护者构建与验证

用户只需下载已验证的 `PDFWorkspace.exe`。无需安装 Python、Conda、pip，也不用 BAT。
关闭程序后可将这个单文件移到桌面、其他普通本地目录再运行；不会依赖原源码目录。
**这不是现有 onedir EXE：旧版单独复制 EXE 仍然不能运行。**

## 当前状态

2026-10-31 的 [Windows CI 构建与验证](https://github.com/ZhuWeiwen315/pdf-workspace/actions/runs/41185582673) 已通过：Windows Server 2022 x64 / CPython 3.12.10，147 项回归、单文件 EXE 构建、两个搬移路径上的实际 EXE 自检全部成功。
已验证 EXE 来自源码提交 `0296905f8c9e9c83505a448d14842dfa99e85f91`，SHA256：`8536ef3d54113bce54bb7b88100e8538f6212c446b68df4086f1c758dfa781c4`。
双自检涵盖完整 UI 初始化、TkDnD 2.9.4 加载、14 项 PDF 功能、原件字节不变及内嵌许可证导出。
**未签名；真实鼠标拖放手势、高 DPI、所有用户系统和从未安装 Python 的干净虚拟机未全面验证。** CI 移除了子进程 PATH 中的 Python 和 Python/Conda/Tcl 环境变量，但主机本身安装了 Python。

普通用户可[直接下载 EXE](https://github.com/ZhuWeiwen315/pdf-workspace/raw/refs/heads/exe/PDFWorkspace.exe)，或查看 [exe 分支说明与校验值](https://github.com/ZhuWeiwen315/pdf-workspace/tree/exe)。该分支下载不受 Actions artifact 保留期限影响。构建清单、报告和日志仍可从上述 Actions artifact 获取，保留至 2026-11-30；未创建永久 Release。后续 main 中的说明或 CI 更新不改变上述已验证二进制及其源码归属。

## 可复核构建流程

- `.github/workflows/windows-portable.yml` 使用 GitHub-hosted `windows-2022`、官方 setup-python 提供的 CPython 3.12.10 x64；不是用户的 Conda。
- 官方 Actions 固定提交 SHA；全部运行/打包依赖在 `requirements-windows-build.lock` 固定版本及 Windows wheel SHA256。
- 用 `--only-binary=:all: --require-hashes` 安装，随后 `pip check` 和完整回归。
- `build_portable.py` 明确拒绝非 Windows x64/指定 Python/Conda。构建 `--onefile --windowed --noupx`。
- 保留标准 Tkinter hook，显式收集 TkDnD、PDFium及其原生库、DOCX模板和 ReportLab。
- 先收集第三方许可与 Python/Tcl/Tk notice，再嵌入单EXE。GUI“关于→导出第三方许可证”可以随时查看；也可运行 `PDFWorkspace.exe --export-licenses NEW_DIRECTORY`。不能覆盖已有目录。
- 构建输出含 `environment.txt`（实际安装依赖）、构建日志，以及 `build-manifest.json`：记录 Python/平台、`commit`、EXE 的 `sha256`、锁文件的 `lock_sha256` 和 `code_signed: false`。**输出不复制锁文件本身**；应从对应源码提交获取 `requirements-windows-build.lock` 并核对哈希。
- `commit` 直接读取环境变量 `GITHUB_SHA`。GitHub Actions 中它是该次构建的提交；本地未设置时写入 `local`，脚本不会自动运行 `git rev-parse`，也不检查工作区是否有未提交修改。本地构建需另行保存准确的源码版本和修改记录；不要把 `local` 当作可追溯的 commit。
- 固定输入有助重复构建/审计，但 runner 镜像更新、打包时间信息意味着**不承诺位级完全一致的 EXE**。

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

## 自动回归、手动构建与发布

- `.github/workflows/regression.yml`（`Regression tests`）在推送 `main`、提交/更新面向 `main` 的 PR 或手动触发时运行。使用 Windows Server 2022 / CPython 3.12.10 x64，安装同一份带哈希的锁定依赖，执行 `pip check` 和完整回归；同一分支/PR 的新提交取消尚未结束的旧测试。**不执行 PyInstaller、不生成或上传二进制、不修改任何分支**。
- `.github/workflows/windows-portable.yml`（`Windows portable EXE`）仅保留 `workflow_dispatch`。维护者在 Actions 中选择该工作流和要验证的分支后手动运行；普通 push/PR 不会触发耗时的完整打包，也不再依赖旧的 `portable-exe` 分支。
- 两个工作流都只有 `contents: read`，checkout 不持久保存凭据，不需要用户创建 PAT、提供密码或新增长期密钥。仓库须启用 Actions，提交工作流或手动触发需相应的仓库权限。
- 手动构建的成功产物是 Actions artifact，保留 30 天；失败诊断保留 7 天。它不会自动创建 Release、更新 `exe`/`main` 分支或发布签名文件。
- 更新 `exe` 下载或创建 Release 是单独的维护者发布步骤，应先确认实际 EXE 的验证结果和 SHA256。

## 边界与安全

- 每次启动会把内嵌运行库解压到系统临时目录，退出通常清理；不是反复下载/安装依赖。
- 需要正常可写/可执行的 TEMP 和磁盘空间；崩溃可能遗留临时目录。网络盘、极长路径、企业阻止临时执行等不保证。
- 不需要管理员权限，不建议管理员运行 onefile。
- 未购买/配置代码签名证书，所以 Windows SmartScreen 或安全软件可能提示未知发布者；不能保证无误报，也不要关闭杀毒软件或下载第三方 DLL。
- 移动 EXE 不移动用户的 PDF/DOCX 输出。移动后旧桌面快捷方式可能失效，需要重新创建。
- 本方案无安装器、注册表安装项或自动更新。若以后提供安装版，安装目录不能任意搬动后还保证快捷方式/卸载正常。
- 支持目标为 Windows x64；不承诺 Windows 7、32位或所有 ARM系统。
