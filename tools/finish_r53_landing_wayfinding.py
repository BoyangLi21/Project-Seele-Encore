"""Finish measured fixed lift thresholds and signs, preserving original devices."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import nbtlib
from query_blocks import read_box, iter_block_entities, AIR
from repair_r53_reported_landings import apply

DIM = 'projectseele:geofront'
DIRECTIONS = dict(north=(0, -1), south=(0, 1), east=(1, 0), west=(-1, 0))
NAMES = {
    's20-command-rear-x12-z253-v4': ('西侧主电梯', '指挥区 / 机库', '发射区 / 终极教条'),
    'r25-east-command-gallery': ('东侧主电梯', '总部 / 科研区', '机库 / 发射区'),
    's23-commander-office-x28-z321-v1': ('总指挥办公电梯', '办公 / 联络厅', '会议层须刷卡'),
    's20-compact-cage-x93-z204-v4': ('实验区电梯', 'LCL 同步实验层', '原机库站接驳层'),
}


def plan(world, output):
    manifest = json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    measured = json.loads((world.parents[2]/'landings692.json').read_text('utf8'))
    assert Path(measured['world']).resolve() == world.resolve()
    shapes = json.loads((world/'native_collision_shapes.json').read_text('utf8'))
    rows, signs = [], []
    for lift in manifest['lifts']:
        if lift['id'] not in NAMES:
            continue
        for floor in lift['floors']:
            baseline = next(r for r in measured['floors']
                            if r['lift'] == lift['id'] and r['cabin'] == floor['cabin'])
            if any(s['kind'] in ('minecraft:sign', 'projectseele:station_departure_board')
                   for s in baseline['signs']):
                continue
            call = floor['calls'][0]
            x,y,z = call['position']; dx,dz = DIRECTIONS[call['facing']]
            # This label belongs to the existing call jamb. A recessed jamb
            # may put its measured outside face one cell farther forward.
            candidates = [(x,y+1,z), (x+dx,y+1,z+dz)]
            p = None
            for at in candidates:
                back = at[0]-dx, at[1], at[2]-dz
                lo = tuple(min(a,b) for a,b in zip(at,back))
                hi = tuple(max(a,b) for a,b in zip(at,back))
                cells = read_box(world,DIM,lo,hi)
                tags = dict(iter_block_entities(world,DIM,lo,hi))
                if cells.get(at) in AIR and at not in tags and shapes.get(cells.get(back)) == [[0,0,0,1,1,1]]:
                    p = at
                    break
            if p is None:
                raise ValueError(('No measured fixed call-jamb face',lift['id'],floor['label']))
            name,via,destination = NAMES[lift['id']]
            lines = [name, floor['label'], via, destination]
            face = nbtlib.Compound({'messages': nbtlib.List[nbtlib.String]([
                nbtlib.String(json.dumps({'text':s},ensure_ascii=False)) for s in lines]),
                'color':nbtlib.String('white'),'has_glowing_text':nbtlib.Byte(1)})
            tag = nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),
                'x':nbtlib.Int(p[0]),'y':nbtlib.Int(p[1]),'z':nbtlib.Int(p[2]),
                'front_text':face,'back_text':copy.deepcopy(face),'is_waxed':nbtlib.Byte(1)})
            rows.append(dict(pos=p,before=cells[p],after=f'minecraft:dark_oak_wall_sign[facing={call["facing"]},waterlogged=false]',
                             before_nbt=None,after_nbt=tag.snbt(),reason='missing_landing_wayfinding'))
            signs.append(dict(lift=lift['id'],floor=floor['label'],pos=p,text=lines))

    # The five missing fixed cells lie outside the original car's X=128..132
    # capture footprint and inside the already-authored landing throat.
    public = next(l for l in manifest['lifts'] if l['id']=='s20-surface-transit-v2')
    lower = next(f for f in public['floors'] if f['cabin']==[130,-535,273])
    assert lower['exit']=='west' and all(d['pos'][0]==126 for d in lower['landing_doors'])
    cells=read_box(world,DIM,(126,-536,271),(128,-536,275))
    tags=dict(iter_block_entities(world,DIM,(127,-536,271),(127,-536,275)))
    for z in range(271,276):
        p=(127,-536,z)
        assert cells[p] in AIR and p not in tags
        assert cells[126,-536,z]=='projectseele:nerv_floor_panel'
        rows.append(dict(pos=p,before=cells[p],after='projectseele:nerv_floor_panel',
                         before_nbt=None,after_nbt=None,reason='public_lift_fixed_threshold'))
    output.mkdir(parents=True,exist_ok=True)
    (output/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False).encode('utf8'),mtime=0))
    report=dict(world=str(world),changed_cells=len(rows),threshold_cells=5,signs=signs,
                original_devices_unchanged=True,installed=False)
    (output/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--apply',action='store_true')
    a=p.parse_args()
    (apply if a.apply else plan)(a.world,a.output)
