#!/bin/sh
# Post-remove script for the system-wide .deb / .rpm package.
# Refreshes desktop caches; user DC configuration is intentionally left untouched.
set -e

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

exit 0
