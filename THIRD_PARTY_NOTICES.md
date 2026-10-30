# Third-party dependencies

本仓库发布本项目的源码及测试，不打包第三方库、Python 运行时或测试 PDF。依赖由 `requirements.txt` 在本机安装。项目的 MIT 许可证不替代第三方组件自己的许可证。

| 组件 | 用途 | 许可提示 |
| --- | --- | --- |
| pypdf 6.10.0 | PDF 读取与页面导出 | BSD-3-Clause |
| tkinterdnd2 0.4.3 | Tk 桌面拖放适配 | Python 包使用 MIT；附带 TkDnD 及其相关组件有各自的许可声明，应一并保留 |
| cryptography（由 pypdf[crypto] 引入） | 加密 PDF 支持 | Apache-2.0 或 BSD-3-Clause，具体以安装版本的许可文件为准 |
| Python / Tcl / Tk | 运行时与界面 | 各自的许可证，以所安装发行包中的许可文件为准 |
| PyInstaller（仅构建时安装） | Windows 打包 | 其自身许可证及分发例外适用；不是本项目的 MIT 许可证 |

构建或再分发 EXE 时，请保留所打包依赖与运行时中的版权及许可证文件，并核对其实际版本和附带声明。上表是组件提示，不是完整的二进制分发许可清单。依赖可能还包括传递依赖，不能把所有内容统一标成 MIT。
