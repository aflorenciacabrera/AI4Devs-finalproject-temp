<#
.SYNOPSIS
  Desinstala Firmadoc Agent del usuario actual (sin privilegios de administrador).
.DESCRIPTION
  Detiene el agente y elimina el ejecutable, el arranque automatico y la configuracion.
  Con -KeepLogs conserva el registro de actividad.
#>
[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FirmadocAgent"),
    [string]$ConfigDir = (Join-Path $env:APPDATA "FirmadocAgent"),
    [string]$RunValueName = "FirmadocAgent",
    [switch]$KeepLogs
)
$ErrorActionPreference = "Stop"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$target = Join-Path $InstallDir "firmadoc-agent.exe"
$logDir = Join-Path $env:LOCALAPPDATA "FirmadocAgent"

Get-Process -Name "firmadoc-agent" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $target } | Stop-Process -Force
Start-Sleep -Milliseconds 500

if (Get-ItemProperty -Path $RunKey -Name $RunValueName -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $RunKey -Name $RunValueName
    Write-Host "Arranque automatico eliminado."
}
if (Test-Path $target) { Remove-Item -Force -LiteralPath $target; Write-Host "Ejecutable eliminado." }
if (Test-Path $ConfigDir) { Remove-Item -Recurse -Force -LiteralPath $ConfigDir; Write-Host "Configuracion eliminada." }

if (-not $KeepLogs -and (Test-Path $logDir)) {
    Get-ChildItem -LiteralPath $logDir -Filter "agent.log*" -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "Registro eliminado."
}
foreach ($dir in @($InstallDir, $logDir)) {
    if ((Test-Path $dir) -and -not (Get-ChildItem -LiteralPath $dir -Force)) { Remove-Item -Force -LiteralPath $dir }
}
Write-Host "Desinstalacion completa."
