# install.ps1 - Installer for secret-paste
#
# Copies all .py files to $env:USERPROFILE\bin\secret-paste\ and adds
# PowerShell profile functions (secret-paste, secret-get, secret-list, secret-revoke).
#
# Usage (PowerShell):
#   .\install.ps1                # normal installation
#   .\install.ps1 -SkipSmokeTest # without smoke test

param(
    [switch]$SkipSmokeTest = $false,
    [switch]$SkipClaudeSkill = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = 'Stop'

# --- 0) Platform check ---------------------------------------------------
if (-not $IsWindows -and -not ($env:OS -eq 'Windows_NT')) {
    Write-Host "ERROR: secret-paste is currently Windows-only." -ForegroundColor Red
    Write-Host "Linux/Mac via keyring planned — see ROADMAP.md and POLISH_PROMPT.md." -ForegroundColor Red
    exit 1
}

Write-Host "=== secret-paste installer ===" -ForegroundColor Cyan

# --- 1) Python check -----------------------------------------------------
Write-Host "`n[1/5] Python check..." -ForegroundColor Yellow
$pyVer = $null
try {
    $pyVer = & python --version 2>&1
} catch {
    Write-Host "ERROR: 'python' not in PATH. Install Python 3.10+ from python.org." -ForegroundColor Red
    exit 1
}
Write-Host "  $pyVer"
$verMatch = [regex]::Match($pyVer, 'Python (\d+)\.(\d+)')
if (-not $verMatch.Success) {
    Write-Host "ERROR: Could not parse Python version." -ForegroundColor Red
    exit 1
}
$major = [int]$verMatch.Groups[1].Value
$minor = [int]$verMatch.Groups[2].Value
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Host "ERROR: Python 3.10+ required, found $pyVer." -ForegroundColor Red
    exit 1
}

# --- 2) tkinter + pywin32 ------------------------------------------------
Write-Host "`n[2/5] Checking tkinter + pywin32..." -ForegroundColor Yellow
$tkProbe = & python -c "import tkinter; print('tk-ok')" 2>&1
if ($tkProbe -notmatch 'tk-ok') {
    Write-Host "ERROR: tkinter not available. Re-run the python.org installer with 'tcl/tk and IDLE' enabled." -ForegroundColor Red
    Write-Host "  Output: $tkProbe" -ForegroundColor Red
    exit 1
}
Write-Host "  tkinter OK"

$pwProbe = & python -c "import win32crypt; print('pywin32-ok')" 2>&1
if ($pwProbe -notmatch 'pywin32-ok') {
    Write-Host "  pywin32 missing -> installing via pip..." -ForegroundColor DarkYellow
    & python -m pip install --user pywin32
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install pywin32 failed." -ForegroundColor Red
        exit 1
    }
    $pwProbe2 = & python -c "import win32crypt; print('pywin32-ok')" 2>&1
    if ($pwProbe2 -notmatch 'pywin32-ok') {
        Write-Host "ERROR: pywin32 still not importable." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  pywin32 OK"

# --- 3) Copy files -------------------------------------------------------
Write-Host "`n[3/5] Installing scripts..." -ForegroundColor Yellow
$srcDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$dstDir = Join-Path $env:USERPROFILE 'bin\secret-paste'
if (-not (Test-Path $dstDir)) {
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
}
$pyFiles = Get-ChildItem -Path $srcDir -Filter '*.py'
foreach ($f in $pyFiles) {
    Copy-Item -Path $f.FullName -Destination $dstDir -Force
    Write-Host "  -> $($f.Name)"
}

# --- 4) Update PowerShell profile ----------------------------------------
Write-Host "`n[4/5] Updating PowerShell profile..." -ForegroundColor Yellow

$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
}
if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Force -Path $profilePath | Out-Null
}

$marker = '# >>> secret-paste >>>'
$endMarker = '# <<< secret-paste <<<'
$block = @"
$marker
function secret-paste  { python "`$env:USERPROFILE\bin\secret-paste\secret_paste_cli.py"  @args }
function secret-get    { python "`$env:USERPROFILE\bin\secret-paste\secret_get_cli.py"    @args }
function secret-list   { python "`$env:USERPROFILE\bin\secret-paste\secret_list_cli.py"   @args }
function secret-revoke { python "`$env:USERPROFILE\bin\secret-paste\secret_revoke_cli.py" @args }
$endMarker
"@

$currentContent = Get-Content -Raw -Path $profilePath -ErrorAction SilentlyContinue
if ($null -eq $currentContent) { $currentContent = '' }
if ($currentContent -match [regex]::Escape($marker)) {
    $pattern = "(?s)" + [regex]::Escape($marker) + ".*?" + [regex]::Escape($endMarker)
    $newContent = [regex]::Replace($currentContent, $pattern, $block)
    Set-Content -Path $profilePath -Value $newContent -Encoding UTF8
    Write-Host "  secret-paste block updated in profile: $profilePath"
} else {
    Add-Content -Path $profilePath -Value "`n$block" -Encoding UTF8
    Write-Host "  secret-paste block appended to profile: $profilePath"
}

# --- 5) Install Claude skill --------------------------------------------
if (-not $SkipClaudeSkill) {
    Write-Host "`n[5/6] Installing Claude-Code skill..." -ForegroundColor Yellow
    $skillSrc = Join-Path $srcDir 'secret_paste_skill\secret-paste.md'
    $skillDir = Join-Path $env:USERPROFILE '.claude\skills'
    if (Test-Path $skillSrc) {
        if (-not (Test-Path $skillDir)) {
            New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
        }
        Copy-Item -Path $skillSrc -Destination $skillDir -Force
        Write-Host "  Skill -> $skillDir\secret-paste.md" -ForegroundColor Green
        Write-Host "  Open a new Claude-Code session so the skill is picked up." -ForegroundColor DarkGray
    } else {
        Write-Host "  Skill source missing ($skillSrc), skipped." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "`n[5/6] Claude skill install skipped (-SkipClaudeSkill)." -ForegroundColor DarkGray
}

# --- 6) Smoke test -------------------------------------------------------
if (-not $SkipSmokeTest) {
    Write-Host "`n[6/6] Smoke test (secret-paste TEST_KEY --ttl=1)..." -ForegroundColor Yellow
    Write-Host "  A GUI dialog will appear. Type a test value + OK." -ForegroundColor Cyan
    Write-Host "  (Or Cancel to skip.)" -ForegroundColor Cyan
    & python (Join-Path $dstDir 'secret_paste_cli.py') 'TEST_KEY' '--ttl=1'
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Smoke test: OK" -ForegroundColor Green
        Write-Host "  Run 'python $dstDir\secret_list_cli.py' to see TEST_KEY (without value)." -ForegroundColor DarkGray
    } else {
        Write-Host "  Smoke test: cancelled (no error)." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "`n[6/6] Smoke test skipped." -ForegroundColor DarkGray
}

Write-Host "`n=== Installation complete ===" -ForegroundColor Green
Write-Host "Open a new PowerShell window (or run '. `$PROFILE'),"
Write-Host "then 'secret-paste', 'secret-get', 'secret-list', 'secret-revoke' are available."
Write-Host "Claude-Code will now auto-use secret-paste when it needs a credential."
