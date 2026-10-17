"""Complete the existing migrated pyramid crown using its original shell slope."""
from pathlib import Path
from collections import defaultdict
import argparse, gzip, json, math, msvcrt
from query_blocks import read_box, iter_block_entities, dimension_dir, AIR
from apply_s20_approved_semantic_repairs import Change, rewrite_region, atomic_replace

DIM = 'projectseele:geofront'
PANEL = 'projectseele:nerv_pyramid_panel'
LO, HI = (15, -407, 312), (45, -384, 342)


def radius(y):
    # Original R09 shell, translated down 93 blocks by the current migration.
    return math.floor(120 * (1 - (y + 93 + 466) / 172) + .5)


def draw(before, after, output):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (1400, 650), '#162027')
    d = ImageDraw.Draw(image)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 23)
    small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
    for i, (cells, label) in enumerate(((before, '修补前：截断的平顶'), (after, '修补后：原坡度收尖、连续封边'))):
        solid = {p for p, s in cells.items() if s not in AIR}
        faces = []
        for x, y, z in solid:
            for direction, offsets, color in (
                ((1,0,0), ((1,0,0),(1,0,1),(1,1,1),(1,1,0)), '#424e55'),
                ((0,0,1), ((0,0,1),(1,0,1),(1,1,1),(0,1,1)), '#59656b'),
                ((0,1,0), ((0,1,0),(1,1,0),(1,1,1),(0,1,1)), '#738087')):
                if (x+direction[0], y+direction[1], z+direction[2]) in solid: continue
                points = [(x+a,y+b,z+c) for a,b,c in offsets]
                projected = [(350+i*700+(a-30-(c-327))*10,480+(a-30+c-327)*5-(b+407)*13) for a,b,c in points]
                faces.append((x+z+y*.04, projected, color))
        for _, points, color in sorted(faces): d.polygon(points, fill=color, outline='#2d383f')
        d.text((35+i*700,25), label, font=font, fill='#e8edef')
    d.text((35,600), '当前存档方块几何对照（非游戏截图）｜塔尖 Y=-387｜下方房间、单向玻璃和画作保留', font=small, fill='#c8d1d7')
    image.save(output)


def run(world, output, apply=False):
    before = read_box(world, DIM, LO, HI)
    tags = dict(iter_block_entities(world, DIM, LO, HI))
    desired = {}
    for y in range(-406, -386):
        r = radius(y)
        inner = max(0, radius(y+1)-1) if y < -387 else 0
        for x in range(30-r,31+r):
            for z in range(327-r,328+r):
                if max(abs(x-30), abs(z-327)) >= inner:
                    desired[x,y,z] = PANEL
    # Remove only the previous authored flat cap material inside the new shell.
    for p,s in before.items():
        if p[1] == -391 and (s == 'projectseele:nerv_machine_panel' or s.startswith('projectseele:nerv_alert_light')):
            desired.setdefault(p, 'minecraft:air')
    rows = []
    after = before.copy()
    for p,wanted in desired.items():
        old = before[p]
        assert p not in tags, ('Crown would touch an original device', p)
        assert old in AIR or old in (PANEL, 'projectseele:nerv_machine_panel') or old.startswith('projectseele:nerv_alert_light'), (p,old)
        if old != wanted:
            rows.append(dict(pos=p,before=old,after=wanted))
            after[p] = wanted
    # Both rising edges and the ledge below the next course have real blocks.
    for p,s in desired.items(): assert after[p] == s
    assert all(after[p] == s for p,s in before.items() if p[1] == -407 or p in tags)
    output.mkdir(parents=True,exist_ok=True)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report = dict(changed_cells=len(rows), crown_y=-387, existing_slope_preserved=True,
                  original_ceiling_and_devices_preserved=True, actual_installed=False)
    if apply:
        with (world/'session.lock').open('r+b') as lock:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            regions=defaultdict(lambda:defaultdict(list))
            for row in rows:
                x,y,z=row['pos']
                regions[x>>9,z>>9][x>>4,z>>4].append(Change('r53-crown',x,y,z,row['before'],row['after'],'restore','complete_original_pyramid_crown'))
            for (rx,rz),chunks in regions.items():
                path=dimension_dir(world,DIM)/f'region/r.{rx}.{rz}.mca'
                atomic_replace(path,rewrite_region(path,chunks))
            actual=read_box(world,DIM,LO,HI)
            assert actual == after, 'Actual installed crown differs'
            assert dict(iter_block_entities(world,DIM,LO,HI)) == tags
            after=actual
            report.update(actual_installed=True,actual_readback=True)
    draw(before,after,output/'crown-before-after.png')
    (output/('INSTALLED.json' if apply else 'PLAN.json')).write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true')
    a=p.parse_args();run(a.world,a.output,a.apply)
