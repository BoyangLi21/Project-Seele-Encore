"""Plan views and sections from dogma_survey.py output, for the Central Dogma shaft plan.

  python dogma_views.py <survey.npz> <out dir> [--shaft x0 x1 z0 z1 ytop ybottom] [--mark name x y z ...]

Plans: one image per height band (built blue, open air white, glass cyan, LCL orange, rock grey, ungenerated black),
4 px per block, a 16-block grid with coordinates. Sections: north-south through the shaft centre x, east-west through
its centre z. A proposed shaft is drawn as a red outline.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

COL = {0: (245, 245, 245), 1: (70, 70, 74), 2: (60, 110, 200), 3: (90, 210, 230), 4: (240, 140, 40), 5: (0, 0, 0)}
BANDS = [(-1000, -991, '机库上方'), (-1013, -1001, '机库层 y-1013..-1001'), (-1040, -1014, 'y-1040..-1014'),
         (-1090, -1041, 'y-1090..-1041（含 LCL 长廊）'), (-1150, -1091, 'y-1150..-1091'), (-1195, -1151, 'y-1195..-1151'),
         (-1232, -1196, 'y-1232..-1196（天堂之门、莉莉丝层上半）'), (-1280, -1233, 'y-1280..-1233（莉莉丝层下半）')]
FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)
S = 3


def band_image(cls, origin, y0, y1):
    ox, oy, oz = origin
    a, b = max(0, y0 - oy), min(cls.shape[0], y1 - oy + 1)
    sl = cls[a:b]
    out = np.full(sl.shape[1:] + (3,), COL[1], np.uint8)
    air = (sl == 0).mean(0)
    for v in (5,):
        out[(sl == v).all(0)] = COL[5]
    shade = (70 + air * 175).astype(np.uint8)
    m = air > 0
    out[m] = np.stack([shade[m]] * 3, -1)
    out[(sl == 4).any(0)] = COL[4]
    out[(sl == 3).any(0)] = COL[3]
    out[(sl == 2).any(0)] = COL[2]
    return out                                   # (z, x, 3)


def grid(img, origin, horiz, vert, flip_v=False, vlabel='z'):
    """horiz: world coord of column 0 and step; vert likewise. Draw lines every 16 blocks with labels."""
    d = ImageDraw.Draw(img)
    (h0, hn), (v0, vn) = horiz, vert
    for i in range(hn):
        c = h0 + i
        if c % 32 == 0:
            d.line([(i * S, 0), (i * S, img.height)], fill=(255, 255, 0) if c == 0 else (150, 150, 0), width=1)
            d.text((i * S + 2, 2), str(c), font=FONT, fill=(255, 255, 0))
    for j in range(vn):
        c = v0 + (vn - 1 - j if flip_v else j)
        if c % 32 == 0:
            d.line([(0, j * S), (img.width, j * S)], fill=(150, 150, 0), width=1)
            d.text((2, j * S + 2), f'{vlabel}{c}', font=FONT, fill=(255, 255, 0))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('survey'); ap.add_argument('out')
    ap.add_argument('--shaft', nargs=6, type=int)
    ap.add_argument('--mark', nargs=4, action='append', default=[])
    a = ap.parse_args()
    data = np.load(a.survey)
    cls, origin = data['classes'], data['origin']
    ox, oy, oz = (int(v) for v in origin)
    ny, nz, nx = cls.shape
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tiles = []
    for y0, y1, label in BANDS:
        im = Image.fromarray(band_image(cls, origin, y0, y1)).resize((nx * S, nz * S), Image.NEAREST)
        d = grid(im, origin, (ox, nx), (oz, nz))
        if a.shaft:
            x0, x1, z0, z1, yt, yb = a.shaft
            if yb <= y1 and yt >= y0:
                d.rectangle([((x0 - ox) * S, (z0 - oz) * S), ((x1 - ox + 1) * S, (z1 - oz + 1) * S)], outline=(255, 30, 30), width=3)
        for name, x, y, z in a.mark:
            x, y, z = int(x), int(y), int(z)
            if y0 - 6 <= y <= y1 + 6:
                d.ellipse([((x - ox) * S - 5, (z - oz) * S - 5), ((x - ox) * S + 5, (z - oz) * S + 5)], outline=(255, 0, 255), width=3)
                d.text(((x - ox) * S + 8, (z - oz) * S - 8), name, font=FONT, fill=(255, 0, 255))
        d.text((8, im.height - 26), label + '  （上北下南，x 向右）', font=FONT, fill=(255, 80, 80))
        tiles.append(im)
    cols = 2
    W, H = tiles[0].width, tiles[0].height
    sheet = Image.new('RGB', (cols * W + 10, ((len(tiles) + 1) // cols) * (H + 10)), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (W + 10), (i // cols) * (H + 10)))
    sheet.save(out / 'plans.png')
    if a.shaft:
        x0, x1, z0, z1, yt, yb = a.shaft
        cxw, czw = (x0 + x1) // 2, (z0 + z1) // 2
        for name, fixed in (('section-ns', cxw), ('section-ew', czw)):
            if name == 'section-ns':
                sl = cls[:, :, fixed - ox]            # (y, z)
                h0, hn, r0, r1 = oz, nz, z0, z1
            else:
                sl = cls[:, fixed - oz, :]            # (y, x)
                h0, hn, r0, r1 = ox, nx, x0, x1
            rgb = np.zeros(sl.shape + (3,), np.uint8)
            for v, c in COL.items():
                rgb[sl == v] = c
            im = Image.fromarray(rgb[::-1]).resize((hn * S, ny * S), Image.NEAREST)
            d = grid(im, origin, (h0, hn), (oy, ny), flip_v=True, vlabel='y')
            top = (oy + ny - 1 - yt) * S; bot = (oy + ny - 1 - yb + 1) * S
            d.rectangle([((r0 - h0) * S, top), ((r1 - h0 + 1) * S, bot)], outline=(255, 30, 30), width=3)
            for mname, x, y, z in a.mark:
                x, y, z = int(x), int(y), int(z)
                hc = z if name == 'section-ns' else x
                other = x if name == 'section-ns' else z
                if abs(other - fixed) <= 24:
                    py_ = (oy + ny - 1 - y) * S
                    d.ellipse([((hc - h0) * S - 5, py_ - 5), ((hc - h0) * S + 5, py_ + 5)], outline=(255, 0, 255), width=3)
                    d.text(((hc - h0) * S + 8, py_ - 8), mname, font=FONT, fill=(255, 0, 255))
            label = f'南北剖面 x={fixed}（左北右南）' if name == 'section-ns' else f'东西剖面 z={fixed}（左西右东）'
            d.text((8, im.height - 26), label, font=FONT, fill=(255, 80, 80))
            im.save(out / f'{name}.png')
    print('views in', out)


if __name__ == '__main__':
    main()
