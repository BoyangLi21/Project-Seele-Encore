"""pairs.py out.png name1,name2,... — before|after side by side per name (r2before-/r2after-)."""
import sys
from PIL import Image, ImageDraw
S='E:/eva-map-buildings/client/screenshots/'
out, names = sys.argv[1], sys.argv[2].split(',')
bp = sys.argv[3] if len(sys.argv) > 3 else 'r2before-'
ap = sys.argv[4] if len(sys.argv) > 4 else 'r2after-'
w, h = 480, 270
img = Image.new('RGB', (2 * (w + 8) + 10, len(names) * (h + 16) + 10), 'white'); d = ImageDraw.Draw(img)
for i, n in enumerate(names):
    y = 10 + i * (h + 16)
    for j, p in enumerate((bp, ap)):
        x = 10 + j * (w + 8)
        d.text((x, y), f"{n} {'before' if j == 0 else 'after'}", fill='black')
        try: img.paste(Image.open(S + p + n + '.png').resize((w, h)), (x, y + 13))
        except Exception: pass
img.save(out); print(img.size)
