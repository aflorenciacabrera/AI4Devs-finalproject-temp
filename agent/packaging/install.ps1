<#
.SYNOPSIS
  Instala Firmadoc Agent para el usuario actual (sin privilegios de administrador).
.DESCRIPTION
  Copia el ejecutable a %LOCALAPPDATA%\FirmadocAgent, crea la configuracion inicial en
  %APPDATA%\FirmadocAgent\config.json, registra el arranque con la sesion del usuario
  (HKCU\...\Run) y lo inicia.
.EXAMPLE
  .\install.ps1 -Origin https://firmadoc.example.org -Pkcs11Module "C:\Windows\System32\<biblioteca-pkcs11-del-fabricante>.dll"
.NOTES
  Para desplegar por politica de dominio: ejecutar este script como inicio de sesion (GPO) con
  los mismos parametros. Una reinstalacion actualiza el ejecutable y conserva la configuracion
  existente, salvo que se use -Force.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string[]]$Origin,
    [string]$Pkcs11Module,
    [int]$Port = 47123,
    [string]$ExePath,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "FirmadocAgent"),
    [string]$ConfigDir = (Join-Path $env:APPDATA "FirmadocAgent"),
    [string]$RunValueName = "FirmadocAgent",
    [switch]$Force,
    [switch]$NoStart
)
$ErrorActionPreference = "Stop"
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$OriginPattern = '^https?://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?$'

foreach ($o in $Origin) {
    if ($o -notmatch $OriginPattern) {
        throw "Origen invalido: '$o'. Debe ser exacto, con el formato esquema://host[:puerto], sin comodines ni rutas."
    }
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw "Puerto invalido: $Port (debe estar entre 1024 y 65535)." }

if (-not $ExePath) {
    foreach ($candidate in @((Join-Path $PSScriptRoot "firmadoc-agent.exe"), (Join-Path $PSScriptRoot "..\dist\firmadoc-agent.exe"))) {
        if (Test-Path $candidate) { $ExePath = $candidate; break }
    }
}
if (-not $ExePath -or -not (Test-Path $ExePath)) {
    throw "No se encontro firmadoc-agent.exe. Compilelo con agent\packaging\build.ps1 o indique -ExePath."
}
if ($Pkcs11Module -and -not (Test-Path $Pkcs11Module)) {
    Write-Warning "La biblioteca PKCS#11 '$Pkcs11Module' no existe todavia: instale el middleware del fabricante del token."
}

$target = Join-Path $InstallDir "firmadoc-agent.exe"
$configPath = Join-Path $ConfigDir "config.json"

# Si ya hay una instancia en ejecucion desde la ruta de instalacion, detenerla antes de reemplazar el .exe
Get-Process -Name "firmadoc-agent" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $target } | Stop-Process -Force
Start-Sleep -Milliseconds 300

New-Item -ItemType Directory -Force -Path $InstallDir, $ConfigDir | Out-Null
Copy-Item -Force -LiteralPath $ExePath -Destination $target

if ((Test-Path $configPath) -and -not $Force) {
    Write-Host "Se conserva la configuracion existente: $configPath (use -Force para reemplazarla)."
}
else {
    $config = [ordered]@{ port = $Port; allowed_origins = @($Origin); log_level = "INFO" }
    if ($Pkcs11Module) { $config["pkcs11_module"] = $Pkcs11Module }
    $json = $config | ConvertTo-Json -Depth 4
    [System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Configuracion escrita en $configPath"
}

$command = "`"$target`" --config `"$configPath`" run"
New-ItemProperty -Path $RunKey -Name $RunValueName -Value $command -PropertyType String -Force | Out-Null
Write-Host "Arranque automatico registrado ($RunKey\$RunValueName)."

if (-not $NoStart) {
    Start-Process -FilePath $target -ArgumentList @("--config", $configPath, "run") -WindowStyle Hidden
    $listening = $false
    $effectivePort = (Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json).port
    foreach ($i in 1..20) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect("127.0.0.1", $effectivePort)
            $client.Close()
            $listening = $true
            break
        }
        catch { Start-Sleep -Milliseconds 250 }
    }
    if ($listening) { Write-Host "Firmadoc Agent en ejecucion en 127.0.0.1:$effectivePort." }
    else { Write-Warning "El agente no responde en 127.0.0.1:$effectivePort. Revise %LOCALAPPDATA%\FirmadocAgent\agent.log." }
}
Write-Host "Instalacion completa. Diagnostico del token: `"$target`" diagnose"
