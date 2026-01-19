import re, json, pathlib, math

root = pathlib.Path(r"C:\Users\raiko\OneDrive\Desktop\26\OCR")
proj = root/"project_data.json"
res  = root/"verify"/"result_p004.txt"
out  = root/"verify"/"debug"/"p004_missing_to_detected_report.txt"

miss_ids = {5,6,10,13,19,20}

def area(r):
    x1,y1,x2,y2 = r
    return max(0,x2-x1)*max(0,y2-y1)

def inter(a,b):
    ax1,ay1,ax2,ay2=a; bx1,by1,bx2,by2=b
    x1=max(ax1,bx1); y1=max(ay1,by1); x2=min(ax2,bx2); y2=min(ay2,by2)
    return [x1,y1,x2,y2]

def iou(a,b):
    ia = area(inter(a,b))
    if ia<=0: return 0.0
    return ia / (area(a)+area(b)-ia)

def contain_ratio(inner, outer):
    ia = area(inter(inner, outer))
    if area(inner)<=0: return 0.0
    return ia/area(inner)

d = json.loads(proj.read_text(encoding="utf-8"))
clusters = d.get("clusters", [])
miss = [c for c in clusters if c.get("id") in miss_ids]

det = []
pat = re.compile(r"^\s*-\s*\[(\d+)\]\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]")
for line in res.read_text(encoding="utf-8", errors="ignore").splitlines():
    m = pat.match(line)
    if m:
        idx = int(m.group(1))
        rect = [int(m.group(2)),int(m.group(3)),int(m.group(4)),int(m.group(5))]
        det.append((idx, rect))

lines=[]
lines.append(f"detected_items={len(det)}")
lines.append(f"missing_clusters={len(miss)} (ids={sorted(miss_ids)})")
lines.append("")

for c in miss:
    cid = c.get("id")
    r = c.get("rect")
    txt = (c.get("text") or "").replace("\n"," ")[:120]
    best=None
    for idx, dr in det:
        cr = contain_ratio(r, dr)
        j  = iou(r, dr)
        score = (cr, j)
        if (best is None) or score > best[0]:
            best = (score, idx, dr)
    (cr,j), idx, dr = best
    verdict = "ATTACH_OK" if cr >= 0.80 else ("NEAR" if j>0 else "MISS_OUTSIDE")
    lines.append(f"id={cid} verdict={verdict} contain={cr:.3f} iou={j:.3f} best_detected=[{idx}] rect={r} text='{txt}'")

out.write_text("\n".join(lines), encoding="utf-8")
print("wrote", out)
