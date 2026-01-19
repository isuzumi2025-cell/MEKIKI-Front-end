import sys
import os
import traceback

sys.path.append(os.getcwd())

try:
    import app.main
    print("Import Successful")
except Exception:
    with open("startup_error.txt", "w", encoding="utf-8") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
