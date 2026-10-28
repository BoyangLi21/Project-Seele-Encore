"""Prepare only declared cover openings; do not modify the world."""
import argparse
import json
from pathlib import Path
from query_blocks import read_box

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    source=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/eva/carrier_bay_lift_slots_r54.json'
    retained={tuple(r['at']) for r in json.loads(source.with_name('carrier_bay_retained_supports_r54.json').read_text('utf8'))['cells']}
    rows=[]
    for slot in json.loads(source.read_text('utf8'))['slots']:
        openings=slot.get('cover_openings',[])
        if not openings:continue
        lo=tuple(min(p[a] for p in openings) for a in range(3))
        hi=tuple(max(p[a] for p in openings) for a in range(3))
        actual=read_box(args.world,'projectseele:geofront',lo,hi)
        for pos in openings:
            if tuple(pos) in retained:continue
            before=actual[tuple(pos)]
            if before=='projectseele:nerv_floor_panel':
                rows.append(dict(pos=pos,before=before,after='minecraft:air',purpose='Fixed deck edge and independent receiver sleeve cover clearance'))
            elif before!='minecraft:air' and not before.startswith('projectseele:lcl['):
                raise ValueError(('Unexpected block at declared cover opening',pos,before))
    args.out.mkdir(parents=True,exist_ok=True)
    def dump(name,value):(args.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    dump('forwardPatch.json',rows)
    dump('inversePatch.json',[dict(r,before=r['after'],after=r['before']) for r in rows])
    dump('positiveEditMask.json',[r['pos'] for r in rows])
    dump('installation_manifest.json',dict(world=str(args.world.resolve()),static_cells=len(rows),world_tables=[],metadata_preconditions=[]))
    print(json.dumps(dict(cells=len(rows),out=str(args.out))))

if __name__=='__main__':main()
