param(
    [switch]$NoReset,
    [ValidateSet('lite','small','medium','large')]
    [string]$Size = 'lite'
)

Write-Host "This script will reset (unless --NoReset) and seed the PostgreSQL database with the '$Size' profile."
$confirm = Read-Host -Prompt "Type YES to continue"
if ($confirm -ne 'YES') {
    Write-Host "Aborted by user." -ForegroundColor Yellow
    exit 1
}

# Try to locate and activate the virtual environment
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path "$root\.." | Select-Object -ExpandProperty Path
$venvPaths = @(
    "$repoRoot\venv\Scripts\Activate.ps1",
    "$repoRoot\.venv\Scripts\Activate.ps1",
    "$repoRoot\env\Scripts\Activate.ps1"
)
$activated = $false
foreach ($p in $venvPaths) {
    if (Test-Path $p) {
        Write-Host "Activating virtualenv at $p"
        & $p
        $activated = $true
        break
    }
}

if (-not $activated) {
    Write-Host "Warning: Could not find a virtualenv activation script. Ensure Python is on PATH." -ForegroundColor Yellow
}

$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python executable not found on PATH. Ensure your venv is activated or python is available." -ForegroundColor Red
    exit 1
}

$seedScript = Join-Path $repoRoot 'scripts\seed_postgres_e2e.py'
if (-not (Test-Path $seedScript)) {
    Write-Host "Seed script not found at: $seedScript" -ForegroundColor Red
    exit 1
}

$cmd = "$python `"$seedScript`" --size $Size"
if ($NoReset) { $cmd += ' --no-reset' }

Write-Host "Running: $cmd"
Invoke-Expression $cmd

if ($LASTEXITCODE -ne 0) {
    Write-Host "Seeding failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Seeding completed successfully." -ForegroundColor Green
