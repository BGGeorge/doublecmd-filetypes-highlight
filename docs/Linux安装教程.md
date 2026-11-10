# Double Commander 文件类型高亮 · Linux 安装教程

> 适用系统：Ubuntu / Debian / Linux Mint / Pop!_OS / Fedora / RHEL / Rocky Linux / AlmaLinux / openSUSE / Arch Linux / Manjaro 等主流发行版。
>
> 适用 Double Commander：**1.0.x / 1.1.x / 1.2.x**（GTK、Qt、Qt6 版本都可以，颜色配置是共通的）。
>
> 本工具**不是** DC 插件，而是把“按扩展名给文件名着色”的规则写入 DC 自带的「选项 → 颜色 → 文件类型颜色」。效果与手动在 DC 里逐条添加完全相同，不改 DC 一行源码。

---

## 0. 一分钟安装（推荐）

如果你用的是 Ubuntu / Debian / Fedora / openSUSE / Arch 等常见发行版，并且已经装好 Double Commander，可以直接在终端执行：

```bash
curl -fsSL https://github.com/BGGeorge/doublecmd-filetypes-highlight/releases/latest/download/install-linux.sh | bash
```

这条命令会：

1. 从 GitHub Release 下载 Linux 安装包；
2. 用 SHA256 校验安装包完整性；
3. 把程序安装到你的用户目录（**不需要 sudo**）；
4. 创建 `dcmd-hl` / `dcmd-hl-gui` 命令和桌面菜单入口；
5. 自动探测 Double Commander 的配置目录，备份后写入颜色规则；
6. 提示你重启 DC。

> 安装前请**完全退出 Double Commander**（包括托盘图标）。DC 退出时会把内存里的设置写回配置文件，运行中修改会被覆盖。
>
> 如果你不想用 `curl | bash`，请看下面的“方式 B：下载 tar.gz 手动安装”，效果完全一样。

安装完成后，重新启动 Double Commander，文件面板里的文件名就会按类型着色。

---

## 1. 先安装 Double Commander

如果还没装 DC，先按你的发行版安装（任选 GTK / Qt 版本，颜色功能相同）：

### Ubuntu / Debian / Linux Mint / Pop!_OS

```bash
sudo apt update
sudo apt install doublecmd-gtk
```

如果提示找不到软件包，先启用 `universe` 仓库：

```bash
sudo add-apt-repository universe
sudo apt update
sudo apt install doublecmd-gtk
```

### Fedora

```bash
sudo dnf install doublecmd-gtk
```

### RHEL / Rocky Linux / AlmaLinux

```bash
sudo dnf install epel-release
sudo dnf install doublecmd-gtk
```

### openSUSE

```bash
sudo zypper install doublecmd-gtk
```

### Arch Linux / Manjaro

```bash
sudo pacman -S doublecmd-gtk
```

也可以安装 `doublecmd-qt` / `doublecmd-qt6`，只要 DC 能正常启动即可。

### 验证 DC 是否安装成功

```bash
doublecmd --version
```

能看到版本号（例如 `Double Commander 1.1.11`）就说明安装成功。第一次启动 DC 后，它会自动生成配置目录；**建议先启动一次再安装高亮包**，这样配置目录一定存在。

---

## 2. 先搞清楚：你的 DC 配置在哪里？

| 安装方式 | 配置目录 |
| --- | --- |
| Ubuntu / Debian / Fedora 等系统包（普通安装） | `~/.config/doublecmd` |
| DC 便携版（程序目录里有 `settings/doublecmd.inf`） | `<DC 程序目录>/settings` |
| Flatpak | `~/.var/app/<AppID>/config/doublecmd` |
| 自定义 `--config-dir` 启动 | 你指定的目录 |

颜色规则存放位置：

| DC 版本 | 文件 | 说明 |
| --- | --- | --- |
| 1.1.x / 1.2.x | `colors.json` | 包含浅色/深色两套颜色，推荐 |
| 1.0.x | `doublecmd.xml` | 只有一套颜色，使用规则包里的浅色值 |

本工具会自动判断；你也可以运行：

```bash
dcmd-hl detect
```

如果还没安装 `dcmd-hl`，可以直接用源码：

```bash
python3 src/dcmd_hl.py detect
```

---

## 3. 方式 A：一键脚本（最适合新手）

### 3.1 执行安装

```bash
curl -fsSL https://github.com/BGGeorge/doublecmd-filetypes-highlight/releases/latest/download/install-linux.sh | bash
```

如果系统没有 `curl`，先安装：

```bash
# Ubuntu / Debian
sudo apt install curl

# Fedora
sudo dnf install curl

# Arch
sudo pacman -S curl
```

也可以用 `wget` 手动下载后执行（见方式 B）。

### 3.2 安装脚本会做什么？

脚本**不会**修改系统目录，**不会**使用 sudo，所有文件都在你的用户目录：

| 内容 | 位置 |
| --- | --- |
| 程序文件 | `~/.local/share/dcmd-filetypes-highlight/` |
| 命令入口 | `~/.local/bin/dcmd-hl`、`~/.local/bin/dcmd-hl-gui` |
| 桌面菜单 | `~/.local/share/applications/dcmd-filetypes-highlight.desktop` |
| 图标 | `~/.local/share/icons/hicolor/scalable/apps/dcmd-filetypes-highlight.svg` |
| 安装记录 | 用户级安装：程序目录下的 `installed.json`；系统级包（`.deb` / `.rpm`）或程序目录不可写：`~/.local/state/dcmd-filetypes-highlight/`（遵循 `XDG_STATE_HOME`） |
| DC 原配置备份 | 与 `colors.json` / `doublecmd.xml` 同目录，文件名含 `.fth-backup-时间` |

安装过程中会自动探测 DC 配置目录，并在写入前备份原文件。你可以随时用 `dcmd-hl uninstall` 移除规则，或用备份还原。

### 3.3 如果提示 `dcmd-hl: command not found`

`~/.local/bin` 可能不在 PATH 中。临时使用：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

永久生效（写入 `~/.profile`）：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile
```

然后注销并重新登录，或者执行 `source ~/.profile`。

你也可以始终使用绝对路径：

```bash
~/.local/bin/dcmd-hl detect
~/.local/bin/dcmd-hl install
```

---

## 4. 方式 B：下载 tar.gz 手动安装（离线/公司网络推荐）

### 4.1 下载

打开：

<https://github.com/BGGeorge/doublecmd-filetypes-highlight/releases/latest>

下载：

```text
dcmd-filetypes-highlight-1.1.0-linux.tar.gz
```

### 4.2 解压并安装

```bash
tar -xzf dcmd-filetypes-highlight-1.1.0-linux.tar.gz
cd dcmd-filetypes-highlight-1.1.0-linux
bash install.sh
```

安装脚本会自动完成“复制程序 + 创建菜单入口 + 写入 DC 配置”。

### 4.3 常用选项

```bash
# 只安装程序，不写 DC 配置（稍后自己运行 dcmd-hl install）
bash install.sh --no-config

# 先看看会做什么，不写任何文件
bash install.sh --dry-run

# 指定 DC 配置目录（安装版）
bash install.sh -c "$HOME/.config/doublecmd"

# 指定 DC 便携版程序目录
bash install.sh --dc-path "$HOME/Applications/doublecmd"

# 只安装部分分类
bash install.sh --only archives,images,audio

# 排除某些分类
bash install.sh --except temp,fonts

# 卸载程序（保留 DC 中已写入的规则）
bash install.sh --uninstall

# 卸载程序并移除颜色规则
bash install.sh --uninstall --purge
```

### 4.4 图形界面方式

如果你不习惯终端，也可以在文件管理器里解压后，右键 `install.sh` → **“在终端中运行”**（不同桌面环境名称略有差异）。如果双击只是打开文本编辑器，请右键选择“属性 → 权限 → 允许作为程序执行”，再双击。

---

## 5. 方式 C：Ubuntu / Debian 的 .deb 包

### 5.1 安装

下载：

```text
dcmd-filetypes-highlight_1.1.0_all.deb
```

在下载目录执行（注意 `./`，否则 apt 会去软件源里找同名包）：

```bash
sudo apt install ./dcmd-filetypes-highlight_1.1.0_all.deb
```

如果系统提示缺少依赖：

```bash
sudo apt --fix-broken install
```

### 5.2 安装后启用

`.deb` 只把程序安装到系统目录（`/usr/lib/dcmd-filetypes-highlight`、`/usr/bin/dcmd-hl`），**不会**自动改你的 DC 配置（因为包管理器以 root 运行，而 DC 配置属于桌面用户）。安装完成后任选一种：

- 打开应用菜单，搜索 **“Double Commander 文件类型高亮”**，打开图形界面，点右下角 **“安装 / 更新到 Double Commander”**；
- 或者在终端执行：

```bash
dcmd-hl install
```

### 5.3 卸载

先移除 DC 中的颜色规则（推荐）：

```bash
dcmd-hl uninstall
```

再卸载软件包：

```bash
sudo apt remove dcmd-filetypes-highlight
```

---

## 6. 方式 D：Fedora / RHEL / openSUSE 的 .rpm 包

### 6.1 安装

下载：

```text
dcmd-filetypes-highlight-1.1.0-1.noarch.rpm
```

Fedora / RHEL / Rocky / Alma：

```bash
sudo dnf install ./dcmd-filetypes-highlight-1.1.0-1.noarch.rpm
```

openSUSE：

```bash
sudo zypper install ./dcmd-filetypes-highlight-1.1.0-1.noarch.rpm
```

### 6.2 安装后启用

同 .deb：打开应用菜单里的 **“Double Commander 文件类型高亮”**，或执行：

```bash
dcmd-hl install
```

### 6.3 卸载

```bash
dcmd-hl uninstall
sudo dnf remove dcmd-filetypes-highlight
# openSUSE: sudo zypper remove dcmd-filetypes-highlight
```

---

## 7. 方式 E：Arch Linux / Manjaro

推荐直接用 tar.gz 一键安装（方式 B），它不依赖 AUR：

```bash
tar -xzf dcmd-filetypes-highlight-1.1.0-linux.tar.gz
cd dcmd-filetypes-highlight-1.1.0-linux
bash install.sh
```

如果你希望手动放到系统目录，也可以把 `src/`、`rules/` 复制到任意位置，然后运行：

```bash
python3 /你的路径/src/dcmd_hl.py install
```

---

## 8. 第一次使用：图形界面（推荐给新手）

1. 完全退出 Double Commander。
2. 打开应用菜单，搜索 **“Double Commander 文件类型高亮”** 并打开。
3. 顶部“配置目录”应该显示 `~/.config/doublecmd`（或你的便携版 `settings` 目录）。
   - 如果显示不对，点 **“浏览…”** 选择 DC 配置目录；
   - 也可以直接填入 DC 程序目录或 `doublecmd` 可执行文件路径，工具会自动定位。
4. 左侧列表会显示 14 个分类（压缩包、图片、代码、音频……），可以取消不想用的分类。
5. 点右下角 **“安装 / 更新到 Double Commander”**。
6. 看到成功提示后，重新启动 DC。

> 如果 DC 正在运行，工具会拒绝写入并提示你先退出。这是为了避免 DC 退出时覆盖修改。

---

## 9. 第一次使用：命令行

```bash
# 1. 探测配置目录
dcmd-hl detect

# 2. 安装/更新全部规则（自动备份）
dcmd-hl install

# 3. 查看安装状态
dcmd-hl status

# 4. 列出规则包内容
dcmd-hl list

# 5. 生成浅色/深色 HTML 预览并打开浏览器
dcmd-hl preview --open

# 6. 只安装部分分类
dcmd-hl install --only archives,images,audio

# 7. 排除某些分类
dcmd-hl install --except temp,fonts

# 8. 扩展名扫描：找出你磁盘上还没覆盖的扩展名
dcmd-hl scan "$HOME/Downloads" "$HOME/Documents"

# 9. 卸载（只移除本工具写入的规则，保留你自己的规则）
dcmd-hl uninstall

# 10. 查看备份 / 还原
dcmd-hl backups
dcmd-hl restore colors.json.fth-backup-20261109-120000
```

如果你是从源码目录运行，把 `dcmd-hl` 换成 `python3 src/dcmd_hl.py` 即可。

---

## 10. 怎么确认安装成功？

### 10.1 终端检查

```bash
dcmd-hl status
```

应该能看到：

- 配置目录（例如 `/home/you/.config/doublecmd`）
- 当前存储模式（`colors.json` 或 `doublecmd.xml`）
- 本工具安装的 14 条规则
- 最近一次安装时间和备份文件

### 10.2 查看 DC 配置

```bash
grep -n '"Name"' ~/.config/doublecmd/colors.json | head
```

应该能看到类似：

```text
"Name" : "压缩包·软件包"
"Name" : "磁盘·光盘镜像"
...
```

### 10.3 在 DC 里查看

打开 Double Commander → **选项 → 颜色 → 文件类型颜色**，应该能看到 14 个分类的规则。重启 DC 后，文件面板中的文件名会按类型着色。

---

## 11. 常见问题（FAQ）

### Q1：提示“检测到 Double Commander 正在运行”

请**完全退出** DC，包括：

- 主窗口
- 托盘图标（如果有）
- 其它工作区/虚拟桌面里的 DC 窗口

检查是否还有进程：

```bash
pgrep -a doublecmd
```

如果确实需要强制结束（**先保存工作**）：

```bash
pkill -TERM doublecmd
```

然后再运行 `dcmd-hl install`。

### Q2：提示“未能自动找到 Double Commander 配置目录”

手动指定即可：

```bash
# 普通安装版
dcmd-hl install -c "$HOME/.config/doublecmd"

# 便携版：给程序目录（含 doublecmd 可执行文件）
dcmd-hl install "$HOME/Applications/doublecmd"

# 便携版：给 settings 目录
dcmd-hl install -c "$HOME/Applications/doublecmd/settings"

# 直接给可执行文件
dcmd-hl install --exe "$HOME/Applications/doublecmd/doublecmd"
```

Flatpak 用户：

```bash
ls ~/.var/app/*/config/doublecmd
dcmd-hl install -c "$HOME/.var/app/<AppID>/config/doublecmd"
```

### Q3：`No module named tkinter` / 图形界面打不开

安装 tkinter：

```bash
# Ubuntu / Debian
sudo apt install python3-tk

# Fedora / RHEL
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk

# openSUSE
sudo zypper install python3-tk
```

验证：

```bash
python3 -m tkinter
```

能弹出一个测试窗口就说明安装成功。此时命令行功能一直可用，不受影响。

### Q4：Wayland 桌面下 GUI 空白/无法启动

Tk 通过 XWayland 运行。可以尝试：

```bash
GDK_BACKEND=x11 dcmd-hl-gui
```

如果仍然不行，请用命令行 `dcmd-hl install`；或者切换到 X11 会话后再打开 GUI。

### Q5：安装成功，但文件名没有变色

按顺序检查：

1. **是否重启了 DC？** 颜色规则在 DC 启动/刷新面板时读取。
2. **DC 版本与存储模式是否匹配？**
   ```bash
   dcmd-hl status
   ```
   DC 1.1.x / 1.2.x 应该使用 `colors.json`；DC 1.0.x 使用 `doublecmd.xml`。
3. **规则是否被其它规则抢先匹配？** DC 按列表顺序匹配，第一条命中生效。可以加 `--prepend` 把本工具规则放到最前面：
   ```bash
   dcmd-hl install --prepend
   ```
4. **是否只安装了部分分类？** 检查 `dcmd-hl status` 中的规则数量。
5. **是否在 DC 运行时安装？** 如果用了 `--force`，DC 退出时可能覆盖；请退出 DC 后重新安装。

### Q6：权限错误 / `Permission denied`

不要用 `sudo` 运行本工具。DC 配置属于当前用户：

```bash
ls -ld "$HOME/.config/doublecmd"
ls -l "$HOME/.config/doublecmd/colors.json"
```

如果文件属主不对（例如曾经用 sudo 运行过），修正：

```bash
sudo chown -R "$USER":"$USER" "$HOME/.config/doublecmd"
```

### Q7：如何备份和还原？

工具每次写入前都会自动备份，文件名类似：

```text
colors.json.fth-backup-20261109-120000
```

查看和还原：

```bash
dcmd-hl backups
dcmd-hl restore colors.json.fth-backup-20261109-120000
```

还原前也会先备份当前文件，所以可以反复操作。

### Q8：会不会覆盖我自己在 DC 里加的规则？

不会。工具只更新/删除**同名**的 14 个分类，其它用户自建规则原样保留。安装时会提示“保留用户规则 N 条”。

### Q9：如何彻底卸载？

```bash
# 1. 移除 DC 中的颜色规则
dcmd-hl uninstall

# 2. 移除程序文件（tar.gz 安装方式）
bash install.sh --uninstall

# 如果连安装记录/状态也想清理
bash install.sh --uninstall --purge
```

`.deb` / `.rpm` 用户：

```bash
dcmd-hl uninstall
sudo apt remove dcmd-filetypes-highlight     # Debian/Ubuntu
sudo dnf remove dcmd-filetypes-highlight     # Fedora/RHEL
```

### Q10：支持 ARM / 32 位 Linux 吗？

支持。Linux 包是 Python 源码，`deb` 标记为 `all`、`rpm` 标记为 `noarch`，与 CPU 架构无关；只要系统有 Python 3.8+ 即可。GUI 需要对应架构的 tkinter。

### Q11：DC 1.2.x 能用吗？

可以。DC 1.1 起颜色规则就保存在 `colors.json`，1.2.x 继续使用该格式。工具会自动识别。

### Q12：Flatpak / Snap 版 DC 能用吗？

可以，但配置目录与系统包不同。先找到配置目录：

```bash
# Flatpak（把 <AppID> 换成实际的 DC AppID）
ls ~/.var/app/*/config/doublecmd

# Snap
ls ~/snap/*/current/.config/doublecmd
```

然后：

```bash
dcmd-hl install -c "/home/you/.var/app/<AppID>/config/doublecmd"
```

如果 DC 正在运行，工具仍会拒绝写入；请先退出 Flatpak/Snap 版 DC。

---

## 12. 文件位置与卸载对照表

### tar.gz / 一键脚本安装

| 内容 | 路径 |
| --- | --- |
| 程序 | `~/.local/share/dcmd-filetypes-highlight/` |
| 命令 | `~/.local/bin/dcmd-hl`、`~/.local/bin/dcmd-hl-gui` |
| 桌面菜单 | `~/.local/share/applications/dcmd-filetypes-highlight.desktop` |
| 图标 | `~/.local/share/icons/hicolor/scalable/apps/dcmd-filetypes-highlight.svg` |
| 状态/安装记录 | 用户级安装：程序目录下 `installed.json`；系统级包：`~/.local/state/dcmd-filetypes-highlight/`（不会写进 `/usr/lib`） |
| DC 配置 | `~/.config/doublecmd/colors.json`（1.1+）或 `doublecmd.xml`（1.0.x） |
| DC 配置备份 | 同目录，`*.fth-backup-*` |

### .deb / .rpm 安装

| 内容 | 路径 |
| --- | --- |
| 程序 | `/usr/lib/dcmd-filetypes-highlight/` |
| 命令 | `/usr/bin/dcmd-hl`、`/usr/bin/dcmd-hl-gui` |
| 桌面菜单 | `/usr/share/applications/dcmd-filetypes-highlight.desktop` |
| 图标 | `/usr/share/icons/hicolor/scalable/apps/dcmd-filetypes-highlight.svg` |
| 文档 | `/usr/share/doc/dcmd-filetypes-highlight/` |

---

## 13. 安全说明

- 安装包只包含 Python 源码、规则 JSON、文档和图标；没有二进制可执行文件、没有联网上报、没有遥测。
- 一键脚本从 GitHub Release 下载，并用 `SHA256SUMS` 校验；你也可以手动下载后核对哈希。
- 工具只写 DC 的配置文件（`colors.json` / `doublecmd.xml`），不改 DC 程序、不写系统目录。
- 每次写入前自动备份；卸载时只移除本工具写入的同名规则，保留你的其它规则。

---

## 14. 从源码运行（开发者）

```bash
git clone https://github.com/BGGeorge/doublecmd-filetypes-highlight.git
cd doublecmd-filetypes-highlight

python3 src/dcmd_hl.py detect
python3 src/dcmd_hl.py install
python3 src/dcmd_hl.py status

# 图形界面
python3 src/dcmd_hl_gui.py

# 交互式菜单
bash src/dcmd_hl_cli.sh
```

依赖：Python 3.8+；GUI 需要 tkinter（`python3-tk` / `python3-tkinter`）。

---

## 15. 获取帮助

如果遇到问题，请在 GitHub Issues 中反馈，并附上：

```bash
dcmd-hl --version
dcmd-hl detect
cat /etc/os-release
doublecmd --version
```

以及完整报错信息。这样能最快定位问题。

项目地址：

<https://github.com/BGGeorge/doublecmd-filetypes-highlight>
