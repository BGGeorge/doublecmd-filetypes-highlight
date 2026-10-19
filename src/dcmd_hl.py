#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dcmd_hl.py —— Double Commander「文件类型高亮」规则管理器

作用：
    把 rules/default_rules.json 中的“按扩展名着色”规则写入 Double Commander 的配置，
    效果等同于 DC「选项 → 颜色 → 文件类型颜色」中逐条添加的颜色规则。

原理（源码依据，doublecmd/doublecmd 主仓库）：
    * DC 面板绘制文件名时使用 TFile.TextColor（fileviews/ufileviewwithgrid.pas 等）；
    * 该颜色由全局对象 gColorExt 提供：TColorExt.GetColorBy()（src/uColorExt.pas），
      按规则列表顺序匹配“文件名掩码 + 文件属性”，第一条命中的规则生效；
    * DC 1.1.x 起规则保存在配置目录的 colors.json（键名 "FileColors"）；
      DC 1.0.x 保存在 doublecmd.xml 的 <Colors><FileFilters><Filter> 节点中。

兼容性：
    * DC 1.1.x：colors.json（浅色/深色主题颜色分别保存）
    * DC 1.0.x：doublecmd.xml（单一颜色，使用规则包中的浅色值）
    * 运行环境：Python 3.8+（仅管理工具需要，DC 本身不需要 Python）

用法示例（详见 README.md）：
    python dcmd_hl.py detect                  # 查找 DC 配置目录
    python dcmd_hl.py install                 # 安装/更新全部规则
    python dcmd_hl.py install --except images # 跳过某些分类
    python dcmd_hl.py uninstall               # 卸载本工具的规则（保留用户自建规则）
    python dcmd_hl.py status                  # 查看当前安装状态
    python dcmd_hl.py list                    # 列出规则包内容（终端着色预览）
    python dcmd_hl.py preview                 # 生成 preview.html 预览
    python dcmd_hl.py backups                 # 列出备份
    python dcmd_hl.py restore <备份文件>      # 恢复备份
    python dcmd_hl.py menu                    # 交互式中文菜单（双击 dcmd_hl_cli.cmd 同样效果）
    python dcmd_hl.py scan D:\\Media --apply --install   # 扫描目录扩展名，自动归类补全规则并安装
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

TOOL_NAME = "doublecmd-filetype-highlight"
TOOL_VERSION = "1.0.1"

def _app_dir() -> Path:
    """脚本所在目录；打包成 exe（PyInstaller 冻结）时用 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


SCRIPT_DIR = _app_dir()
DEFAULT_RULES_FILE = SCRIPT_DIR / "rules" / "default_rules.json"
# 源码位于 src/、规则包位于上一级 rules/ 时（本仓库布局），自动向上找一层
if not DEFAULT_RULES_FILE.exists():
    _alt_rules = SCRIPT_DIR.parent / "rules" / "default_rules.json"
    if _alt_rules.exists():
        DEFAULT_RULES_FILE = _alt_rules

COLORS_JSON = "colors.json"          # DC 1.1.x 颜色配置文件
MAIN_XML = "doublecmd.xml"           # DC 主配置（1.0.x 中保存文件颜色）
PORTABLE_FLAG = "doublecmd.inf"      # 便携模式标记（位于 <程序目录>\settings\）
BACKUP_MARK = ".fth-backup-"         # 备份文件名标记
TMP_SUFFIX = ".fth-tmp"


def _default_state_dir() -> Path:
    """安装记录目录：环境变量 DCMD_HL_STATE_DIR > 程序目录（可写时）> %LOCALAPPDATA%。

    程序目录只读（例如放在 Program Files）或需要独立测试记录时自动换位置。
    """
    override = os.environ.get("DCMD_HL_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    probe = SCRIPT_DIR / f".write-test{TMP_SUFFIX}"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return SCRIPT_DIR
    except OSError:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "dcmd-filetypes-highlight"
        return SCRIPT_DIR


STATE_DIR = _default_state_dir()
MANIFEST_FILE = STATE_DIR / "installed.json"

MANIFEST_VERSION = 1

# ---------------------------------------------------------------------------
# 终端辅助
# ---------------------------------------------------------------------------

_ANSI = False


def _enable_ansi() -> bool:
    """在 Windows 控制台启用 ANSI/VT 转义序列（失败则退回无色输出）。"""
    global _ANSI
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            if not kernel32.SetConsoleMode(handle, mode.value | 0x0004):
                return False
        except Exception:
            return False
    _ANSI = sys.stdout.isatty() or sys.platform == "win32"
    return _ANSI


def _init_console() -> None:
    """终端编码保护：真实控制台走系统接口（中文正常显示），重定向/管道时输出 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream.isatty():
                stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
            else:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    _enable_ansi()


def colorize(text: str, rgb_hex: str) -> str:
    if not _ANSI:
        return text
    h = rgb_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"\x1b[38;2;{r};{g};{b}m{text}\x1b[0m"


def print_ok(msg: str) -> None:
    print(colorize("[OK] ", "#1B7F1B") + msg if _ANSI else "[OK] " + msg)


def print_warn(msg: str) -> None:
    print(("[警告] " if not _ANSI else colorize("[警告] ", "#C07500")) + msg)


def print_err(msg: str) -> None:
    print(("[错误] " if not _ANSI else colorize("[错误] ", "#C62828")) + msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# 颜色转换
# ---------------------------------------------------------------------------
# DC（Delphi 兼容）的 TColor 为 32 位整数，低 24 位按 $00BBGGRR 存放（Windows COLORREF）。


def hex_to_tcolor(value: str) -> int:
    h = str(value).strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        raise ValueError(f"无效的颜色值: {value!r}（应为 #RRGGBB）")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def tcolor_to_hex(value: int) -> str:
    v = int(value) & 0xFFFFFF
    return "#%02X%02X%02X" % (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)


# ---------------------------------------------------------------------------
# 规则包读取与校验
# ---------------------------------------------------------------------------


class RuleError(Exception):
    pass


def load_rules(path: Path) -> list[dict]:
    """读取规则包 JSON，返回规范化后的规则列表。"""
    if not path.exists():
        raise RuleError(f"规则文件不存在: {path}")
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            obj = json.load(fh)
    except json.JSONDecodeError as exc:
        raise RuleError(f"规则文件不是有效的 JSON: {path}（{exc}）") from exc

    raw_rules = obj.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise RuleError(f"规则文件中没有 \"rules\" 数组: {path}")

    rules: list[dict] = []
    seen_masks: dict[str, str] = {}
    for index, raw in enumerate(raw_rules):
        if not isinstance(raw, dict):
            raise RuleError(f"第 {index + 1} 条规则不是对象")
        name = str(raw.get("name") or raw.get("id") or "").strip()
        if not name:
            raise RuleError(f"第 {index + 1} 条规则缺少 name")
        masks = raw.get("masks", [])
        if isinstance(masks, str):
            masks = [m.strip() for m in masks.split(";") if m.strip()]
        masks = [str(m).strip() for m in masks if str(m).strip()]
        if not masks:
            raise RuleError(f"规则 {name!r} 没有掩码 (masks)")
        light = str(raw.get("light", "")).strip()
        dark = str(raw.get("dark", light)).strip()
        hex_to_tcolor(light)  # 校验
        hex_to_tcolor(dark)
        for mask in masks:
            key = mask.casefold()
            if key in seen_masks and seen_masks[key] != name:
                print_warn(f"掩码 {mask!r} 同时出现在 {seen_masks[key]!r} 与 {name!r} 中（先出现的规则生效）")
            seen_masks.setdefault(key, name)
        rules.append(
            {
                "id": str(raw.get("id") or name),
                "name": name,
                "enabled": bool(raw.get("enabled", True)),
                "masks": masks,
                "light": light,
                "dark": dark,
                "examples": [str(x) for x in raw.get("examples", [])] or [masks[0].replace("*", "sample")],
                "comment": str(raw.get("comment", "")),
            }
        )
    return rules


def select_rules(rules: list[dict], only: str | None = None, except_: str | None = None) -> list[dict]:
    """按 enabled / --only / --except 过滤规则。only/except 接受 id 或名称（不区分大小写，逗号分隔）。"""

    def tokens(value: str | None) -> set[str]:
        if not value:
            return set()
        return {x.strip().casefold() for x in value.split(",") if x.strip()}

    only_set = tokens(only)
    except_set = tokens(except_)
    result = []
    for rule in rules:
        keys = {rule["id"].casefold(), rule["name"].casefold()}
        if only_set and not (keys & only_set):
            continue
        if keys & except_set:
            continue
        if not rule["enabled"] and not only_set:
            continue
        result.append(rule)
    return result


# ---------------------------------------------------------------------------
# DC 配置目录探测
# ---------------------------------------------------------------------------


def _norm(path) -> Path:
    return Path(os.path.normpath(str(path)))


def _strip_quotes(value) -> str:
    """去掉拖拽/粘贴路径时常见的两侧引号。"""
    text = str(value).strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def resolve_path_hint(raw) -> tuple[str, Path, str]:
    """
    把用户给的路径（拖拽/粘贴常见）归类：
      文件                    → 按 DC 可执行文件处理
      含 doublecmd.exe 的目录  → 按 DC 程序目录处理
      settings 目录 / 配置目录 → 按配置目录处理
    返回 (kind, path, note)；kind: "exe" / "config" / "missing"。
    """
    path = _norm(_strip_quotes(raw))
    if not path.exists():
        return "missing", path, f"路径不存在: {path}"
    if path.is_file():
        return "exe", path, f"按 DC 可执行文件处理: {path}"

    if looks_like_config_dir(path):
        return "config", path, f"按 DC 配置目录处理: {path}"

    exe = path / "doublecmd.exe"
    if exe.is_file():
        return "exe", exe, f"按 DC 程序目录处理: {path}"

    settings = path / "settings"
    if looks_like_config_dir(settings):
        return "config", settings, f"按 <程序目录>\\settings 处理: {path}"

    return "config", path, f"按配置目录处理: {path}"


def platform_candidates() -> list[tuple[Path, str]]:
    """按平台给出可能的配置目录（不检查是否存在）。"""
    result: list[tuple[Path, str]] = []

    for env_name in ("DC_CONFIG_PATH", "COMMANDER_INI_PATH"):
        value = os.environ.get(env_name)
        if value:
            result.append((_norm(value), f"环境变量 {env_name}（从 DC 内启动）"))

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            result.append((_norm(Path(appdata) / "doublecmd"), "Windows %APPDATA%\\doublecmd"))
        local = os.environ.get("LOCALAPPDATA")
        if local:
            result.append((_norm(Path(local) / "doublecmd"), "Windows %LOCALAPPDATA%\\doublecmd（一般不用）"))
    elif sys.platform == "darwin":
        result.append((_norm(Path.home() / "Library" / "Preferences" / "doublecmd"), "macOS ~/Library/Preferences/doublecmd"))
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = _norm(xdg) if xdg else Path.home() / ".config"
        result.append((_norm(base / "doublecmd"), "Linux ~/.config/doublecmd"))
    return result


def common_install_executables() -> list[Path]:
    """常见安装位置的 doublecmd.exe（Windows：每次启动时定位配置目录用）。"""
    result: list[Path] = []
    env_exe = os.environ.get("DCMD_EXE", "").strip()
    if env_exe:
        result.append(_norm(env_exe))
    if sys.platform == "win32":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(env_name)
            if base:
                result.append(_norm(Path(base) / "Double Commander" / "doublecmd.exe"))
        local = os.environ.get("LOCALAPPDATA")
        if local:
            result.append(_norm(Path(local) / "Programs" / "Double Commander" / "doublecmd.exe"))
        which = shutil.which("doublecmd")
        if which:
            result.append(_norm(which))
    return result


def nearby_candidates() -> list[tuple[Path, str]]:
    """在当前目录、本工具所在目录及其父目录附近找 Double Commander。

    便携版没有固定安装位置，但用户常把本工具解压到 DC 文件夹里或旁边；
    沿目录树向上再找一层形如 *doublecmd* 的子目录即可覆盖绝大多数情况。
    """
    result: list[tuple[Path, str]] = []

    bases: list[Path] = []
    for start in (Path.cwd(), SCRIPT_DIR):
        base = _norm(start)
        for _ in range(4):  # 自身 + 3 层父目录
            if base not in bases:
                bases.append(base)
            parent = base.parent
            if parent == base:
                break
            base = parent

    seen: set[str] = set()

    def add_dir(cfg_dir: Path, label: str) -> None:
        key = str(cfg_dir).casefold()
        if key not in seen:
            seen.add(key)
            result.append((cfg_dir, label))

    def add_exe(exe: Path) -> None:
        key = str(exe).casefold()
        if key not in seen:
            seen.add(key)
            result.extend(exe_candidates(exe, prefix="附近发现"))

    for base in bases:
        exe = base / "doublecmd.exe"
        if exe.is_file():
            add_exe(exe)
        if base.is_dir() and looks_like_config_dir(base):
            add_dir(base, f"附近发现配置目录: {base}")
        if not base.is_dir():
            continue
        count = 0
        try:
            for entry in os.scandir(base):
                count += 1
                if count > 400:
                    break
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                except OSError:
                    continue
                if not is_dir or "doublecmd" not in entry.name.casefold():
                    continue
                child = Path(entry.path)
                child_exe = child / "doublecmd.exe"
                if child_exe.is_file():
                    add_exe(child_exe)
                elif looks_like_config_dir(child):
                    add_dir(child, f"附近发现配置目录: {child}")
                else:
                    sub = child / "settings"
                    if looks_like_config_dir(sub):
                        add_dir(sub, f"附近发现便携配置目录: {sub}")
        except OSError:
            continue
    return result


def exe_candidates(exe_path, prefix: str = "") -> list[tuple[Path, str]]:
    """根据 DC 可执行文件位置给出候选配置目录（便携模式优先）。"""
    base = _norm(Path(exe_path)).parent
    label = f"{prefix}: {_norm(Path(exe_path))}" if prefix else ""
    return [
        (base / "settings", f"便携模式 <程序目录>\\settings" + (f"（{label}）" if label else "")),
        (base, "可执行文件所在目录" + (f"（{label}）" if label else "")),
    ]


def running_dc_executables() -> list[Path]:
    """查找正在运行的 Double Commander 可执行文件（用于自动定位便携版配置目录）。"""
    result: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            result.append(path)

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

            capacity = 2048
            pids: list[int] = []
            while True:
                array = (wintypes.DWORD * capacity)()
                needed = wintypes.DWORD()
                if not psapi.EnumProcesses(array, ctypes.sizeof(array), ctypes.byref(needed)):
                    break
                count = needed.value // ctypes.sizeof(wintypes.DWORD)
                if count < capacity:
                    pids = list(array[:count])
                    break
                capacity *= 2

            for pid in pids:
                if pid == 0:
                    continue
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
                if not handle:
                    continue
                try:
                    size = wintypes.DWORD(32768)
                    buffer = ctypes.create_unicode_buffer(size.value)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                        path = Path(buffer.value)
                        if path.name.casefold() == "doublecmd.exe":
                            add(path)
                finally:
                    kernel32.CloseHandle(handle)
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        proc_root = Path("/proc")
        if proc_root.is_dir():
            for entry in proc_root.iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    target = (entry / "exe").resolve(strict=True)
                except (OSError, RuntimeError):
                    continue
                if target.name.casefold().startswith("doublecmd"):
                    add(target)
    return result


def config_files_state(cfg_dir: Path) -> dict:
    return {
        "colors_json": (cfg_dir / COLORS_JSON).exists(),
        "doublecmd_xml": (cfg_dir / MAIN_XML).exists(),
        "portable_inf": (cfg_dir / PORTABLE_FLAG).exists(),
    }


def looks_like_config_dir(cfg_dir: Path) -> bool:
    state = config_files_state(cfg_dir)
    return state["colors_json"] or state["doublecmd_xml"] or state["portable_inf"]


def remembered_config_dirs() -> list[tuple[Path, str]]:
    """从安装记录里找回以前用过/装过的配置目录（便携版未运行时也能定位）。"""
    out: list[tuple[Path, str]] = []
    installs = load_manifest().get("installs", {})
    if not isinstance(installs, dict):
        return out
    entries = sorted(installs.values(), key=lambda e: str(e.get("date", "")), reverse=True)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        dir_text = str(entry.get("config_dir") or "")
        if dir_text:
            out.append((Path(dir_text), "上次安装记录"))
    return out


def detect_config_dir(exe_path=None) -> tuple[Path | None, str, list[tuple]]:
    """
    返回 (配置目录, 来源说明, 检查过的候选列表)。
    候选列表元素: (路径, 来源, 是否存在, 是否像 DC 配置目录)

    探测顺序：显式指定 → 运行中的 DC → 目录附近（便携版）→ 上次安装记录
              → 常见安装位置 → 平台默认（%APPDATA% 等）。
    """
    checked: list[tuple] = []
    candidates: list[tuple[Path, str]] = []
    if exe_path:
        candidates.extend(exe_candidates(exe_path))
    else:
        # 便携版往往不在 %APPDATA%，优先从正在运行的进程定位
        for dc_exe in running_dc_executables():
            candidates.extend(exe_candidates(dc_exe, prefix="运行中的 DC"))
        candidates.extend(nearby_candidates())
    candidates.extend(remembered_config_dirs())
    if not exe_path:
        for dc_exe in common_install_executables():
            candidates.extend(exe_candidates(dc_exe, prefix="常见安装位置"))
    candidates.extend(platform_candidates())

    seen: set[str] = set()
    for cfg_dir, source in candidates:
        key = str(cfg_dir).casefold()
        if key in seen:
            continue
        seen.add(key)
        exists = cfg_dir.is_dir()
        looks = exists and looks_like_config_dir(cfg_dir)
        checked.append((cfg_dir, source, exists, looks))

    for cfg_dir, source, exists, looks in checked:
        if looks:
            return cfg_dir, source, checked
    for cfg_dir, source, exists, _ in checked:
        # DC 程序目录本身不是配置目录（便携模式的配置在 <程序目录>\settings）
        if exists and not (cfg_dir / "doublecmd.exe").is_file():
            return cfg_dir, source + "（目录存在但尚无 DC 配置文件）", checked
    return None, "", checked


# ---------------------------------------------------------------------------
# 备份 / manifest
# ---------------------------------------------------------------------------


def make_backup(target: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = target.with_name(target.name + BACKUP_MARK + stamp)
    counter = 1
    while backup.exists():  # 同一秒内多次操作时避免覆盖
        counter += 1
        backup = target.with_name(f"{target.name}{BACKUP_MARK}{stamp}-{counter}")
    shutil.copy2(target, backup)
    return backup


def list_backups(cfg_dir: Path) -> list[Path]:
    if not cfg_dir.is_dir():
        return []
    return sorted(cfg_dir.glob("*" + BACKUP_MARK + "*"), key=lambda p: p.name)


def load_manifest() -> dict:
    if not MANIFEST_FILE.exists():
        return {"version": MANIFEST_VERSION, "installs": {}}
    try:
        with open(MANIFEST_FILE, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError
        data.setdefault("version", MANIFEST_VERSION)
        data.setdefault("installs", {})
        return data
    except Exception:
        return {"version": MANIFEST_VERSION, "installs": {}}


def save_manifest(data: dict) -> None:
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST_FILE.with_name(MANIFEST_FILE.name + TMP_SUFFIX)
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, MANIFEST_FILE)


def manifest_key(cfg_dir: Path) -> str:
    return str(cfg_dir).casefold()


def get_manifest_install(cfg_dir: Path) -> dict | None:
    return load_manifest()["installs"].get(manifest_key(cfg_dir))


def record_install(cfg_dir: Path, mode: str, store_file: str, names: list[str], backup: Path | None) -> None:
    data = load_manifest()
    entry = data["installs"].get(manifest_key(cfg_dir), {})
    entry.update(
        {
            "config_dir": str(cfg_dir),
            "mode": mode,
            "store_file": store_file,
            "names": names,
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    if backup:
        entry["last_backup"] = str(backup)
    data["installs"][manifest_key(cfg_dir)] = entry
    save_manifest(data)


def clear_install_record(cfg_dir: Path) -> None:
    data = load_manifest()
    if manifest_key(cfg_dir) in data["installs"]:
        del data["installs"][manifest_key(cfg_dir)]
        save_manifest(data)


# ---------------------------------------------------------------------------
# DC 风格的“宽松 JSON”读写（colors.json）
# ---------------------------------------------------------------------------
# Double Commander 的 colors.json 由 FPC fpjson 的
#   FRoot.FormatJSON([foDoNotQuoteMembers])
# 生成：成员名不带引号（如 `FileColors : [`），并且 FPC 的扫描器默认还允许
# 注释、单引号字符串等。Python 标准 json 无法解析这种文件，因此这里实现了一个
# 宽松解析器和与 DC 输出风格一致的序列化器。

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


class _RelaxedParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)

    def fail(self, message: str):
        line = self.text.count("\n", 0, self.pos) + 1
        raise RuleError(f"colors.json 解析失败（第 {line} 行）：{message}")

    def skip_ws(self):
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch in " \t\r\n":
                self.pos += 1
            elif ch == "/" and self.pos + 1 < self.length and self.text[self.pos + 1] == "/":
                end = self.text.find("\n", self.pos)
                self.pos = self.length if end < 0 else end + 1
            elif ch == "/" and self.pos + 1 < self.length and self.text[self.pos + 1] == "*":
                end = self.text.find("*/", self.pos + 2)
                if end < 0:
                    self.fail("块注释未闭合")
                self.pos = end + 2
            else:
                break

    def parse(self):
        self.skip_ws()
        value = self.parse_value()
        self.skip_ws()
        if self.pos != self.length:
            self.fail("根对象之后还有多余内容")
        return value

    def parse_value(self):
        self.skip_ws()
        if self.pos >= self.length:
            self.fail("意外的文件结尾")
        ch = self.text[self.pos]
        if ch == "{":
            return self.parse_object()
        if ch == "[":
            return self.parse_array()
        if ch in "\"'":
            return self.parse_string()
        if ch == "-" or ch.isdigit():
            return self.parse_number()
        if ch.isalpha() or ch == "_":
            ident = self.parse_identifier()
            if ident == "true":
                return True
            if ident == "false":
                return False
            if ident == "null":
                return None
            return ident
        self.fail(f"无法识别的字符 {ch!r}")

    def parse_identifier(self) -> str:
        start = self.pos
        while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] == "_"):
            self.pos += 1
        if start == self.pos:
            self.fail("缺少标识符")
        return self.text[start:self.pos]

    def parse_string(self) -> str:
        quote = self.text[self.pos]
        self.pos += 1
        chunks: list[str] = []
        escapes = {'"': '"', "'": "'", "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch == quote:
                self.pos += 1
                return "".join(chunks)
            if ch == "\\":
                self.pos += 1
                if self.pos >= self.length:
                    self.fail("字符串中的转义序列不完整")
                esc = self.text[self.pos]
                if esc == "u":
                    hex_digits = self.text[self.pos + 1:self.pos + 5]
                    if len(hex_digits) != 4 or not re.fullmatch(r"[0-9a-fA-F]{4}", hex_digits):
                        self.fail("无效的 \\uXXXX 转义")
                    code = int(hex_digits, 16)
                    self.pos += 5
                    # UTF-16 代理对
                    if 0xD800 <= code <= 0xDBFF and self.text[self.pos:self.pos + 2] == "\\u":
                        low_hex = self.text[self.pos + 2:self.pos + 6]
                        if re.fullmatch(r"[0-9a-fA-F]{4}", low_hex or ""):
                            low = int(low_hex, 16)
                            if 0xDC00 <= low <= 0xDFFF:
                                code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                                self.pos += 6
                    chunks.append(chr(code))
                    continue
                if esc not in escapes:
                    self.fail(f"不支持的转义 \\{esc}")
                chunks.append(escapes[esc])
                self.pos += 1
                continue
            chunks.append(ch)
            self.pos += 1
        self.fail("字符串未闭合")

    def parse_number(self):
        match = _NUMBER_RE.match(self.text, self.pos)
        if not match:
            self.fail("无效的数字")
        token = match.group(0)
        self.pos = match.end()
        if any(c in token for c in ".eE"):
            return float(token)
        return int(token)

    def parse_array(self):
        self.pos += 1  # [
        items = []
        self.skip_ws()
        if self.pos < self.length and self.text[self.pos] == "]":
            self.pos += 1
            return items
        while True:
            items.append(self.parse_value())
            self.skip_ws()
            if self.pos >= self.length:
                self.fail("数组未闭合")
            ch = self.text[self.pos]
            if ch == ",":
                self.pos += 1
                self.skip_ws()
                if self.pos < self.length and self.text[self.pos] == "]":  # 容忍尾随逗号
                    self.pos += 1
                    return items
                continue
            if ch == "]":
                self.pos += 1
                return items
            self.fail("数组中缺少逗号或 ]")

    def parse_object(self):
        self.pos += 1  # {
        result = {}
        self.skip_ws()
        if self.pos < self.length and self.text[self.pos] == "}":
            self.pos += 1
            return result
        while True:
            self.skip_ws()
            if self.pos >= self.length:
                self.fail("对象未闭合")
            ch = self.text[self.pos]
            if ch in "\"'":
                key = self.parse_string()
            elif ch.isalpha() or ch == "_":
                key = self.parse_identifier()
            else:
                self.fail("缺少成员名")
            self.skip_ws()
            if self.pos >= self.length or self.text[self.pos] != ":":
                self.fail("成员名之后缺少冒号")
            self.pos += 1
            result[key] = self.parse_value()
            self.skip_ws()
            if self.pos >= self.length:
                self.fail("对象未闭合")
            ch = self.text[self.pos]
            if ch == ",":
                self.pos += 1
                self.skip_ws()
                if self.pos < self.length and self.text[self.pos] == "}":  # 容忍尾随逗号
                    self.pos += 1
                    return result
                continue
            if ch == "}":
                self.pos += 1
                return result
            self.fail("对象中缺少逗号或 }")


def parse_relaxed_json(text: str):
    return _RelaxedParser(text).parse()


def _dump_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def dump_relaxed_json(value, newline: str = "\n") -> str:
    """按 DC (fpjson FormatJSON + foDoNotQuoteMembers) 的风格输出：成员名不带引号。"""

    def scalar(val):
        if val is True:
            return "true"
        if val is False:
            return "false"
        if val is None:
            return "null"
        if isinstance(val, int):
            return str(val)
        if isinstance(val, float):
            text = repr(val)
            return text
        if isinstance(val, str):
            return _dump_string(val)
        raise TypeError(f"无法序列化的类型: {type(val)!r}")

    def emit(val, level: int) -> str:
        pad = "  " * level
        if isinstance(val, dict):
            if not val:
                return "{}"
            lines = ["{"]
            items = list(val.items())
            for index, (key, item) in enumerate(items):
                key_text = str(key) if _IDENT_RE.match(str(key)) else _dump_string(str(key))
                rendered = emit(item, level + 1)
                suffix = "," if index < len(items) - 1 else ""
                lines.append(f"{'  ' * (level + 1)}{key_text} : {rendered}{suffix}")
            lines.append(pad + "}")
            return newline.join(lines)
        if isinstance(val, list):
            if not val:
                return "[" + newline + pad + "]"
            lines = ["["]
            for index, item in enumerate(val):
                rendered = emit(item, level + 1)
                suffix = "," if index < len(val) - 1 else ""
                lines.append(f"{'  ' * (level + 1)}{rendered}{suffix}")
            lines.append(pad + "]")
            return newline.join(lines)
        return scalar(val)

    return emit(value, 0) + newline


def detect_newline(path: Path, default: str | None = None) -> str:
    if default is None:
        default = "\r\n" if os.name == "nt" else "\n"
    try:
        raw = path.read_bytes()[:65536]
    except OSError:
        return default
    return "\r\n" if b"\r\n" in raw else default


# ---------------------------------------------------------------------------
# JSON 存储（DC 1.1.x：colors.json）
# ---------------------------------------------------------------------------


def read_colors_json(path: Path, force: bool = False) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig", errors="strict").strip()
    if not text:
        return {}
    try:
        data = parse_relaxed_json(text)
    except RuleError as exc:
        if force:
            print_warn(f"colors.json 解析失败，已按 --force 覆盖: {exc}")
            return {}
        raise
    if not isinstance(data, dict):
        if force:
            print_warn("colors.json 顶层不是对象，已按 --force 覆盖")
            return {}
        raise RuleError(f"无法处理 {path}：顶层应为 JSON 对象")
    return data


def write_json_atomic(path: Path, data: dict) -> None:
    newline = detect_newline(path)
    text = dump_relaxed_json(data, newline=newline)
    tmp = path.with_name(path.name + TMP_SUFFIX)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def rules_to_filecolor_entries(rules: list[dict]) -> list[dict]:
    entries = []
    for rule in rules:
        entries.append(
            {
                "Name": rule["name"],
                "Masks": ";".join(rule["masks"]),
                "Colors": [hex_to_tcolor(rule["light"]), hex_to_tcolor(rule["dark"])],
                "Attributes": "",
            }
        )
    return entries


def merge_filecolors(existing: list, entries: list[dict], owned: set[str], prepend: bool = False) -> tuple[list, dict]:
    """
    把 entries 合并进现有 FileColors 列表：
      * 与现有条目同名 → 原位替换（更新）
      * 属于本工具旧版本、但本次未选择的分类 → 移除（保持与规则包同步）
      * 其他用户自建条目 → 原样保留
      * 新条目默认追加到末尾（DC 按顺序匹配，先到先得）；prepend=True 则放到最前
    """
    stats = {"added": 0, "updated": 0, "removed": 0, "kept": 0}
    pending = {e["Name"].casefold(): e for e in entries}
    used: set[str] = set()
    result: list = []

    for item in existing:
        if not isinstance(item, dict):
            result.append(item)  # 原样保留无法识别的条目
            stats["kept"] += 1
            continue
        key = str(item.get("Name", "")).casefold()
        if key in pending:
            result.append(pending[key])
            used.add(key)
            stats["updated"] += 1
        elif key in owned:
            stats["removed"] += 1  # 旧的工具规则，本次未选择 → 移除
        else:
            result.append(item)
            stats["kept"] += 1

    fresh = [e for e in entries if e["Name"].casefold() not in used]
    stats["added"] = len(fresh)
    return (fresh + result) if prepend else (result + fresh), stats


# ---------------------------------------------------------------------------
# XML 存储（DC 1.0.x：doublecmd.xml 的 <Colors><FileFilters>）
# ---------------------------------------------------------------------------


def _parse_xml(path: Path) -> ET.ElementTree:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(path, parser=parser)


def _find_child(parent: ET.Element, tag: str) -> ET.Element | None:
    for child in parent:
        if isinstance(child.tag, str) and child.tag.casefold() == tag.casefold():
            return child
    return None


def _filter_name(filter_node: ET.Element) -> str:
    name_node = _find_child(filter_node, "Name")
    return (name_node.text or "").strip() if name_node is not None else ""


def _make_filter_element(rule: dict) -> ET.Element:
    node = ET.Element("Filter")
    ET.SubElement(node, "Name").text = rule["name"]
    ET.SubElement(node, "FileMasks").text = ";".join(rule["masks"])
    # 1.0.x 只有单一颜色，使用浅色值
    ET.SubElement(node, "Color").text = str(hex_to_tcolor(rule["light"]))
    ET.SubElement(node, "Attributes").text = ""
    return node


def merge_filters(container: ET.Element, rules: list[dict], owned: set[str]) -> dict:
    stats = {"added": 0, "updated": 0, "removed": 0, "kept": 0}
    pending = {r["name"].casefold(): r for r in rules}
    used: set[str] = set()
    keep_children: list[ET.Element] = []

    for child in list(container):
        if not isinstance(child.tag, str) or child.tag.casefold() != "filter":
            keep_children.append(child)  # 注释等原样保留
            continue
        key = _filter_name(child).casefold()
        if key in pending:
            keep_children.append(_make_filter_element(pending[key]))
            used.add(key)
            stats["updated"] += 1
        elif key in owned:
            stats["removed"] += 1
        else:
            keep_children.append(child)
            stats["kept"] += 1

    fresh = [r for r in rules if r["name"].casefold() not in used]
    stats["added"] = len(fresh)

    for child in list(container):
        container.remove(child)
    for child in keep_children:
        container.append(child)
    for rule in fresh:
        container.append(_make_filter_element(rule))
    return stats


def write_xml_atomic(tree: ET.ElementTree, path: Path) -> None:
    tmp = path.with_name(path.name + TMP_SUFFIX)
    tree.write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# 进程 / 存储模式
# ---------------------------------------------------------------------------


def doublecmd_running() -> bool:
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq doublecmd.exe", "/NH"],
                capture_output=True,
                timeout=15,
            )
            return b"doublecmd" in proc.stdout.lower()
        proc = subprocess.run(["pgrep", "-f", "doublecmd"], capture_output=True, timeout=15)
        return proc.returncode == 0
    except Exception:
        return False


def choose_store(cfg_dir: Path, mode: str = "auto") -> tuple[str, Path]:
    colors = cfg_dir / COLORS_JSON
    xml = cfg_dir / MAIN_XML
    if mode == "json":
        return "json", colors
    if mode == "xml":
        return "xml", xml
    if colors.exists():
        return "json", colors
    if xml.exists():
        return "xml", xml
    return "json", colors


def owned_names(cfg_dir: Path, rules: list[dict]) -> set[str]:
    """本工具“拥有”的规则名（用于更新/卸载）：manifest 记录 ∪ 当前规则包。"""
    owned = {r["name"].casefold() for r in rules}
    record = get_manifest_install(cfg_dir)
    if record:
        owned |= {str(n).casefold() for n in record.get("names", [])}
    return owned


# ---------------------------------------------------------------------------
# 安装 / 卸载
# ---------------------------------------------------------------------------


def install(
    cfg_dir: Path,
    rules: list[dict],
    *,
    mode: str = "auto",
    prepend: bool = False,
    dry_run: bool = False,
    force: bool = False,
    make_backup_file: bool = True,
) -> dict:
    if not cfg_dir.is_dir():
        raise RuleError(f"配置目录不存在: {cfg_dir}")
    if not rules:
        raise RuleError("没有可安装的规则（检查 --only/--except 或规则文件的 enabled 字段）")

    store_mode, store_path = choose_store(cfg_dir, mode)
    names = [r["name"] for r in rules]
    backup = None
    summary = {"mode": store_mode, "store_file": str(store_path), "added": 0, "updated": 0, "removed": 0, "kept": 0}

    if store_mode == "json":
        data = read_colors_json(store_path, force=force)
        existing = data.get("FileColors", [])
        if existing is None:
            existing = []
        if not isinstance(existing, list):
            if not force:
                raise RuleError(f"{store_path} 中的 FileColors 不是数组，无法安全合并（可用 --force 覆盖）")
            print_warn("FileColors 不是数组，已按 --force 覆盖")
            existing = []
        entries = rules_to_filecolor_entries(rules)
        merged, stats = merge_filecolors(existing, entries, owned_names(cfg_dir, rules), prepend=prepend)
        summary.update(stats)
        if dry_run:
            return summary
        if store_path.exists() and make_backup_file:
            backup = make_backup(store_path)
        data["FileColors"] = merged
        write_json_atomic(store_path, data)
    else:
        if not store_path.exists():
            if dry_run:
                summary.update({"added": len(rules)})
                return summary
            raise RuleError(
                f"XML 模式需要已存在的 {MAIN_XML}（未找到）。\n"
                f"     如果使用 DC 1.0.x，请先运行一次 DC 生成配置；1.1.x 请用默认的 JSON 模式。"
            )
        tree = _parse_xml(store_path)
        root = tree.getroot()
        colors_node = _find_child(root, "Colors")
        if colors_node is None:
            colors_node = ET.SubElement(root, "Colors")
        filters_node = _find_child(colors_node, "FileFilters")
        if filters_node is None:
            filters_node = ET.SubElement(colors_node, "FileFilters")
        stats = merge_filters(filters_node, rules, owned_names(cfg_dir, rules))
        summary.update(stats)
        if dry_run:
            return summary
        backup = make_backup(store_path) if make_backup_file else None
        write_xml_atomic(tree, store_path)

    record_install(cfg_dir, store_mode, store_path.name, names, backup)
    summary["backup"] = str(backup) if backup else None
    return summary


def uninstall(cfg_dir: Path, rules: list[dict], *, force: bool = False, dry_run: bool = False) -> dict:
    if not cfg_dir.is_dir():
        raise RuleError(f"配置目录不存在: {cfg_dir}")
    owned = owned_names(cfg_dir, rules)
    record = get_manifest_install(cfg_dir)
    mode = (record or {}).get("mode")
    summary = {"mode": mode or "auto", "removed": 0, "kept": 0, "backup": None}

    # 优先按 manifest 指定的存储；否则自动
    targets: list[tuple[str, Path]] = []
    if mode == "json":
        targets.append(("json", cfg_dir / COLORS_JSON))
    elif mode == "xml":
        targets.append(("xml", cfg_dir / MAIN_XML))
    else:
        store_mode, store_path = choose_store(cfg_dir, "auto")
        targets.append((store_mode, store_path))

    for store_mode, store_path in targets:
        if not store_path.exists():
            continue
        if store_mode == "json":
            data = read_colors_json(store_path, force=force)
            existing = data.get("FileColors", [])
            if not isinstance(existing, list):
                raise RuleError(f"FileColors 不是数组，无法安全修改: {store_path}")
            remaining = []
            for item in existing:
                key = str(item.get("Name", "")).casefold() if isinstance(item, dict) else ""
                if key and key in owned:
                    summary["removed"] += 1
                else:
                    remaining.append(item)
                    summary["kept"] += 1
            if summary["removed"] == 0:
                continue
            if dry_run:
                continue
            backup = make_backup(store_path)
            summary["backup"] = str(backup)
            data["FileColors"] = remaining
            write_json_atomic(store_path, data)
        else:
            tree = _parse_xml(store_path)
            root = tree.getroot()
            colors_node = _find_child(root, "Colors")
            if colors_node is None:
                continue
            filters_node = _find_child(colors_node, "FileFilters")
            if filters_node is None:
                continue
            remaining = []
            for child in list(filters_node):
                if isinstance(child.tag, str) and child.tag.casefold() == "filter":
                    key = _filter_name(child).casefold()
                    if key and key in owned:
                        summary["removed"] += 1
                        continue
                    summary["kept"] += 1
                remaining.append(child)
            if summary["removed"] == 0:
                continue
            if dry_run:
                continue
            backup = make_backup(store_path)
            summary["backup"] = str(backup)
            for child in list(filters_node):
                filters_node.remove(child)
            for child in remaining:
                filters_node.append(child)
            write_xml_atomic(tree, store_path)

    if summary["removed"] and not dry_run:
        clear_install_record(cfg_dir)
    summary["mode"] = mode or summary["mode"]
    return summary


# ---------------------------------------------------------------------------
# 预览（HTML / 终端）
# ---------------------------------------------------------------------------


def write_preview_html(rules: list[dict], out_path: Path, title: str = "Double Commander 文件类型高亮 · 预览") -> Path:
    import html as html_mod

    def render_files(rule: dict, theme: str) -> str:
        color = rule["light"] if theme == "light" else rule["dark"]
        items = "".join(
            f'<span class="fname" style="color:{html_mod.escape(color)}">{html_mod.escape(name)}</span>'
            for name in rule["examples"]
        )
        return items or '<span class="fname">&nbsp;</span>'

    cards_light = []
    cards_dark = []
    for rule in rules:
        masks = " ".join(html_mod.escape(m) for m in rule["masks"])
        comment = html_mod.escape(rule["comment"])
        name = html_mod.escape(rule["name"])
        count = len(rule["masks"])
        for theme, cards in (("light", cards_light), ("dark", cards_dark)):
            cards.append(
                f"""
      <div class="card">
        <div class="cat">{name} <span class="hex">{html_mod.escape(rule['light' if theme == 'light' else 'dark'])}</span></div>
        <div class="files">{render_files(rule, theme)}</div>
        <div class="meta">{comment} · {count} 个掩码</div>
        <details><summary>掩码</summary><div class="masks">{masks}</div></details>
      </div>"""
            )

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html_mod.escape(title)}</title>
<style>
  body {{ font-family: "Segoe UI", "Microsoft YaHei", sans-serif; margin: 24px; background:#eef1f4; color:#222; }}
  h1 {{ font-size: 20px; margin: 0 0 6px; }}
  .sub {{ color:#666; font-size: 13px; margin-bottom: 18px; }}
  .themes {{ display: flex; gap: 20px; align-items: flex-start; flex-wrap: wrap; }}
  .theme {{ flex: 1 1 420px; border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 4px rgba(0,0,0,.15); }}
  .theme.light {{ background:#ffffff; color:#222; }}
  .theme.dark {{ background:#23262b; color:#ddd; }}
  .theme h2 {{ font-size: 15px; margin: 0 0 10px; }}
  .card {{ border-bottom: 1px dashed rgba(128,128,128,.35); padding: 8px 0; }}
  .card:last-child {{ border-bottom: none; }}
  .cat {{ font-weight: 600; font-size: 13px; }}
  .cat .hex {{ font-weight: 400; color:#888; font-size: 11px; margin-left: 6px; }}
  .files {{ margin: 4px 0; }}
  .fname {{ font-family: Consolas, "Courier New", monospace; font-size: 17px; margin-right: 14px; }}
  .meta {{ font-size: 11px; color:#8a8a8a; }}
  details summary {{ font-size: 11px; color:#8a8a8a; cursor: pointer; }}
  .masks {{ font-size: 11px; color:#8a8a8a; font-family: Consolas, monospace; line-height: 1.5; word-break: break-all; }}
</style>
</head>
<body>
  <h1>{html_mod.escape(title)}</h1>
  <div class="sub">生成时间 {stamp} · 规则按顺序匹配，第一条命中生效 · 安装后在 DC『选项 → 颜色 → 文件类型颜色』中可继续调整</div>
  <div class="themes">
    <div class="theme light"><h2>浅色主题 (Light)</h2>{''.join(cards_light)}</div>
    <div class="theme dark"><h2>深色主题 (Dark)</h2>{''.join(cards_dark)}</div>
  </div>
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8", newline="\n")
    return out_path


# ---------------------------------------------------------------------------
# 扩展名扫描：核对规则覆盖率，自动补全规则包
# ---------------------------------------------------------------------------

_SCAN_SKIP_DIRS = {
    "$recycle.bin", "system volume information", "windows", "winsxs",
    "program files", "program files (x86)", "programdata",
    "$windows.~bt", "$windows.~ws", "recovery", "perflogs", "appdata",
    "node_modules", ".git", ".svn", ".hg", ".idea", ".vs", ".vscode",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
}

_EXT_RE = re.compile(r"^\.[a-z0-9][a-z0-9_+\-]{0,15}$")

# 扩展名 → 分类 id（补充规则包未收录的常见类型；"other" = 其他·待归类）
EXT_HINTS = {
    # 图片 / 图形 / 3D
    ".webp": "images", ".avif": "images", ".jxl": "images", ".heic": "images", ".heif": "images",
    ".tga": "images", ".dds": "images", ".exr": "images", ".hdr": "images", ".rgbe": "images",
    ".arw": "images", ".cr2": "images", ".cr3": "images", ".nef": "images", ".nrw": "images",
    ".orf": "images", ".raf": "images", ".rw2": "images", ".pef": "images", ".srw": "images",
    ".dng": "images", ".3fr": "images", ".fff": "images", ".iiq": "images", ".mos": "images",
    ".psb": "images", ".xcf": "images", ".kra": "images", ".ora": "images", ".clip": "images",
    ".ase": "images", ".aseprite": "images", ".pdn": "images", ".sai": "images", ".sai2": "images",
    ".csp": "images", ".afdesign": "images", ".afphoto": "images", ".afpub": "images",
    ".ai": "images", ".cdr": "images", ".cmx": "images", ".eps": "images", ".epsi": "images",
    ".indd": "images", ".sketch": "images", ".fig": "images", ".xd": "images", ".pbm": "images",
    ".pgm": "images", ".ppm": "images", ".pnm": "images", ".xpm": "images", ".xbm": "images",
    ".wbmp": "images", ".pcx": "images", ".iff": "images", ".lbm": "images", ".qoi": "images",
    ".jp2": "images", ".j2k": "images", ".jpf": "images", ".jpx": "images", ".mj2": "images",
    ".blend": "images", ".blend1": "images", ".3ds": "images", ".max": "images", ".fbx": "images",
    ".dae": "images", ".gltf": "images", ".glb": "images", ".stl": "images", ".ply": "images",
    ".ma": "images", ".mb": "images", ".c4d": "images", ".lwo": "images", ".lws": "images",
    ".ma": "images", ".mb": "images", ".c4d": "images", ".lwo": "images", ".lws": "images",
    # 音频
    ".opus": "audio", ".m4a": "audio", ".m4b": "audio", ".m4p": "audio", ".m4r": "audio",
    ".ape": "audio", ".wv": "audio", ".tak": "audio", ".tta": "audio", ".dsf": "audio",
    ".dff": "audio", ".cda": "audio", ".mpc": "audio", ".spx": "audio", ".caf": "audio",
    ".ac3": "audio", ".dts": "audio", ".thd": "audio", ".mka": "audio", ".amr": "audio",
    ".aif": "audio", ".aifc": "audio", ".au": "audio", ".snd": "audio", ".ra": "audio",
    ".gsm": "audio", ".voc": "audio", ".8svx": "audio", ".it": "audio", ".xm": "audio",
    ".mod": "audio", ".s3m": "audio", ".mtm": "audio", ".umx": "audio", ".mid": "audio",
    ".midi": "audio", ".rmi": "audio", ".kar": "audio", ".m3u": "audio", ".m3u8": "audio",
    ".pls": "audio", ".xspf": "audio", ".asx": "audio", ".wpl": "audio", ".ncm": "audio",
    ".flac": "audio", ".aac": "audio", ".wma": "audio", ".ogg": "audio", ".oga": "audio",
    # 视频 / 字幕
    ".rmvb": "video", ".rm": "video", ".ogv": "video", ".ogm": "video", ".asf": "video",
    ".wmv": "video", ".m2ts": "video", ".mts": "video", ".m2v": "video", ".m1v": "video",
    ".mpg": "video", ".mpeg": "video", ".vob": "video", ".divx": "video", ".f4v": "video",
    ".3gp": "video", ".3g2": "video", ".amv": "video", ".mxf": "video", ".roq": "video",
    ".nsv": "video", ".wtv": "video", ".dvr-ms": "video", ".rec": "video", ".tod": "video",
    ".y4m": "video", ".viv": "video", ".mve": "video", ".bik": "video", ".smk": "video",
    ".vtt": "video", ".ass": "video", ".ssa": "video", ".srt": "video", ".sub": "video",
    ".sbv": "video", ".smi": "video", ".sami": "video", ".lrc": "audio", ".idx": "video",
    ".sup": "video", ".ttml": "video", ".dfxp": "video",
    ".m4v": "video", ".mkv": "video", ".webm": "video", ".mov": "video", ".avi": "video",
    ".flv": "video", ".mp4": "video", ".wmv": "video", ".ts": "code",
    # 压缩 / 打包
    ".xapk": "archives", ".apks": "archives", ".obb": "archives", ".aar": "archives",
    ".tar": "archives", ".taz": "archives", ".tgz": "archives", ".txz": "archives",
    ".lzo": "archives", ".sis": "archives", ".udf": "diskimages", ".vcd": "diskimages",
    ".ha": "archives", ".001": "archives", ".r00": "archives", ".r01": "archives",
    ".r02": "archives", ".snap": "archives", ".flatpak": "archives",
    ".appimage": "executables", ".pkg": "archives", ".run": "executables",
    # 文档 / 电子书 / 办公
    ".nfo": "documents", ".hlp": "documents", ".eml": "documents", ".msg": "documents",
    ".vsd": "documents", ".vsdx": "documents", ".vss": "documents", ".one": "documents",
    ".onetoc2": "documents", ".pages": "documents", ".numbers": "spreadsheets", ".key": "documents",
    ".abw": "documents", ".zabw": "documents", ".wpd": "documents", ".wps": "documents",
    ".sxw": "documents", ".sxc": "spreadsheets", ".sxi": "documents", ".stw": "documents",
    ".dotm": "documents", ".xps": "documents", ".oxps": "documents", ".pub": "documents",
    ".md": "documents", ".markdown": "documents", ".org": "documents", ".textile": "documents",
    ".rst": "documents", ".adoc": "documents", ".asciidoc": "documents", ".texi": "documents",
    ".fodt": "documents", ".fods": "spreadsheets", ".fodp": "documents", ".fodg": "images",
    ".pdf": "documents", ".djvu": "documents", ".fb2": "documents", ".lit": "documents",
    ".prc": "documents", ".pdb": "temp", ".cbz": "documents", ".cbr": "documents",
    ".cb7": "documents", ".cbt": "documents", ".epub": "documents", ".mobi": "documents",
    ".azw": "documents", ".azw3": "documents", ".kfx": "documents", ".ibooks": "documents",
    # 表格 / 数据 / 数据库
    ".db": "configs", ".db3": "configs", ".sqlite": "configs", ".sqlite3": "configs",
    ".fdb": "configs", ".mdb": "configs", ".accdb": "configs", ".dbf": "configs",
    ".parquet": "configs", ".arrow": "configs", ".feather": "configs", ".orc": "configs",
    ".avro": "configs", ".ndjson": "configs", ".jsonl": "configs", ".sas7bdat": "configs",
    ".rdata": "configs", ".rds": "configs", ".dta": "configs", ".sav": "configs",
    ".por": "configs", ".xpt": "configs", ".tsv": "spreadsheets", ".csv": "spreadsheets",
    ".dif": "spreadsheets", ".slk": "spreadsheets", ".et": "spreadsheets", ".ett": "spreadsheets",
    ".gnumeric": "spreadsheets", ".wk1": "spreadsheets", ".wk3": "spreadsheets",
    # 配置 / 日志 / 记录 / 杂项数据
    ".ini": "configs", ".cfg": "configs", ".conf": "configs", ".cnf": "configs",
    ".log": "configs", ".txt": "documents", ".dat": "configs",
    ".pid": "configs", ".lock": "configs", ".state": "configs", ".session": "configs",
    ".prefs": "configs", ".plist": "configs", ".reg": "configs", ".inf": "configs",
    ".inx": "configs", ".manifest": "configs", ".sfv": "configs",
    ".md5": "configs", ".sha1": "configs", ".sha256": "configs", ".sha512": "configs",
    ".crc": "configs", ".par": "configs", ".par2": "configs", ".torrent": "configs",
    ".magnet": "configs", ".ics": "configs", ".vcf": "configs", ".url": "scripts",
    ".webloc": "scripts", ".desktop": "scripts", ".dsc": "configs",
    ".cue": "diskimages", ".etl": "configs",
    ".evtx": "configs", ".wer": "configs", ".trace": "configs", ".dlv": "configs",
    # 源码 / 脚本 / 开发
    ".ipynb": "code", ".rmd": "code", ".qmd": "code", ".pyi": "code", ".pyx": "code",
    ".pxi": "code", ".pxd": "code", ".rpy": "code", ".rev": "code", ".cob": "code",
    ".cbl": "code", ".ada": "code", ".adb": "code", ".ads": "code", ".purs": "code",
    ".idr": "code", ".agda": "code", ".coq": "code", ".lean": "code", ".vhd": "code",
    ".nix": "code", ".dhall": "code", ".g4": "code", ".bnf": "code",
    ".ebnf": "code", ".peg": "code", ".proto3": "code",
    ".wgsl": "code", ".glsl": "code", ".vert": "code", ".frag": "code", ".comp": "code",
    ".geom": "code", ".tesc": "code", ".tese": "code", ".hlsl": "code", ".shader": "code",
    ".cu": "code", ".cuh": "code", ".cl": "code", ".hip": "code", ".m4": "code",
    ".ac": "code", ".am": "code", ".mk": "code", ".cmake.in": "code", ".ninja": "code",
    ".sln": "code", ".vcxproj": "code", ".vcproj": "code", ".csproj": "code", ".vbproj": "code",
    ".fsproj": "code", ".xcodeproj": "code", ".pbxproj": "code", ".gradle.kts": "code",
    ".pom": "code", ".lockb": "configs", ".env": "configs",
    ".gitignore": "configs", ".gitattributes": "configs", ".editorconfig": "configs",
    ".dockerignore": "configs", ".npmrc": "configs", ".yarnrc": "configs", ".prettierrc": "configs",
    ".eslintrc": "configs", ".babelrc": "configs", ".flake8": "configs", ".pylintrc": "configs",
    ".nsi": "scripts", ".iss": "scripts", ".wxs": "scripts", ".rc": "configs", ".resx": "configs",
    ".s": "code", ".asm": "code", ".S": "code", ".inc": "code", ".def": "configs",
    ".lua": "code", ".nut": "code", ".wren": "code", ".zig": "code", ".odin": "code",
    ".cr": "code", ".vim": "configs", ".vimrc": "configs",
    # 字体
    ".ttc": "fonts", ".woff2": "fonts", ".woff": "fonts", ".otc": "fonts", ".dfont": "fonts",
    ".pfb": "fonts", ".pfm": "fonts", ".afm": "fonts", ".bdf": "fonts", ".pcf": "fonts",
    ".fnt": "fonts", ".fon": "fonts", ".eot": "fonts", ".ttf": "fonts", ".otf": "fonts",
    # 可执行 / 库 / 系统
    ".pyd": "executables", ".pyc": "temp", ".pyo": "temp", ".node": "executables",
    ".wasm": "executables", ".ko": "temp", ".o": "temp", ".a": "temp", ".lib": "temp",
    ".obj": "temp", ".exe": "executables", ".dll": "executables", ".sys": "executables",
    ".msu": "executables", ".cab": "archives", ".msix": "executables", ".appx": "executables",
    ".efi": "executables", ".so": "executables", ".dylib": "executables", ".jar": "archives",
    ".class": "temp", ".dex": "executables", ".apk": "archives", ".ipa": "archives",
    # 磁盘镜像
    ".iso": "diskimages", ".img": "diskimages", ".ima": "diskimages", ".vhd": "diskimages",
    ".vhdx": "diskimages", ".vmdk": "diskimages", ".vdi": "diskimages", ".qcow": "diskimages",
    ".qcow2": "diskimages", ".dmg": "diskimages", ".nrg": "diskimages", ".mdf": "diskimages",
    ".mds": "diskimages", ".ccd": "diskimages", ".bin": "diskimages", ".cif": "diskimages",
    ".b5t": "diskimages", ".b6t": "diskimages", ".bwt": "diskimages", ".cdi": "diskimages",
    ".cso": "diskimages", ".isz": "diskimages", ".dax": "diskimages", ".wim": "diskimages",
    ".esd": "diskimages", ".swm": "diskimages", ".xva": "diskimages", ".ovf": "diskimages",
    # 临时 / 备份
    ".tmp": "temp", ".temp": "temp", ".bak": "temp", ".old": "temp", ".orig": "temp",
    ".part": "temp", ".partial": "temp", ".crdownload": "temp", ".download": "temp",
    ".opdownload": "temp", ".aria2": "temp", ".!ut": "temp", ".bc!": "temp",
    ".dmp": "temp", ".dump": "temp", ".chk": "temp", ".swap": "temp", ".swp": "temp",
    # 游戏 / 引擎资源（RPG Maker、Ren'Py、Kirikiri、Unity、Live2D 等）
    ".rpgmvp": "images", ".rpgmvo": "audio", ".rpgmvm": "audio", ".png_": "images",
    ".ogg_": "audio", ".m4a_": "audio", ".webp_": "images",
    ".rpa": "archives", ".rpi": "configs", ".rpe": "configs", ".rpym": "code",
    ".rpymc": "code", ".rpy": "code", ".rpyc": "code", ".rpgsave": "configs",
    ".rmmzsave": "configs", ".rmmzrpg": "configs", ".dust": "configs", ".dectest": "configs",
    ".xp3": "archives", ".npa": "archives", ".npk": "archives", ".ypf": "archives",
    ".ks": "code", ".ksd": "configs", ".tjs": "code", ".asd": "configs", ".asb": "configs",
    ".moc": "images", ".moc3": "images", ".model3": "images", ".physics3": "configs",
    ".cdi3": "images", ".can3": "configs", ".motion3": "configs", ".exp3": "configs",
    ".efkefc": "images", ".efkmat": "images", ".efkproj": "images", ".lrj": "configs",
    ".unity": "configs", ".asset": "configs", ".prefab": "configs", ".controller": "configs",
    ".anim": "configs", ".overridecontroller": "configs", ".mat": "configs",
    ".material": "configs", ".scene": "configs", ".mesh": "images", ".shader": "code",
    ".shadergraph": "code", ".xshader": "code", ".gljson": "configs", ".glsl": "code",
    ".gd": "code", ".gdshader": "code", ".tscn": "configs", ".tres": "configs",
    ".godot": "configs", ".import": "configs", ".pck": "archives",
    ".sl2": "configs", ".vdf": "configs", ".sav": "configs", ".save": "configs",
    ".gal": "configs", ".al": "configs", ".int": "configs",
    # 机器学习 / 数据序列化
    ".npy": "configs", ".npz": "configs", ".onnx": "configs", ".pt": "configs",
    ".pth": "configs", ".h5": "configs", ".hdf5": "configs", ".pb": "configs",
    ".tflite": "configs", ".safetensors": "configs", ".gguf": "configs", ".ggml": "configs",
    ".ckpt": "configs", ".caffemodel": "configs", ".protobin": "configs", ".pbtxt": "configs",
    ".msgpack": "configs", ".cbor": "configs", ".bson": "configs", ".pkl": "configs",
    ".pickle": "configs", ".joblib": "configs", ".tfrecord": "configs",
    # 证书 / 密钥 / 摘要
    ".pem": "configs", ".crt": "configs", ".cer": "configs", ".der": "configs",
    ".p12": "configs", ".pfx": "configs", ".key": "configs", ".pub": "configs",
    ".gpg": "configs", ".asc": "configs", ".sig": "configs", ".signature": "configs",
    ".jks": "configs", ".keystore": "configs",
    # 翻译 / 本地化
    ".po": "configs", ".mo": "configs", ".qm": "configs",
    ".xlf": "configs", ".xliff": "configs",
    # 开发杂项
    ".lfm": "code", ".lpi": "code", ".lpk": "code", ".lpr": "code", ".lps": "code",
    ".xaml": "code", ".qmltypes": "code", ".mplstyle": "configs", ".in": "configs",
    ".tmpl": "configs", ".tpl": "configs", ".template": "configs", ".mustache": "configs",
    ".hbs": "configs", ".ejs": "configs", ".j2": "configs", ".jinja": "configs",
    ".jinja2": "configs", ".apache": "documents", ".bsd": "documents", ".gpl": "documents",
    ".mit": "documents", ".lgpl": "documents", ".info": "documents", ".man": "documents",
    ".1": "documents", ".2": "documents", ".3": "documents", ".4": "documents",
    ".5": "documents", ".6": "documents", ".7": "documents", ".8": "documents",
    ".9": "documents", ".license": "documents", ".copying": "documents", ".authors": "documents",
    ".typed": "configs", ".tab": "configs", ".rmt": "configs", ".pkgmeta": "configs",
    # 实机扫描补充：游戏 / 工具 / 存档 / 工程格式
    ".rt": "configs", ".enc": "configs", ".ipt": "configs", ".sd": "configs",
    ".pk6": "configs", ".pk7": "configs", ".pk8": "configs", ".pk9": "configs",
    ".pa8": "configs", ".pa9": "configs", ".pb6": "configs", ".pb7": "configs", ".pb8": "configs",
    ".rip": "audio", ".ngs": "audio", ".pyf": "code", ".rpyb": "code", ".aspx": "code",
    ".hlsli": "code", ".dockerfile": "scripts", ".arff": "configs", ".ffpreset": "configs",
    ".index": "configs", ".nnet": "configs", ".pot": "configs", ".example": "configs",
    ".dic": "configs", ".aff": "configs", ".texture": "images", ".efkmodel": "images",
    ".icns": "images", ".wc3": "archives", ".wc4": "archives", ".wc6": "archives",
    ".wc6full": "archives", ".model": "images", ".meta": "configs", ".pym": "code",
    ".dtd": "configs", ".stp": "images", ".step": "images",
    ".000": "archives", ".002": "archives", ".003": "archives", ".004": "archives",
    ".005": "archives", ".006": "archives", ".007": "archives", ".008": "archives",
    ".009": "archives",
    # TeX Live / 排版工具链（E:\texlive 实测）
    ".tfm": "fonts", ".vf": "fonts", ".htf": "fonts", ".ofm": "fonts", ".ovf": "fonts",
    ".gft": "fonts", ".fea": "fonts", ".fdd": "fonts", ".pk": "fonts", ".gf": "fonts",
    ".sty": "documents", ".cls": "documents", ".dtx": "documents", ".ins": "documents",
    ".fd": "documents", ".def": "documents", ".mf": "fonts", ".mp": "documents",
    ".tikz": "documents", ".asy": "documents", ".ltx2": "documents", ".lmt": "documents",
    ".bst": "documents", ".bbx": "documents", ".cbx": "documents", ".clo": "documents",
    ".cmap": "documents", ".4ht": "documents", ".4hf": "documents", ".etx": "documents",
    ".dfu": "documents", ".ltx": "documents", ".tex": "documents", ".texi": "documents",
    ".tlpobj": "configs", ".tex-json": "configs", ".entryfilelist": "configs",
    ".ocp": "configs", ".ocd2": "configs", ".hyb": "configs", ".ist": "configs",
    ".texlive": "configs", ".gnuplot": "code", ".nanorc": "configs", ".perl": "code",
    ".qasm": "code", ".mako": "configs", ".hjson": "configs", ".dict": "configs",
    ".lang": "configs", ".la": "configs", ".init": "configs", ".xdy": "configs",
    ".cache-9": "temp", ".qmlc": "temp",
    # Steam 游戏资源（D:\SteamLibrary 实测）
    ".dcx": "archives", ".hkx": "archives", ".flver": "images", ".tpf": "images",
    ".tpfbdt": "images", ".tpfbhd": "images", ".mdl": "images", ".mtl": "images",
    ".anm2": "configs", ".fev": "audio", ".fsb": "audio", ".bk2": "video",
    ".hks": "code", ".effect": "code", ".fx": "code", ".fxh": "code", ".ui": "code",
    ".gv": "code", ".icc": "images", ".icm": "images", ".thumb": "images",
    ".itl": "configs", ".pdmodel": "configs", ".pdiparams": "configs",
    ".rsa": "configs", ".typelib": "configs", ".db-wal": "configs", ".db-shm": "configs",
}

_MAGIC_SIGNATURES = (
    (0, b"MZ", "executables", "PE 可执行"),
    (0, b"\x7fELF", "executables", "ELF"),
    (0, b"\xca\xfe\xba\xbe", "executables", "Mach-O"),
    (0, b"PK\x03\x04", "archives", "ZIP 容器"),
    (0, b"Rar!\x1a\x07", "archives", "RAR"),
    (0, b"7z\xbc\xaf\x27\x1c", "archives", "7-Zip"),
    (0, b"\x1f\x8b", "archives", "gzip"),
    (0, b"BZh", "archives", "bzip2"),
    (0, b"\xfd7zXZ\x00", "archives", "xz"),
    (0, b"\x28\xb5\x2f\xfd", "archives", "zstd"),
    (0, b"%PDF", "documents", "PDF"),
    (0, b"\xd0\xcf\x11\xe0", "documents", "OLE 复合文档 (doc/xls/ppt)"),
    (0, b"{\\rtf", "documents", "RTF"),
    (0, b"\x89PNG\r\n\x1a\n", "images", "PNG"),
    (0, b"\xff\xd8\xff", "images", "JPEG"),
    (0, b"GIF87a", "images", "GIF"),
    (0, b"GIF89a", "images", "GIF"),
    (0, b"BM", "images", "BMP"),
    (0, b"II*\x00", "images", "TIFF"),
    (0, b"MM\x00*", "images", "TIFF"),
    (0, b"\x00\x00\x01\x00", "images", "ICO"),
    (0, b"\x00\x00\x02\x00", "images", "CUR/ICO"),
    (0, b"DDS ", "images", "DDS"),
    (0, b"\x76\x2f\x31\x01", "images", "OpenEXR"),
    (0, b"#?RADIANCE", "images", "Radiance HDR"),
    (0, b"P1", "images", "Netpbm"), (0, b"P2", "images", "Netpbm"),
    (0, b"P3", "images", "Netpbm"), (0, b"P4", "images", "Netpbm"),
    (0, b"P5", "images", "Netpbm"), (0, b"P6", "images", "Netpbm"),
    (0, b"qoif", "images", "QOI"),
    (0, b"ID3", "audio", "MP3 (ID3)"),
    (0, b"\xff\xfb", "audio", "MP3"),
    (0, b"\xff\xf3", "audio", "MP3"),
    (0, b"\xff\xf2", "audio", "MP3"),
    (0, b"fLaC", "audio", "FLAC"),
    (0, b"MAC ", "audio", "Monkey's Audio"),
    (0, b"wvpk", "audio", "WavPack"),
    (0, b"TTA1", "audio", "True Audio"),
    (0, b"DSD ", "audio", "DSD"),
    (0, b"FRM8", "audio", "DSD/DFF"),
    (0, b"Extended Module:", "audio", "Tracker 模块"),
    (0, b"Impulse Tracker", "audio", "Tracker 模块"),
    (0, b"\x1a\x45\xdf\xa3", "video", "Matroska/WebM"),
    (0, b"FLV\x01", "video", "FLV"),
    (0, b"\x00\x00\x01\xba", "video", "MPEG-PS"),
    (0, b"\x00\x00\x01\xb3", "video", "MPEG 视频"),
    (0, b"\x30\x26\xb2\x75", "video", "ASF/WMV"),
    (0, b"\x00\x00\x00\x0c", "video", "QuickTime/MP4"),
    (0, b"\x00\x00\x00\x14", "video", "QuickTime/MP4"),
    (0, b"\x00\x00\x00\x18", "video", "QuickTime/MP4"),
    (0, b"\x00\x00\x00\x20", "video", "QuickTime/MP4"),
    (0, b"OTTO", "fonts", "OpenType (CFF)"),
    (0, b"\x00\x01\x00\x00", "fonts", "TrueType"),
    (0, b"true", "fonts", "TrueType (mac)"),
    (0, b"ttcf", "fonts", "TrueType 集合"),
    (0, b"wOFF", "fonts", "WOFF"),
    (0, b"wOF2", "fonts", "WOFF2"),
    (0, b"SQLite format 3\x00", "configs", "SQLite 数据库"),
    (0, b"RPGMV", "images", "RPG Maker MV 加密文件"),
    (0, b"MPQ\x1a", "archives", "MPQ 归档 (暴雪)"),
    (0, b"icns", "images", "macOS 图标"),
    (0, b"\x53\x51\x4c\x69", "configs", "SQLite 数据库"),
)


def mask_to_regex(mask: str):
    """把 DC 掩码转成正则（"*"/"?" 通配）；">" 开头的搜索模板无法在此评估，返回 None。"""
    if mask.startswith(">"):
        return None
    out = []
    for ch in mask:
        if ch == "*":
            out.append(".*")
        elif ch == "?":
            out.append(".")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)


def compiled_rule_masks(rules: list[dict]) -> list:
    regexes = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        for mask in rule.get("masks", []):
            rx = mask_to_regex(str(mask))
            if rx is not None:
                regexes.append(rx)
    return regexes


def matches_any(name: str, regexes) -> bool:
    return any(rx.match(name) for rx in regexes)


def sniff_category(path: Path) -> tuple[str | None, str]:
    """读取文件头部字节猜测分类（用于规则包未覆盖的扩展名）。"""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return None, "无法读取样本"
    if not head:
        return None, "空文件"
    for offset, magic, category, label in _MAGIC_SIGNATURES:
        if head[offset:offset + len(magic)] == magic:
            return category, f"魔数: {label}"
    if head[:4] == b"RIFF" and len(head) >= 12:
        kind = head[8:12]
        if kind == b"WAVE":
            return "audio", "魔数: RIFF/WAVE"
        if kind == b"AVI ":
            return "video", "魔数: RIFF/AVI"
        if kind == b"WEBP":
            return "images", "魔数: RIFF/WEBP"
        if kind == b"ACON":
            return "images", "魔数: RIFF/ANI"
        return "audio", "魔数: RIFF 容器"
    if head[4:8] == b"ftyp" and len(head) >= 12:
        brand = head[8:12].lower()
        if brand in (b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"mif1", b"msf1",
                     b"avif", b"avis", b"crx ", b"jxl "):
            return "images", f"魔数: ISOBMFF 图片 ({brand.decode('latin1')})"
        return "video", f"魔数: ISOBMFF 视频 ({brand.decode('latin1')})"
    if head[0] == 0x47 and len(head) > 188 and head[188] == 0x47:
        return "video", "魔数: MPEG-TS"
    if head[:4] == b"OggS":
        if head[28:35] == b"\x01vorbis" or head[28:33] == b"\x7fFLAC" or head[28:34] == b"OpusH":
            return "audio", "魔数: Ogg 音频"
        return "video", "魔数: Ogg 媒体"
    if head[:6] == b"ustar\x00" or head[257:263] == b"ustar\x00":
        return "archives", "魔数: tar"
    printable = sum(1 for b in head[:1024] if 9 <= b <= 13 or 32 <= b < 127)
    if printable > 900:
        text = head.decode("utf-8", "ignore").lstrip()
        if text.startswith("<?xml") or text.startswith("<!DOCTYPE html") or text.startswith("<html"):
            return "code", "文本: XML/HTML"
        if text[:1] in ("{", "["):
            return "configs", "文本: JSON 风格"
        if text.startswith("#!/"):
            return "scripts", "文本: 脚本 shebang"
        if re.match(r"^[A-Za-z0-9_.-]+\s*[:=]", text):
            return "configs", "文本: 键值配置"
        return None, "纯文本，无法判断"
    return None, "未知二进制"


def scan_files(roots, time_limit: float | None = None, progress=None):
    """遍历目录统计扩展名：返回 (计数器, 样本路径, 文件总数, 是否超时)。"""
    counts: dict[str, int] = {}
    samples: dict[str, Path] = {}
    total = 0
    started = time.monotonic()
    timed_out = False
    seen_dirs = set()
    stack = [_norm(r) for r in roots]
    while stack:
        current = stack.pop()
        try:
            st = os.stat(current)  # 跟随 junction/符号链接，用于去重防止环路
            key = (st.st_dev, st.st_ino)
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
        except OSError:
            continue
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if time_limit is not None and time.monotonic() - started > time_limit:
                        timed_out = True
                        stack.clear()
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            lowered = entry.name.casefold()
                            if lowered in _SCAN_SKIP_DIRS or lowered.startswith("."):
                                continue
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += 1
                            name = entry.name
                            dot = name.rfind(".")
                            if dot <= 0:
                                continue
                            ext = name[dot:].casefold()
                            if not _EXT_RE.match(ext):
                                continue
                            counts[ext] = counts.get(ext, 0) + 1
                            if ext not in samples:
                                samples[ext] = Path(entry.path)
                            if progress and total % 200000 == 0:
                                progress(total, time.monotonic() - started)
                    except OSError:
                        continue
        except OSError:
            continue
    return counts, samples, total, timed_out


def save_rules(path: Path, rules: list[dict], backup: bool = True) -> Path | None:
    """保存规则包（标准 JSON，UTF-8，LF），返回备份路径。"""
    backup_path = None
    if backup and path.exists():
        backup_path = make_backup(path)
    payload = {
        "version": 1,
        "generator": TOOL_NAME,
        "description": "Double Commander 文件类型高亮规则包（按扩展名/掩码给文件名着色）。"
                       "安装后可在 DC 的『选项 → 颜色 → 文件类型颜色』中查看和调整。"
                       "规则按顺序匹配，第一个匹配到的规则生效。",
        "rules": [
            {
                "id": rule.get("id", rule["name"]),
                "name": rule["name"],
                "enabled": bool(rule.get("enabled", True)),
                "masks": list(rule["masks"]),
                "light": rule["light"],
                "dark": rule["dark"],
                "examples": list(rule.get("examples", [])),
                "comment": rule.get("comment", ""),
            }
            for rule in rules
        ],
    }
    tmp = path.with_name(path.name + TMP_SUFFIX)
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return backup_path


OTHER_RULE = {
    "id": "other",
    "name": "其他·待归类",
    "enabled": True,
    "masks": [],
    "light": "#C2185B",
    "dark": "#FF80AB",
    "examples": ["mystery.xyz", "data.qqq"],
    "comment": "扫描发现的、暂时无法归类的扩展名（可手动移到合适分类）",
}


def cmd_scan(args) -> int:
    roots = [Path(p) for p in (args.dirs or [])]
    if not roots:
        raise RuleError("请给出要扫描的目录，例如: python dcmd_hl.py scan D:\\Media C:\\Users\\<用户名>")
    for root in roots:
        if not root.is_dir():
            raise RuleError(f"目录不存在: {root}")

    rules_path = Path(args.rules)
    rules = load_rules(rules_path)
    regexes = compiled_rule_masks(rules)

    print(f"规则包: {rules_path}（{len(rules)} 个分类，{sum(len(r['masks']) for r in rules)} 个掩码）")
    print("开始扫描：")
    for root in roots:
        print(f"  - {root}")
    print("（只读取文件名，不读内容；跳过 node_modules/.git/系统目录等）")
    print()

    def progress(total, elapsed):
        print(f"  … 已扫描 {total:,} 个文件（{elapsed:.0f} 秒）")

    counts, samples, total, timed_out = scan_files(roots, time_limit=args.time_limit, progress=progress)

    covered = 0
    uncovered: list[tuple[int, str]] = []
    for ext, count in counts.items():
        sample_name = samples[ext].name
        if matches_any("x" + ext, regexes) or matches_any(sample_name, regexes):
            covered += 1
        else:
            uncovered.append((count, ext))
    uncovered.sort(key=lambda item: (-item[0], item[1]))

    print()
    print(f"扫描完成：{total:,} 个文件，{len(counts)} 种扩展名"
          + ("（达到时间上限，结果可能不完整）" if timed_out else ""))
    print(f"  已被规则覆盖: {covered} 种")
    print(f"  未覆盖      : {len(uncovered)} 种")

    if uncovered:
        print()
        print("未覆盖扩展名（按出现次数排序）：")
        print("   %9s  %-13s %-14s %s" % ("数量", "扩展名", "建议分类", "判断依据"))
        suggestions: dict[str, str | None] = {}
        reports: list[tuple[int, str, str | None, str]] = []
        for count, ext in uncovered[:args.top]:
            if ext in EXT_HINTS:
                category, reason = EXT_HINTS[ext], "扩展名表"
            else:
                category, reason = sniff_category(samples[ext])
            suggestions[ext] = category
            reports.append((count, ext, category, reason))
        for count, ext, category, reason in reports:
            cat_name = category or "（待归类）"
            for rule in rules:
                if rule.get("id") == category:
                    cat_name = rule["name"]
                    break
            else:
                if category == "other":
                    cat_name = OTHER_RULE["name"]
            print("   %9d  %-13s %-14s %s" % (count, ext, cat_name, reason))
        rest = len(uncovered) - len(reports)
        if rest > 0:
            print(f"   … 另有 {rest} 种未显示（--top N 调整）")

    # ---- 写入规则包 ----
    if args.apply and uncovered:
        per_category: dict[str, list[str]] = {}
        unknown_count = 0
        for count, ext in uncovered:
            if count < args.min_count:
                continue
            if re.fullmatch(r"\.\d+", ext) and ext not in EXT_HINTS:
                continue  # 纯数字“扩展名”（日期/时间戳产物）不建立规则
            category = suggestions.get(ext)
            if category is None:
                category = EXT_HINTS.get(ext)
            if category is None:
                category, _ = sniff_category(samples[ext])
            if category is None:
                category = "other"
                unknown_count += 1
            per_category.setdefault(category, []).append(ext)
        if not per_category:
            print()
            print("没有满足 --min-count 的扩展名，未修改规则包。")
            return 0
        for category, exts in per_category.items():
            target = None
            for rule in rules:
                if rule.get("id") == category or rule["name"] == category:
                    target = rule
                    break
            if target is None:
                if category != "other":
                    continue
                target = copy.deepcopy(OTHER_RULE)
                rules.append(target)
            existing = {m.casefold() for m in target["masks"]}
            added = 0
            for ext in exts:
                mask = "*" + ext
                lowered = mask.casefold()
                if lowered in existing:
                    continue
                # 同一掩码若曾落在别的分类（例如“其他·待归类”），先移走，避免重复
                for other_rule in rules:
                    if other_rule is not target:
                        other_rule["masks"][:] = [
                            m for m in other_rule["masks"] if m.casefold() != lowered
                        ]
                target["masks"].append(mask)
                existing.add(lowered)
                added += 1
            print()
            print(f"  [{target['name']}] 新增 {added} 个掩码" + ("（含无法归类项）" if category == "other" and unknown_count else ""))
        backup_path = save_rules(rules_path, rules)
        print()
        print(f"[OK] 规则包已更新: {rules_path}")
        if backup_path:
            print(f"     原文件已备份: {backup_path}")
        if args.install:
            install_args = argparse.Namespace(
                config_dir=getattr(args, "config_dir", None),
                exe=getattr(args, "exe", None),
                rules=str(rules_path),
                only=None,
                except_=None,
                mode="auto",
                prepend=False,
                dry_run=False,
                force=False,
            )
            _check_dc_running(install_args)
            summary = install(
                _resolve_cfg(install_args),
                load_rules(rules_path),
                mode="auto",
                prepend=False,
                dry_run=False,
                force=False,
            )
            print()
            print(f"[OK] 已写入 DC 配置: {summary['store_file']}")
            print(f"     新增 {summary['added']}，更新 {summary['updated']}，"
                  f"移除旧规则 {summary['removed']}，保留用户规则 {summary['kept']}")
            if summary.get("backup"):
                print(f"     原文件已备份: {summary['backup']}")
            print("     重启 Double Commander 后生效。")
    elif not args.apply and uncovered:
        print()
        print("提示：加 --apply 可以把这些扩展名自动归类写入规则包（--install 顺便安装到 DC）。")

    return 0


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------


def _cfg_not_found_error(checked: list[tuple]) -> RuleError:
    lines = ["未能自动找到 Double Commander 配置目录，检查过以下位置："]
    for path, src, exists, looks in checked:
        mark = "存在" if exists else "不存在"
        lines.append(f"  - {path} （{src}；{mark}）")
    lines.append(
        "请用 -c/--config-dir 指定配置目录，或把 DC 程序目录 / settings 目录 / doublecmd.exe 直接作为\n"
        "     参数传入（支持从资源管理器把文件夹或 doublecmd.exe 拖拽到命令行 / install.cmd 上）。"
    )
    return RuleError("\n".join(lines))


def _resolve_cfg(args, create_missing: bool = False) -> Path:
    # 1) 位置参数：doublecmd.exe 路径、DC 程序目录或 settings 目录均可
    hint = getattr(args, "path", None)
    if hint:
        kind, resolved, note = resolve_path_hint(hint)
        print(f"[i] {note}")
        if kind == "exe":
            cfg_dir, _source, checked = detect_config_dir(str(resolved))
            if cfg_dir is None:
                raise _cfg_not_found_error(checked)
            return cfg_dir
        if kind == "missing":
            raise RuleError(f"指定的路径不存在: {resolved}")
        return resolved

    # 2) -c/--config-dir：也允许误给可执行文件/程序目录，自动纠正
    if getattr(args, "config_dir", None):
        kind, resolved, note = resolve_path_hint(args.config_dir)
        if kind == "exe":
            print(f"[i] {note}")
            cfg_dir, _source, checked = detect_config_dir(str(resolved))
            if cfg_dir is None:
                raise _cfg_not_found_error(checked)
            return cfg_dir
        cfg_dir = resolved
        if not cfg_dir.is_dir():
            if create_missing:
                cfg_dir.mkdir(parents=True, exist_ok=True)
            else:
                raise RuleError(f"指定的配置目录不存在: {cfg_dir}")
        return cfg_dir

    # 3) --exe：也允许误给配置目录
    exe_hint = getattr(args, "exe", None)
    if exe_hint:
        kind, resolved, note = resolve_path_hint(exe_hint)
        if kind == "config":
            print(f"[i] {note}")
            if resolved.is_dir():
                return resolved
        if kind == "missing":
            raise RuleError(f"指定的路径不存在: {resolved}")
        if kind == "exe":
            exe_hint = str(resolved)

    # 4) 自动探测
    cfg_dir, _source, checked = detect_config_dir(exe_hint)
    if cfg_dir is None and create_missing:
        # 默认平台目录
        candidates = platform_candidates()
        if candidates:
            cfg_dir = candidates[0][0]
            cfg_dir.mkdir(parents=True, exist_ok=True)
            return cfg_dir
    if cfg_dir is None:
        raise _cfg_not_found_error(checked)
    return cfg_dir


def _check_dc_running(args) -> None:
    if getattr(args, "force", False):
        return
    if doublecmd_running():
        raise RuleError(
            "检测到 Double Commander 正在运行。\n"
            "     DC 退出时会把内存中的颜色配置写回磁盘，覆盖本工具的修改，请先完全退出 DC 再执行；\n"
            "     确实要在运行时修改可加 --force（改动可能被 DC 覆盖）。"
        )


def cmd_detect(args) -> int:
    exe_hint = getattr(args, "exe", None)
    path_arg = getattr(args, "path", None)
    if path_arg:
        kind, resolved, note = resolve_path_hint(path_arg)
        print(f"[i] {note}")
        if kind == "missing":
            print_err(f"指定的路径不存在: {resolved}")
            return 2
        if kind == "exe":
            exe_hint = str(resolved)
        else:
            state = config_files_state(resolved)
            print_ok(f"将使用: {resolved}")
            print("     来源: 命令行指定")
            print(f"     colors.json: {'有' if state['colors_json'] else '无'}   "
                  f"doublecmd.xml: {'有' if state['doublecmd_xml'] else '无'}   "
                  f"doublecmd.inf: {'有' if state['portable_inf'] else '无'}")
            mode, _ = choose_store(resolved, "auto")
            print(f"     默认存储模式: {'JSON (colors.json，DC 1.1.x)' if mode == 'json' else 'XML (doublecmd.xml，DC 1.0.x)'}")
            return 0
    exes = [Path(exe_hint)] if exe_hint else running_dc_executables()
    if exes:
        print("检测到 Double Commander 程序：")
        for exe in exes:
            print(f"  - {exe}")
        print()
    cfg_dir, source, checked = detect_config_dir(exe_hint)
    print("检查过的候选配置目录：")
    for path, src, exists, looks in checked:
        state = "存在" if exists else "不存在"
        flag = "，含 DC 配置文件" if looks else ""
        print(f"  - {path}  （{src}；{state}{flag}）")
    print()
    if cfg_dir is None:
        print_warn("未找到可用配置目录。可用 -c/--config-dir 指定，或把 DC 程序目录 / doublecmd.exe / settings 目录直接作为参数传入。")
        return 1
    state = config_files_state(cfg_dir)
    print_ok(f"将使用: {cfg_dir}")
    print(f"     来源: {source}")
    print(f"     colors.json: {'有' if state['colors_json'] else '无'}   "
          f"doublecmd.xml: {'有' if state['doublecmd_xml'] else '无'}   "
          f"doublecmd.inf: {'有' if state['portable_inf'] else '无'}")
    mode, _ = choose_store(cfg_dir, "auto")
    print(f"     默认存储模式: {'JSON (colors.json，DC 1.1.x)' if mode == 'json' else 'XML (doublecmd.xml，DC 1.0.x)'}")
    return 0


def cmd_list(args) -> int:
    rules = select_rules(load_rules(Path(args.rules)), args.only, args.except_)
    if not rules:
        print_warn("没有符合筛选条件的规则。")
        return 1
    print(f"规则包: {args.rules}")
    print(f"{'ID':<14} {'名称':<14} 颜色(浅色/深色)                 掩码数  示例")
    print("-" * 100)
    for rule in rules:
        swatch = colorize("███", rule["light"]) + "/" + colorize("███", rule["dark"])
        samples = "  ".join(rule["examples"][:3])
        print(f"{rule['id']:<14} {rule['name']:<14} {swatch} {rule['light']}/{rule['dark']:<9} {len(rule['masks']):>4}   {samples}")
    print("-" * 100)
    total = sum(len(r["masks"]) for r in rules)
    print(f"共 {len(rules)} 个分类，{total} 个掩码。")
    return 0


def cmd_status(args) -> int:
    cfg_dir = _resolve_cfg(args)
    state = config_files_state(cfg_dir)
    print(f"配置目录: {cfg_dir}")
    print(f"  colors.json : {'有' if state['colors_json'] else '无'}")
    print(f"  doublecmd.xml: {'有' if state['doublecmd_xml'] else '无'}")
    mode, store_path = choose_store(cfg_dir, "auto")
    print(f"  当前存储模式: {'JSON（DC 1.1.x）' if mode == 'json' else 'XML（DC 1.0.x）'} -> {store_path.name}")

    rules = load_rules(Path(args.rules))
    pack_names = {r["name"].casefold() for r in rules}
    record = get_manifest_install(cfg_dir)
    owned = set(pack_names)
    if record:
        owned |= {str(n).casefold() for n in record.get("names", [])}

    entries: list[tuple[str, str]] = []
    if mode == "json" and store_path.exists():
        data = read_colors_json(store_path)
        for item in data.get("FileColors", []) or []:
            if isinstance(item, dict):
                entries.append((str(item.get("Name", "")), ";".join(map(str, item.get("Colors", [])))))
    elif mode == "xml" and store_path.exists():
        tree = _parse_xml(store_path)
        root = tree.getroot()
        colors_node = _find_child(root, "Colors")
        filters_node = _find_child(colors_node, "FileFilters") if colors_node is not None else None
        if filters_node is not None:
            for child in filters_node:
                if isinstance(child.tag, str) and child.tag.casefold() == "filter":
                    color_node = _find_child(child, "Color")
                    entries.append((_filter_name(child), color_node.text if color_node is not None else ""))

    if not entries:
        print("文件中还没有任何文件类型颜色规则。")
    else:
        mine = [e for e in entries if e[0].casefold() in owned]
        others = [e for e in entries if e[0].casefold() not in owned]
        print(f"文件中规则总数: {len(entries)}（本工具: {len(mine)}，其它: {len(others)}）")
        for name, _ in entries:
            flag = "*" if name.casefold() in owned else " "
            print(f"  {flag} {name}")
        print("  (* = 由本工具安装/管理)")

    if record:
        print(f"本工具最近一次安装: {record.get('date', '?')}，模式 {record.get('mode', '?')}，"
              f"写入 {record.get('store_file', '?')}")
        if record.get("last_backup"):
            print(f"       最近备份: {record['last_backup']}")
    else:
        print("本工具尚未在此配置目录安装过规则。")
    backups = list_backups(cfg_dir)
    if backups:
        print(f"可用备份 {len(backups)} 个（用 `backups` 命令查看，`restore` 命令还原）")
    return 0


def cmd_install(args) -> int:
    cfg_dir = _resolve_cfg(args, create_missing=True)
    _check_dc_running(args)
    all_rules = load_rules(Path(args.rules))
    rules = select_rules(all_rules, args.only, args.except_)
    if not rules:
        print_warn("筛选后没有规则可安装。")
        return 1
    summary = install(
        cfg_dir,
        rules,
        mode=args.mode,
        prepend=args.prepend,
        dry_run=args.dry_run,
        force=args.force,
    )
    action = "试运行（未写入）" if args.dry_run else "已写入"
    print_ok(f"{action}: {summary['store_file']}")
    print(f"     存储模式: {'JSON（DC 1.1.x，含深色主题颜色）' if summary['mode'] == 'json' else 'XML（DC 1.0.x，使用浅色值）'}")
    print(f"     新增 {summary['added']}，更新 {summary['updated']}，"
          f"移除旧的工具规则 {summary['removed']}，保留用户规则 {summary['kept']}")
    if summary.get("backup"):
        print(f"     原文件已备份: {summary['backup']}")
    if not args.dry_run:
        print("     重启 Double Commander 后生效（面板中的文件名将按类型着色）。")
    return 0


def cmd_uninstall(args) -> int:
    cfg_dir = _resolve_cfg(args)
    _check_dc_running(args)
    rules = load_rules(Path(args.rules))
    summary = uninstall(cfg_dir, rules, force=args.force, dry_run=args.dry_run)
    action = "试运行（未写入）" if args.dry_run else "已完成"
    if summary["removed"] == 0:
        print_warn(f"没有找到本工具安装的规则（{action}）。配置文件未改动。")
        return 0
    print_ok(f"卸载{action}: 移除 {summary['removed']} 条规则，保留 {summary['kept']} 条其它规则")
    if summary.get("backup"):
        print(f"     原文件已备份: {summary['backup']}")
    print("     重启 Double Commander 后生效。")
    return 0


def cmd_backups(args) -> int:
    cfg_dir = _resolve_cfg(args)
    backups = list_backups(cfg_dir)
    if not backups:
        print("没有备份文件。")
        return 0
    print(f"{cfg_dir} 中的备份：")
    for path in backups:
        stat = path.stat()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        print(f"  {path.name}  ({stat.st_size} 字节, {stamp})")
    print("用 `python dcmd_hl.py restore <上述文件名或完整路径>` 可还原。")
    return 0


def cmd_restore(args) -> int:
    cfg_dir = _resolve_cfg(args)
    backup = Path(args.backup)
    if not backup.is_absolute():
        backup = cfg_dir / backup
    if not backup.exists():
        raise RuleError(f"备份文件不存在: {backup}")
    original_name = backup.name.split(BACKUP_MARK)[0]
    if not original_name:
        raise RuleError(f"无法从备份文件名推断原文件: {backup.name}")
    original = cfg_dir / original_name
    if not args.yes:
        answer = input(f"将用 {backup.name} 覆盖 {original.name}（会先备份当前文件），继续？[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("已取消。")
            return 1
    if original.exists():
        extra = make_backup(original)
        print(f"当前文件已另存为: {extra.name}")
    shutil.copy2(backup, original)
    print_ok(f"已还原: {original}")
    return 0


def cmd_preview(args) -> int:
    rules = select_rules(load_rules(Path(args.rules)), args.only, args.except_)
    out = Path(args.out) if args.out else SCRIPT_DIR / "preview.html"
    write_preview_html(rules, out)
    print_ok(f"预览已生成: {out}")
    if args.open:
        webbrowser.open(out.as_uri())
    return 0


def cmd_export(args) -> int:
    rules = select_rules(load_rules(Path(args.rules)), args.only, args.except_)
    if args.format == "json":
        data = {"FileColors": rules_to_filecolor_entries(rules)}
        text = dump_relaxed_json(data, newline=os.linesep)
        default_name = "colors-fragment.json"
    else:
        root = ET.Element("Colors")
        filters = ET.SubElement(root, "FileFilters")
        for rule in rules:
            filters.append(_make_filter_element(rule))
        text = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(root, encoding="unicode")
            + "\n"
        )
        default_name = "doublecmd-colors-fragment.xml"
    out = Path(args.out) if args.out else (SCRIPT_DIR / default_name)
    out.write_text(text, encoding="utf-8", newline="\n")
    print_ok(f"已导出 {len(rules)} 条规则到: {out}")
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _menu_run(parser: argparse.ArgumentParser, argv: list[str]) -> int:
    """在菜单里执行一个子命令（复用同一套参数解析与错误处理）。"""
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 1
    try:
        return args.func(args)
    except RuleError as exc:
        print_err(str(exc))
        return 2
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130


def cmd_menu(args) -> int:
    """交互式中文菜单（双击 dcmd_hl_cli.cmd 使用）。"""
    parser = build_parser()
    print("提示：任何写入前都会自动备份；检测到 Double Commander 正在运行时会拒绝写入。")

    def ask(prompt: str) -> str | None:
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

    def bye() -> int:
        print()
        print("已退出。")
        return 0

    while True:
        print()
        print("=" * 62)
        print("  Double Commander 文件类型高亮 · 命令行菜单")
        print("=" * 62)
        print()
        print("  1  检测 DC 配置目录")
        print("  2  查看安装状态 + 已有备份")
        print("  3  查看规则包内容（分类 / 掩码数量 / 颜色）")
        print("  4  生成 HTML 预览（浅色 + 深色）并用浏览器打开")
        print("  5  安装 / 更新全部规则到 DC 配置")
        print("  6  选择性安装（只装部分分类）")
        print("  7  扫描目录扩展名并补全规则（自动归类，查漏）")
        print("  8  卸载本工具写入的规则")
        print("  9  从备份还原配置文件")
        print(" 10  查看完整命令行帮助")
        print("  0  退出")
        print()
        sel = ask("请输入编号并回车> ")
        if sel is None:
            return bye()
        if sel == "":
            continue
        if sel == "0":
            return bye()
        if sel == "1":
            _menu_run(parser, ["detect"])
        elif sel == "2":
            _menu_run(parser, ["status"])
            _menu_run(parser, ["backups"])
        elif sel == "3":
            _menu_run(parser, ["list"])
        elif sel == "4":
            _menu_run(parser, ["preview", "--open"])
        elif sel == "5":
            print()
            print("将把全部规则写入 DC 配置（自动备份，之后可卸载或还原）。")
            print("如果 Double Commander 正在运行，请先退出。")
            ans = ask("确认安装？输入 y 回车> ")
            if ans is None:
                return bye()
            if ans.lower() == "y":
                _menu_run(parser, ["install"])
        elif sel == "6":
            _menu_run(parser, ["list"])
            only = ask("输入要安装的分类（id，逗号分隔，例如 archives,images,code；直接回车返回）> ")
            if only is None:
                return bye()
            if only:
                _menu_run(parser, ["install", "--only", only])
        elif sel == "7":
            dirs = ask("输入要扫描的目录（多个用空格分隔；直接回车返回）> ")
            if dirs is None:
                return bye()
            if dirs:
                dir_list = [d.strip('"') for d in dirs.split() if d.strip()]
                rc = _menu_run(parser, ["scan", *dir_list])
                if rc == 0:
                    ans = ask("把上面这些新扩展名归类写入规则包并安装到 DC？输入 y 回车> ")
                    if ans is None:
                        return bye()
                    if ans.lower() == "y":
                        _menu_run(parser, ["scan", *dir_list, "--apply", "--install"])
        elif sel == "8":
            print()
            print("将从 DC 配置中删除本工具写入的规则（你自己的规则会保留）。")
            ans = ask("确认卸载？输入 y 回车> ")
            if ans is None:
                return bye()
            if ans.lower() == "y":
                _menu_run(parser, ["uninstall"])
        elif sel == "9":
            _menu_run(parser, ["backups"])
            name = ask("输入要还原的备份文件名（相对配置目录，或完整路径；直接回车返回）> ")
            if name is None:
                return bye()
            if name:
                _menu_run(parser, ["restore", name])
        elif sel == "10":
            parser.print_help()
            print()
            input("按回车返回菜单…")
        else:
            print()
            print("无效输入，请重新选择。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dcmd_hl.py",
        description="Double Commander 文件类型高亮规则管理器（按扩展名给文件名着色）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
        "  python dcmd_hl.py detect\n"
        "  python dcmd_hl.py install --except video,fonts\n"
        "  python dcmd_hl.py install --prepend --mode json\n"
        "  python dcmd_hl.py install \"D:\\Tools\\doublecmd\"      便携版：直接给 DC 程序目录\n"
        "  python dcmd_hl.py install \"D:\\Tools\\doublecmd\\doublecmd.exe\"\n"
        "  python dcmd_hl.py status\n"
        "  python dcmd_hl.py uninstall\n",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-c", "--config-dir",
                        help="DC 配置目录（默认自动探测；也可用 DC_CONFIG_PATH 环境变量；给程序目录/doublecmd.exe 也会自动识别）")
    common.add_argument("--exe", help="doublecmd.exe 路径（也可给 DC 程序目录或配置目录），用于推断便携模式的配置目录")
    common.add_argument("--rules", default=str(DEFAULT_RULES_FILE), help=f"规则包文件（默认 {DEFAULT_RULES_FILE}）")
    common.add_argument("--only", help="只安装/处理这些分类（id 或名称，逗号分隔）")
    common.add_argument("--except", dest="except_", help="排除这些分类（id 或名称，逗号分隔）")

    path_help = "可选：DC 程序目录、settings 目录或 doublecmd.exe 路径（支持从资源管理器拖拽到命令行上）"

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("detect", parents=[common], help="探测 DC 配置目录")
    p.add_argument("path", nargs="?", help=path_help)
    p.set_defaults(func=cmd_detect)

    p = sub.add_parser("list", parents=[common], help="列出规则包内容")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", parents=[common], help="查看配置目录中的安装状态")
    p.add_argument("path", nargs="?", help=path_help)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("install", parents=[common], help="安装/更新规则")
    p.add_argument("path", nargs="?", help=path_help)
    p.add_argument("--mode", choices=["auto", "json", "xml"], default="auto",
                   help="存储模式：auto 自动（默认）、json=colors.json（DC 1.1.x）、xml=doublecmd.xml（DC 1.0.x）")
    p.add_argument("--prepend", action="store_true", help="把本工具规则放到列表最前（默认追加到末尾，避免覆盖用户已有规则）")
    p.add_argument("--dry-run", action="store_true", help="试运行，不写入文件")
    p.add_argument("--force", action="store_true", help="DC 正在运行时也继续；损坏文件也强制覆盖")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", parents=[common], help="移除本工具安装的规则（保留其它规则）")
    p.add_argument("path", nargs="?", help=path_help)
    p.add_argument("--dry-run", action="store_true", help="试运行，不写入文件")
    p.add_argument("--force", action="store_true", help="DC 正在运行时也继续")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("backups", parents=[common], help="列出备份文件")
    p.add_argument("path", nargs="?", help=path_help)
    p.set_defaults(func=cmd_backups)

    p = sub.add_parser("restore", parents=[common], help="从备份还原配置文件")
    p.add_argument("backup", help="备份文件名（相对于配置目录）或完整路径")
    p.add_argument("-y", "--yes", action="store_true", help="不再询问")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("preview", parents=[common], help="生成 HTML 预览（浅色/深色主题）")
    p.add_argument("-o", "--out", help="输出文件（默认 preview.html）")
    p.add_argument("--open", action="store_true", help="生成后用浏览器打开")
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("export", parents=[common], help="导出配置片段（手动粘贴用）")
    p.add_argument("--format", choices=["json", "xml"], default="json")
    p.add_argument("-o", "--out", help="输出文件")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("menu", help="交互式菜单（双击 dcmd_hl_cli.cmd 使用）")
    p.set_defaults(func=cmd_menu)

    p = sub.add_parser("scan", parents=[common], help="扫描目录中的扩展名，核对并补全规则覆盖")
    p.add_argument("dirs", nargs="*", help="要扫描的目录（可多个）")
    p.add_argument("--time-limit", type=float, default=300.0, help="扫描时间上限秒数（默认 300）")
    p.add_argument("--top", type=int, default=40, help="报表最多列出多少个未覆盖扩展名（默认 40）")
    p.add_argument("--min-count", type=int, default=1, help="只把出现次数 >= N 的扩展名写入规则包（默认 1）")
    p.add_argument("--apply", action="store_true", help="把新扩展名归类写入规则包（自动备份原规则包）")
    p.add_argument("--install", action="store_true", help="写入规则包后立即安装到 DC 配置")
    p.set_defaults(func=cmd_scan)

    return parser


def main(argv: list[str] | None = None) -> int:
    _init_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuleError as exc:
        print_err(str(exc))
        return 2
    except KeyboardInterrupt:
        print("\n已中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
