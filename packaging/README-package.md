# Double Commander 文件类型高亮 · 一键安装包

让 Double Commander（双击指挥官）**文件面板里的文件名按类型着色** —— 压缩包蓝色、图片品红、代码靛蓝、音频橙色……效果与 Total Commander 的“按类型着色”修改版一致，也是 DC 官方设置「选项 → 颜色 → 文件类型颜色」的原生效果。

![图形界面](docs/gui.png)

* **14 个分类 / 2600+ 条掩码**：压缩包、镜像、可执行、脚本、源代码、文档、表格、音视频、图片、字体、配置数据、临时文件、其他，浅色 + 深色两套配色
* **免安装 Python**：`install.cmd` 一键写入 DC 配置，开箱即用（exe 已内置运行时）
* **便携版 / 安装版**都支持：装错位置或找不到目录时，可把 DC 程序文件夹 / `settings` 文件夹 / `doublecmd.exe` **拖进窗口**，或弹出文件夹选择框
* **自动备份**：改动前自动备份 DC 配置文件，可一键卸载 / 还原，不影响你自己的其它规则
* 附带**图形界面**（改颜色、调顺序、启停分类）与**命令行**（含“扩展名扫描查漏补缺”），全部中文
* 兼容 **Windows 7 SP1 / 8 / 8.1 / 10 / 11**（`win64` 包用于 64 位系统，`win32` 包用于 32 位系统）；兼容 **DC 1.1.x**（`colors.json`）与 **DC 1.0.x**（`doublecmd.xml`）

> 本工具包的位数与你的 Double Commander 位数**无关**（32/64 位 DC 都可用），只看你的 Windows 是 32 还是 64 位。
> 若不慎下错包：`install.cmd` 会在 32 位系统上明确提示改用 `win32` 包（win32 包在 64 位系统上可正常使用）。

> 说明：DC 的 5 类插件（WCX/WDX/WFX/WLX/DSX）都没有“给面板文件名重新着色”的接口，所以本包采用与 DC 设置对话框完全相同的机制——把“文件类型颜色”规则写进 DC 自己的配置文件。不改 DC 一行源码，安装后照样能在 DC 选项里手工微调。

---

## 一、一键安装（推荐）

1. **解压**整个文件夹到任意位置（不要直接在压缩包里双击运行，也不要放在只读目录）。
2. **完全退出 Double Commander**（DC 退出时会把设置写回配置文件；运行中修改会被覆盖）。
3. 双击 **`install.cmd`**，按屏幕提示操作，看到 `[DONE]` 即安装成功。
4. 启动 Double Commander —— 文件面板里的文件名就会按类型着色。

`install.cmd` 会自动探测 DC 配置目录（运行中的 DC 进程 → 解压目录附近 → 常见安装位置 → `%APPDATA%`），并在安装前显示结果请你确认：

* **回车**：使用探测到的目录直接安装；
* **拖拽**：把 DC 的**程序文件夹**（含 `doublecmd.exe`）、**`settings` 文件夹**或 **`doublecmd.exe`** 从资源管理器拖进本窗口，回车即用该目录；
* **直接回车**（探测不到时）：弹出**文件夹选择框**。

便携版用户推荐直接用第二种方式（拖程序文件夹），工具会自动使用 `<程序目录>\settings`。

也可以带参数运行（路径换成你自己的）：

```bat
install.cmd "D:\Tools\doublecmd"                              :: 便携版：程序文件夹
install.cmd -c "D:\Tools\doublecmd\settings"                  :: 便携版：配置目录（含 doublecmd.inf / colors.json）
install.cmd -c "C:\Users\你的用户名\AppData\Roaming\doublecmd" :: 安装版
install.cmd --only archives,images                            :: 只装部分分类
```

命令行工具同样支持直接给路径（程序文件夹 / `settings` / `doublecmd.exe` 都能识别）：

```bat
dcmd_hl_cli.exe install "D:\Tools\doublecmd"
dcmd_hl_cli.exe install --exe "D:\Tools\doublecmd\doublecmd.exe"
```

> 提示：配置目录的判别标志是里面有 `doublecmd.inf`（便携模式标记，便携包自带）或 `colors.json`（DC 1.1.x）/ `doublecmd.xml`（DC 1.0.x）。
> **便携版从未启动过 DC 也能安装**；装完启动 DC 即可看到颜色。
> 也可以在运行 DC 的状态下先让工具自动探测（工具会从进程里找到 DC 位置），再按提示关闭 DC 后重试。

## 二、图形界面（可选）

双击 **`dcmd_hl_gui.exe`** 打开管理器：

* 左侧列表：勾选/取消分类（颜色即时预览）；上移/下移调整匹配优先级（列表从上到下即优先级）
* 右侧编辑：分类名称、掩码（如 `*.psd;*.ai`）、浅色/深色主题颜色、示例文件名
* **安装 / 更新到 Double Commander**：写入 DC 配置（自动备份）
* **保存规则文件**：把改动写回 `rules\default_rules.json`
* **卸载本工具的规则** / **生成 HTML 预览**（浅色 + 深色对照）

顶部“配置目录”通常会自动填好；留空时点“自动检测”，或手工浏览选择。

## 三、命令行（可选）

```bat
dcmd_hl_cli.exe --help              :: 全部命令
dcmd_hl_cli.exe detect              :: 探测 DC 配置目录（打印探测来源）
dcmd_hl_cli.exe install --dry-run   :: 试跑，只显示将要做什么
dcmd_hl_cli.exe install             :: 写入 DC 配置（自动备份）
dcmd_hl_cli.exe status              :: 查看当前安装状态
dcmd_hl_cli.exe install --only archives,images,audio   :: 只装部分分类（可用中文名）
dcmd_hl_cli.exe install --except temp,fonts            :: 排除部分分类
dcmd_hl_cli.exe uninstall           :: 移除本工具写入的规则
dcmd_hl_cli.exe backups             :: 列出备份    restore <备份> -y  还原
dcmd_hl_cli.exe preview --open      :: 生成预览页并打开
dcmd_hl_cli.exe menu                :: 交互式中文菜单（不知道用哪个就选它）

:: 扫描磁盘上的真实扩展名，自动归类补全规则（认不出的进“其他·待归类”，保证全覆盖）
dcmd_hl_cli.exe scan D:\工作 E:\下载 --top 300
dcmd_hl_cli.exe scan D:\工作 --apply --install
```

### 一键安装脚本可带参数

`install.cmd` 支持把参数原样传给工具，例如：

```bat
install.cmd "D:\Tools\doublecmd"              :: 位置参数：程序文件夹 / settings / doublecmd.exe
install.cmd -c "D:\Tools\doublecmd\settings"
install.cmd --only archives,images
```

## 四、卸载与还原

```bat
dcmd_hl_cli.exe uninstall                              :: 只删本工具的规则，你的其它规则不受影响
dcmd_hl_cli.exe backups                                :: 列出所有备份
dcmd_hl_cli.exe restore colors.json.fth-backup-20261018-132204 -y   :: 整文件还原
```

* 每次写入前自动备份：`<原文件>.fth-backup-<时间戳>`（就在配置目录里）
* 安装记录：`installed.json`（记录每个配置目录装了哪些规则；程序目录只读时会自动改存 `%LOCALAPPDATA%\dcmd-filetypes-highlight`）

## 五、兼容性

| 项目 | 支持范围 |
| --- | --- |
| Windows | 7 SP1 / 8 / 8.1 / 10 / 11；`win64` 包用于 **64 位**系统，`win32` 包用于 **32 位**系统（也可用 `python-src\` 里的源码，装 Python 3.8+ 运行） |
| Double Commander | 1.1.x（实测 1.1.32）与 1.0.x；便携版 / 安装版均可；32 / 64 位 DC 均可 |
| 依赖 | 无。`dcmd_hl_cli.exe` / `dcmd_hl_gui.exe` 已内置 Python 3.8 运行时 |

* **Win7**：需已安装 SP1 与常规系统更新（Universal C Runtime）。首次运行若出现“Windows 已保护你的电脑”（SmartScreen），点“更多信息 → 仍要运行”即可；个别杀软可能对单文件 exe 提示，放行即可（源码在 `python-src\`，可自行审查）。
* **没有管理员权限**：需要，也只需要对“DC 配置目录”的写权限。

## 六、常见问题

**装完颜色没变化？**
重启 DC（DC 在启动/退出时读写配置）。若仍无变化：`dcmd_hl_cli.exe detect` 确认探测到的配置目录就是 DC 实际在用的那个（便携版应指向 `<程序目录>\settings`，安装版一般是 `%APPDATA%\doublecmd`）；再确认没有你自己的同名规则挡在前面（本工具默认把规则**追加在列表末尾**，优先级最低，可用 `--prepend` 插到最前）。

**提示“Double Commander 正在运行，拒绝写入”？**
DC 退出时会把内存中的设置写回配置文件，覆盖你的修改。请完全退出 DC（含托盘图标）后再装。确实要强行写入可加 `--force`（不推荐）。

**便携版找不到配置目录？**
双击 `install.cmd`，把 DC 的程序文件夹（或 `settings` 文件夹、`doublecmd.exe`）**拖进窗口**回车即可；也可以直接回车使用弹出的文件夹选择框。便携版配置目录一般是 `<DC 程序目录>\settings`（判断标志：里面有 `doublecmd.inf`，便携包自带该文件——从未启动过 DC 也能安装）。

**控制台中文乱码？**
真实控制台窗口会正常显示；把输出重定向到文件时是 UTF-8 编码，请用支持 UTF-8 的查看器打开。

**会不会弄坏我的 DC 配置？**
每次写入都会自动备份；写入采用“同目录临时文件 + 原子替换”；配置文件按 DC 的宽松 JSON 语法解析，除 `FileColors` 外的所有设置原样保留（已用真实 DC 1.1.32 配置做过往返验证）。

**`.ts` 被当成源代码，我想当视频？**
两种归属都常见。打开 `dcmd_hl_gui.exe`，把 `*.ts` 掩码从“源代码·网页”挪到“视频·字幕”再点“安装 / 更新”即可；或者直接编辑 `rules\default_rules.json`。

**想在 DC 里手工改？**
可以。安装后打开 DC：**配置 → 选项 → 颜色 → 文件类型颜色**，所有规则都在，可继续编辑、增删。改名同一条规则再重新安装会被本工具覆盖，改别的规则则不受影响。

## 七、目录结构

```
dcmd-filetypes-highlight-1.0.1-win64\   （32 位系统会得到 -win32\ 包）
├─ install.cmd               一键安装（双击即用；可带参数、支持拖拽 DC 文件夹定位）
├─ pick-folder.ps1           文件夹选择对话框（install.cmd 在探测不到时调用）
├─ arch.txt                  包位数标记（win64 / win32；装错包时 install.cmd 会提示）
├─ dcmd_hl_cli.exe           命令行工具（含中文交互菜单、扩展名扫描）
├─ dcmd_hl_gui.exe           图形界面
├─ rules\
│  └─ default_rules.json     规则包（14 分类 / 2600+ 条掩码，可编辑、可被 scan 扩充）
├─ docs\
│  ├─ gui.png                界面截图
│  └─ 技术文档.md            原理、源码依据、规则格式等完整文档
├─ python-src\               同功能的 Python 源码（有 Python 3.8+ 可直接用）
│  ├─ dcmd_hl.py
│  ├─ dcmd_hl_gui.py
│  ├─ dcmd_hl_cli.cmd
│  └─ dcmd_hl_gui.cmd
└─ README.md                 本文件
```

## 八、安全与隐私

* 工具**只写 DC 配置文件**（`colors.json` / `doublecmd.xml`，写入前自动备份），不写注册表、不联网。
* `scan` 只统计文件名与扩展名（不读文件内容）；个别无法从扩展名判断的格式会抽样读取文件头几十字节用于识别类型，全程本地执行。

---

更多技术细节（原理、源码依据、规则文件格式、分类颜色表）见 `docs\技术文档.md`。
