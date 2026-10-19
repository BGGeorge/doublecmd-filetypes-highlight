#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dcmd_hl_gui.py —— Double Commander「文件类型高亮」图形管理器

依赖：Python 3.8+（自带 tkinter），无需安装第三方库。
命令行参数（均可省略）：
    -c / --config-dir DIR   DC 配置目录（默认自动探测，便携版会从运行中的进程定位）
    --rules FILE            规则包文件（默认 rules/default_rules.json）

功能：
    * 分类列表（颜色即时预览）、启用/停用、调整优先级顺序
    * 编辑分类名称、掩码、浅色/深色主题颜色、示例文件名
    * 一键写入 DC 配置（自动备份、可撤销），或卸载本工具的规则
    * 生成浅色/深色双主题 HTML 预览
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import colorchooser, filedialog, font as tkfont, messagebox, ttk
except Exception as exc:  # pragma: no cover
    print("无法加载 tkinter，图形界面不可用。请改用命令行: python dcmd_hl.py --help")
    print(f"错误: {exc}")
    sys.exit(1)

import dcmd_hl


APP_TITLE = "Double Commander 文件类型高亮管理器"
DARK_BG = "#23262b"
LIGHT_BG = "#ffffff"


def _set_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def _open_in_explorer(path: Path) -> None:
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" &')
    except Exception as exc:
        messagebox.showerror(APP_TITLE, f"无法打开目录：\n{exc}")


class HighlighterApp(tk.Tk):
    def __init__(self, config_dir: str | None, rules_path: str | None):
        super().__init__()
        self.title(f"{APP_TITLE}  v{dcmd_hl.TOOL_VERSION}")
        self.scale = self._detect_scale()
        self._apply_initial_geometry()

        self.rules_path = Path(rules_path) if rules_path else dcmd_hl.DEFAULT_RULES_FILE
        self.rules: list[dict] = []
        self.dirty = False
        self._loading_form = False
        self._errors: list[str] = []

        self._make_fonts()
        self._build_ui()
        self._load_rules(self.rules_path)
        self.after(150, self._init_sash)

        if config_dir:
            self.var_cfg.set(config_dir)
        else:
            self._detect_config(silent=True)
        self._update_config_status()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI

    def _make_fonts(self) -> None:
        families = set(tkfont.families(self))
        family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else (
            "Microsoft YaHei" if "Microsoft YaHei" in families else "Segoe UI"
        )
        self.font_ui = (family, 9)
        self.font_ui_bold = (family, 9, "bold")
        self.font_title = (family, 10, "bold")
        self.font_mono = ("Consolas" if "Consolas" in families else "Courier New", 12)
        self.option_add("*Font", self.font_ui)
        style = ttk.Style(self)
        try:
            style.theme_use("vista" if sys.platform == "win32" else style.theme_use())
        except Exception:
            pass
        style.configure("Treeview", font=self.font_ui, rowheight=22)

    # ------------------------------------------------------------------ DPI

    def _detect_scale(self) -> float:
        """屏幕缩放系数（96 DPI 为 1.0）。"""
        try:
            scale = float(self.winfo_fpixels("1i")) / 96.0
        except Exception:
            scale = 1.0
        return max(1.0, min(scale, 4.0))

    def _px(self, value: float) -> int:
        """把设计尺寸（96 DPI 下的像素）换算成本机实际像素。"""
        return int(round(value * self.scale))

    def _apply_initial_geometry(self) -> None:
        """按屏幕缩放设置窗口大小并居中，避免高 DPI 下界面被挤爆。"""
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(min(self._px(1060), sw - self._px(32)), min(self._px(900), sw - self._px(32)))
        h = max(min(self._px(760), sh - self._px(96)), min(self._px(620), sh - self._px(96)))
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 3)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(self._px(820), w), min(self._px(560), h))

    def _init_sash(self, attempt: int = 0) -> None:
        """按列表内容宽度设置左右分栏位置（高 DPI 下防止左侧列表被挤扁）。

        窗口刚创建时可能尚未映射完成，此时设置 sash 会静默失败——这里做有限次重试。
        """
        paned = getattr(self, "paned", None)
        if paned is None:
            return
        try:
            self.update_idletasks()
        except Exception:
            return
        if (not paned.winfo_ismapped() or paned.winfo_width() <= 1) and attempt < 12:
            self.after(120, lambda: self._init_sash(attempt + 1))
            return
        try:
            f = tkfont.Font(font=self.lb.cget("font") or self.font_ui)
            texts = [self.lb.get(i) for i in range(self.lb.size())]
            texts += ["分类（上→下 优先级递减）", "全不选全选", "↑ 上移↓ 下移"]
            widest = max(f.measure(t) for t in texts)
        except Exception:
            widest = self._px(150)
        target = widest + self._px(48)
        pane_w = paned.winfo_width()
        if pane_w > self._px(240):
            target = max(int(pane_w * 0.18), min(target, int(pane_w * 0.55)))
        try:
            paned.sashpos(0, int(target))
        except Exception:
            if attempt < 12:
                self.after(120, lambda: self._init_sash(attempt + 1))

    def _build_ui(self) -> None:
        P = self._px
        pad = {"padx": P(8), "pady": P(4)}

        # ---- 顶部：配置目录 & 规则文件 ----
        top = ttk.LabelFrame(self, text=" Double Commander 配置 ")
        top.pack(fill="x", **pad)

        row1 = ttk.Frame(top)
        row1.pack(fill="x", padx=P(8), pady=(P(6), P(2)))
        ttk.Label(row1, text="配置目录：").pack(side="left")
        self.var_cfg = tk.StringVar()
        self.ed_cfg = ttk.Entry(row1, textvariable=self.var_cfg)
        self.ed_cfg.pack(side="left", fill="x", expand=True, padx=(0, P(6)))
        ttk.Button(row1, text="自动检测", command=self._detect_config).pack(side="left", padx=P(2))
        ttk.Button(row1, text="浏览…", command=self._browse_config).pack(side="left", padx=P(2))
        ttk.Button(row1, text="打开目录", command=lambda: self._open_cfg_dir()).pack(side="left", padx=P(2))

        row2 = ttk.Frame(top)
        row2.pack(fill="x", padx=P(8), pady=(0, P(6)))
        ttk.Label(row2, text="规则文件：").pack(side="left")
        self.var_rules = tk.StringVar(value=str(self.rules_path))
        ttk.Entry(row2, textvariable=self.var_rules).pack(side="left", fill="x", expand=True, padx=(0, P(6)))
        ttk.Button(row2, text="打开…", command=self._browse_rules).pack(side="left", padx=P(2))
        ttk.Button(row2, text="重新载入", command=self._reload_rules).pack(side="left", padx=P(2))

        self.lbl_cfg_state = ttk.Label(top, text="", foreground="#666666")
        self.lbl_cfg_state.pack(fill="x", padx=P(10), pady=(0, P(6)))

        # ---- 主体：左列表 / 右编辑 ----
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=P(8), pady=P(2))
        self.paned = paned

        left = ttk.LabelFrame(paned, text=" 分类（上→下 优先级递减） ")
        paned.add(left, weight=1)

        self.lb = tk.Listbox(
            left,
            activestyle="none",
            exportselection=False,
            width=26,
            borderwidth=1,
            relief="solid",
            font=self.font_ui,
            selectbackground="#316ac5",
            selectforeground="#ffffff",
        )
        self.lb.pack(fill="both", expand=True, padx=P(6), pady=(P(6), P(2)))
        self.lb.bind("<<ListboxSelect>>", self._on_select)

        lbtns = ttk.Frame(left)
        lbtns.pack(fill="x", padx=P(6), pady=(0, P(6)))
        sub_btns = (
            ("↑ 上移", lambda: self._move(-1)),
            ("↓ 下移", lambda: self._move(1)),
            ("全选", lambda: self._set_all(True)),
            ("全不选", lambda: self._set_all(False)),
        )
        for _i, (_label, _cmd) in enumerate(sub_btns):
            ttk.Button(lbtns, text=_label, width=7, command=_cmd).grid(
                row=_i // 2, column=_i % 2, sticky="we", padx=(0, P(3)), pady=(0, P(3)))
        lbtns.columnconfigure(0, weight=1)
        lbtns.columnconfigure(1, weight=1)

        right = ttk.LabelFrame(paned, text=" 规则编辑 ")
        paned.add(right, weight=2)
        self._build_editor(right)

        # ---- 底部按钮 ----
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=P(8), pady=(P(4), 0))

        self.var_prepend = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text="优先于 DC 中已有的同名掩码规则（插入到列表最前）",
                        variable=self.var_prepend).pack(side="left")

        ttk.Button(bottom, text="生成预览 HTML…", command=self._preview_html).pack(side="right", padx=P(3))
        ttk.Button(bottom, text="卸载本工具规则", command=self._uninstall).pack(side="right", padx=P(3))
        ttk.Button(bottom, text="保存规则文件…", command=self._save_rules).pack(side="right", padx=P(3))
        self.btn_install = ttk.Button(bottom, text="安装 / 更新到 Double Commander", command=self._install)
        self.btn_install.pack(side="right", padx=P(3))

        self.lbl_status = ttk.Label(self, text="就绪", anchor="w", foreground="#444444")
        self.lbl_status.pack(fill="x", padx=P(10), pady=(P(2), P(6)))

    def _build_editor(self, parent: ttk.Frame) -> None:
        P = self._px
        body = ttk.Frame(parent)
        body.pack(fill="both", expand=True, padx=P(8), pady=P(8))
        body.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(body, text="名称：").grid(row=r, column=0, sticky="w", pady=3)
        self.var_name = tk.StringVar()
        self.ed_name = ttk.Entry(body, textvariable=self.var_name)
        self.ed_name.grid(row=r, column=1, columnspan=3, sticky="we", pady=3)
        self.var_enabled = tk.BooleanVar(value=True)
        self.chk_enabled = ttk.Checkbutton(body, text="启用此分类", variable=self.var_enabled,
                                           command=self._form_changed)
        self.chk_enabled.grid(row=r, column=4, sticky="w", padx=(8, 0))

        r += 1
        ttk.Label(body, text="掩码：").grid(row=r, column=0, sticky="nw", pady=3)
        self.txt_masks = tk.Text(body, height=5, wrap="word", undo=True, font=self.font_mono,
                                 relief="solid", borderwidth=1)
        self.txt_masks.grid(row=r, column=1, columnspan=4, sticky="we", pady=3)
        hint = ttk.Label(body, text="每行一个，或用分号分隔；支持 * 和 ?，例如 *.png、*.tar.gz",
                         foreground="#777777")
        hint.grid(row=r + 1, column=1, columnspan=4, sticky="w")

        r += 2
        ttk.Label(body, text="浅色主题：").grid(row=r, column=0, sticky="w", pady=3)
        self.sw_light = tk.Label(body, text="", width=10, relief="groove", borderwidth=1, cursor="hand2")
        self.sw_light.grid(row=r, column=1, sticky="w", pady=3)
        self.var_light = tk.StringVar()
        self.ed_light = ttk.Entry(body, textvariable=self.var_light, width=10)
        self.ed_light.grid(row=r, column=2, sticky="w", padx=(6, 12), pady=3)
        self.sw_light.bind("<Button-1>", lambda e: self._pick_color("light"))
        ttk.Button(body, text="选择…", command=lambda: self._pick_color("light")).grid(
            row=r, column=3, sticky="w")

        ttk.Label(body, text="深色主题：").grid(row=r, column=4, sticky="e", padx=(16, 4))
        self.sw_dark = tk.Label(body, text="", width=10, relief="groove", borderwidth=1, cursor="hand2")
        self.sw_dark.grid(row=r, column=5, sticky="w", pady=3)
        self.var_dark = tk.StringVar()
        self.ed_dark = ttk.Entry(body, textvariable=self.var_dark, width=10)
        self.ed_dark.grid(row=r, column=6, sticky="w", padx=(6, 4), pady=3)
        self.sw_dark.bind("<Button-1>", lambda e: self._pick_color("dark"))
        ttk.Button(body, text="选择…", command=lambda: self._pick_color("dark")).grid(
            row=r, column=7, sticky="w")
        body.columnconfigure(7, weight=0)

        r += 1
        ttk.Label(body, text="说明：").grid(row=r, column=0, sticky="w", pady=3)
        self.var_comment = tk.StringVar()
        ttk.Entry(body, textvariable=self.var_comment).grid(
            row=r, column=1, columnspan=7, sticky="we", pady=3)

        r += 1
        ttk.Label(body, text="示例文件名：").grid(row=r, column=0, sticky="w", pady=3)
        self.var_examples = tk.StringVar()
        ttk.Entry(body, textvariable=self.var_examples).grid(
            row=r, column=1, columnspan=7, sticky="we", pady=3)
        ttk.Label(body, text="分号分隔，用于下方预览", foreground="#777777").grid(
            row=r + 1, column=1, columnspan=7, sticky="w")

        r += 2
        preview_box = ttk.LabelFrame(body, text=" 预览 ")
        preview_box.grid(row=r, column=0, columnspan=8, sticky="nsew", pady=(P(8), 0))
        body.rowconfigure(r, weight=1)

        light_row = tk.Frame(preview_box, bg=LIGHT_BG, height=P(52))
        light_row.pack(fill="x", padx=P(6), pady=(P(6), P(3)))
        tk.Label(light_row, text="浅色", bg=LIGHT_BG, fg="#888888", width=5, anchor="w").pack(side="left")
        self.preview_light = tk.Frame(light_row, bg=LIGHT_BG)
        self.preview_light.pack(side="left", fill="x", expand=True)

        dark_row = tk.Frame(preview_box, bg=DARK_BG, height=P(52))
        dark_row.pack(fill="x", padx=P(6), pady=(0, P(6)))
        tk.Label(dark_row, text="深色", bg=DARK_BG, fg="#888888", width=5, anchor="w").pack(side="left")
        self.preview_dark = tk.Frame(dark_row, bg=DARK_BG)
        self.preview_dark.pack(side="left", fill="x", expand=True)

        # 绑定编辑事件
        self.var_name.trace_add("write", lambda *a: self._form_changed())
        self.var_light.trace_add("write", lambda *a: self._form_changed())
        self.var_dark.trace_add("write", lambda *a: self._form_changed())
        self.var_comment.trace_add("write", lambda *a: self._form_changed())
        self.var_examples.trace_add("write", lambda *a: self._form_changed())
        self.var_enabled.trace_add("write", lambda *a: self._form_changed())
        self.txt_masks.bind("<<Modified>>", self._on_masks_modified)

        self._set_editor_state(False)

    # ------------------------------------------------------------- rules

    def _load_rules(self, path: Path) -> None:
        try:
            rules = dcmd_hl.load_rules(Path(path))
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"载入规则失败：\n{exc}")
            if not self.rules:
                self.destroy()
            return
        self.rules = rules
        self.rules_path = Path(path)
        self.var_rules.set(str(path))
        self.dirty = False
        self._refresh_list(select=0)
        self._set_status(f"已载入 {len(rules)} 个分类（{sum(len(r['masks']) for r in rules)} 个掩码）")

    def _reload_rules(self) -> None:
        if self.dirty and not messagebox.askyesno(APP_TITLE, "当前修改尚未保存，重新载入会丢失修改。继续？"):
            return
        self._load_rules(Path(self.var_rules.get().strip()))

    def _browse_rules(self) -> None:
        filename = filedialog.askopenfilename(
            title="选择规则文件",
            filetypes=[("规则文件", "*.json"), ("所有文件", "*.*")],
            initialdir=str(self.rules_path.parent),
        )
        if filename:
            if self.dirty and not messagebox.askyesno(APP_TITLE, "当前修改尚未保存，打开新文件会丢失修改。继续？"):
                return
            self._load_rules(Path(filename))

    def _save_rules(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="保存规则文件",
            defaultextension=".json",
            filetypes=[("规则文件", "*.json")],
            initialdir=str(self.rules_path.parent),
            initialfile=self.rules_path.name if self.rules_path.name != "default_rules.json" else "custom_rules.json",
        )
        if not filename:
            return
        payload = {
            "version": 1,
            "generator": "doublecmd-filetype-highlight",
            "description": "由 dcmd_hl_gui.py 保存的规则包",
            "rules": [
                {
                    "id": r.get("id", r["name"]),
                    "name": r["name"],
                    "enabled": r["enabled"],
                    "masks": list(r["masks"]),
                    "light": r["light"],
                    "dark": r["dark"],
                    "examples": list(r["examples"]),
                    "comment": r["comment"],
                }
                for r in self.rules
            ],
        }
        try:
            Path(filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8", newline="\n")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"保存失败：\n{exc}")
            return
        self.rules_path = Path(filename)
        self.var_rules.set(str(self.rules_path))
        self.dirty = False
        self._set_status(f"规则已保存: {filename}")

    # ---------------------------------------------------------- config dir

    def _detect_config(self, silent: bool = False) -> None:
        cfg, source, _checked = dcmd_hl.detect_config_dir()
        if cfg is None:
            self.var_cfg.set("")
            if not silent:
                messagebox.showwarning(
                    APP_TITLE,
                    "未能自动找到 Double Commander 配置目录。\n\n"
                    "可以把下面任意一种路径填进“配置目录”（或点『浏览…』选择），\n"
                    "工具会自动定位到真正的配置目录：\n"
                    "  · 便携版：DC 程序目录（含 doublecmd.exe），配置一般是 <程序目录>\\settings\n"
                    "  · 安装版：%APPDATA%\\doublecmd\n"
                    "  · 也可以直接填 doublecmd.exe 的路径",
                )
        else:
            self.var_cfg.set(str(cfg))
            if not silent:
                self._set_status(f"已检测到配置目录（{source}）")
        self._update_config_status()

    def _browse_config(self) -> None:
        initial = self.var_cfg.get().strip() or str(Path.home())
        directory = filedialog.askdirectory(title="选择 Double Commander 配置目录", initialdir=initial)
        if directory:
            self.var_cfg.set(directory)
            self._update_config_status()

    def _current_cfg(self) -> Path | None:
        text = self.var_cfg.get().strip().strip('"')
        if not text:
            return None
        return Path(text)

    def _open_cfg_dir(self) -> None:
        cfg = self._current_cfg()
        if cfg and cfg.is_dir():
            _open_in_explorer(cfg)
        else:
            messagebox.showinfo(APP_TITLE, "请先选择一个有效的配置目录。")

    def _update_config_status(self) -> None:
        cfg = self._current_cfg()
        if cfg and not dcmd_hl.looks_like_config_dir(cfg):
            # 允许填 DC 程序目录 / doublecmd.exe，自动定位到真正的配置目录
            kind, resolved, _note = dcmd_hl.resolve_path_hint(str(cfg))
            if kind == "exe":
                found, source, _checked = dcmd_hl.detect_config_dir(str(resolved))
                if found is not None:
                    cfg = found
                    self.var_cfg.set(str(found))
                    self._set_status(f"已自动定位到配置目录（{source}）")
            elif kind == "config" and str(resolved) != str(cfg):
                cfg = resolved
                self.var_cfg.set(str(resolved))
                self._set_status(f"已自动定位到配置目录: {resolved}")
        if not cfg or not cfg.is_dir():
            self.lbl_cfg_state.configure(
                text="⚠ 配置目录无效：请选择 DC 的配置目录（便携版一般为 <程序目录>\\settings）",
                foreground="#c07500")
            return
        state = dcmd_hl.config_files_state(cfg)
        mode, _ = dcmd_hl.choose_store(cfg, "auto")
        parts = []
        parts.append("colors.json: " + ("有" if state["colors_json"] else "无"))
        parts.append("doublecmd.xml: " + ("有" if state["doublecmd_xml"] else "无"))
        parts.append("存储: " + ("JSON (DC 1.1.x)" if mode == "json" else "XML (DC 1.0.x)"))
        text = "  ·  ".join(parts)
        color = "#1b7f1b"
        if dcmd_hl.doublecmd_running():
            text += "  ·  ⚠ 检测到 DC 正在运行，安装前请先退出"
            color = "#c07500"
        self.lbl_cfg_state.configure(text=text, foreground=color)

    # ------------------------------------------------------------- editor

    def _selected_index(self) -> int:
        selection = self.lb.curselection()
        return int(selection[0]) if selection else -1

    def _refresh_list(self, select: int | None = None) -> None:
        self.lb.delete(0, "end")
        for rule in self.rules:
            prefix = "✔  " if rule["enabled"] else "✘  "
            self.lb.insert("end", prefix + rule["name"])
            color = rule["light"] if rule["enabled"] else "#9a9a9a"
            try:
                self.lb.itemconfig("end", foreground=color)
            except tk.TclError:
                pass
        if select is not None and self.rules:
            select = max(0, min(select, len(self.rules) - 1))
            self.lb.selection_set(select)
            self.lb.see(select)
            self._show_rule(select)
        elif not self.rules:
            self._set_editor_state(False)

    def _on_select(self, _event=None) -> None:
        index = self._selected_index()
        if index >= 0:
            self._show_rule(index)

    def _show_rule(self, index: int) -> None:
        rule = self.rules[index]
        self._loading_form = True
        try:
            self.var_name.set(rule["name"])
            self.var_enabled.set(rule["enabled"])
            self.txt_masks.delete("1.0", "end")
            self.txt_masks.insert("1.0", "\n".join(rule["masks"]))
            self.txt_masks.edit_modified(False)
            self.var_light.set(rule["light"])
            self.var_dark.set(rule["dark"])
            self.var_comment.set(rule["comment"])
            self.var_examples.set("; ".join(rule["examples"]))
        finally:
            self._loading_form = False
        self._set_editor_state(True)
        self._refresh_swatches()
        self._refresh_preview()

    def _set_editor_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.ed_name, self.chk_enabled, self.txt_masks, self.ed_light,
                       self.ed_dark, self.sw_light, self.sw_dark):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass
        if not enabled:
            for frame in (self.preview_light, self.preview_dark):
                for child in frame.winfo_children():
                    child.destroy()

    def _on_masks_modified(self, _event=None) -> None:
        if self.txt_masks.edit_modified():
            self.txt_masks.edit_modified(False)
            if not self._loading_form:
                self._form_changed()

    def _form_changed(self) -> None:
        if self._loading_form:
            return
        index = self._selected_index()
        if index < 0:
            return
        rule = self.rules[index]
        rule["name"] = self.var_name.get().strip() or rule["name"]
        rule["enabled"] = bool(self.var_enabled.get())
        masks_text = self.txt_masks.get("1.0", "end")
        masks = [m.strip() for m in masks_text.replace("\n", ";").split(";") if m.strip()]
        if masks:
            rule["masks"] = masks
        if self._is_hex(self.var_light.get()):
            rule["light"] = self.var_light.get().strip()
        if self._is_hex(self.var_dark.get()):
            rule["dark"] = self.var_dark.get().strip()
        rule["comment"] = self.var_comment.get().strip()
        rule["examples"] = [x.strip() for x in self.var_examples.get().split(";") if x.strip()] or rule["examples"]

        self.dirty = True
        prefix = "✔  " if rule["enabled"] else "✘  "
        self.lb.delete(index)
        self.lb.insert(index, prefix + rule["name"])
        self.lb.itemconfig(index, foreground=rule["light"] if rule["enabled"] else "#9a9a9a")
        self.lb.selection_set(index)
        self._refresh_swatches()
        self._refresh_preview()

    @staticmethod
    def _is_hex(value: str) -> bool:
        try:
            dcmd_hl.hex_to_tcolor(value)
            return True
        except Exception:
            return False

    def _refresh_swatches(self) -> None:
        for var, swatch in ((self.var_light, self.sw_light), (self.var_dark, self.sw_dark)):
            value = var.get().strip()
            try:
                dcmd_hl.hex_to_tcolor(value)
                swatch.configure(bg=value, text="")
            except Exception:
                swatch.configure(bg="#ffcccc", text="?")

    def _refresh_preview(self) -> None:
        examples = [x.strip() for x in self.var_examples.get().split(";") if x.strip()]
        if not examples:
            examples = [mask.replace("*", "sample") for mask in
                        [m.strip() for m in self.txt_masks.get("1.0", "end").replace("\n", ";").split(";") if m.strip()][:3]]
        for frame, color, bg in ((self.preview_light, self.var_light.get(), LIGHT_BG),
                                 (self.preview_dark, self.var_dark.get(), DARK_BG)):
            for child in frame.winfo_children():
                child.destroy()
            if not self._is_hex(color):
                color = "#888888"
            for name in examples[:5]:
                tk.Label(frame, text=name, fg=color, bg=bg, font=self.font_mono).pack(side="left", padx=(0, 18))

    def _pick_color(self, which: str) -> None:
        current = self.var_light.get() if which == "light" else self.var_dark.get()
        title = "选择浅色主题颜色" if which == "light" else "选择深色主题颜色"
        try:
            initial = current if self._is_hex(current) else "#000000"
        except Exception:
            initial = "#000000"
        _rgb, hex_value = colorchooser.askcolor(color=initial, title=title, parent=self)
        if not hex_value:
            return
        value = hex_value.upper()
        (self.var_light if which == "light" else self.var_dark).set(value)
        self._refresh_swatches()
        self._refresh_preview()

    # --------------------------------------------------------- list actions

    def _move(self, delta: int) -> None:
        index = self._selected_index()
        target = index + delta
        if index < 0 or target < 0 or target >= len(self.rules):
            return
        self.rules[index], self.rules[target] = self.rules[target], self.rules[index]
        self.dirty = True
        self._refresh_list(select=target)

    def _set_all(self, enabled: bool) -> None:
        for rule in self.rules:
            rule["enabled"] = enabled
        self.dirty = True
        index = self._selected_index()
        self._refresh_list(select=index if index >= 0 else 0)

    # ------------------------------------------------------------- actions

    def _resolve_cfg_for_action(self) -> Path | None:
        cfg = self._current_cfg()
        if not cfg or not cfg.is_dir():
            messagebox.showerror(APP_TITLE, "请先选择有效的 Double Commander 配置目录。")
            return None
        return cfg

    def _confirm_run_when_dc_running(self) -> bool:
        if not dcmd_hl.doublecmd_running():
            return True
        return messagebox.askyesno(
            APP_TITLE,
            "检测到 Double Commander 正在运行。\n\n"
            "DC 退出时会把内存中的颜色配置写回磁盘，可能覆盖本次修改。\n"
            "建议先完全退出 DC 再安装。\n\n仍要继续吗？",
        )

    def _selected_rules(self) -> list[dict]:
        return [r for r in self.rules if r["enabled"]]

    def _install(self) -> None:
        cfg = self._resolve_cfg_for_action()
        if cfg is None:
            return
        rules = self._selected_rules()
        if not rules:
            messagebox.showwarning(APP_TITLE, "没有启用的分类，无法安装。")
            return
        if not self._confirm_run_when_dc_running():
            return
        try:
            summary = dcmd_hl.install(
                cfg, rules, mode="auto",
                prepend=bool(self.var_prepend.get()),
                force=True,  # 已经通过上面的对话框确认
            )
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"安装失败：\n{exc}")
            return
        self.dirty = False
        mode_text = "colors.json（DC 1.1.x，含深色主题）" if summary["mode"] == "json" else "doublecmd.xml（DC 1.0.x）"
        messagebox.showinfo(
            APP_TITLE,
            "写入成功！\n\n"
            f"文件：{summary['store_file']}\n"
            f"模式：{mode_text}\n"
            f"新增 {summary['added']} 条，更新 {summary['updated']} 条，"
            f"移除旧规则 {summary['removed']} 条，保留其它规则 {summary['kept']} 条\n"
            + (f"\n原文件已备份：\n{summary['backup']}\n" if summary.get("backup") else "")
            + "\n请重启 Double Commander 查看效果。\n"
            "之后也可以在 DC 的『选项 → 颜色 → 文件类型颜色』里继续微调。",
        )
        self._update_config_status()
        self._set_status(f"已写入 {summary['store_file']}（新增 {summary['added']}，更新 {summary['updated']}）")

    def _uninstall(self) -> None:
        cfg = self._resolve_cfg_for_action()
        if cfg is None:
            return
        if not messagebox.askyesno(
            APP_TITLE,
            "将从 DC 配置中移除本工具管理的颜色规则。\n"
            "其它（手动添加的）规则会保留。\n\n继续吗？",
        ):
            return
        if not self._confirm_run_when_dc_running():
            return
        try:
            summary = dcmd_hl.uninstall(cfg, dcmd_hl.load_rules(self.rules_path), force=True)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"卸载失败：\n{exc}")
            return
        if summary["removed"] == 0:
            messagebox.showinfo(APP_TITLE, "没有找到本工具安装的规则，配置文件未改动。")
        else:
            messagebox.showinfo(
                APP_TITLE,
                f"已移除 {summary['removed']} 条规则，保留 {summary['kept']} 条其它规则。\n"
                + (f"\n备份：\n{summary['backup']}\n" if summary.get("backup") else "")
                + "\n重启 Double Commander 后生效。",
            )
        self._update_config_status()
        self._set_status(f"已卸载（移除 {summary['removed']} 条规则）")

    def _preview_html(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="保存预览 HTML",
            defaultextension=".html",
            filetypes=[("HTML 文件", "*.html")],
            initialdir=str(dcmd_hl.SCRIPT_DIR),
            initialfile="preview.html",
        )
        if not filename:
            return
        try:
            dcmd_hl.write_preview_html(self.rules, Path(filename))
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"生成预览失败：\n{exc}")
            return
        if messagebox.askyesno(APP_TITLE, "预览已生成，是否用浏览器打开？"):
            webbrowser.open(Path(filename).as_uri())
        self._set_status(f"预览已生成: {filename}")

    # -------------------------------------------------------------- misc

    def _set_status(self, text: str) -> None:
        self.lbl_status.configure(text=text)

    def _on_close(self) -> None:
        if self.dirty and not messagebox.askyesno(
            APP_TITLE, "规则有未保存的修改（尚未写入规则文件）。确定退出吗？"
        ):
            return
        self.destroy()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Double Commander 文件类型高亮管理器（图形界面）")
    parser.add_argument("-c", "--config-dir", help="DC 配置目录（默认自动探测）")
    parser.add_argument("--rules", help="规则包文件（默认 rules/default_rules.json）")
    args = parser.parse_args(argv)

    _set_dpi_awareness()
    app = HighlighterApp(args.config_dir, args.rules)
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
