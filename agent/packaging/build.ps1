<#
.SYNOPSIS
  Compila el agente a un ejecutable único para Windows (agent/dist/firmadoc-agent.exe).
.DESCRIPTION
  Requiere `pip install -e "agent[build]"`. No necesita privilegios de administrador.
  El ejecutable es de 32 o 64 bits según el Python que lo compile: debe coincidir con la
  arquitectura de la biblioteca PKCS#11 del fabricante del token.
#>
$ErrorActionPreference = "Stop"
$agent = Split-Path -Parent $PSScriptRoot
Push-Location $agent
try {
    python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller no está instalado: pip install -e `"agent[build]`"" }

    python -m PyInstaller `
        --noconfirm --clean --onefile --noconsole `
        --name firmadoc-agent `
        --paths src `
        --collect-submodules pkcs11 `
        --hidden-import firmadoc_agent.ui_tk `
        --distpath dist --workpath build/pyinstaller --specpath build `
        packaging/entry.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falló (código $LASTEXITCODE)" }

    $exe = Join-Path $agent "dist/firmadoc-agent.exe"
    if (-not (Test-Path $exe)) { throw "no se generó $exe" }
    $bits = if ([Environment]::Is64BitOperatingSystem -and (python -c "import struct;print(struct.calcsize('P')*8)") -eq "64") { "64" } else { "32" }
    Write-Host "OK: $exe ($bits bits, $([math]::Round((Get-Item $exe).Length / 1MB, 1)) MB)"
}
finally {
    Pop-Location
}
