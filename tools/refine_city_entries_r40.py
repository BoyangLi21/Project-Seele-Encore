"""Measure and rebuild authored city entrances as coherent storefront/lobby bays."""
import argparse,json,math
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT,properties
from query_blocks import iter_block_entities,AIR

OUT=ROOT/'artifacts/world_combat_r40/city_entries'
def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;OUT.mkdir(parents=True,exist_ok=True);p=v.Painter();w=MeasuredWorld()
    places=json.loads((ROOT/'artifacts/world_expansion_20260907/geometry_all/places.json').read_text())['landmarks']
    places=[q for q in places if 'entry' in q and q['entry'][1]>0]
    for r in places:
        x,y,z=r['entry'];w.box((x-5,y-3,z-6),(x+5,y+7,z+6))
    w.load();native=json.loads((WORLD/'native_transit_r28.json').read_text());rails=np.asarray([q for c in native['curves'] if c['mode']=='TRAIN' for q in c['points']]);tree=cKDTree(rails[:,[0,2]])
    changes={};entries=[];held=[]
    safe={'minecraft:air','minecraft:light','minecraft:smooth_stone','minecraft:polished_andesite','minecraft:gray_concrete','minecraft:black_concrete','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:gray_stained_glass','minecraft:glass','minecraft:smooth_quartz','projectseele:nerv_wall_panel','projectseele:nerv_structural_panel','projectseele:clear_glass'}
    def put(q,s,why):
        old=w.block(q)
        if old is None:raise RuntimeError(('Unknown cell',q))
        if old!=s:changes[q]=(s,why)
    for r in places:
        x,y,z=map(int,r['entry']);door=(x,y,z-1);old=w.block(door)
        if not old or not old.startswith('minecraft:oak_door['):held.append(dict(id=r['id'],reason='Original entrance has moved or uses a different door',actual=old));continue
        if -144<=x<=207 and 41<=z<=392:held.append(dict(id=r['id'],reason='Retracting combat block; preserved'));continue
        cells=[(X,Y,Z) for X in range(x-1,x+2) for Y in range(y,y+3) for Z in range(z-4,z+2)]
        conflicts=[(q,w.block(q)) for q in cells if w.block(q).partition('[')[0] not in safe|{'minecraft:oak_door'}]
        if conflicts:held.append(dict(id=r['id'],reason='Occupied doorway/lobby volume',cells=conflicts));continue
        if properties(old).get('facing')!='south':held.append(dict(id=r['id'],reason='Nonstandard facade orientation'));continue
        # Door jambs remain bearing, but the lobby no longer dead-ends one
        # block behind the front door in a decorative partition.
        for X in range(x-1,x+2):
            for Z in range(z-4,z):
                put((X,y-1,Z),'minecraft:polished_andesite','lobby_floor')
                for Y in range(y,y+3):put((X,Y,Z),'minecraft:air','lobby_clearance')
        for X,hinge in [(x,'left'),(x+1,'right')]:
            for Y,half in [(y,'lower'),(y+1,'upper')]:put((X,Y,z-1),f'mcwdoors:store_door[facing=south,half={half},hinge={hinge},open=false,powered=false]','glazed_double_entrance')
        for X in (x-2,x+2):
            for Y in range(y,y+3):
                q=X,Y,z-1
                if w.block(q).partition('[')[0] in safe:put(q,'minecraft:gray_concrete','metal_frame_jamb')
        # A shallow entrance apron stays at the existing floor level. The
        # street beyond it, native rails, and neighbouring storefronts remain.
        for X in range(x-3,x+4):
            for Z in range(z,z+3):
                if w.get(X,y-1,Z).partition('[')[0] in safe-{'minecraft:air','minecraft:light'} and all(w.get(X,Y,Z).partition('[')[0] in AIR for Y in (y,y+1)):
                    put((X,y-1,Z),'minecraft:polished_andesite','entrance_apron')
        nearby=tree.query_ball_point([x,z],6)
        track_conflict=any(y-2<=rails[i,1]<=y+10 for i in nearby)
        canopy=[]
        if not track_conflict:
            for X in range(x-3,x+4):
                for Z in range(z-1,z+2):
                    q=X,y+3,Z
                    if w.block(q).partition('[')[0] in safe:
                        put(q,'minecraft:smooth_stone_slab[type=top,waterlogged=false]','cantilever_canopy');canopy.append(q)
            # Fixtures are embedded against the underside of the canopy.
            for X in (x-2,x+2):
                q=X,y+2,z
                if w.block(q).partition('[')[0] in AIR:put(q,'projectseele:nerv_ceiling_light[hanging=true,lit=true]','porch_light')
        entries.append(dict(id=r['id'],style=r.get('style'),entry=[x,y,z],door=[x,y,z-1],canopy_cells=len(canopy),rail_clearance_preserved=track_conflict,
            path=[[x+.5,y,z+2.5],[x+.5,y,z-3.5]]))
    for q,(after,why) in sorted(changes.items()):p.match((*q,*q),w.block(q),after,'r40/city/'+why)
    p.meta.update(entrances=entries,held=held,source='Original authored 199 entrance identities, measured in R40; external Macaw store doors pinned to Forge 1.20.1',walk_nodes=[dict(id='r40/city_entry/'+r['id'],path=r['path'],useDoor=True,door=r['door']) for r in entries])
    p.save_plan('city_lobby_portals')
    if apply:p.apply('city_lobby_portals')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('City entrances',len(entries),'held',len(held),'changes',len(p.ops),dict(Counter(q['reason'] for q in held)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
