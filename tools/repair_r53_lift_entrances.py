"""Repair the measured doorway throats and call-button approaches of both old lifts.

Only fixed landing aprons are edited. Native cages, controllers, door planes,
sign block entities, floor lists and live progress remain owned by their devices.
"""
from pathlib import Path
import argparse, gzip, json, msvcrt
import regional_voxels as vox
from query_blocks import read_box, iter_block_entities

DIM = 'projectseele:geofront'
IDS = ('s20-command-rear-x12-z253-v4', 'r25-east-command-gallery')
AIR = 'minecraft:air'
FLOOR = 'projectseele:nerv_floor_panel'
WALL = 'projectseele:nerv_structural_panel'


def run(world, output, apply=False):
    manifest = json.loads((world / 'personnel_lifts_r52.json').read_text('utf8'))
    rows, checks = [], []
    for lift in manifest['lifts']:
        if lift['id'] not in IDS:
            continue
        for floor in lift['floors']:
            x, y, z = floor['cabin']
            lo, hi = (x-5, y-1, z+3), (x+6, y+4, z+10)
            cells = read_box(world, DIM, lo, hi)
            tags = dict(iter_block_entities(world, DIM, lo, hi))
            doors = {tuple(d['pos']) for d in floor['landing_doors']}
            calls = {tuple(c['position']) for c in floor['calls']}
            desired, reasons = {}, {}

            def put(p, value, reason):
                assert p in cells, p
                if p in doors or p in calls or p in tags:
                    return
                assert not cells[p].startswith('movingelevators:'), p
                desired[p], reasons[p] = value, reason

            # Full five-wide aperture between the native car and fixed door,
            # plus the landing's first row. The former B1 edit started at the
            # door itself and left a wall at z+3 across the entire opening.
            for xx in range(x-2, x+3):
                for zz in range(z+3, z+6):
                    put((xx, y-1, zz), FLOOR, 'continuous_landing_threshold')
                    for yy in range(y, y+3):
                        put((xx, yy, zz), AIR, 'full_width_doorway')
            # Main lift has a south-facing call on the left jamb. Clear the
            # whole short apron, including the old wall next to that button.
            if lift['id'] == IDS[0]:
                for xx in range(x-3, x+3):
                    for zz in range(z+5, z+7):
                        put((xx, y-1, zz), FLOOR, 'call_button_standing_floor')
                        for yy in range(y, y+3):
                            put((xx, yy, zz), AIR, 'unobstructed_call_approach')
            # Frame only the actual door, not the adjacent corridor. Existing
            # direction signs and moving door collision cells are untouched.
            for xx in (x-3, x+3):
                for yy in range(y, y+3):
                    put((xx, yy, z+4), WALL, 'consistent_landing_jamb')
            for xx in range(x-3, x+4):
                put((xx, y+3, z+4), WALL, 'continuous_door_header')
            for call in floor['calls']:
                p = tuple(call['position'])
                dx, dz = dict(south=(0, 1), east=(1, 0), north=(0, -1), west=(-1, 0))[call['facing']]
                # Fixed control backing and a two-high human approach.
                put((p[0]-dx, p[1], p[2]-dz), WALL, 'call_button_backing')
                q = (p[0]+dx, y, p[2]+dz)
                put((q[0], y-1, q[2]), FLOOR, 'call_button_standing_floor')
                for yy in (y, y+1, y+2):
                    put((q[0], yy, q[2]), AIR, 'call_button_face_clearance')
            obstacles = []
            for p, value in desired.items():
                if cells[p] != value:
                    rows.append(dict(pos=list(p), before=cells[p], after=value,
                                     before_nbt=None, after_nbt=None,
                                     lift=lift['id'], floor=y, reason=reasons[p]))
                    if value == AIR:
                        obstacles.append(list(p))
            checks.append(dict(lift=lift['id'], floor=y, removed_obstructions=obstacles,
                               preserved_doors=len(doors), preserved_block_entities=len(tags)))
    output.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(rows, ensure_ascii=False, indent=2)+'\n').encode('utf8')
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(raw, mtime=0))
    # The plan itself includes every old state for exact inverse application.
    report = dict(world=str(world), floors=len(checks), changed_cells=len(rows), checks=checks,
                  actual_installed=False, player_entities_tasks_traffic_untouched=True)
    if apply:
        lock = (world/'session.lock').open('r+b')
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            vox.WORLD, vox.DIM, vox.OUT = world, DIM, output
            painter = vox.Painter(vertical_bounds=(-1440, 320))
            for r in rows:
                p = tuple(r['pos'])
                painter.exact((*p, *p), r['before'], r['after'], r['reason'])
            painter.apply('r53_original_lift_fixed_entrances', session_lock=lock)
            for lift in manifest['lifts']:
                if lift['id'] not in IDS: continue
                for floor in lift['floors']:
                    x,y,z=floor['cabin']
                    back=read_box(world,DIM,(x-5,y-1,z+3),(x+6,y+4,z+10))
                    for r in rows:
                        if r['lift']==lift['id'] and r['floor']==y:
                            assert back[tuple(r['pos'])]==r['after'],r['pos']
            report['actual_installed']=True
            report['actual_readback']=True
        finally:
            lock.close()
    (output/('INSTALLED.json' if apply else 'PLAN.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true')
    a=p.parse_args();run(a.world,a.output,a.apply)
