#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 Double Commander 文件类型高亮的 Linux 发行包。

产物（默认输出到 <仓库>/_dist/linux/）：
    dcmd-filetypes-highlight-<版本>-linux.tar.gz   通用包（含一键 install.sh）
    dcmd-filetypes-highlight_<版本>_all.deb        Ubuntu / Debian
    dcmd-filetypes-highlight-<版本>-1.noarch.rpm   Fedora / RHEL / openSUSE
    install-linux.sh                               在线安装器
    SHA256SUMS                                     所有产物的校验和

依赖：Python 3.8+；生成 deb/rpm 需要 nfpm（https://nfpm.goreleaser.com）。
    Windows: 从 https://github.com/goreleaser/nfpm/releases 下载 nfpm.exe，
             用 --nfpm 指定，或放到 PATH 中。
    Linux:   go install github.com/goreleaser/nfpm/v2/cmd/nfpm@latest

示例：
    python packaging/linux/build_linux.py
    python packaging/linux/build_linux.py --version 1.1.0 --nfpm C:/tools/nfpm.exe
    python packaging/linux/build_linux.py --no-deb --no-rpm
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                      # <仓库>/
SRC = ROOT / "src"
RULES = ROOT / "rules"
DOCS = ROOT / "docs"

APP_NAME = "dcmd-filetypes-highlight"
APP_TITLE = "Double Commander 文件类型高亮"
APP_DIR = f"/usr/lib/{APP_NAME}"
DOC_DIR = f"/usr/share/doc/{APP_NAME}"
LICENSE_DIR = f"/usr/share/licenses/{APP_NAME}"


def read_version() -> str:
    text = (SRC / "dcmd_hl.py").read_text(encoding="utf-8")
    match = re.search(r'^TOOL_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("无法从 src/dcmd_hl.py 读取 TOOL_VERSION")
    return match.group(1).strip()


def find_nfpm(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get("NFPM", "").strip()
    if env:
        return env
    for name in ("nfpm", "nfpm.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def copy_file(src: Path, dst: Path, mode: int = 0o644) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    try:
        os.chmod(dst, mode)
    except OSError:
        pass


def write_text(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def make_tar(version: str, out_dir: Path) -> Path:
    pkg_name = f"{APP_NAME}-{version}-linux"
    stage = out_dir / "_stage" / "tar" / pkg_name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    copy_file(ROOT / "README.md", stage / "README.md")
    copy_file(ROOT / "CHANGELOG.md", stage / "CHANGELOG.md")
    copy_file(ROOT / "LICENSE", stage / "LICENSE")
    copy_file(HERE / "install.sh", stage / "install.sh", 0o755)
    write_text(stage / "VERSION", version + "\n")

    for rel in (
        "dcmd_hl.py",
        "dcmd_hl_gui.py",
        "dcmd_hl_cli.sh",
        "dcmd_hl_gui.sh",
    ):
        mode = 0o755 if rel.endswith(".sh") else 0o644
        copy_file(SRC / rel, stage / "src" / rel, mode)

    copy_file(RULES / "default_rules.json", stage / "rules" / "default_rules.json")
    for rel in ("gui.png", "icon.svg", "技术文档.md", "Linux安装教程.md"):
        source = DOCS / rel
        if source.is_file():
            copy_file(source, stage / "docs" / rel)

    target = out_dir / f"{pkg_name}.tar.gz"
    if target.exists():
        target.unlink()

    # 用固定的 uid/gid/mtime，便于重复构建时得到稳定内容
    with target.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                entries = sorted(stage.rglob("*"))
                for path in entries:
                    arcname = f"{pkg_name}/{path.relative_to(stage).as_posix()}"
                    info = tar.gettarinfo(str(path), arcname=arcname)
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = 0
                    if path.is_dir():
                        info.mode = 0o755
                    elif path.name.endswith(".sh"):
                        info.mode = 0o755
                    else:
                        info.mode = 0o644
                    if path.is_file():
                        with path.open("rb") as fh:
                            tar.addfile(info, fh)
                    else:
                        tar.addfile(info)
    return target


def prepare_system_stage(version: str, out_dir: Path) -> Path:
    stage = out_dir / "_stage" / "system"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    app = stage / APP_DIR.lstrip("/")
    for rel in ("dcmd_hl.py", "dcmd_hl_gui.py", "dcmd_hl_cli.sh", "dcmd_hl_gui.sh"):
        mode = 0o755 if rel.endswith(".sh") else 0o644
        copy_file(SRC / rel, app / "src" / rel, mode)
    copy_file(RULES / "default_rules.json", app / "rules" / "default_rules.json")
    copy_file(ROOT / "README.md", app / "README.md")
    copy_file(ROOT / "CHANGELOG.md", app / "CHANGELOG.md")
    copy_file(ROOT / "LICENSE", app / "LICENSE")
    write_text(app / "VERSION", version + "\n")
    for rel in ("gui.png", "icon.svg", "技术文档.md", "Linux安装教程.md"):
        source = DOCS / rel
        if source.is_file():
            copy_file(source, app / "docs" / rel)

    copy_file(HERE / "system" / "dcmd-hl", stage / "usr" / "bin" / "dcmd-hl", 0o755)
    copy_file(HERE / "system" / "dcmd-hl-gui", stage / "usr" / "bin" / "dcmd-hl-gui", 0o755)

    desktop = stage / "usr" / "share" / "applications" / f"{APP_NAME}.desktop"
    copy_file(HERE / "system" / "dcmd-filetypes-highlight.desktop", desktop)
    icon = stage / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_NAME}.svg"
    copy_file(DOCS / "icon.svg", icon)

    doc = stage / DOC_DIR.lstrip("/")
    copy_file(ROOT / "README.md", doc / "README.md")
    copy_file(ROOT / "CHANGELOG.md", doc / "CHANGELOG.md")
    copy_file(ROOT / "LICENSE", doc / "copyright")
    for rel in ("技术文档.md", "Linux安装教程.md"):
        source = DOCS / rel
        if source.is_file():
            copy_file(source, doc / rel)

    copy_file(ROOT / "LICENSE", stage / LICENSE_DIR.lstrip("/") / "LICENSE")
    copy_file(HERE / "system" / "postinstall.sh", stage / "postinstall.sh", 0o755)
    copy_file(HERE / "system" / "postremove.sh", stage / "postremove.sh", 0o755)
    return stage


def yaml_str(value: str) -> str:
    # JSON 双引号字符串同时是合法的 YAML 双引号标量，避免路径/中文转义问题
    return json.dumps(value, ensure_ascii=False)


def build_nfpm_config(
    version: str,
    stage: Path,
    packager: str,
    description: str,
) -> Path:
    files: list[Path] = []
    for path in sorted((stage / "usr").rglob("*")):
        if path.is_file():
            files.append(path)

    # RPM 只会删除 cpio 中显式列出的目录；只打包文件会留下空的
    # /usr/lib/dcmd-filetypes-highlight 等目录。这里显式声明本包专属目录，
    # 让 .rpm 在卸载时能干净移除（.deb 同样受益）。共享父目录
    # （/usr、/usr/bin、/usr/share/applications 等）不归本包所有。
    app_root = stage / APP_DIR.lstrip("/")
    dirs: list[Path] = [app_root]
    if app_root.is_dir():
        dirs.extend(sorted(p for p in app_root.rglob("*") if p.is_dir()))
    for shared in (DOC_DIR, LICENSE_DIR):
        path = stage / shared.lstrip("/")
        if path.is_dir():
            dirs.append(path)

    lines: list[str] = [
        f"name: {yaml_str(APP_NAME)}",
        "arch: all",
        "platform: linux",
        f"version: {yaml_str(version)}",
        "section: utils",
        "priority: optional",
        'maintainer: "BGGeorge <BGGeorge@users.noreply.github.com>"',
        'vendor: "BGGeorge"',
        'homepage: "https://github.com/BGGeorge/doublecmd-filetypes-highlight"',
        'license: "MIT"',
        f"description: {yaml_str(description)}",
        "depends:",
        '  - "python3"',
    ]
    if packager == "deb":
        lines += [
            "recommends:",
            '  - "python3-tk"',
        ]
    else:
        # RPM 用 release 1（文件名形如 1.1.0-1.noarch.rpm）
        lines += [
            'release: "1"',
            "rpm:",
            '  group: "Applications/File"',
        ]

    lines += [
        "contents:",
    ]
    for path in files:
        rel = path.relative_to(stage).as_posix()
        dst = "/" + rel
        # /usr/bin 下的启动器和源码目录里的 .sh 需要可执行
        executable = dst.startswith("/usr/bin/") or dst.endswith(".sh")
        mode = "0755" if executable else "0644"
        lines += [
            f"  - src: {yaml_str(rel)}",
            f"    dst: {yaml_str(dst)}",
            "    file_info:",
            f"      mode: {mode}",
        ]

    for path in dirs:
        rel = path.relative_to(stage).as_posix()
        lines += [
            f"  - dst: {yaml_str('/' + rel)}",
            "    type: dir",
            "    file_info:",
            "      mode: 0755",
        ]

    lines += [
        "scripts:",
        f"  postinstall: {yaml_str('postinstall.sh')}",
        f"  postremove: {yaml_str('postremove.sh')}",
        "",
    ]
    cfg = stage / f"nfpm-{packager}.yaml"
    cfg.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return cfg


def run_nfpm(nfpm: str, stage: Path, cfg: Path, packager: str, target: Path) -> None:
    cmd = [
        nfpm,
        "package",
        "--config",
        cfg.name,
        "--packager",
        packager,
        "--target",
        str(target),
    ]
    print("    " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(stage))
    if proc.returncode != 0:
        raise SystemExit(f"nfpm 生成 {packager} 失败（退出码 {proc.returncode}）")
    if not target.is_file() or target.stat().st_size == 0:
        raise SystemExit(f"nfpm 没有生成预期的文件: {target}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sums(paths: list[Path], out_dir: Path) -> Path:
    lines = []
    for path in sorted(paths, key=lambda p: p.name):
        lines.append(f"{sha256(path)}  {path.name}")
    target = out_dir / "SHA256SUMS"
    write_text(target, "\n".join(lines) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 Linux 发行包（tar.gz / deb / rpm）")
    parser.add_argument("--version", default=None, help="版本号（默认读取 src/dcmd_hl.py 的 TOOL_VERSION）")
    parser.add_argument("--out", default=None, help="输出目录（默认 <仓库>/_dist/linux）")
    parser.add_argument("--nfpm", default=None, help="nfpm 可执行文件路径")
    parser.add_argument("--no-tar", action="store_true", help="不生成 tar.gz")
    parser.add_argument("--no-deb", action="store_true", help="不生成 .deb")
    parser.add_argument("--no-rpm", action="store_true", help="不生成 .rpm")
    parser.add_argument("--keep-stage", action="store_true", help="保留中间目录，便于检查")
    args = parser.parse_args(argv)

    version = (args.version or read_version()).strip().lstrip("v")
    out_dir = Path(args.out).expanduser().resolve() if args.out else ROOT / "_dist" / "linux"
    out_dir.mkdir(parents=True, exist_ok=True)

    nfpm = find_nfpm(args.nfpm)
    want_deb = not args.no_deb
    want_rpm = not args.no_rpm
    if (want_deb or want_rpm) and not nfpm:
        raise SystemExit(
            "找不到 nfpm。请从 https://github.com/goreleaser/nfpm/releases 下载，"
            "并用 --nfpm 指定路径；或者加 --no-deb --no-rpm 只生成 tar.gz。"
        )

    print("=" * 64)
    print(f"  {APP_TITLE} · Linux 发行包构建")
    print(f"  版本: {version}")
    print(f"  输出: {out_dir}")
    print("=" * 64)

    artifacts: list[Path] = []
    started = time.time()

    tar_path = None
    if not args.no_tar:
        print("\n==> 1/4 生成通用 tar.gz")
        tar_path = make_tar(version, out_dir)
        artifacts.append(tar_path)
        print(f"    OK  {tar_path.name}  ({tar_path.stat().st_size / 1024 / 1024:.2f} MiB)")
    else:
        print("\n==> 1/4 跳过 tar.gz")

    deb_path = out_dir / f"{APP_NAME}_{version}_all.deb"
    rpm_path = out_dir / f"{APP_NAME}-{version}-1.noarch.rpm"
    stage = None
    if want_deb or want_rpm:
        print("\n==> 2/4 准备系统安装目录")
        stage = prepare_system_stage(version, out_dir)
        print(f"    OK  {stage}")

        if want_deb:
            print("\n==> 3/4 生成 .deb")
            cfg = build_nfpm_config(
                version, stage, "deb",
                "为 Double Commander 文件名按文件类型着色（Linux 系统级安装）",
            )
            if deb_path.exists():
                deb_path.unlink()
            run_nfpm(nfpm, stage, cfg, "deb", deb_path)
            artifacts.append(deb_path)
            print(f"    OK  {deb_path.name}  ({deb_path.stat().st_size / 1024:.1f} KiB)")
        else:
            print("\n==> 3/4 跳过 .deb")

        if want_rpm:
            print("\n==> 3/4 生成 .rpm")
            cfg = build_nfpm_config(
                version, stage, "rpm",
                "为 Double Commander 文件名按文件类型着色（Linux 系统级安装）",
            )
            if rpm_path.exists():
                rpm_path.unlink()
            run_nfpm(nfpm, stage, cfg, "rpm", rpm_path)
            artifacts.append(rpm_path)
            print(f"    OK  {rpm_path.name}  ({rpm_path.stat().st_size / 1024:.1f} KiB)")
        else:
            print("\n==> 3/4 跳过 .rpm")
    else:
        print("\n==> 2/4 跳过 deb/rpm")
        print("\n==> 3/4 跳过 deb/rpm")

    print("\n==> 4/4 生成在线安装器与 SHA256SUMS")
    template = (HERE / "install-linux.sh.in").read_text(encoding="utf-8")
    installer = out_dir / "install-linux.sh"
    write_text(installer, template.replace("@VERSION@", version), 0o755)
    artifacts.append(installer)
    sums = write_sums(artifacts, out_dir)
    print(f"    OK  {installer.name}")
    print(f"    OK  {sums.name}")

    if not args.keep_stage and stage is not None:
        shutil.rmtree(stage.parent, ignore_errors=True)

    print()
    print("=" * 64)
    print("  构建完成，产物：")
    for path in artifacts + [sums]:
        print(f"    {path.name}  ({path.stat().st_size / 1024:.1f} KiB)")
    print(f"  用时 {time.time() - started:.1f} 秒")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
