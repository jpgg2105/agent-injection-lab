# Runs every attack and clean task against every defence on Gemini's free tier.
# Safe to run again: finished runs are kept and only the rest is retried. If the daily quota
# stops it, run it again after the reset (midnight Pacific: 5 a.m. in Argentina).
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_gemini.ps1             # everything (~1,000 calls)
#   powershell -ExecutionPolicy Bypass -File scripts\run_gemini.ps1 -Limit 6    # a first look
param([int]$Limit = 0)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run($exe, [string[]]$argv) {
    & $exe @argv
    if ($LASTEXITCODE -ne 0) { throw "Failed: $exe $($argv -join ' ')" }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python not found. Install Python 3.11 or newer from python.org (tick 'Add to PATH')." }
if (-not (Test-Path "..\research-agent\pyproject.toml")) { throw "Expected the research-agent repo next to this one (..\research-agent)." }

if (-not (Test-Path ".venv")) { Write-Host "Creating the virtual environment..."; Run python @("-m", "venv", ".venv") }
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path ".venv\.installed")) {
    Write-Host "Installing dependencies..."
    Run $py @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
    Run $py @("-m", "pip", "install", "--quiet", "-e", "..\research-agent[openai]", "-e", ".[dev]")
    Write-Host "Running the tests..."
    Run $py @("-m", "pytest", "-q")
    New-Item ".venv\.installed" -ItemType File | Out-Null
}

if (-not ((Test-Path ".env") -and (Select-String -Path ".env" -Pattern "^GEMINI_API_KEY=." -Quiet))) {
    if (Test-Path "..\agent-benchmark\.env") {
        $line = Select-String -Path "..\agent-benchmark\.env" -Pattern "^GEMINI_API_KEY=." | Select-Object -First 1
        if ($line) { Add-Content ".env" $line.Line; Write-Host "Reusing the Gemini key from agent-benchmark\.env" }
    }
}
if (-not ((Test-Path ".env") -and (Select-String -Path ".env" -Pattern "^GEMINI_API_KEY=." -Quiet))) {
    $key = Read-Host "Paste your Gemini API key (aistudio.google.com/apikey)"
    Add-Content ".env" "GEMINI_API_KEY=$key"
}

$argv = @("-m", "injection_lab.cli", "run")
if ($Limit -gt 0) { $argv += @("--limit", "$Limit") }
Write-Host "Running (it waits between calls to stay under the free quota)..."
Run $py $argv
Write-Host "`nDone for now. When it says 0 to go, send results\runs.jsonl and results\REPORT.md."
