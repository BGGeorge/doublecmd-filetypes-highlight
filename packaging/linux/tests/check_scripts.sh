#!/usr/bin/env sh
# 静态检查仓库里的所有 Linux shell 脚本（语法 + 行尾）。
set -eu
HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH='' cd -- "$HERE/../../.." && pwd)
cd "$ROOT"

status=0
for f in \
    packaging/linux/install.sh \
    packaging/linux/install-linux.sh.in \
    packaging/linux/system/dcmd-hl \
    packaging/linux/system/dcmd-hl-gui \
    packaging/linux/system/postinstall.sh \
    packaging/linux/system/postremove.sh \
    src/dcmd_hl_cli.sh \
    src/dcmd_hl_gui.sh
do
    if [ ! -f "$f" ]; then
        echo "MISSING  $f"
        status=1
        continue
    fi
    if sh -n "$f"; then
        echo "OK       $f"
    else
        echo "FAIL     $f"
        status=1
    fi
    if grep -q "$(printf '\r')" "$f" 2>/dev/null; then
        echo "FAIL     $f 含有 CRLF 行尾（Linux 脚本必须是 LF）"
        status=1
    fi
done

exit "$status"
