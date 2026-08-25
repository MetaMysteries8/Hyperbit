param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildRoot = Join-Path $Root ".firmware-build"
$Samples = Join-Path $BuildRoot "microbit-v2-samples"
$Firmware = Join-Path $Root "firmware"
$OutHex = Join-Path $Firmware "HyperBit.hex"

function Banner($s) {
    Write-Host ""
    Write-Host "=== $s ===" -ForegroundColor Cyan
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user;$env:Path"
}

function Have($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function WingetInstall($id) {
    Write-Host "Installing $id with winget..."
    & winget install --id $id -e --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed installing $id (exit $LASTEXITCODE)"
    }
}

if (-not $SkipInstall) {
    Banner "Checking build tools"

    if (-not (Have "winget")) {
        throw "winget is required for automatic tool installation. Install/update App Installer from Microsoft, or install Git/CMake/Ninja/GNU Arm Embedded manually."
    }

    if (-not (Have "git"))   { WingetInstall "Git.Git" }
    if (-not (Have "cmake")) { WingetInstall "Kitware.CMake" }
    if (-not (Have "ninja")) { WingetInstall "Ninja-build.Ninja" }
    if (-not (Have "arm-none-eabi-gcc")) { WingetInstall "Arm.GnuArmEmbeddedToolchain" }

    Refresh-Path
}

if (-not (Have "arm-none-eabi-gcc")) {
    $candidates = @(
        "$env:ProgramFiles\Arm GNU Toolchain arm-none-eabi\*\bin",
        "${env:ProgramFiles(x86)}\Arm GNU Toolchain arm-none-eabi\*\bin",
        "$env:LOCALAPPDATA\Programs\Arm GNU Toolchain arm-none-eabi\*\bin"
    )
    foreach ($pattern in $candidates) {
        if (-not $pattern) { continue }
        $dirs = Get-Item $pattern -ErrorAction SilentlyContinue
        foreach ($d in $dirs) {
            if (Test-Path (Join-Path $d.FullName "arm-none-eabi-gcc.exe")) {
                $env:Path = "$($d.FullName);$env:Path"
                break
            }
        }
        if (Have "arm-none-eabi-gcc") { break }
    }
}

foreach ($cmd in @("git", "cmake", "ninja", "arm-none-eabi-gcc")) {
    if (-not (Have $cmd)) {
        throw "$cmd is still missing after setup. Close this window, reopen a terminal, and rerun BUILD_FIRMWARE.bat."
    }
}

$Python = $null
if (Have "py") {
    $Python = @("py", "-3")
} elseif (Have "python3") {
    $Python = @("python3")
} elseif (Have "python") {
    $Python = @("python")
} else {
    throw "Python 3 is required."
}

Banner "Preparing official CODAL build project"
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

if (-not (Test-Path (Join-Path $Samples ".git"))) {
    & git clone --depth 1 https://github.com/lancaster-university/microbit-v2-samples.git $Samples
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
} else {
    Push-Location $Samples
    try {
        & git fetch --depth 1 origin master
        & git reset --hard origin/master
        if ($LASTEXITCODE -ne 0) { throw "git update failed" }
    } finally {
        Pop-Location
    }
}

Banner "Copying HyperBit firmware"
$SampleSource = Join-Path $Samples "source"
Get-ChildItem $SampleSource -File | Remove-Item -Force
Copy-Item (Join-Path $Firmware "source\*") $SampleSource -Force
Copy-Item (Join-Path $Firmware "codal.json") (Join-Path $Samples "codal.json") -Force

Banner "Compiling micro:bit V2 firmware"
Push-Location $Samples
try {
    if ($Python.Count -eq 2) {
        & $Python[0] $Python[1] "build.py"
    } else {
        & $Python[0] "build.py"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "CODAL build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$BuiltHex = Join-Path $Samples "MICROBIT.hex"
if (-not (Test-Path $BuiltHex)) {
    throw "Build finished but MICROBIT.hex was not found."
}

Copy-Item $BuiltHex $OutHex -Force

Banner "SUCCESS"
Write-Host "Real compiled firmware:" -ForegroundColor Green
Write-Host "  $OutHex"
Write-Host ""
Write-Host "Now connect the micro:bit V2 by its OWN USB port and run FLASH_FIRMWARE.bat."
