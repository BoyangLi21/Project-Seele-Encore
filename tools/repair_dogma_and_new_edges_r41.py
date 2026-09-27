"""Complete the documented Dogma galleries and newly mapped personnel edges."""
from pathlib import Path
from collections import defaultdict
import argparse,json
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/spatial_repair_r41';WORLD=ROOT/'run/saves/SEELE_FIELD_R41_REVIEW'


def main(apply=False):
    if apply:
        from release_combat_r36 import guard
        guard()
    rows=json.loads((ART/'triage/new_navigation_edges.json').read_text('utf8'))
    w=MeasuredWorld(WORLD);w.box((-37,-571,266),(97,-562,402))
    for r in rows:w.around(r['pos'],2)
    w.load();v.WORLD=WORLD;v.OUT=ART/'expanded_edges';p=v.Painter();changes={};rails=defaultdict(set);held=[]
    def state(q):return changes.get(tuple(q),(w.block(q),''))[0]
    def put(q,after,why,allowed):
        q=tuple(q);old=w.block(q)
        if old==after:return
        assert old is not None and old.partition('[')[0] in allowed,(q,old,why)
        changes[q]=(after,why)
    # R04's named galleries stopped short of the pressure shell. Join their
    # existing three-layer slabs to the wall, retaining the open central lake.
    seams={(x,z) for x in (-35,95) for z in range(268,401)}
    seams|={(x,268) for x in range(-35,96)}
    seams|={(x,z) for x in range(-35,96) for z in range(397,401)}
    for x,z in seams:
        for y in (-569,-568,-567):
            if state((x,y,z)) in AIR:put((x,y,z),'minecraft:gray_concrete' if y==-567 else 'minecraft:polished_deepslate','dogma/gallery_to_pressure_shell_bearing',AIR)
    old_rails=set()
    for x0,x1 in [(-28,18),(42,88)]:old_rails|={(x,y,295) for x in range(x0,x1+1) for y in (-566,-565)}
    old_rails|={(x,y,z) for x in (22,38) for z in range(296,307) for y in (-566,-565)}
    old_rails|={(x,y,306) for x in range(23,38) for y in (-566,-565)}
    old_rails|={(x,y,z) for x in (-28,88) for z in range(296,394) for y in (-566,-565)}
    for q in old_rails:
        if (state(q) or '').startswith('minecraft:iron_bars['):put(q,'minecraft:air','dogma/replace_outboard_floating_rails',{'minecraft:iron_bars'})
    names={(1,0,0):'east',(-1,0,0):'west',(0,0,1):'south',(0,0,-1):'north'}
    def rail(q,normal,reason):
        q=tuple(q);old=state(q)
        if old is None:raise RuntimeError(('Unmeasured edge',q))
        if old.startswith('projectseele:nerv_edge_rail['):rails[q].update(k for k in names.values() if k+'=true' in old)
        elif old.startswith('minecraft:light['):
            above=(q[0],q[1]+3,q[2])
            if state(above) in AIR:put(above,old,'edge/retain_existing_illumination_above_headroom',AIR)
            else:held.append(dict(pos=q,state=old,reason='Light has no clear relocation cell'));return
        elif old not in AIR:
            held.append(dict(pos=q,state=old,reason='Preserve existing fixture/barrier',source=reason));return
        rails[q].add(names[tuple(normal)])
    gallery_floor={'minecraft:gray_concrete','minecraft:polished_deepslate','projectseele:nerv_floor_panel','projectseele:nerv_structural_panel'}
    for x in range(-35,96):
        for z in range(268,401):
            floor=state((x,-567,z));q=(x,-566,z)
            if floor is None or floor.partition('[')[0] not in gallery_floor or state(q) not in AIR and not state(q).startswith('minecraft:light['):continue
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                below=state((x+dx,-567,z+dz));at=state((x+dx,-566,z+dz))
                if below in AIR and at in AIR:rail(q,(dx,0,dz),'complete_named_dogma_gallery_boundary')
    for r in rows:
        q=r['pos']
        if q[1]==-566:continue
        if q[1]==-329:
            held.append(dict(pos=q,reason='Commander-room roof exterior, not a personnel corridor; preserve pyramid silhouette'));continue
        rail(q,r['normal'],'newly_connected_measured_personnel_floor')
    for q,sides in rails.items():
        after='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower() for k in ('east','north','south','west'))+']'
        put(q,after,'gallery_edge_mounted_rail',AIR|{'minecraft:light','projectseele:nerv_edge_rail','minecraft:iron_bars'})
    tags={}
    for cx,cz in {(q[0]//16,q[2]//16) for q in changes}:
        yy=[q[1] for q in changes if q[0]//16==cx and q[2]//16==cz]
        tags.update(iter_block_entities(WORLD,v.DIM,(cx*16,min(yy),cz*16),(cx*16+15,max(yy),cz*16+15)))
    assert not set(tags)&set(changes),'Gallery plan intersects a block entity'
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r41/'+why)
    p.meta.update(held=held,rail_cells=len(rails),named_basis='R04 arrival_gallery / viewing_platform / side_gallery / rear_gallery, actual R41 floor and pressure-shell coordinates',
                  protected=['Central LCL lake at Y-601','Original Lilith entity and cross','Restricted lift and checkpoint','Pyramid exterior roof'],source_new_graph_edges=len(rows))
    p.save_plan('dogma_gallery_bearings_and_new_edges')
    if apply:
        p.apply('dogma_gallery_bearings_and_new_edges')
        f=WORLD/'regional_states.json';states=set(json.loads(f.read_text('utf8')));states.update(v[0] for v in changes.values());f.write_text(json.dumps(sorted(states)),'utf8')
    (ART/'expanded_edges/contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
