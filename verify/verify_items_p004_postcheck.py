from __future__ import annotations
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]      # ...\OCR
VERIFY = ROOT / "verify"
p = VERIFY / "result_p004.txt"

if not p.exists():
    print(f"FAIL: missing {p}")
    sys.exit(2)

text = p.read_text(encoding="utf-8", errors="replace")

# 例外・致命的エラー検出
fatal = re.search(r"Traceback \(most recent call last\):|ModuleNotFoundError|ImportError|Exception:", text)
if fatal:
    print("FAIL: exception detected in result_p004.txt")
    sys.exit(2)

m = re.search(r"Propagation Results:\s*(\d+)\s*items found\.", text)
if not m:
    print("FAIL: cannot find 'Propagation Results: N items found.' in result_p004.txt")
    sys.exit(2)

items_found = int(m.group(1))
has_pass = "PASS: Found significant number of aligned regions." in text
has_fail = "FAIL:" in text

ids = re.findall(r"Matched Original ID:\s*([0-9]+|New/Unknown)", text)
unknown = sum(1 for x in ids if x == "New/Unknown")
numeric = [int(x) for x in ids if x.isdigit()]
c = Counter(numeric)
dups = sorted([k for k,v in c.items() if v > 1])
unique = len(set(numeric))

# ここが「Bの品質ゲート（項目分割）」の閾値です
MIN_ITEMS = 15        # 現在の実績値（15）を最低ラインに固定
MAX_UNKNOWN = 1       # New/Unknown は 1 まで許容

covered = unique + unknown

reasons = []
if not has_pass:
    reasons.append("missing PASS line")
if has_fail:
    reasons.append("FAIL line present")
if items_found < MIN_ITEMS:
    reasons.append(f"items_found {items_found} < {MIN_ITEMS}")
if unknown > MAX_UNKNOWN:
    reasons.append(f"unknown {unknown} > {MAX_UNKNOWN}")
if dups:
    reasons.append(f"duplicate Matched IDs: {dups}")
if covered < MIN_ITEMS:
    reasons.append(f"covered(unique+unknown) {covered} < {MIN_ITEMS}")

if reasons:
    print("FAIL: P-004 item segmentation gate failed")
    for r in reasons:
        print(f" - {r}")
    print(f"summary: items_found={items_found}, unique_matched={unique}, unknown={unknown}, covered={covered}")
    sys.exit(1)

print("PASS: P-004 item segmentation gate ok")
print(f"summary: items_found={items_found}, unique_matched={unique}, unknown={unknown}, covered={covered}")
sys.exit(0)
