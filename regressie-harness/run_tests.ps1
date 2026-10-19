# Portable runner. UnitOnly needs only requirements-test.txt; model runs are explicit.
[CmdletBinding()]
param(
    [string]$Repo = $env:ANONYMIZER_REPO,
    [string]$Model = $env:GLINER_MODEL_PATH,
    [string]$HfCache = $env:HF_HUB_CACHE,
    [string]$Python = "python",
    [switch]$UnitOnly,
    [switch]$WithModel
)
$ErrorActionPreference = "Stop"
if ($UnitOnly -and $WithModel) { throw "UnitOnly and WithModel are mutually exclusive." }
Push-Location $PSScriptRoot
try {
    if ($Repo) { $env:ANONYMIZER_REPO = $Repo }
    if ($WithModel) {
        if (-not $Model) { throw "WithModel requires Model or GLINER_MODEL_PATH." }
        $env:GLINER_MODEL_PATH = $Model
        if ($HfCache) { $env:HF_HUB_CACHE = $HfCache }
        $env:HF_HUB_OFFLINE = "1"
        $env:TRANSFORMERS_OFFLINE = "1"
    }
    if ($env:SNAPSHOT_UPDATE) { throw "Unset SNAPSHOT_UPDATE before running regression checks." }
    $pytestArgs = @("-m", "pytest", "-ra")
    if ($UnitOnly) { $pytestArgs += "--unit-only" }
    else { $pytestArgs += "--require-full-suite" }
    & $Python @pytestArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not $UnitOnly) {
        if (-not (Test-Path "baseline-v2.json")) { throw "baseline-v2.json is missing; automatic baseline updates are disabled." }
        $scoreArgs = @("scorecard.py", "--gate", "baseline-v2.json")
        if ($WithModel) { $scoreArgs += @("--full", "--strict-ner") }
        & $Python @scoreArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host "Checks completed. See KNOWN_FAILURES.md: a green run includes known failures and limited test coverage."
} finally {
    Pop-Location
}
