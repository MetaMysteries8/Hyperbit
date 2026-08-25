$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Release ZIPs place HyperBit.hex at the package root. Development builds may
# place it under firmware\. Accept both layouts.
$Candidates = @(
    (Join-Path $Root "HyperBit.hex"),
    (Join-Path $Root "firmware\HyperBit.hex")
)

$Hex = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Hex) {
    throw "HyperBit.hex was not found. Download/extract the full GitHub release ZIP, or place HyperBit.hex next to FLASH_FIRMWARE.bat."
}

Write-Host "Using firmware: $Hex" -ForegroundColor Cyan

$volumes = Get-Volume -ErrorAction SilentlyContinue | Where-Object {
    $_.FileSystemLabel -eq "MICROBIT" -and $_.DriveLetter
}

if (-not $volumes) {
    # Fallback for systems where Get-Volume is restricted/unavailable.
    $volumes = Get-CimInstance Win32_LogicalDisk -ErrorAction SilentlyContinue | Where-Object {
        $_.VolumeName -eq "MICROBIT" -and $_.DeviceID
    } | ForEach-Object {
        [PSCustomObject]@{ DriveLetter = $_.DeviceID.TrimEnd(':') }
    }
}

if (-not $volumes) {
    throw "No MICROBIT drive found. Plug the micro:bit V2 into the PC using the micro:bit's own USB port and wait for the MICROBIT drive to appear."
}

foreach ($v in $volumes) {
    $dest = "$($v.DriveLetter):\HyperBit.hex"
    Write-Host "Flashing $dest ..." -ForegroundColor Yellow
    Copy-Item $Hex $dest -Force
}

Write-Host ""
Write-Host "Flash copy complete." -ForegroundColor Green
Write-Host "Wait for the micro:bit activity LED to finish, then unplug USB if you want to power it from the Wukong battery."
