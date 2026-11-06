"""Remeasure all published road columns against the actual R52 block shapes.

The inherited profile supplies surveyed road ownership/height, never a pass.
Later station uses are reported for component review, not blindly cleared.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json, hashlib, math, time
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from query_blocks import iter_selected_sections, AIR
from regional_voxels import canonical_state
from r52_spatial_plan import BASE

SOURCE=Path('D:/eva/artifacts/rebuild_r45/terrain_global_agent/roads/full_width_structure.columns.npz')
OUT=BASE/'final_map_audit/full_road_columns'

def main():
    start=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    assert not (OUT/'CURRENT_ROAD_COLUMNS.json').exists(), 'Use the existing actual receipt'
    a=np.load(SOURCE);coords=a['coordinates'];feet=a['actual_feet'];oldflags=a['flags']
    world=BASE/'WORLD_R52';shapes={canonical_state(k):v for k,v in json.loads((world/'native_collision_shapes.json').read_text()).items()}
    groups=defaultdict(list)
    for i,(x,z) in enumerate(coords):groups[int(x)//512,int(z)//512].append(i)
    issues=[];counts=Counter();unknown=Counter();newflags=np.zeros(len(coords),np.uint8)
    revisedfeet=np.full(len(coords),np.nan,np.float32)
    empty=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern','minecraft:dandelion','minecraft:poppy','minecraft:cornflower'}
    for region,indices in sorted(groups.items()):
        selected=defaultdict(set)
        for i in indices:
            x,z=map(int,coords[i]);y=math.floor(float(feet[i]));selected[x//16,z//16].update(range((y-2)//16,(y+6)//16+1))
        tiles={}
        for cx,cz,sy,pal,ix in iter_selected_sections(world,'projectseele:geofront',selected,skip_unfinished=True):tiles[cx,cz,sy]=pal,ix
        def get(x,y,z):
            t=tiles.get((x//16,z//16,y//16))
            return t[0][t[1][(y%16)*256+(z%16)*16+x%16]] if t else None
        def box(state):
            if state in empty:return []
            if state is None:return None
            q=shapes.get(state)
            if q is None:unknown[state]+=1
            return q
        for i in indices:
            x,z=map(int,coords[i]);f=float(feet[i]);base=math.floor(f-.001);st=get(x,base,z);shape=box(st)
            floor=[] if shape is None else [base+b[4] for b in shape if b[0]<=.2 and b[3]>=.8 and b[2]<=.2 and b[5]>=.8 and abs(base+b[4]-f)<=.501]
            if not floor:
                issues.append(dict(position=[x,f,z],kind='FLOOR_COMPONENT_REVIEW',state=st,inherited_flags=int(oldflags[i])));counts['floor_review']+=1;continue
            f=min(floor,key=lambda q:abs(q-f));revisedfeet[i]=f;newflags[i]|=1
            obstruction=[];unmeasured=False
            for y in range(math.floor(f),math.ceil(f+6)):
                state=get(x,y,z);ss=box(state)
                if ss is None:unmeasured=True;continue
                if any(b[0]<.8 and b[3]>.2 and b[2]<.8 and b[5]>.2 and y+b[1]<f+6-.001 and y+b[4]>f+.001 for b in ss):
                    obstruction.append((y,state,min(y+b[1] for b in ss if b[3]>.2 and b[0]<.8 and b[5]>.2 and b[2]<.8)))
            player=[p for p in obstruction if p[2]<f+1.8-.001]
            if not player and not unmeasured:newflags[i]|=2
            if not obstruction and not unmeasured:newflags[i]|=4
            if player or unmeasured:
                counts['player_review']+=1;issues.append(dict(position=[x,f,z],kind='PLAYER_COMPONENT_REVIEW' if player else 'UNMEASURED_SHAPE',obstruction=player,inherited_flags=int(oldflags[i])))
            elif obstruction and oldflags[i]&16:
                counts['vehicle_review']+=1;issues.append(dict(position=[x,f,z],kind='VEHICLE_COMPONENT_REVIEW',obstruction=obstruction,inherited_flags=int(oldflags[i])))
        print('roads',region,'columns',len(indices),'read',sum(counts.values()),'review entries',flush=True)
    np.savez_compressed(OUT/'CURRENT_ROAD_COLUMNS.npz',coordinates=coords,actual_feet=revisedfeet,flags=newflags,inherited_flags=oldflags)
    report=dict(world=str(world),world_written=False,source_profile=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        full_width_declared_columns=len(coords),actual_floor_columns=int(((newflags&1)!=0).sum()),actual_player_clear_columns=int(((newflags&3)==3).sum()),
        actual_six_metre_clear_columns=int(((newflags&5)==5).sum()),counts=dict(counts),unknown_shapes=dict(unknown),issues=issues,
        seconds=time.monotonic()-start,road_art_passed=False,native_vehicle_route_passed=False,
        limits=['All inherited surveyed road columns reread, not arbitrary topmost floor panels.','Changed station/building components need explicit ownership review.','Scalar column clearance does not prove full vehicle width, support or a native journey.'])
    (OUT/'CURRENT_ROAD_COLUMNS.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('issues','limits','unknown_shapes')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
