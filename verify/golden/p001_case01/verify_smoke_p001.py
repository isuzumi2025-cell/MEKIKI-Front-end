import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMG  = HERE / "page_1.jpg"
JS   = HERE / "project_data.json"

def fail(msg, code=1):
    print(f"FAIL: {msg}")
    raise SystemExit(code)

def main():
    if not IMG.exists(): fail(f"missing image: {IMG}")
    if not JS.exists():  fail(f"missing json: {JS}")

    # image load (Pillow)
    try:
        from PIL import Image
        im = Image.open(IMG); im.load()
        print(f"Image Loaded: {im.size}")
    except Exception as e:
        fail(f"image load failed: {e}")

    # json load (utf-8 fixed)
    try:
        data = json.loads(JS.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"json load failed: {e}")

    clusters = data.get("clusters", [])
    print(f"clusters={len(clusters)}")
    if len(clusters) < 5: fail("too few clusters")

    rect_ok = sum(1 for c in clusters if isinstance(c.get("rect"), list) and len(c["rect"])==4)
    print(f"rect_ok={rect_ok}/{len(clusters)}")
    if rect_ok == 0: fail("no rect found in clusters")

    print("PASS: P-001 smoke check (image+json+rect)")

if __name__ == "__main__":
    main()
