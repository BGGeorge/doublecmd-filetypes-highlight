# 更新日志

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
