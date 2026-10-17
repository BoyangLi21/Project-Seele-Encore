"""Read-only floor atlas for the two original main lifts and rear alternatives.

The footprint overlay is a spatial proposal, never a world-write mask. Full
states come from the existing query_blocks measurement, with new bounded reads
only for the Terminal Dogma floor outside that measurement.
"""
from pathlib import Path
import argparse
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import survey_r52_original_complex as survey
from survey_facility_target import role_of

FONT = 'C:/Windows/Fonts/msyh.ttc'
COLOURS = {'air': (239, 242, 241), 'natural': (188, 191, 188),
           'floor': (202, 216, 211), 'wall': (61, 79, 83),
           'glass': (77, 169, 183), 'lift': (163, 79, 157),
           'stair': (235, 159, 65), 'fluid': (175, 116, 69),
           'device': (187, 72, 75)}


def kind(state):
    role = role_of(state)
    if role in ('air', 'natural', 'fluid'): return role
    if 'elevator' in state: return 'lift'
    if 'stairs' in state: return 'stair'
    if 'glass' in state: return 'glass'
    if any(s in state for s in ('button', 'display', 'wall_artwork', 'reader')): return 'device'
    return 'wall'


def panel(cells, palette, origin, y, box, title, axes, scale=4):
    x0, z0, x1, z1 = box
    ox, oy, oz = map(int, origin)
    values = cells[y-1-oy:y+2-oy, z0-oz:z1+1-oz, x0-ox:x1+1-ox]
    assert values.shape == (3, z1-z0+1, x1-x0+1), (title, values.shape)
    classes = np.asarray([list(COLOURS).index(kind(s)) for s in palette])
    colours = np.asarray(list(COLOURS.values()), np.uint8)
    foot, head = classes[values[1]], classes[values[2]]
    ground = classes[values[0]]
    air = list(COLOURS).index('air')
    natural = list(COLOURS).index('natural')
    result = foot.copy()
    result[(foot == air) & (head != air)] = head[(foot == air) & (head != air)]
    standing = (foot == air) & (head == air) & (ground != air) & (ground != natural)
    result[standing] = list(COLOURS).index('floor')
    img = Image.fromarray(colours[result]).resize(((x1-x0+1)*scale, (z1-z0+1)*scale), Image.Resampling.NEAREST)
    canvas = Image.new('RGB', (img.width+50, img.height+76), 'white')
    canvas.paste(img, (38, 55)); d = ImageDraw.Draw(canvas)
    d.text((10, 6), title, font=ImageFont.truetype(FONT, 23), fill=(28,49,55))
    font = ImageFont.truetype(FONT, 12)
    for x in range((x0//20+1)*20, x1+1, 20):
        px = 38+(x-x0)*scale
        d.line((px,55,px,55+img.height), fill=(208,215,211), width=1)
        d.text((px-8,37),str(x),font=font,fill='black')
    for z in range((z0//20+1)*20, z1+1, 20):
        pz = 55+(z-z0)*scale
        d.line((38,pz,38+img.width,pz), fill=(208,215,211), width=1)
        d.text((0,pz-5),str(z),font=font,fill='black')
    for label, x, z, colour in axes:
        if not x0 <= x <= x1 or not z0 <= z <= z1: continue
        px,pz = 38+(x-x0)*scale,55+(z-z0)*scale
        d.rectangle((px-3*scale,pz-3*scale,px+4*scale-1,pz+4*scale-1),outline=colour,width=3)
        d.text((px+4*scale,pz),label,font=font,fill=colour,stroke_width=1,stroke_fill='white')
    return canvas


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    args=ap.parse_args(); out=args.base/'lift-spatial-review';out.mkdir(exist_ok=True)
    axes=[('原主梯',9,253,(171,44,45)),('原东梯',66,302,(171,44,45)),
          ('后方主梯提案',-42,366,(18,104,200)),('后方东梯提案',58,366,(18,104,200))]
    with np.load(args.base/'facility-model/headquarters.npz') as data:
        cells,palette,origin=data['states'],data['palette'].tolist(),data['origin']
    levels=[-554,-541,-527,-516,-513,-512,-502,-499,-485,-471,-457]
    for start in range(0,len(levels),4):
        panels=[panel(cells,palette,origin,y,(-65,235,100,390),f'总部脚位 Y={y}',axes) for y in levels[start:start+4]]
        page=Image.new('RGB',(panels[0].width*2,panels[0].height*2+70),'white')
        ImageDraw.Draw(page).text((20,10),'现状平面：灰绿=现有承重面；深色=实体；橙=楼梯；蓝框=待审位置；上方为北',font=ImageFont.truetype(FONT,20),fill='black')
        for i,p in enumerate(panels): page.paste(p,((i%2)*p.width,(i//2)*p.height+70))
        page.save(out/f'HQ_{start//4+1}.png')
    survey.WORLD=args.base/'CANDIDATE'
    lo,hi=(-55,-1231,232),(105,-1229,380)
    terminal,names=survey.measure(lo,hi)
    np.savez_compressed(out/'terminal_landing.npz',origin=lo,states=terminal,palette=names)
    panel(terminal,names,lo,-1230,(-55,232,105,380),'Terminal Dogma 现有入口与后方提案',axes).save(out/'Terminal.png')
    with np.load(args.base/'facility-model/deep_hangar.npz') as data:
        cells,palette,origin=data['states'],data['palette'].tolist(),data['origin']
    for y in (-987,-1014,-1030):
        panel(cells,palette,origin,y,(-55,245,105,395),f'机库脚位 Y={y}',axes).save(out/f'Hangar_{-y}.png')
    (out/'README.json').write_text(json.dumps(dict(world_written=False,footprints_are_proposals=True,
        source='query_blocks measured R53 CANDIDATE volumes',levels=levels,
        partial_shapes_require_native_verification=True),indent=2),'utf8')
    print('Read-only landing atlas written:',out)


if __name__=='__main__':main()
