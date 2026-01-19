$ErrorActionPreference = "Stop"
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
chcp 65001 | Out-Null

$root   = "C:\Users\raiko\OneDrive\Desktop\26\OCR"
$verify = Join-Path $root "verify"

Write-Host "== Quality Gate(B): Operational (run_verify_all.ps1) =="
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $verify "run_verify_all.ps1") | Out-Host

# Operationalの結果ファイルに例外がないことを確認
$setup = Join-Path $verify "result_setup.txt"
if (Test-Path $setup) {
    if (Select-String -Path $setup -Pattern "Traceback|ImportError|ModuleNotFoundError|Exception" -Quiet) {
        throw "Operational FAIL: Setup has error. See: $setup"
    }
}

Write-Host "== Quality Gate(B): P-004 item segmentation (postcheck) =="
py -3 (Join-Path $verify "verify_items_p004_postcheck.py") | Out-Host

Write-Host "== Quality Gate(B): Golden P-004 (reproducible) =="
$env:PYTHONPATH = $root
$g004 = Join-Path $verify "golden\p004_case01"
$act004 = Join-Path $g004 "actual_result_p004.txt"
py -3 (Join-Path $g004 "verify_propagation_page4.py") 2>&1 | Out-File -FilePath $act004 -Encoding utf8
if (Select-String -Path $act004 -Pattern "Traceback|ImportError|ModuleNotFoundError|Exception" -Quiet) { throw "Golden P-004 FAIL (exception). See: $act004" }
if (-not (Select-String -Path $act004 -Pattern "PASS:" -SimpleMatch -Quiet)) { throw "Golden P-004 FAIL (no PASS). See: $act004" }
if (Select-String -Path $act004 -Pattern "FAIL:" -SimpleMatch -Quiet) { throw "Golden P-004 FAIL (FAIL present). See: $act004" }

Write-Host "== Quality Gate(B): Golden P-001 (smoke) =="
$g001 = Join-Path $verify "golden\p001_case01"
$act001 = Join-Path $g001 "actual_result_p001.txt"
py -3 (Join-Path $g001 "verify_smoke_p001.py") 2>&1 | Out-File -FilePath $act001 -Encoding utf8
if (Select-String -Path $act001 -Pattern "Traceback|ImportError|ModuleNotFoundError|Exception" -Quiet) { throw "Golden P-001 FAIL (exception). See: $act001" }
if (-not (Select-String -Path $act001 -Pattern "rect_ok=\d+/\d+" -Quiet)) { throw "Golden P-001 FAIL (rect_ok missing). See: $act001" }

Write-Host "QUALITY GATE PASS (B): Operational + P-004 item segmentation + Golden P-004 + Golden P-001."
