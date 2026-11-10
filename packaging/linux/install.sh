#!/usr/bin/env sh
# ============================================================================
#  Double Commander 文件类型高亮 · Linux 一键安装脚本
#
#  用法：
#    bash install.sh                  # 安装程序 + 写入 DC 配置（推荐）
#    bash install.sh --no-config      # 只安装程序，不写 DC 配置
#    bash install.sh --dry-run        # 只显示将要做的事情，不写任何文件
#    bash install.sh --uninstall      # 卸载程序（保留 DC 中已安装的颜色规则）
#    bash install.sh --uninstall --purge  # 同时移除颜色规则和状态文件
#
#  可选参数（会传给 dcmd_hl.py install）：
#    -c, --config-dir DIR   指定 DC 配置目录（默认自动探测）
#        --exe FILE         指定 DC 主程序路径（便携版）
#        --dc-path PATH     DC 程序目录 / settings / 可执行文件路径
#        --only LIST        只安装部分分类（逗号分隔）
#        --except LIST      排除部分分类
#        --mode MODE        auto / json / xml
#        --prepend          把本工具规则放到最前面
#        --force            DC 正在运行时也写入（不推荐）
#        --no-config        只安装程序，不写 DC 配置
#        --dry-run          试运行
# ============================================================================
set -eu

APP_NAME="dcmd-filetypes-highlight"
APP_TITLE="Double Commander 文件类型高亮"
HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

# 源码根目录：发行包根目录（src/ 同级），或仓库里的 packaging/linux/../../
if [ -f "$HERE/src/dcmd_hl.py" ]; then
    ROOT=$HERE
elif [ -f "$HERE/../../src/dcmd_hl.py" ]; then
    ROOT=$(CDPATH='' cd -- "$HERE/../.." && pwd)
else
    echo "错误：找不到 src/dcmd_hl.py。" >&2
    echo "      请把整个发行包解压后，在包根目录运行：bash install.sh" >&2
    exit 1
fi

VERSION="1.1.0"
if [ -f "$ROOT/VERSION" ]; then
    VERSION=$(cat "$ROOT/VERSION" 2>/dev/null || echo "$VERSION")
fi

# ---------------------------------------------------------------- 默认路径
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_HOME=${XDG_BIN_HOME:-$HOME/.local/bin}
DESKTOP_DIR=$DATA_HOME/applications
ICON_DIR=$DATA_HOME/icons/hicolor/scalable/apps
APP_DIR=$DATA_HOME/$APP_NAME
STATE_HOME=${XDG_STATE_HOME:-$HOME/.local/state}
STATE_DIR=$STATE_HOME/$APP_NAME

ACTION=install
NO_CONFIG=0
DRY_RUN=0
PURGE=0
CFG_DIR=""
EXE_PATH=""
DC_PATH=""
ONLY=""
EXCEPT=""
MODE=""
PREPEND=0
FORCE=0

usage() {
    sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --uninstall|uninstall)
            ACTION=uninstall
            shift
            ;;
        --purge)
            PURGE=1
            shift
            ;;
        --no-config)
            NO_CONFIG=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        -c|--config-dir)
            [ $# -ge 2 ] || { echo "错误：$1 需要一个目录参数" >&2; exit 2; }
            CFG_DIR=$2
            shift 2
            ;;
        --exe)
            [ $# -ge 2 ] || { echo "错误：$1 需要一个文件参数" >&2; exit 2; }
            EXE_PATH=$2
            shift 2
            ;;
        --dc-path)
            [ $# -ge 2 ] || { echo "错误：$1 需要一个路径参数" >&2; exit 2; }
            DC_PATH=$2
            shift 2
            ;;
        --only)
            [ $# -ge 2 ] || { echo "错误：$1 需要一个分类列表" >&2; exit 2; }
            ONLY=$2
            shift 2
            ;;
        --except)
            [ $# -ge 2 ] || { echo "错误：$1 需要一个分类列表" >&2; exit 2; }
            EXCEPT=$2
            shift 2
            ;;
        --mode)
            [ $# -ge 2 ] || { echo "错误：$1 需要 auto/json/xml" >&2; exit 2; }
            MODE=$2
            shift 2
            ;;
        --prepend)
            PREPEND=1
            shift
            ;;
        --force)
            FORCE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --version)
            echo "$APP_TITLE $VERSION"
            exit 0
            ;;
        -*)
            echo "错误：未知参数 $1（用 --help 查看用法）" >&2
            exit 2
            ;;
        *)
            if [ -n "$DC_PATH" ]; then
                echo "错误：只能指定一个 DC 路径（已经给出：$DC_PATH）" >&2
                exit 2
            fi
            DC_PATH=$1
            shift
            ;;
    esac
done

# ---------------------------------------------------------------- 环境检查
if [ "$(id -u)" -eq 0 ]; then
    echo "错误：请不要用 sudo / root 运行本脚本。" >&2
    echo "      DC 的配置属于当前桌面用户；用普通用户运行即可。" >&2
    echo "      如果你要系统级安装，请使用 .deb / .rpm 包。" >&2
    exit 1
fi

if [ "$(uname -s 2>/dev/null || echo unknown)" != "Linux" ]; then
    echo "错误：本脚本用于 Linux。macOS 可直接用 python3 src/dcmd_hl.py install。" >&2
    exit 1
fi

if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
    echo "错误：HOME 未设置或不是目录。" >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PY=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    PY=$(command -v python)
else
    echo "错误：未找到 Python 3。" >&2
    echo "      Ubuntu/Debian: sudo apt install python3 python3-tk" >&2
    echo "      Fedora/RHEL:   sudo dnf install python3 python3-tkinter" >&2
    echo "      Arch:          sudo pacman -S python tk" >&2
    echo "      openSUSE:      sudo zypper install python3 python3-tk" >&2
    exit 1
fi

if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
    echo "错误：需要 Python 3.8 或更高版本（当前：$("$PY" --version 2>&1)）。" >&2
    exit 1
fi

GUI_OK=1
if ! "$PY" -c 'import tkinter' >/dev/null 2>&1; then
    GUI_OK=0
    echo "提示：未安装 tkinter，命令行可以使用，但图形界面不可用。"
    echo "      Ubuntu/Debian: sudo apt install python3-tk"
    echo "      Fedora/RHEL:   sudo dnf install python3-tkinter"
    echo "      Arch:          sudo pacman -S tk"
    echo "      openSUSE:      sudo zypper install python3-tk"
    echo
fi

# ---------------------------------------------------------------- 卸载
if [ "$ACTION" = "uninstall" ]; then
    if [ "$PURGE" -eq 1 ] && [ -f "$APP_DIR/src/dcmd_hl.py" ]; then
        echo "正在从 Double Commander 配置中移除颜色规则..."
        set -- uninstall
        [ -n "$CFG_DIR" ] && set -- "$@" -c "$CFG_DIR"
        [ -n "$EXE_PATH" ] && set -- "$@" --exe "$EXE_PATH"
        [ -n "$DC_PATH" ] && set -- "$@" "$DC_PATH"
        [ "$FORCE" -eq 1 ] && set -- "$@" --force
        if ! "$PY" "$APP_DIR/src/dcmd_hl.py" "$@"; then
            echo "提示：颜色规则未移除（可能 DC 正在运行或配置目录找不到）。" >&2
            echo "      程序文件仍会继续卸载；之后可重试：dcmd-hl uninstall" >&2
        fi
    fi

    echo "正在卸载程序文件..."
    for name in dcmd-hl dcmd-hl-gui; do
        target=$BIN_HOME/$name
        if [ -L "$target" ]; then
            link=$(readlink "$target" 2>/dev/null || true)
            if [ "$link" = "$APP_DIR/$name" ]; then
                rm -f "$target"
            fi
        elif [ -f "$target" ] && grep -q 'Managed by dcmd-filetypes-highlight' "$target" 2>/dev/null; then
            rm -f "$target"
        fi
    done
    rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
    rm -f "$ICON_DIR/$APP_NAME.svg"
    rm -rf "$APP_DIR"
    if [ "$PURGE" -eq 1 ]; then
        rm -rf "$STATE_DIR"
    fi

    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true

    echo "[DONE] 已卸载 $APP_TITLE。"
    if [ "$PURGE" -eq 0 ]; then
        echo "      已安装到 DC 的颜色规则仍保留；需要移除请运行："
        echo "      dcmd-hl uninstall   （或重新运行本脚本加 --purge）"
    fi
    exit 0
fi

# ---------------------------------------------------------------- 安装
echo "============================================================"
echo "  $APP_TITLE  $VERSION"
echo "  Linux 一键安装"
echo "============================================================"
echo "  程序目录: $APP_DIR"
echo "  命令入口: $BIN_HOME/dcmd-hl  /  $BIN_HOME/dcmd-hl-gui"
echo "  菜单入口: $DESKTOP_DIR/$APP_NAME.desktop"
echo

if [ "$DRY_RUN" -eq 1 ]; then
    echo "试运行：不会复制文件，也不会写入 DC 配置。"
    set -- install --dry-run
    [ -n "$CFG_DIR" ] && set -- "$@" -c "$CFG_DIR"
    [ -n "$EXE_PATH" ] && set -- "$@" --exe "$EXE_PATH"
    [ -n "$DC_PATH" ] && set -- "$@" "$DC_PATH"
    [ -n "$ONLY" ] && set -- "$@" --only "$ONLY"
    [ -n "$EXCEPT" ] && set -- "$@" --except "$EXCEPT"
    [ -n "$MODE" ] && set -- "$@" --mode "$MODE"
    [ "$PREPEND" -eq 1 ] && set -- "$@" --prepend
    [ "$FORCE" -eq 1 ] && set -- "$@" --force
    "$PY" "$ROOT/src/dcmd_hl.py" "$@"
    exit $?
fi

echo "==> 1/3 复制程序文件"
mkdir -p "$APP_DIR" "$BIN_HOME" "$DESKTOP_DIR" "$ICON_DIR"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
cp -R "$ROOT/src" "$APP_DIR/src"
cp -R "$ROOT/rules" "$APP_DIR/rules"
if [ -d "$ROOT/docs" ]; then
    cp -R "$ROOT/docs" "$APP_DIR/docs"
fi
if [ -f "$ROOT/README.md" ]; then
    cp "$ROOT/README.md" "$APP_DIR/README.md"
fi
if [ -f "$ROOT/VERSION" ]; then
    cp "$ROOT/VERSION" "$APP_DIR/VERSION"
fi
find "$APP_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
chmod 755 "$APP_DIR/src/dcmd_hl.py" "$APP_DIR/src/dcmd_hl_gui.py" 2>/dev/null || true
[ -f "$APP_DIR/src/dcmd_hl_cli.sh" ] && chmod 755 "$APP_DIR/src/dcmd_hl_cli.sh"
[ -f "$APP_DIR/src/dcmd_hl_gui.sh" ] && chmod 755 "$APP_DIR/src/dcmd_hl_gui.sh"

# 生成入口包装器（运行时重新查找 python3，避免 Python 升级后路径失效）
write_launcher() {
    dest=$1
    target=$2
    cat > "$dest" <<EOF
#!/usr/bin/env sh
# Managed by dcmd-filetypes-highlight. Safe to delete after uninstalling.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python 3 is required. Install python3 first." >&2
    exit 1
fi
exec "\$PY" "$target" "\$@"
EOF
    chmod 755 "$dest"
}
write_launcher "$APP_DIR/dcmd-hl" "$APP_DIR/src/dcmd_hl.py"

write_gui_launcher() {
    dest=$1
    target=$2
    cat > "$dest" <<EOF
#!/usr/bin/env sh
# Managed by dcmd-filetypes-highlight. Safe to delete after uninstalling.
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "Python 3 is required. Install python3 first." >&2
    exit 1
fi
if ! "\$PY" -c 'import tkinter' >/dev/null 2>&1; then
    MSG="图形界面需要 tkinter。请安装后重试：
Ubuntu/Debian: sudo apt install python3-tk
Fedora/RHEL:   sudo dnf install python3-tkinter
Arch:          sudo pacman -S tk
openSUSE:      sudo zypper install python3-tk

也可以先用命令行：$BIN_HOME/dcmd-hl install"
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --title="Double Commander 文件类型高亮" --text="\$MSG" 2>/dev/null || true
    elif command -v kdialog >/dev/null 2>&1; then
        kdialog --error "\$MSG" 2>/dev/null || true
    else
        printf '%s\\n' "\$MSG" >&2
    fi
    exit 1
fi
exec "\$PY" "$target" "\$@"
EOF
    chmod 755 "$dest"
}
write_gui_launcher "$APP_DIR/dcmd-hl-gui" "$APP_DIR/src/dcmd_hl_gui.py"
ln -sf "$APP_DIR/dcmd-hl" "$BIN_HOME/dcmd-hl"
ln -sf "$APP_DIR/dcmd-hl-gui" "$BIN_HOME/dcmd-hl-gui"

echo "==> 2/3 创建桌面菜单入口"
if [ -f "$APP_DIR/docs/icon.svg" ]; then
    cp "$APP_DIR/docs/icon.svg" "$ICON_DIR/$APP_NAME.svg"
    ICON_VALUE=$APP_NAME
else
    ICON_VALUE=applications-system
fi
cat > "$DESKTOP_DIR/$APP_NAME.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_TITLE
Name[en]=Double Commander File Type Highlight
Comment=为 Double Commander 文件名按类型着色（写入 DC 原生「文件类型颜色」配置）
Comment[en]=Native file-type colors for Double Commander
Exec="$BIN_HOME/dcmd-hl-gui"
TryExec="$BIN_HOME/dcmd-hl-gui"
Icon=$ICON_VALUE
Terminal=false
Categories=Utility;FileManager;
StartupNotify=true
EOF
chmod 644 "$DESKTOP_DIR/$APP_NAME.desktop"

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true

echo "==> 3/3 写入 Double Commander 配置"
if [ "$NO_CONFIG" -eq 1 ]; then
    echo "已跳过（--no-config）。之后可运行：dcmd-hl install"
else
    set -- install
    [ -n "$CFG_DIR" ] && set -- "$@" -c "$CFG_DIR"
    [ -n "$EXE_PATH" ] && set -- "$@" --exe "$EXE_PATH"
    [ -n "$DC_PATH" ] && set -- "$@" "$DC_PATH"
    [ -n "$ONLY" ] && set -- "$@" --only "$ONLY"
    [ -n "$EXCEPT" ] && set -- "$@" --except "$EXCEPT"
    [ -n "$MODE" ] && set -- "$@" --mode "$MODE"
    [ "$PREPEND" -eq 1 ] && set -- "$@" --prepend
    [ "$FORCE" -eq 1 ] && set -- "$@" --force
    if "$PY" "$APP_DIR/src/dcmd_hl.py" "$@"; then
        :
    else
        rc=$?
        echo
        echo "程序文件已经安装，但写入 DC 配置失败（退出码 $rc）。" >&2
        echo "常见原因：Double Commander 仍在运行，或没有找到配置目录。" >&2
        echo "请完全退出 DC 后重试：" >&2
        echo "  $BIN_HOME/dcmd-hl install" >&2
        echo "或指定配置目录：" >&2
        echo "  $BIN_HOME/dcmd-hl install -c ~/.config/doublecmd" >&2
        exit $rc
    fi
fi

echo
echo "============================================================"
echo "  [DONE] 安装完成"
echo "============================================================"
echo "  重新启动 Double Commander 后即可看到文件名按类型着色。"
echo
echo "  图形界面: $BIN_HOME/dcmd-hl-gui"
echo "  命令行:   $BIN_HOME/dcmd-hl --help"
echo "  卸载:     $BIN_HOME/dcmd-hl uninstall"
echo "  程序卸载: bash \"$ROOT/install.sh\" --uninstall"
echo
case ":${PATH:-}:" in
    *":$BIN_HOME:"*) ;;
    *)
        echo "  提示：$BIN_HOME 不在 PATH 中。"
        echo "        可以把它加入 ~/.profile，或直接用上面的绝对路径。"
        echo
        ;;
esac
if [ "$GUI_OK" -eq 0 ]; then
    echo "  提示：tkinter 未安装，图形界面暂时不可用；按上面的命令安装后即可使用。"
    echo
fi
