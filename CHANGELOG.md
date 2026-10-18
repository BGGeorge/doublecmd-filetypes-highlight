# 更新日志

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
