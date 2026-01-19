# Visual Sitemap Generator — Windows Runbook (Local Verification)
**Generated:** 2026-01-09  
**Scope:** Start the local app, confirm HTTP reachability, verify Jobs API endpoint, and capture reproducible logs (`result.txt`).  
**Audience:** Developers/operators running the project on Windows (PowerShell).

---

## 0) What “PASS” means (minimum bar)
You are in a **PASS** state when **all** are true:

1. Uvicorn shows: `Application startup complete.`
2. `Invoke-WebRequest http://127.0.0.1:8000` returns **StatusCode 200**
3. `verify_jobs_endpoint.py` returns:
   - `Status Code: 200`
   - `Success! Jobs found: <N>`

---

## 1) Recommended working directory (avoid OneDrive surprises)
For verification and logs, use a OneDrive-free working directory:

- `C:\temp\verify_run`

Rationale: OneDrive sync can introduce latency/locking that complicates output files and logs.

---

## 2) Prerequisites checklist
### 2.1 Python
You should have at least one of:
- `py -3` (Python Launcher for Windows), or
- `python`

Confirm:
```powershell
py -3 --version
python --version
```

### 2.2 Uvicorn (and project deps)
From the project root (where `app\main.py` exists):
```powershell
py -3 -m pip show uvicorn
```
If missing, install per your project’s dependency management (pip/uv/poetry).

---

## 3) Open “another PowerShell” (second terminal)
Keep Uvicorn running in one PowerShell window, and run checks in another window.

Ways to open a second window:
- Start menu → type `powershell` → Enter
- `Win + R` → `powershell` → Enter
- From an existing PowerShell: `start powershell`

---

## 4) Quick Start (copy/paste)
### 4.1 Terminal A: Start the app (from project root)
1) Move to the project root (must contain `app\main.py`):
```powershell
cd C:\path\to\your\project
```

2) Start Uvicorn:
```powershell
py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Leave Terminal A running.

### 4.2 Terminal B: Verify HTTP and Jobs API
1) Confirm the dashboard responds:
```powershell
Invoke-WebRequest http://127.0.0.1:8000 -UseBasicParsing
```

2) Run jobs endpoint verification and write a persistent log:
```powershell
cd C:\temp\verify_run
py -3 .\verify_jobs_endpoint.py > result.txt 2>&1
Get-Content .\result.txt -TotalCount 200
```

If you see:
- `Status Code: 200`
- `Success! Jobs found: 1` (or more)

…you are **PASS**.

---

## 5) If verification scripts are in a ZIP (extract cleanly)
If you have a backup ZIP (example):
- `sitemap_pro_backup_YYYYMMDD_HHMMSS.zip`

### 5.1 Extract to working directory
```powershell
$ErrorActionPreference = "Continue"

$srcZip = "C:\Users\raiko\OneDrive\Desktop\26\sitemap_pro_backup_20260106_191023.zip"
$work   = "C:\temp\verify_run"

New-Item -ItemType Directory -Force $work | Out-Null
Copy-Item $srcZip $work -Force
Set-Location $work

$zipPath = Join-Path $work (Split-Path $srcZip -Leaf)
Expand-Archive -Path $zipPath -DestinationPath $work -Force

# Confirm required files exist somewhere under the directory
Get-ChildItem -Recurse -File -Filter "verify_setup.py" | Select-Object -First 5 FullName
Get-ChildItem -Recurse -File -Filter "verify_jobs_endpoint.py" | Select-Object -First 5 FullName
```

### 5.2 Run `verify_setup.py` and capture output
This writes logs to `result.txt` reliably:
```powershell
$script = (Get-ChildItem -Recurse -File -Filter "verify_setup.py" | Select-Object -First 1).FullName
cmd /c "py -3 ""$script"" > result.txt 2>&1"
Get-Content .\result.txt -TotalCount 200
```

---

## 6) Common issues and fastest fixes
### 6.1 `result.txt` does not exist
**Cause:** The command never wrote it (or you ran from a different folder).

**Fix:** Always redirect stdout+stderr:
```powershell
py -3 .\verify_jobs_endpoint.py > result.txt 2>&1
```

### 6.2 `AmpersandNotAllowed` in PowerShell
**Cause:** Using `&` inside a quoted `cmd /c` line or in a context PowerShell parses as an operator.

**Fix:** Do not use `&` at all. Use `$LASTEXITCODE` after the command:
```powershell
cmd /c "py -3 ""$script"" > result.txt 2>&1"
$LASTEXITCODE
```

### 6.3 `python: can't open file ... No such file or directory`
**Cause:** You are not in the folder containing the script, or the script was never extracted from ZIP.

**Fix:** Locate and execute using a full path:
```powershell
$script = (Get-ChildItem -Recurse -File -Filter "verify_jobs_endpoint.py" | Select-Object -First 1).FullName
py -3 "$script" > result.txt 2>&1
```

### 6.4 Uvicorn running but checks fail (connection refused)
**Cause:** Wrong port/host, or server is not actually bound.

**Fix:** Confirm port:
```powershell
netstat -ano | findstr :8000
```
Also confirm Uvicorn’s “running on …” line and match the port.

### 6.5 HTTP 200 on `/` but Jobs verification fails (404 / 401 / 500)
**Interpretation:**
- **404:** wrong endpoint path in `verify_jobs_endpoint.py`
- **401/403:** missing auth (API key / session)
- **500:** server exception; check Terminal A logs (stack trace)

**Next step:** Open docs if available:
```powershell
Start-Process http://127.0.0.1:8000/docs
```

---

## 7) Hardening recommendations (prevents recurrence)
### 7.1 Make verification output deterministic
Modify verification scripts to always produce a machine-readable summary:
- Write `result.txt` in `finally:` even on exceptions (PASS/FAIL, reason).
- Include exit code and target URL used.

### 7.2 Add a single entrypoint script
Add `verify.ps1` that:
1) Confirms Python and deps
2) Confirms server reachability
3) Runs endpoint checks
4) Writes `result.txt` + `debug.log`

### 7.3 Keep run artifacts out of synced folders
Store:
- logs
- screenshots
- sitemaps
- reports  
under `C:\temp\...` or a project-local `./artifacts/` folder that is not OneDrive-synced.

---

## 8) Stop/Restart
- Stop server: focus Terminal A and press `Ctrl + C`
- Restart: re-run the Uvicorn command in Terminal A

“P-004: PASS（15/20）— re.search / threshold=0.75 / header filter relaxed”

cd C:\temp\verify_run; py -3 C:\Users\raiko\OneDrive\Desktop\26\OCR\verify_propagation_page4.py 2>&1 | Out-File -FilePath result.txt -Encoding utf8


Expected: "Propagation Results: 15 items found." + "PASS: Found significant number of aligned regions."