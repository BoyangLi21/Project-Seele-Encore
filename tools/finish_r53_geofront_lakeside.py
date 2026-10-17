"""Authorized lakeside lighting, small equipment and redundant wet collar fix.

The lake footprint is the authored R52 square X-269..6/Z348..623. Lights and
equipment use its existing eight-wide paved bank; the centre remains open.
The original pyramid wall is measured before closing its external air collar.
"""
from pathlib import Path
from collections import Counter
import argparse, gzip, json
from query_blocks import read_box, iter_block_entities, AIR
from repair_r53_reported_landings import apply
from repair_r53_pyramid_crown import radius

DIM='projectseele:geofront'
FLOOR='projectseele:nerv_floor_panel'
MACHINE='projectseele:nerv_machine_panel'
EDGE='projectseele:nerv_machine_edge'
# The ceiling strip only exposes its luminous texture on the underside.
# An all-face warm emitter remains visible when recessed in a basin wall.
LIGHT='minecraft:ochre_froglight[axis=y]'

def plan(world,out):
    cells={};tags={};wanted={};reasons={}
    def read(lo,hi):
        cells.update(read_box(world,DIM,lo,hi));tags.update(iter_block_entities(world,DIM,lo,hi))
    def put(p,state,reason):
        assert p in cells and p not in tags,('Existing device',p)
        wanted[p]=state;reasons[p]=reason
    read((-72,-525,348),(6,-473,432))
    wet=[]
    for p,before in cells.items():
        x,y,z=p;r=radius(y);distance=max(abs(x-30),abs(z-327))
        if distance==r:
            assert before not in AIR,('Original wet wall opening',p)
        if r<distance<=r+4 and (before in AIR or before=='minecraft:black_concrete'):
            # No inner room cell is eligible. Water must already meet the
            # outside of this same course; below the basin bed is excluded.
            probes=[(30-r-5,y,z),(x,y,327+r+5)]
            if not any(cells.get(q,'').startswith('minecraft:water') for q in probes):continue
            put(p,'minecraft:water[level=0]','remove_external_air_moat_after_skin_retirement');wet.append(p)
    # Full one-block light ribbon recessed in the four existing basin walls,
    # three metres below the water surface, rather than floating on the water.
    banks=[((-270,-478,347),(-270,-464,624)),((7,-478,347),(7,-464,624)),
           ((-270,-478,347),(7,-464,347)),((-270,-478,624),(7,-464,624))]
    for lo,hi in banks:read(lo,hi)
    ribbon={(x,-476,z) for x in (-270,7) for z in range(348,624)}
    ribbon|={(x,-476,z) for z in (347,624) for x in range(-270,8)}
    for p in ribbon:
        if cells[p] not in {'minecraft:stone','minecraft:black_concrete',EDGE,FLOOR,
                            'projectseele:nerv_strip_light[lit=true]'}:continue
        put(p,LIGHT,'continuous_submerged_basin_light')
    posts=[(x,z) for x in (-276,13) for z in range(360,624,28)]
    posts += [(x,z) for z in (341,630) for x in range(-258,7,28)]
    installed_posts=[]
    for x,z in posts:
        read((x,-468,z),(x,-465,z))
        if cells[x,-468,z]!=FLOOR or any(cells[x,y,z] not in AIR for y in range(-467,-464)):continue
        put((x,-467,z),EDGE,'lakeside_warning_bollard')
        put((x,-466,z),MACHINE,'lakeside_warning_bollard')
        put((x,-465,z),'projectseele:nerv_alert_light[hanging=false,lit=true]','red_warning_light')
        installed_posts.append([x,-465,z])
    # Small open service fittings occupy only the outer three metres of the
    # eight-metre bank. No new room, dead corridor or active machine is implied.
    pads=[(-276,394,3,5),(-276,506,3,5),(11,450,3,5),(11,562,3,5),
          (-224,341,5,3),(-112,341,5,3),(-224,628,5,3),(-112,628,5,3)]
    installed_pads=[]
    for x,z,sx,sz in pads:
        read((x,-468,z),(x+sx-1,-464,z+sz-1))
        if any(cells[a,-468,b]!=FLOOR for a in range(x,x+sx) for b in range(z,z+sz)):continue
        if any(cells[a,y,b] not in AIR for a in range(x,x+sx) for b in range(z,z+sz) for y in range(-467,-463)):continue
        for a in range(x,x+sx):
            for b in range(z,z+sz):put((a,-468,b),'projectseele:nerv_hazard_paving','service_equipment_pad')
        # Paired cabinets, top ventilation grilles, and an exposed service pipe.
        length=max(sx,sz)
        def at(u,v,y):return (x+v,y,z+u) if sz>sx else (x+u,y,z+v)
        for u in (0,length-2):
            for v in (0,1):
                for y in (-467,-466):put(at(u,v,y),MACHINE,'small_bank_service_cabinet')
                put(at(u,v,-465),'minecraft:iron_trapdoor[facing=north,half=bottom,open=false,powered=false,waterlogged=false]','service_cabinet_vent')
        for u in range(length):
            put(at(u,2,-467),EDGE,'ground_service_conduit')
        put(at(2,0,-467),'projectseele:nerv_machine_hazard','local_guard_bollard')
        installed_pads.append(dict(origin=[x,-468,z],size=[sx,sz]))
    rows=[]
    for p,state in wanted.items():
        if cells[p]!=state:rows.append(dict(pos=p,before=cells[p],after=state,before_nbt=None,after_nbt=None,reason=reasons[p]))
    out.mkdir(parents=True,exist_ok=True)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report=dict(world=str(world),cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),
                warning_lights=installed_posts,small_service_pads=installed_pads,
                original_wall_preserved=True,minimum_bank_walk_width=5,
                scope='Authored lake bank and external pyramid collar only; no room/rail/entity changes')
    (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    plan(a.world,a.output)
    if a.apply:apply(a.world,a.output)
