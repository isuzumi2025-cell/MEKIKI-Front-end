import sys, json, pathlib
from PIL import Image, ImageDraw

root = pathlib.Path(sys.argv[1])
img  = pathlib.Path(sys.argv[2])

d = json.loads((root/"project_data.json").read_text(encoding="utf-8"))
cs = d.get("clusters", [])
miss = {5,6,10,13,19,20}

im = Image.open(img).convert("RGB")
dr = ImageDraw.Draw(im)

for c in cs:
    if c.get("id") in miss:
        x1,y1,x2,y2 = c["rect"]
        dr.rectangle([x1,y1,x2,y2], outline=(255,0,0), width=3)
        dr.text((x1, max(0,y1-14)), f'id={c.get("id")}', fill=(255,0,0))

out = root/"verify"/"debug"/"p004_missing.png"
out.parent.mkdir(parents=True, exist_ok=True)
im.save(out)
print("wrote", out)
