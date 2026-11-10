#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linux 相关核心逻辑测试。

在 Linux 上运行全部用例；在 Windows 上运行与平台无关的用例（路径识别、
JSON/XML 合并、版本号等）。GitHub Actions 会在 Ubuntu 与 Fedora 上执行完整测试。

    python3 packaging/linux/tests/test_linux.py -v
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# 必须在 import dcmd_hl 之前隔离安装记录，避免写进仓库 src/installed.json
TEST_ROOT = Path(tempfile.mkdtemp(prefix="dcmd-hl-tests-"))
os.environ["DCMD_HL_STATE_DIR"] = str(TEST_ROOT / "state")
os.environ["HOME"] = str(TEST_ROOT / "home")
os.environ["USERPROFILE"] = str(TEST_ROOT / "home")
os.environ["XDG_CONFIG_HOME"] = str(TEST_ROOT / "home" / ".config")
os.environ["XDG_STATE_HOME"] = str(TEST_ROOT / "home" / ".local" / "state")
(TEST_ROOT / "home" / ".config").mkdir(parents=True, exist_ok=True)

import dcmd_hl  # noqa: E402

RULES = [
    {
        "name": "测试分类·甲",
        "masks": ["*.aaa", "*.aab"],
        "light": "#112233",
        "dark": "#445566",
        "enabled": True,
    },
    {
        "name": "测试分类·乙",
        "masks": ["*.bbb"],
        "light": "#778899",
        "dark": "#aabbcc",
        "enabled": True,
    },
]

USER_RULE = {
    "Name": "用户自己的规则",
    "Masks": "*.user",
    "Colors": [255, 255],
    "Attributes": "",
}

LINUX_ONLY = unittest.skipUnless(sys.platform.startswith("linux"), "仅 Linux 运行")


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(dir=TEST_ROOT))
        self.cfg = self.tmp / "doublecmd"
        self.cfg.mkdir()
        # 每个用例使用独立的安装记录，否则“上次安装记录”会把前一个用例的
        # 临时配置目录当成真实候选，干扰 detect_config_dir() 的断言。
        dcmd_hl.MANIFEST_FILE = self.tmp / "state" / "installed.json"

    def write_json(self, data) -> Path:
        path = self.cfg / "colors.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path


class VersionAndNames(TempCase):
    def test_version(self) -> None:
        text = (SRC / "dcmd_hl.py").read_text(encoding="utf-8")
        match = re.search(r'^TOOL_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "1.1.0")

    def test_cli_version(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SRC / "dcmd_hl.py"), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "DCMD_HL_STATE_DIR": str(self.tmp / "state")},
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1.1.0", proc.stdout)

    def test_exe_names(self) -> None:
        for name in (
            "doublecmd",
            "doublecmd.exe",
            "doublecmd-gtk",
            "doublecmd-gtk2",
            "doublecmd-qt",
            "doublecmd-qt5",
            "doublecmd-qt6",
            "DoubleCmd-GTK",
        ):
            self.assertTrue(dcmd_hl.is_dc_exe_name(name), name)
        for name in (
            "doublecmd.help",
            "doublecmd.desktop",
            "doublecmd.svg",
            "notepad.exe",
            "doublecmd-config",
            "readme.txt",
        ):
            self.assertFalse(dcmd_hl.is_dc_exe_name(name), name)

    def test_find_dc_exe(self) -> None:
        dc = self.tmp / "dc"
        dc.mkdir()
        (dc / "doublecmd.help").write_text("help", encoding="utf-8")
        self.assertIsNone(dcmd_hl.find_dc_exe(dc))
        exe = dc / "doublecmd-gtk"
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        self.assertEqual(dcmd_hl.find_dc_exe(dc), exe)

    def test_resolve_path_hint(self) -> None:
        dc = self.tmp / "portable"
        dc.mkdir()
        exe = dc / "doublecmd"
        exe.write_text("#!/bin/sh\n", encoding="utf-8")
        settings = dc / "settings"
        settings.mkdir()
        (settings / "doublecmd.inf").write_text("", encoding="utf-8")
        (settings / "colors.json").write_text("{}", encoding="utf-8")

        kind, path, _ = dcmd_hl.resolve_path_hint(dc)
        self.assertEqual(kind, "exe")
        self.assertEqual(path, exe)

        kind, path, _ = dcmd_hl.resolve_path_hint(settings)
        self.assertEqual(kind, "config")
        self.assertEqual(path, settings)

        kind, path, _ = dcmd_hl.resolve_path_hint(self.tmp / "nope")
        self.assertEqual(kind, "missing")


class JsonStore(TempCase):
    def test_install_update_uninstall_keeps_user_rules(self) -> None:
        store = self.write_json({"FileColors": [USER_RULE], "Other": {"keep": True}})

        summary = dcmd_hl.install(self.cfg, RULES, mode="json")
        self.assertEqual(summary["mode"], "json")
        self.assertEqual(summary["added"], 2)
        data = dcmd_hl.read_colors_json(store)
        self.assertEqual(len(data["FileColors"]), 3)
        self.assertEqual(data["Other"], {"keep": True})
        self.assertEqual(data["FileColors"][0]["Name"], USER_RULE["Name"])
        self.assertEqual(data["FileColors"][1]["Name"], RULES[0]["name"])
        self.assertEqual(data["FileColors"][1]["Masks"], "*.aaa;*.aab")
        self.assertIsNotNone(dcmd_hl.get_manifest_install(self.cfg))

        # 再装一次：不重复添加，只更新
        again = dcmd_hl.install(self.cfg, RULES, mode="json")
        self.assertEqual(again["added"], 0)
        self.assertEqual(again["updated"], 2)
        data = dcmd_hl.read_colors_json(store)
        self.assertEqual(len(data["FileColors"]), 3)

        removed = dcmd_hl.uninstall(self.cfg, RULES)
        self.assertEqual(removed["removed"], 2)
        self.assertEqual(removed["kept"], 1)
        data = dcmd_hl.read_colors_json(store)
        self.assertEqual([item["Name"] for item in data["FileColors"]], [USER_RULE["Name"]])

    def test_prepend(self) -> None:
        store = self.write_json({"FileColors": [USER_RULE]})
        dcmd_hl.install(self.cfg, RULES, mode="json", prepend=True)
        data = dcmd_hl.read_colors_json(store)
        self.assertEqual(data["FileColors"][0]["Name"], RULES[0]["name"])
        self.assertEqual(data["FileColors"][-1]["Name"], USER_RULE["Name"])

    def test_colors_are_dc_tcolor(self) -> None:
        store = self.write_json({"FileColors": []})
        dcmd_hl.install(self.cfg, RULES[:1], mode="json")
        data = dcmd_hl.read_colors_json(store)
        colors = data["FileColors"][0]["Colors"]
        self.assertEqual(len(colors), 2)
        # #112233 -> $00332211（BGR）
        self.assertEqual(colors[0], 0x00332211)
        self.assertEqual(colors[1], 0x00665544)

    def test_dry_run_writes_nothing(self) -> None:
        store = self.write_json({"FileColors": [USER_RULE]})
        before = store.read_bytes()
        summary = dcmd_hl.install(self.cfg, RULES, mode="json", dry_run=True)
        self.assertEqual(summary["added"], 2)
        self.assertEqual(store.read_bytes(), before)
        self.assertEqual([p.name for p in self.cfg.iterdir()], ["colors.json"])


class XmlStore(TempCase):
    def test_install_and_uninstall(self) -> None:
        xml = self.cfg / "doublecmd.xml"
        xml.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<DoubleCmd><Colors><FileFilters>"
            "<Filter><Name>用户自己的规则</Name><FileMasks>*.user</FileMasks>"
            "<Color>255</Color><Attributes></Attributes></Filter>"
            "</FileFilters></Colors></DoubleCmd>\n",
            encoding="utf-8",
        )

        summary = dcmd_hl.install(self.cfg, RULES, mode="xml")
        self.assertEqual(summary["mode"], "xml")
        self.assertEqual(summary["added"], 2)
        text = xml.read_text(encoding="utf-8")
        self.assertIn("测试分类·甲", text)
        self.assertIn("用户自己的规则", text)
        self.assertEqual(text.count("<Filter>"), 3)

        removed = dcmd_hl.uninstall(self.cfg, RULES)
        self.assertEqual(removed["removed"], 2)
        text = xml.read_text(encoding="utf-8")
        self.assertEqual(text.count("<Filter>"), 1)
        self.assertIn("用户自己的规则", text)


class Platform(TempCase):
    def test_platform_candidates_windows_or_linux(self) -> None:
        candidates = dcmd_hl.platform_candidates()
        paths = [path for path, _ in candidates]
        if sys.platform == "win32":
            # Windows 下至少会检查 APPDATA / LOCALAPPDATA（环境变量存在时）
            self.assertTrue(paths)
            self.assertEqual(dcmd_hl.dc_exe_display(), "doublecmd.exe")
        else:
            self.assertTrue(any(str(path).endswith("doublecmd") for path in paths))
            self.assertEqual(dcmd_hl.dc_exe_display(), "doublecmd")

    @LINUX_ONLY
    def test_common_install_executables_includes_path(self) -> None:
        import shutil
        if not any(shutil.which(name) for name in ("doublecmd", "doublecmd-gtk", "doublecmd-qt")):
            self.skipTest("当前环境没有安装 Double Commander")
        found = dcmd_hl.common_install_executables()
        self.assertTrue(any(path.name.startswith("doublecmd") for path in found), found)

    @LINUX_ONLY
    def test_linux_xdg_candidate(self) -> None:
        xdg = self.tmp / "xdg"
        (xdg / "doublecmd").mkdir(parents=True)
        (xdg / "doublecmd" / "colors.json").write_text("{}", encoding="utf-8")
        old = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = str(xdg)
        try:
            candidates = dcmd_hl.platform_candidates()
        finally:
            if old is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = old
        self.assertEqual(candidates[0][0], dcmd_hl._norm(xdg / "doublecmd"))

    @LINUX_ONLY
    def test_linux_flatpak_and_snap_candidates(self) -> None:
        home = Path(os.environ["HOME"])
        flatpak = home / ".var" / "app" / "io.github.doublecmd.Doublecmd" / "config" / "doublecmd"
        snap = home / "snap" / "doublecmd" / "current" / ".config" / "doublecmd"
        flatpak.mkdir(parents=True, exist_ok=True)
        snap.mkdir(parents=True, exist_ok=True)
        candidates = dcmd_hl.platform_candidates()
        labels = [label for _path, label in candidates]
        self.assertTrue(any("Flatpak" in label for label in labels), labels)
        self.assertTrue(any("Snap" in label for label in labels), labels)

    @LINUX_ONLY
    def test_linux_detect_home_config(self) -> None:
        home = Path(os.environ["HOME"])
        cfg = home / ".config" / "doublecmd"
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / "colors.json").write_text("{}", encoding="utf-8")
        detected, source, checked = dcmd_hl.detect_config_dir()
        self.assertIsNotNone(detected, checked)
        self.assertEqual(dcmd_hl._norm(detected), dcmd_hl._norm(cfg))
        self.assertIn("XDG", source)

    @LINUX_ONLY
    def test_linux_portable_detect(self) -> None:
        dc = self.tmp / "DC"
        dc.mkdir()
        (dc / "doublecmd").write_text("#!/bin/sh\n", encoding="utf-8")
        settings = dc / "settings"
        settings.mkdir()
        (settings / "doublecmd.inf").write_text("", encoding="utf-8")
        (settings / "colors.json").write_text("{}", encoding="utf-8")
        # detect_config_dir() 的参数是 DC 可执行文件路径（命令行 --exe 已由
        # resolve_path_hint() 归一化），因此这里传入目录中的 doublecmd。
        detected, _source, _checked = dcmd_hl.detect_config_dir(str(dc / "doublecmd"))
        self.assertEqual(dcmd_hl._norm(detected), dcmd_hl._norm(settings))

    @LINUX_ONLY
    def test_scan_skips_pseudo_filesystems(self) -> None:
        self.assertTrue(dcmd_hl._is_scan_skip_path(Path("/proc")))
        self.assertTrue(dcmd_hl._is_scan_skip_path(Path("/proc/1234")))
        self.assertTrue(dcmd_hl._is_scan_skip_path(Path("/sys/kernel")))
        self.assertFalse(dcmd_hl._is_scan_skip_path(Path("/home/user")))

    @LINUX_ONLY
    def test_system_package_state_dir_is_per_user(self) -> None:
        self.assertTrue(dcmd_hl._is_system_app_dir(Path("/usr/lib/dcmd-filetypes-highlight")))
        self.assertTrue(dcmd_hl._is_system_app_dir(Path("/opt/dcmd-filetypes-highlight")))
        self.assertFalse(dcmd_hl._is_system_app_dir(Path("/home/user/dcmd-filetypes-highlight")))
        old_script = dcmd_hl.SCRIPT_DIR
        old_override = os.environ.pop("DCMD_HL_STATE_DIR", None)
        old_xdg = os.environ.get("XDG_STATE_HOME")
        state_home = self.tmp / "state-home"
        os.environ["XDG_STATE_HOME"] = str(state_home)
        dcmd_hl.SCRIPT_DIR = Path("/usr/lib/dcmd-filetypes-highlight")
        try:
            self.assertEqual(
                dcmd_hl._default_state_dir(),
                state_home / "dcmd-filetypes-highlight",
            )
        finally:
            dcmd_hl.SCRIPT_DIR = old_script
            if old_override is not None:
                os.environ["DCMD_HL_STATE_DIR"] = old_override
            if old_xdg is None:
                os.environ.pop("XDG_STATE_HOME", None)
            else:
                os.environ["XDG_STATE_HOME"] = old_xdg

    @LINUX_ONLY
    def test_permissions_preserved(self) -> None:
        store = self.write_json({"FileColors": []})
        os.chmod(store, 0o600)
        dcmd_hl.install(self.cfg, RULES[:1], mode="json")
        self.assertEqual(store.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main(verbosity=2)
