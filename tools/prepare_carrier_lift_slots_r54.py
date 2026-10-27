"""Declare the three rear mast service slots; preserve feet, front deck and routes."""
import argparse
import json
import math
from pathlib import Path
from query_blocks import read_box, iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    owner=json.loads((args.world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    rows=[];slots=[];rail_supports=set()
    retained_path=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/eva/carrier_bay_retained_supports_r54.json'
    retained_supports={tuple(r['at']) for r in json.loads(retained_path.read_text('utf8'))['cells']} if retained_path.exists() else set()
    trays=json.loads((Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/facility/r53_carrier_bay_trays.json').read_text('utf8'))
    for bay in trays['bays']:
        for rail in bay['rails']:
            values=rail['triangles_rgb'];root=bay['root']
            points=[(root[0]-values[i],root[1]+values[i+1],root[2]-values[i+2]) for i in range(0,len(values),6)]
            low=[min(p[a] for p in points) for a in range(3)];high=[max(p[a] for p in points) for a in range(3)]
            for x in range(math.floor(low[0]),math.ceil(high[0])):
                for z in range(math.floor(low[2]),math.ceil(high[2])):rail_supports.add((x,math.floor(low[1]-.001),z))
    allowed={'minecraft:air','minecraft:deepslate[axis=y]','minecraft:stone','projectseele:nerv_structural_panel',
             'projectseele:nerv_floor_panel','minecraft:iron_block','minecraft:polished_basalt[axis=y]',
             'projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel','minecraft:oxidized_cut_copper','minecraft:polished_blackstone','minecraft:sea_lantern'}
    for unit in owner['units']:
        x,y,z=unit['bay_frame']['position']
        # Declared carrier local X +/-15, rear Z 6..19, twelve-metre stroke.
        lo=(int(x-15),int(y-14),int(z-19));hi=(int(x+15),int(y-1),int(z-6))
        measured=read_box(args.world,'projectseele:geofront',lo,hi)
        tags=dict(iter_block_entities(args.world,'projectseele:geofront',lo,hi))
        assert not tags, ('Equipment slot contains a block entity',list(tags))
        for pos,state in measured.items():
            if pos in rail_supports or pos in retained_supports or state=='minecraft:air' or state.startswith('projectseele:lcl['):continue
            assert state in allowed, ('Keep unclassified equipment',pos,state)
            rows.append(dict(pos=pos,before=state,after='minecraft:air',purpose='Rear mast 12m service stroke, below the original bay floor'))
        slots.append(dict(variant=unit['variant'],lo=lo,hi=hi))
    dump=lambda n,v:(args.out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
    dump('forwardPatch.json',rows)
    dump('inversePatch.json',[dict(r,before=r['after'],after=r['before']) for r in rows])
    dump('positiveEditMask.json',[r['pos'] for r in rows])
    dump('installation_manifest.json',dict(world=str(args.world.resolve()),static_cells=len(rows),world_tables=[],metadata_preconditions=[]))
    dump('carrier_bay_lift_slots_r54.json',dict(schema='projectseele.carrier-bay-lift-slots.r54',stroke=12,slots=slots))
    print(json.dumps(dict(cells=len(rows),slots=slots)))

if __name__=='__main__':main()
