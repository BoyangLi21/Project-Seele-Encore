"""sheet.py out.png prefix name1,name2,... [cols]  — contact sheet of screenshots."""
import sys
from PIL import Image, ImageDraw
S='E:/eva-map-buildings/client/screenshots/'
out, pre, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
per = int(sys.argv[4]) if len(sys.argv) > 4 else 3
w, h = 480, 270
rows = (len(names) + per - 1) // per
img = Image.new('RGB', (per * (w + 8) + 10, rows * (h + 16) + 10), 'white'); d = ImageDraw.Draw(img)
for i, n in enumerate(names):
    r, c = divmod(i, per); x = 10 + c * (w + 8); y = 10 + r * (h + 16)
    d.text((x, y), n, fill='black')
    for p in pre.split('|'):
        try:
            img.paste(Image.open(S + p + n + '.png').resize((w, h)), (x, y + 13)); break
        except Exception:
            pass
img.save(out); print(img.size)
