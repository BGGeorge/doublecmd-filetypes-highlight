# 更新日志

## v1.1.0 (2026-11-09)

**Linux 全平台支持 + 全新一键安装体验**

* **新增 Linux 支持**（Ubuntu / Debian / Linux Mint / Fedora / RHEL / Rocky / AlmaLinux / openSUSE / Arch / Manjaro 等）：
  * 通用 `tar.gz` + `install.sh`：安装到用户目录，**无需 root**；自动创建 `dcmd-hl` / `dcmd-hl-gui` 命令和桌面菜单入口
  * `.deb` / `.rpm` 系统包：走发行版包管理器，只安装程序；用户从菜单打开 GUI 点安装，或执行 `dcmd-hl install`
  * 在线安装器 `install-linux.sh`：下载安装包 + SHA256 校验，一条 `curl ... | bash` 完成
  * 自动识别 Linux 配置目录：`~/.config/doublecmd`、`XDG_CONFIG_HOME`、便携版 `settings`、Flatpak、Snap
  * 识别 `doublecmd` / `doublecmd-gtk` / `doublecmd-qt` / `doublecmd-qt6` 等可执行文件名
  * GUI 适配 Linux 字体回退、`clam` 主题与 `xdg-open`；写入配置保留原文件权限
  * `scan` 自动跳过 `/proc`、`/sys`、`/dev`、`/run` 等伪文件系统
  * 新增 Ubuntu + Fedora CI：自动构建、校验包内容、实际安装/卸载测试
* **Windows 发行包更新到 1.1.0**（win64 / win32），与 Linux 版本号保持一致；功能与安全逻辑同步
* **兼容 Double Commander 1.2.x**（继续使用 `colors.json` 的 `FileColors`）
* 文档：新增 [Linux 安装教程](docs/Linux安装教程.md)；README 与技术文档补充 Linux 下载、配置路径、FAQ 和构建说明

## v1.0.1 (2026-10-19)

**便携版安装失败修复 + 32/64 位分发包**

* **修复便携版定位**（用户反馈：便携版装不上、安装版正常）：
  * 新增“解压目录附近”探测：自动在工具所在目录 / 当前目录及其父目录、`*doublecmd*` 子目录中寻找 DC，解压到 DC 文件夹里或旁边即可直接识别
  * `install.cmd` 交互升级：先显示探测结果 → 回车确认；可把 DC **程序文件夹 / `settings` / `doublecmd.exe` 直接拖进窗口**；探测不到时弹出**文件夹选择器**（`pick-folder.ps1`）
  * `install` / `detect` / `status` / `uninstall` / `backups` 新增**位置参数**：程序目录、配置目录、`doublecmd.exe` 路径均自动识别（`-c` / `--exe` 传入目录/文件也会自动纠正）
  * 便携版**从未启动过 DC 也能安装**（`doublecmd.inf` 即被判为有效配置目录）
* **32 位支持**：发布 `win64` 与 `win32` 两个包；`install.cmd` 内置位数检查（32 位系统装 win64 包会明确提示换包）
* 修复包内 `install.cmd` 的 Python 回退路径（现在正确指向 `python-src\dcmd_hl.py`）
* GUI：可填 DC 程序目录 / `doublecmd.exe`，自动定位到真正的配置目录；提示文案更新
* 文档：下载指引（如何选 win64/win32）、便携版安装指引、FAQ 更新

## v1.0.0 (2026-10-18)

首个正式版：

* 14 个分类 / 2688 条掩码的「文件类型颜色」规则包（浅色 + 深色双主题）
* 免 Python 一键安装包（Windows 7 SP1 / 8 / 8.1 / 10 / 11，64 位）：
  `install.cmd` + `dcmd_hl_cli.exe` + `dcmd_hl_gui.exe`（内置 Python 3.8 运行时）
* 兼容 Double Commander 1.1.x（`colors.json`）与 1.0.x（`doublecmd.xml`）
* 图形界面：分类启停、优先级排序、颜色编辑、实时预览、一键安装/卸载
* 命令行：`detect / install / uninstall / status / backups / restore / preview / export / menu / scan`
* 扩展名扫描（`scan`）：自动归类磁盘上真实出现的扩展名，查漏补缺
* 安全网：DC 运行时拒绝写入、写入前自动备份、原子替换、一键还原
