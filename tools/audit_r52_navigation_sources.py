"""Root navigation migration inventory from original ownership and current block shapes.

This is a candidate node survey, not a routing installation or a native walk pass.
"""
import gzip,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from r52_spatial_plan import BASE,PYRAMID,HANGAR,TERMINAL,HQ_STATION
from query_blocks import iter_selected_sections
from regional_voxels import canonical_state


def main():
    world=BASE/'WORLD_R52';out=BASE/'navigation_rebuild';out.mkdir(exist_ok=True)
    raw=(world/'nerv_routes_r24.json.gz').read_bytes();old=json.loads(gzip.decompress(raw))
    coordinates=np.asarray(old['nodes'],dtype=np.int32)[:,:3];moved=coordinates.copy();ownership=np.full(len(moved),'retained',dtype='U20')
    def mask_owned(filename,key):
        d=np.load(BASE/filename);mask=d[key];q=coordinates-[0,1,0]-d['origin'];shape=np.asarray(mask.shape)[[2,0,1]]
        valid=np.flatnonzero(((q>=0)&(q<shape)).all(axis=1));hit=np.zeros(len(q),bool);at=q[valid];hit[valid]=mask[at[:,1],at[:,2],at[:,0]];return hit
    masks=[('hangar',mask_owned('hangar_component/owner_mask.npz','move'),HANGAR),
           ('hq_station',mask_owned('hq_station_component/OWNERSHIP.npz','owned'),HQ_STATION)]
    for name,low,high,frame in [('pyramid',(-90,-470,207),(150,-291,447),PYRAMID),('terminal',(-56,-647,232),(116,-516,420),TERMINAL)]:
        q=coordinates-[0,1,0];masks.append((name,((q>=low)&(q<=high)).all(axis=1),frame))
    for name,mask,frame in masks:
        for i in np.flatnonzero(mask):
            q=frame.block(coordinates[i]);assert ownership[i]=='retained'or tuple(moved[i])==q
            moved[i]=q;ownership[i]=name
    retired=mask_owned('hangar_component/owner_mask.npz','retire')&(ownership=='retained')
    selected=defaultdict(set);wanted=defaultdict(set)
    for x,y,z in moved:
        for yy in (y-1,y,y+1):selected[int(x)//16,int(z)//16].add(int(yy)//16);wanted[int(x)//16,int(z)//16,int(yy)//16].add((int(x),int(yy),int(z)))
    states={}
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        a=indices.reshape(16,16,16)
        for x,y,z in wanted[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    shapes={canonical_state(k):v for k,v in json.loads((world/'native_collision_shapes.json').read_text('utf8')).items()};unknown=Counter();aliases=set()
    def shape(state):
        if state in shapes:return shapes[state]
        if state.startswith('projectseele:entry_plug_bridge_deck['):
            # UNIT_R52 is paint-only; the exact original collision implementation is unchanged.
            name,props=state[:-1].split('[',1);alias=name+'['+','.join(p for p in props.split(',')if not p.startswith('unit='))+']'
            if alias in shapes:aliases.add(state);return shapes[alias]
        if state.split('[')[0]in('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'):return []
        unknown[state]+=1;return None
    def free(boxes,height):return boxes is not None and not any(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<height for b in boxes)
    valid=[];rejected=[]
    for i,(x,y,z)in enumerate(moved):
        if retired[i]:rejected.append((i,'retired_old_hangar'));continue
        samples=[states.get((int(x),int(y+dy),int(z)),'UNMEASURED')for dy in(-1,0,1)]
        floor,foot,head=map(shape,samples);solid=floor is not None and any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3]and b[2]<=.5<=b[5]for b in floor)
        forbidden=any(any(s.startswith(prefix)for prefix in('minecraft:water','minecraft:lava','projectseele:lcl'))for s in samples[1:])
        thin=any(t in samples[0]for t in('_wall[','_fence[','_bars[','_sign[','station_departure_board','nerv_direction_panel','escalator_side','chair','stool','command_seat','nerv_edge_rail'))
        if solid and not thin and not forbidden and free(foot,1)and free(head,.79):valid.append(i)
        else:rejected.append((i,'current_collision_or_support'))
    np.savez_compressed(out/'ORIGINAL_NODE_MIGRATION.npz',original=coordinates,current=moved,ownership=ownership,valid_original_indices=np.asarray(valid,dtype=np.int32),retired=retired)
    goals=[dict(id=g['id'],name=g['name'],old=coordinates[g['node']].tolist(),candidate=moved[g['node']].tolist(),actual_floor_candidate=g['node']in set(valid))for g in old['goals']]
    report=dict(world_written=False,native_verified=False,graph_installed=False,original_graph_sha256=hashlib.sha256(raw).hexdigest(),
        original_nodes=len(coordinates),component_counts=dict(Counter(ownership.tolist())),current_safe_node_candidates=len(valid),
        rejected_counts=dict(Counter(reason for i,reason in rejected)),unknown_states=dict(unknown),paint_only_collision_aliases=sorted(aliases),goals=goals,
        remaining=['Measure new ring connections and shared-lift approaches','Rebuild native-shape boundary edges and explicit current lift connections',
                   'Separate train journeys from walking graphs','Recompute nearest-lift and signs','Native walk/lift/reader validation and exact installed hashes'])
    (out/'SOURCE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps({k:v for k,v in report.items()if k not in('remaining','paint_only_collision_aliases')},ensure_ascii=False))


if __name__=='__main__':main()
