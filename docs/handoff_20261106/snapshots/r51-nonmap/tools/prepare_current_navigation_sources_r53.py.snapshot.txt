"""Current Root frames and exact owned floors for inherited personnel nodes.

No save writes, public-air inference, stale R52 constants or transport edges.
"""
from pathlib import Path
import argparse, collections, gzip, hashlib, json
import numpy as np
from query_blocks import iter_selected_sections, AIR
from r52_spatial_plan import Frame
from regional_voxels import canonical_state


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();base=a.base.resolve();world=base/'WORLD';out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    raw=(world/'nerv_routes_r24.json.gz').read_bytes();old=json.loads(gzip.decompress(raw))
    assert not old.get('r52_navigation') and not old.get('r53_navigation'), 'Use the frozen original source, never remigrate an installed graph'
    plan=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    frames={name:Frame(**fields)for name,fields in plan['components'].items()}
    coords=np.asarray(old['nodes'],np.int32)[:,:3];current=coords.copy();owners=np.full(len(coords),'retained',dtype='U20')
    def from_mask(relative,key):
        data=np.load(base/relative);mask=data[key];q=coords-[0,1,0]-data['origin'];shape=np.asarray(mask.shape)[[2,0,1]]
        inside=np.flatnonzero(((q>=0)&(q<shape)).all(axis=1));found=np.zeros(len(coords),bool);v=q[inside]
        found[inside]=mask[v[:,1],v[:,2],v[:,0]];return found
    masks=[('hangar',from_mask('hangar_component/owner_mask.npz','move')),
           ('hq_station',from_mask('hq_station_component/OWNERSHIP.npz','owned')),
           ('pyramid',from_mask('pyramid_component/owner_mask.npz','owned'))]
    terminal=json.loads((base/'terminal_move/complete_terminal_translation/PLAN.json').read_text('utf8'))
    lo,hi=map(np.asarray,terminal['source_envelope']);foot=coords-[0,1,0]
    masks.append(('terminal',((foot>=lo)&(foot<=hi)).all(axis=1)))
    for name,mask in masks:
        for i in np.flatnonzero(mask):
            q=frames[name].block(coords[i]);assert owners[i]=='retained' or tuple(current[i])==q, ('Different component owners overlap',i)
            current[i]=q;owners[i]=name
    retired=from_mask('hangar_component/owner_mask.npz','retire')&(owners=='retained')
    spatial=json.loads((world/'spatial_contract_r21.json').read_text('utf8'))
    retired_sections=[r['original']for r in spatial.get('retired_declarations',[])if r.get('kind')=='sections'and r.get('status') in ('RETIRED_BY_ROOT_R53','R53_ORIGINAL_RIGIDLY_MOVED_TO_DEEP_HANGAR')]
    for s in retired_sections:
        if s['id']not in ('pyramid_launch_link','r47_experiment_west_lift_connection'):continue
        for x,X,z,Z in s['rects']:
            retired|=(owners=='retained')&(coords[:,0]>=x)&(coords[:,0]<=X)&(coords[:,2]>=z)&(coords[:,2]<=Z)&(coords[:,1]>=s['floor'])&(coords[:,1]<=s['floor']+s['height'])
    selected=collections.defaultdict(set);wanted=collections.defaultdict(set)
    for x,y,z in current:
        for dy in (-1,0,1):
            q=(int(x),int(y)+dy,int(z));key=(q[0]//16,q[2]//16,q[1]//16)
            wanted[key].add(q);selected[key[:2]].add(key[2])
    states={}
    for cx,cz,sy,pal,idx in iter_selected_sections(world,'projectseele:geofront',selected):
        for q in wanted[cx,cz,sy]:states[q]=pal[int(idx[((q[1]&15)<<8)|((q[2]&15)<<4)|(q[0]&15)])]
    shapes={canonical_state(k):v for k,v in json.loads((world/'native_collision_shapes.json').read_text('utf8')).items()}
    root=Path(__file__).resolve().parents[1]
    shape_sources=[]
    for name in ('CURRENT_PRODUCTION_SUPPLEMENTAL_SHAPES.json','CURRENT_PRODUCTION_REBASED_SHAPES.json','GATE14_RESOLVED_PRODUCTION_SHAPES.json'):
        path=root/'.Codex/map_complete_20261013/route_audit/prelaunch_world_current'/name
        data=json.loads(path.read_text('utf8'))
        for key,value in data['rows'].items():shapes[canonical_state(key)]=value['native_boxes']
        shape_sources.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),scope=data['scope']))
    strip=root/'src/main/java/com/projectseele/world/FacilityStripLightR47.java'
    strip_code=strip.read_text('utf8')
    assert 'extends Block' in strip_code and 'getShape(' not in strip_code and 'getCollisionShape(' not in strip_code
    assert 'projectseele:nerv_strip_light' in shapes
    for lit in ('true','false'):shapes[f'projectseele:nerv_strip_light[lit={lit}]']=shapes['projectseele:nerv_strip_light']
    shape_sources.append(dict(path=str(strip),sha256=hashlib.sha256(strip.read_bytes()).hexdigest(),proof='LIT only state definition/default; no shape/collision override; registered full Block material geometry unchanged'))
    operations={}
    doorfile=world/'r52/headquarters_command_doors.json'
    if doorfile.exists():
        for door in json.loads(doorfile.read_text('utf8'))['doors']:
            for q in door['aperture']:operations[tuple(q)]=('minecraft:air','declared_original_command_sliding_door')
    for gate in json.loads((world/'r44_public_station_gates.json').read_text('utf8'))['gates']:
        operations[tuple(gate['position'])]=(gate['open_state'],'declared_original_native_public_gate')
    lifts=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    for lift in lifts['lifts']:
        for floor in lift['floors']:
            for role in ('landing_doors','cabin_doors'):
                for door in floor[role]:operations[tuple(door['pos'])]=('minecraft:air','declared_lift_port_requires_car_and_real_opening')
    for door in lifts['office_access']['room_controls']['pilot_guard_doors']:
        q=door['lower']
        for dy in (0,1):
            pos=(q[0],q[1]+dy,q[2]);current_state=states.get(pos)
            if current_state and 'city_personnel_door[' in current_state:operations[pos]=(current_state.replace('open=false','open=true'),'declared_original_pilot_guard_door')
    unknown=collections.Counter();aliases=set()
    def shape(s):
        if s in shapes:return shapes[s]
        if s.split('[')[0]in AIR|{'minecraft:light'}:return []
        if s.startswith('mtr:escalator_step[')and'orientation=flat'in s:return [[0,0,0,1,.9375,1]]
        if s.startswith('projectseele:entry_plug_bridge_deck['):
            name,props=s[:-1].split('[',1);alias=name+'['+','.join(v for v in props.split(',')if not v.startswith('unit='))+']'
            if alias in shapes:aliases.add(s);return shapes[alias]
        unknown[s]+=1;return None
    def free(boxes,height):return boxes is not None and not any(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<height for b in boxes)
    valid=[];rejected=[];witnesses=[];conditional=[]
    for i,q in enumerate(current):
        q=tuple(map(int,q))
        if retired[i]:rejected.append((i,'retired_original_component'));continue
        samples=[states.get((q[0],q[1]+dy,q[2]),'UNMEASURED')for dy in(-1,0,1)]
        operated=[operations.get((q[0],q[1]+dy,q[2]),(s,''))[0]for dy,s in zip((-1,0,1),samples)]
        floor,feet,head=map(shape,operated)
        supported=floor is not None and any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3]and b[2]<=.5<=b[5]for b in floor)
        thin=any(t in samples[0]for t in('_wall[','_fence[','_bars[','_sign[','station_departure_board','nerv_direction_panel','escalator_side','chair','stool','command_seat','nerv_edge_rail'))
        fluid=any(s.startswith(('minecraft:water','minecraft:lava','projectseele:lcl'))for s in samples[1:])
        if supported and not thin and not fluid and free(feet,1)and free(head,.79):
            valid.append(i)
            if operated!=samples:conditional.append(dict(original_index=i,current=list(q),actual=samples,operated=operated,requires_actual_operation=True,native_operation_verified=False))
        else:
            reason='unknown_current_native_shape' if floor is None or feet is None or head is None else 'real_current_collision_or_support'
            rejected.append((i,reason))
            witnesses.append(dict(original_index=i,owner=str(owners[i]),original=coords[i].tolist(),current=list(q),states=samples,operated=operated,supported=supported,foot_free=free(feet,1),head_free=free(head,.79),reason=reason))
    np.savez_compressed(out/'ORIGINAL_NODE_MIGRATION.npz',original=coords,current=current,ownership=owners,valid_original_indices=np.asarray(valid,np.int32),retired=retired)
    with gzip.open(out/'CURRENT_SOURCE_STATES.json.gz','wt',encoding='utf8')as f:json.dump([dict(pos=q,state=s)for q,s in sorted(states.items())],f,separators=(',',':'))
    (out/'CURRENT_BOUND_SHAPES.json').write_text(json.dumps(shapes,separators=(',',':')),'utf8')
    (out/'STILL_MISSING_NATIVE_STATES.json').write_text(json.dumps(sorted(unknown),indent=2)+'\n','utf8')
    (out/'CURRENT_INVALID_ORIGINAL_NODES.json').write_text(json.dumps(dict(nodes=witnesses,conditional_nodes=conditional,shape_sources=shape_sources),ensure_ascii=False,indent=2)+'\n','utf8')
    good=set(valid);goals=[dict(id=r['id'],name=r['name'],original=coords[r['node']].tolist(),current=current[r['node']].tolist(),current_safe=r['node']in good)for r in old['goals']]
    report=dict(world=str(world),world_written=False,native_verified=False,original_graph_sha256=hashlib.sha256(raw).hexdigest(),root_plan_sha256=hashlib.sha256((base/'ROOT_SPATIAL_PLAN.json').read_bytes()).hexdigest(),frames={k:v.__dict__ for k,v in frames.items()},original_nodes=len(coords),component_counts=dict(collections.Counter(owners.tolist())),current_safe_inherited_nodes=len(valid),conditional_operation_nodes=len(conditional),rejected_counts=dict(collections.Counter(reason for _,reason in rejected)),unknown_states=dict(unknown),paint_only_shape_aliases=sorted(aliases),rejected_examples=witnesses[:80],goals=goals,scope='Only inherited declared original nodes, exact original owner masks and current explicit component frames; no new public air',pending=['merge exact current HQ ring/stair graph, two named dry bridges and current deep named galleries','rebuild native boundary edges and 25 declared lift landings','player TRAIN connections separate from NPC walking; final exact install/readback'])
    (out/'SOURCE_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({k:v for k,v in report.items()if k not in('rejected_examples','paint_only_shape_aliases','pending')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
