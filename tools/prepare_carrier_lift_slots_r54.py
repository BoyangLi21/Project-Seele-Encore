"""Declare the three rear mast service slots; preserve feet, front deck and routes."""
import argparse
import json
import math
import zipfile
from pathlib import Path
from query_blocks import read_box, iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--jar',type=Path,required=True)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    owner=json.loads((args.world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    rows=[];slots=[];rail_supports=set()
    retained_path=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/eva/carrier_bay_retained_supports_r54.json'
    retained_supports={tuple(r['at']) for r in json.loads(retained_path.read_text('utf8'))['cells']} if retained_path.exists() else set()
    slot_path=retained_path.with_name('carrier_bay_lift_slots_r54.json')
    openings={r['variant']:{tuple(p) for p in r.get('cover_openings',[])} for r in json.loads(slot_path.read_text('utf8'))['slots']} if slot_path.exists() else {}
    with zipfile.ZipFile(args.jar) as archive:
        trays=json.loads(archive.read('assets/projectseele/facility/r53_carrier_bay_trays.json'))
        # All installed routes own their native supports, including neighbours
        # whose sockets fall inside the equipment-well edit box.
        guides=json.loads(archive.read('assets/projectseele/facility/r52_upright_guideway_paths.json'))
        transfer=json.loads(archive.read('assets/projectseele/facility/r53_carrier_transfer_rails.json'))
        retained_supports.update(tuple(a['at']) for a in guides['anchors'])
        retained_supports.update(tuple(s['anchor']['at']) for s in transfer['sockets'])
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
        # Full 52.964m source mast plus clearance below the original floor.
        # Six sole supports end before local Z5.56 and remain untouched.
        lo=(math.floor(x-15),int(y-60),math.floor(z-23));hi=(math.floor(x+15),int(y-1),math.floor(z-6))
        outer_lo=(lo[0]-1,lo[1]-1,lo[2]-1);outer_hi=(hi[0]+1,hi[1],hi[2]+1)
        measured=read_box(args.world,'projectseele:geofront',outer_lo,outer_hi)
        tags=dict(iter_block_entities(args.world,'projectseele:geofront',outer_lo,outer_hi))
        assert not tags, ('Equipment slot contains a block entity',list(tags))
        wet_box=read_box(args.world,'projectseele:geofront',(int(x),int(y),int(z)),(int(x),int(y+44),int(z)))
        wet=any(state.startswith('projectseele:lcl[') for state in wet_box.values())
        for pos,state in measured.items():
            if pos in retained_supports:continue
            if pos in rail_supports and pos[2]>hi[2]:continue
            assert state in allowed or state.startswith('projectseele:lcl['), ('Keep unclassified equipment',pos,state)
            inside=all(lo[a]<=pos[a]<=hi[a] for a in range(3))
            # The original inbound carrier occupies the complete upper rim.
            # Only build deep well walls below its six-block service opening.
            if not inside and pos[1]>=int(y-6):continue
            # Existing solid walls and source bearing materials already seal
            # the well. Fill only actual gaps outside the moving envelope.
            if not inside and state!='minecraft:air' and not state.startswith('projectseele:lcl['):continue
            after='minecraft:air' if inside else 'projectseele:nerv_structural_panel'
            if inside and pos[1]==hi[1] and wet and pos not in openings.get(unit['variant'],set()):after='projectseele:nerv_floor_panel'
            if state!=after:rows.append(dict(pos=pos,before=state,after=after,purpose='Sealed full-stroke rear mast equipment well'))
        slots.append(dict(variant=unit['variant'],lo=lo,hi=hi,initially_closed=wet,cover_openings=sorted(openings.get(unit['variant'],set()))))
    dump=lambda n,v:(args.out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
    dump('forwardPatch.json',rows)
    dump('inversePatch.json',[dict(r,before=r['after'],after=r['before']) for r in rows])
    dump('positiveEditMask.json',[r['pos'] for r in rows])
    dump('installation_manifest.json',dict(world=str(args.world.resolve()),static_cells=len(rows),world_tables=[],metadata_preconditions=[]))
    dump('carrier_bay_lift_slots_r54.json',dict(schema='projectseele.carrier-bay-lift-slots.r54',stroke=54,slots=slots))
    print(json.dumps(dict(cells=len(rows),slots=slots)))

if __name__=='__main__':main()
