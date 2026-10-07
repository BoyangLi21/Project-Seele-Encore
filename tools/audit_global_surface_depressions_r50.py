"""Actual small-column readback of every isolated global Heightmap depression.

Distinguishes generated soil relief from stale maps, trees, roofs and devices.
No block/source write is performed by this audit.
"""
from pathlib import Path
from collections import Counter
import argparse,json
import numpy as np
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from audit_surface_objects_r50 import SOIL

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();base=ROOT/'artifacts/rebuild_r49/surface_r50';out=base/'global_depressions';out.mkdir(parents=True,exist_ok=True)
    screen=json.loads((base/'global_heightmaps/global_screen.json').read_text('utf8'));objects=[r for r in screen['objects']if'DEPRESSION'in r['kind']];w=MeasuredWorld(args.world.resolve());points={tuple(r['examples'][0][:3])for r in objects};maps={}
    def saved_height(x,z):
        key=x//512,z//512
        if key not in maps:maps[key]=np.load(base/f'global_heightmaps/r.{key[0]}.{key[1]}.npz')
        return int(maps[key]['height'][z%512,x%512])
    for x,y,z in points:
        ceiling=min(319,max(saved_height(xx,zz)for xx in range(x-2,x+3)for zz in range(z-2,z+3))+8);w.box((x-2,0,z-2),(x+2,ceiling,z+2))
    w.load();assert set(w.status.values())=={'full'},Counter(w.status.values())
    lo=tuple(min(q[k]for q in points)-(2 if k!=1 else min(q[1]for q in points))for k in range(3));hi=(max(q[0]for q in points)+2,319,max(q[2]for q in points)+2);bes=dict(iter_block_entities(w.world,w.dimension,lo,hi,selected_chunks=set(w.selected)))
    ground={};top={}
    for(cx,sy,cz),(palette,ids)in w.tiles.items():
        index=ids.reshape(16,16,16);yy=np.arange(sy*16,sy*16+16)[:,None,None];names=[s.partition('[')[0]for s in palette]
        soil=np.array([n in SOIL for n in names])[index];solid=np.array([n not in AIR|{'minecraft:water','minecraft:lava','minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}and not n.endswith('_leaves')for n in names])[index];key=cx,cz
        ground[key]=np.maximum(ground.get(key,np.full((16,16),-32768,np.int16)),np.where(soil,yy,-32768).max(axis=0));top[key]=np.maximum(top.get(key,np.full((16,16),-32768,np.int16)),np.where(solid,yy,-32768).max(axis=0))
    def g(cache,x,z):return int(cache[x//16,z//16][z%16,x%16])
    rows=[]
    for r in objects:
        x,y,z=r['examples'][0][:3];soil=[[g(ground,xx,zz)for xx in range(x-2,x+3)]for zz in range(z-2,z+3)];solid=[[g(top,xx,zz)for xx in range(x-2,x+3)]for zz in range(z-2,z+3)];center=soil[2][2];four=[soil[1][2],soil[3][2],soil[2][1],soil[2][3]];actual_top=solid[2][2];near_be=[dict(pos=list(q),id=str(t.get('id','')))for q,t in bes.items()if x-2<=q[0]<=x+2 and z-2<=q[2]<=z+2]
        top_material=[]
        for dx,dz in[(0,0),(-1,0),(1,0),(0,-1),(0,1)]:
            yy=g(top,x+dx,z+dz);top_material.append(dict(pos=[x+dx,yy,z+dz],state=w.get(x+dx,yy,z+dz)))
        terrain_drop=None if center<0 or min(four)<0 else min(four)-center;structural=any(p['state']and p['state'].partition('[')[0]not in SOIL and not p['state'].partition('[')[0].endswith(('_log','_wood'))for p in top_material)
        if near_be or r['finite_owner_xz_overlap']:status='CURRENT_DEVICE_OR_FINITE_STRUCTURE_CONTEXT_RETAINED'
        elif structural:status='CURRENT_ROOF_TRACK_OR_OTHER_NONSOIL_BODY_REQUIRES_COMPONENT_CONTEXT'
        elif terrain_drop is None:status='WATER_OR_NO_SOIL_CONTEXT_RETAINED'
        elif terrain_drop<8:status='NO_ACTUAL_ISOLATED_SOIL_PIT_HEIGHTMAP_TREE_OR_SURFACE_BODY'
        else:status='ACTUAL_ISOLATED_NATURAL_SOIL_DEPRESSION_REQUIRES_GEOLOGICAL_DECISION'
        column=[]
        for yy in range(max(0,center-8),min(319,max(four+[actual_top])+3)+1):column.append(dict(pos=[x,yy,z],state=w.get(x,yy,z)))
        rows.append(dict(id=r['id'],seed=[x,y,z],actual_nonleaf_solid_top_y=actual_top,actual_soil_height_5x5=soil,actual_nonleaf_solid_top_5x5=solid,min_four_neighbor_soil_drop=terrain_drop,top_materials=top_material,current_center_column=column,finite_owner_context=r['finite_owner_xz_overlap'],nearby_block_entities=near_be,status=status,whole_facility_or_terrain_quality_passed=False))
    report=dict(world=str(w.world),actual_objects=len(rows),rows=rows,counts=dict(Counter(r['status']for r in rows)),all_five_by_five_column_frames_read=True,actual_sections=len(w.tiles),no_new_chunks_generated=True,world_written=False,quality_acceptance=False)
    (out/'actual_global_depression_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report['counts']),flush=True)

if __name__=='__main__':main()
