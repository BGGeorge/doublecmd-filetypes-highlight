<#
.SYNOPSIS
    构建 Windows 免 Python 发行包（Win7 兼容组合：Python 3.8 + PyInstaller 4.10）。

.DESCRIPTION
    先用 PyInstaller 构建 dcmd_hl_cli.exe / dcmd_hl_gui.exe（--onefile），
    再组装出与已发布发行包一致的目录结构，并压缩为 zip：

        dcmd-filetypes-highlight-<版本>-<架构>/
        ├─ install.cmd / pick-folder.ps1 / arch.txt
        ├─ dcmd_hl_cli.exe / dcmd_hl_gui.exe / README.md
        ├─ rules/ docs/ python-src/

    架构包分为 win64（64 位 Python）与 win32（32 位 Python）两种，
    请用对应位数的 Python 解释器各构建一次。

.EXAMPLE
    python -m pip install pyinstaller==4.10
    powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python "C:\Python38-x64\python.exe" -Arch win64 -Version 1.0.1
    powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Python "C:\Python38-x86\python.exe" -Arch win32 -Version 1.0.1

.NOTES
    输出目录默认为 <仓库>/_dist/（已在 .gitignore 中忽略）。
#>
param(
    [string]$Python = "python",
    [string]$Version = "1.0.1",
    [ValidateSet("win64", "win32")]
    [string]$Arch = "win64",
    [string]$OutDir = ""
)
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot          # 仓库根目录
if (-not $OutDir) { $OutDir = Join-Path $root "_dist" }
$name = "dcmd-filetypes-highlight-$Version-$Arch"
$pkg = Join-Path $OutDir $name
$work = Join-Path $OutDir "_build\$Arch"

Write-Host "==> 0/4 校验 Python 位数（$Arch）"
$bits = ((& $Python -c "import struct;print(struct.calcsize('P')*8)") | Select-Object -First 1).ToString().Trim()
$want = if ($Arch -eq "win64") { "64" } else { "32" }
if ($bits -ne $want) { throw "解释器位数 $bits 与 -Arch $Arch 不匹配，请使用 $want 位 Python" }
Write-Host "    $Python -> $bits 位，OK"

Write-Host "==> 1/4 构建 exe（PyInstaller --onefile）"
New-Item -ItemType Directory -Force (Join-Path $work "dist"), (Join-Path $work "work"), (Join-Path $work "spec") | Out-Null
& $Python -m PyInstaller --noconfirm --clean --onefile --console --name dcmd_hl_cli --exclude-module tkinter --distpath (Join-Path $work "dist") --workpath (Join-Path $work "work") --specpath (Join-Path $work "spec") (Join-Path $root "src\dcmd_hl.py")
if ($LASTEXITCODE -ne 0) { throw "构建 dcmd_hl_cli.exe 失败" }
& $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name dcmd_hl_gui --distpath (Join-Path $work "dist") --workpath (Join-Path $work "work") --specpath (Join-Path $work "spec") (Join-Path $root "src\dcmd_hl_gui.py")
if ($LASTEXITCODE -ne 0) { throw "构建 dcmd_hl_gui.exe 失败" }

Write-Host "==> 2/4 组装目录 $pkg"
Remove-Item $pkg -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $pkg "rules"), (Join-Path $pkg "docs"), (Join-Path $pkg "python-src") | Out-Null
Copy-Item -Path (Join-Path $work "dist\dcmd_hl_cli.exe"), (Join-Path $work "dist\dcmd_hl_gui.exe") -Destination $pkg
Copy-Item -Path (Join-Path $PSScriptRoot "install.cmd"), (Join-Path $PSScriptRoot "pick-folder.ps1") -Destination $pkg
Copy-Item -Path (Join-Path $PSScriptRoot "README-package.md") -Destination (Join-Path $pkg "README.md")
Copy-Item -Path (Join-Path $root "rules\default_rules.json") -Destination (Join-Path $pkg "rules")
Copy-Item -Path (Join-Path $root "docs\gui.png"), (Join-Path $root "docs\技术文档.md") -Destination (Join-Path $pkg "docs")
Copy-Item -Path (Join-Path $root "src\dcmd_hl.py"), (Join-Path $root "src\dcmd_hl_gui.py"), (Join-Path $root "src\dcmd_hl_cli.cmd"), (Join-Path $root "src\dcmd_hl_gui.cmd") -Destination (Join-Path $pkg "python-src")
Set-Content -Path (Join-Path $pkg "arch.txt") -Value $Arch -Encoding Ascii -NoNewline

# 给包内技术文档加一行“打包版说明”
$tech = Join-Path $pkg "docs\技术文档.md"
$note = "# Double Commander 文件类型高亮（扩展包）`r`n`r`n> 本文件是【打包版】内的技术文档：文中命令以源码写法 ``python dcmd_hl.py ...`` 为例，打包版等价命令为 ``dcmd_hl_cli.exe ...``；文中 `src/` 目录对应包内的 `python-src/`。一键安装请看包根目录的 `README.md`。`r`n"
$txt = [System.IO.File]::ReadAllText($tech)
$txt = $txt -replace "^# Double Commander 文件类型高亮（扩展包）\r?\n", $note
[System.IO.File]::WriteAllText($tech, $txt, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "==> 3/4 打包 zip"
$zip = Join-Path $OutDir "$name.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path $pkg -DestinationPath $zip -CompressionLevel Optimal

Write-Host "==> 4/4 完成"
Get-Item $zip | Select-Object FullName, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 2) } }
