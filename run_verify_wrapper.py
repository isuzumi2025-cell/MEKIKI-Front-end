import subprocess
import sys

try:
    # Run the verification script
    result = subprocess.run(
        [sys.executable, "verify_propagation_page4.py"],
        capture_output=True,
        text=True,
        encoding='utf-8'  # Force UTF-8 capture
    )
    
    output = result.stdout + "\n" + result.stderr
    
    status = "FAIL"
    if "PASS: Found significant number" in output:
        status = "PASS"
        
    with open("result.txt", "w", encoding='utf-8') as f:
        f.write(f"{status}\n")
        f.write("=== TELEMETRY ===\n")
        f.write(output)
        
except Exception as e:
    with open("result.txt", "w") as f:
        f.write(f"ERROR: {e}")
