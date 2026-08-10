[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$PortableOnly,
    [string]$InnoSetupCompiler = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
$ruff = Join-Path $repoRoot ".venv\Scripts\ruff.exe"

foreach ($required in @($python, $pyinstaller, $ruff)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Missing build dependency: $required. Run 'uv sync' first."
    }
}

Set-Location -LiteralPath $repoRoot

$version = (& $python -c "import pathlib,tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])").Trim()
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Unable to read the project version."
}

$bundleName = "DesktopAgent-$version-win64"
$buildRoot = Join-Path $repoRoot "build\release"
$artifactsRoot = Join-Path $repoRoot "artifacts"
$bundlePath = Join-Path $artifactsRoot $bundleName
$installerPath = Join-Path $artifactsRoot "DesktopAgent-Setup-$version.exe"

if (-not $SkipTests) {
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
    & $ruff check src tests
    if ($LASTEXITCODE -ne 0) { throw "Ruff failed." }
}

foreach ($target in @($buildRoot, $bundlePath)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
if (Test-Path -LiteralPath $installerPath) {
    Remove-Item -LiteralPath $installerPath -Force
}
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $artifactsRoot -Force | Out-Null

$env:DESKTOP_AGENT_BUNDLE_NAME = $bundleName
try {
    & $pyinstaller (Join-Path $repoRoot "installer\desktop-agent.spec") --noconfirm --clean --distpath $artifactsRoot --workpath $buildRoot
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
} finally {
    Remove-Item Env:DESKTOP_AGENT_BUNDLE_NAME -ErrorAction SilentlyContinue
}

if (-not $PortableOnly) {
    $candidates = @(
        $InnoSetupCompiler,
        $env:ISCC_PATH,
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
    $iscc = $candidates | Select-Object -First 1
    if (-not $iscc) {
        throw "Inno Setup 6 compiler not found. Pass -InnoSetupCompiler or set ISCC_PATH."
    }
    $installerDir = Join-Path $repoRoot "installer"
    & $iscc "/DAppVersion=$version" "/DSourceDir=$bundlePath" "/DOutputDir=$artifactsRoot" "/DInstallerDir=$installerDir" (Join-Path $installerDir "desktop-agent.iss")
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }
}

$portableFiles = Get-ChildItem -LiteralPath $bundlePath -File -Recurse
$result = [ordered]@{
    Version = $version
    PortablePath = $bundlePath
    PortableBytes = ($portableFiles | Measure-Object -Property Length -Sum).Sum
}
if (Test-Path -LiteralPath $installerPath) {
    $installer = Get-Item -LiteralPath $installerPath
    $result["InstallerPath"] = $installer.FullName
    $result["InstallerBytes"] = $installer.Length
    $result["InstallerSHA256"] = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash
}
[PSCustomObject]$result | Format-List
