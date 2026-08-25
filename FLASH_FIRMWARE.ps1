$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Hex = Join-Path $Root "firmware\HyperBit.hex"

if (-not (Test-Path $Hex)) {
    throw "firmware\HyperBit.hex does not exist yet. Run BUILD_FIRMWARE.bat first."
}

$volumes = Get-Volume -ErrorAction SilentlyContinue | Where-Object {
    $_.FileSystemLabel -eq "MICROBIT" -and $_.DriveLetter
}

if (-not $volumes) {
    throw "No MICROBIT drive found. Plug the micro:bit V2 into the PC using the micro:bit's own USB port."
}

foreach ($v in $volumes) {
    $dest = "$($v.DriveLetter):\HyperBit.hex"
    Write-Host "Flashing $dest ..."
    Copy-Item $Hex $dest -Force
}

Write-Host ""
Write-Host "Flash copy complete. Wait for the MICROBIT activity LED to finish." -ForegroundColor Green
Write-Host "Then you can unplug USB and power it from the Wukong battery."
