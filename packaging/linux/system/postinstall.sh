#!/bin/sh
# Post-install script for the system-wide .deb / .rpm package.
# It only refreshes desktop caches. It never touches a user's DC configuration,
# because package scripts run as root and each user has their own ~/.config/doublecmd.
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

cat <<'EOF'

Double Commander 文件类型高亮已安装。

下一步（每个桌面用户各执行一次）：
  1. 完全退出 Double Commander；
  2. 打开应用菜单，搜索“Double Commander 文件类型高亮”，
     在图形界面里点击“安装 / 更新到 Double Commander”；
     或者在终端执行：dcmd-hl install

提示：系统包不会自动修改 ~/.config/doublecmd，因为软件包以 root 身份安装，
      而 DC 配置属于每个桌面用户。
EOF

exit 0
