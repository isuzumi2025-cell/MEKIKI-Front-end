# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import traceback
from pathlib import Path
import urllib.request

def ok(msg):   print(f"OK:   {msg}")
def warn(msg): print(f"WARN: {msg}")
def fail(msg): print(f"FAIL: {msg}")

print("System Check...")

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ok(f"Project root = {ROOT}")

# 1) app import (critical)
try:
    import app  # noqa
    ok(f"import app: {getattr(app, '__file__', 'n/a')}")
except Exception as e:
    fail(f"import app failed: {e}")
    traceback.print_exc()
    raise SystemExit(1)

# 2) engine import (non-fatal, and FastEngine is optional)
try:
    import app.core.engine as engine  # noqa
    ok(f"import app.core.engine: {getattr(engine, '__file__', 'n/a')}")
    if hasattr(engine, "FastEngine"):
        ok("FastEngine symbol present.")
    else:
        warn("FastEngine symbol NOT present (this is OK).")
except Exception as e:
    warn(f"import app.core.engine failed (non-fatal): {e}")

# 3) simple network fetch (non-fatal)
try:
    with urllib.request.urlopen("https://example.com", timeout=10) as r:
        status = getattr(r, "status", 200) or 200
    ok(f"HTTP fetch example.com status={status}")
except Exception as e:
    warn(f"HTTP fetch failed (non-fatal): {e}")

ok("Verification Complete. Ready to run `uvicorn app.main:app --reload`")
