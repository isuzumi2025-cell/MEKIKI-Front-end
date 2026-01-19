$ErrorActionPreference = "Stop"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
chcp 65001 | Out-Null

$root   = "C:\Users\raiko\OneDrive\Desktop\26\OCR"
$verify = Join-Path $root "verify"

function RunPyToFile([string]$scriptPath, [string]$outFile) {
    cmd /c "py -3 ""$scriptPath"" > ""$outFile"" 2>&1" | Out-Null
    return $LASTEXITCODE
}
function MustHave([string]$path, [string]$pattern, [string]$msg) {
    if (-not (Test-Path $path)) { throw "Missing file: $path" }
    if (-not (Select-String -Path $path -Pattern $pattern -SimpleMatch -Quiet)) { throw $msg }
}
function MustNotHave([string]$path, [string]$pattern, [string]$msg) {
    if (Select-String -Path $path -Pattern $pattern -Quiet) { throw $msg }
}

try {
    Write-Host "== Quality Gate: Operational (run_verify_all.ps1) =="
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $verify "run_verify_all.ps1") | Out-Null

    $setup = Join-Path $verify "result_setup.txt"
    $jobs  = Join-Path $verify "result_jobs.txt"
    $p004  = Join-Path $verify "result_p004.txt"

    MustNotHave $setup "Traceback|ImportError|ModuleNotFoundError|Exception" "Operational FAIL: Setup has error. See: $setup"
    MustHave    $jobs  "Status Code: 200" "Operational FAIL: Jobs not 200. See: $jobs"
    MustHave    $jobs  "Success! Jobs found:" "Operational FAIL: Jobs success missing. See: $jobs"
    MustHave    $p004  "PASS:" "Operational FAIL: P-004 PASS missing. See: $p004"
    MustNotHave $p004  "FAIL:" "Operational FAIL: P-004 has FAIL. See: $p004"
    MustNotHave $p004  "Traceback|ImportError|ModuleNotFoundError|Exception" "Operational FAIL: P-004 has error. See: $p004"

    Write-Host "== Quality Gate: Golden P-004 (reproducible) =="
    $env:PYTHONPATH = $root
    $g004    = Join-Path $verify "golden\p004_case01"
    $act004  = Join-Path $g004 "actual_result_p004.txt"
    $code    = RunPyToFile (Join-Path $g004 "verify_propagation_page4.py") $act004
    if ($code -ne 0) { throw "Golden FAIL: P-004 exit=$code. See: $act004" }
    MustHave    $act004 "PASS:" "Golden FAIL: P-004 PASS missing. See: $act004"
    MustNotHave $act004 "FAIL:" "Golden FAIL: P-004 has FAIL. See: $act004"
    MustNotHave $act004 "Traceback|ImportError|ModuleNotFoundError|Exception" "Golden FAIL: P-004 has error. See: $act004"

    Write-Host "== Quality Gate: Golden P-001 (smoke) =="
    $g001   = Join-Path $verify "golden\p001_case01"
    $act001 = Join-Path $g001 "actual_result_p001.txt"
    $code   = RunPyToFile (Join-Path $g001 "verify_smoke_p001.py") $act001
    if ($code -ne 0) { throw "Golden FAIL: P-001 exit=$code. See: $act001" }
    MustHave    $act001 "PASS: P-001 smoke check" "Golden FAIL: P-001 PASS missing. See: $act001"
    MustNotHave $act001 "FAIL:" "Golden FAIL: P-001 has FAIL. See: $act001"
    MustNotHave $act001 "Traceback|ImportError|ModuleNotFoundError|Exception" "Golden FAIL: P-001 has error. See: $act001"

    Write-Host "QUALITY GATE PASS (Operational + Golden P-004 + Golden P-001)."
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
