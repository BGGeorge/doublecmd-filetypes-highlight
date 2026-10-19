# Folder picker used by install.cmd when the Double Commander config folder
# could not be auto-detected. Prints the chosen path on stdout.
Add-Type -AssemblyName System.Windows.Forms | Out-Null
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "Select the Double Commander program folder, its 'settings' folder, or the folder containing doublecmd.exe"
$dialog.ShowNewFolderButton = $false
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dialog.SelectedPath
}
