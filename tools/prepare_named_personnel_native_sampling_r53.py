"""Finite read-only native sampling plan from proven named personnel geometry."""
from pathlib import Path
import argparse, collections, gzip, hashlib, json, math
import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra
from query_blocks import read_box, iter_block_entities, AIR


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();base=a.base.resolve();world=base/'WORLD';out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1];peer=root/'.Codex/map_complete_20261013/pyramid_connectivity_sol'
    proof=json.loads((peer/'HIGHEST_COMPLETE_TEN_FLOOR_RING_GHOST_PROOF.json').read_text('utf8'))
    volume=np.load(peer/'current_navigation/components/hq/CURRENT.npz');raw=volume['states'];pal=list(map(str,volume['palette']));origin=volume['origin']
    samples={};barriers={};groups=[]
    def add(point,role,floor,clear=True,drop=.12,condition=None):
        key=tuple(round(float(x),4)for x in point)
        if key not in samples:samples[key]=dict(id=f'point/{len(samples)}',feet=list(key),roles=[],named_floor_y=floor,expected_body_clear=clear,body_radius=.3,body_height=1.8,floor9rays=dict(offset_xz=[-.27,0,.27],all9_hits_required=True,max_drop=drop,ray_from_y_offset=.02,ray_to_y_offset=-.90),condition=condition)
        if role not in samples[key]['roles']:samples[key]['roles'].append(role)
        samples[key]['floor9rays']['max_drop']=max(samples[key]['floor9rays']['max_drop'],drop)
        return samples[key]['id']
    def static(q):
        x,y,z=np.asarray(q,dtype=int)-origin
        return pal[int(raw[y,z,x])]if 0<=y<raw.shape[0]and 0<=z<raw.shape[1]and 0<=x<raw.shape[2]else'OUTSIDE_CURRENT_ASSOCIATED_VOLUME'
    for row in proof['floor_paths']:
        floor=row['y'];routes=[]
        for label in ('north','south','whole_four_sides'):
            if label in row:routes.extend([(label,r)for r in row[label]]if label=='whole_four_sides'else[(label,row[label])])
        local=[]
        for label,route in routes:
            for q,Q in zip(route,route[1:]):
                dx,dz=Q[0]-q[0],Q[2]-q[2]
                assert abs(dx)+abs(dz)==1,('Proven ring edge must be cardinal',q,Q)
                stair=q[1]!=Q[1]or'stairs'in static([q[0],q[1]-1,q[2]])or'escalator_step'in static([q[0],q[1]-1,q[2]])
                for lane in(-1,0,1):
                    first=[q[0]-dz*lane+.5,q[1],q[2]+dx*lane+.5];last=[Q[0]-dz*lane+.5,Q[1],Q[2]+dx*lane+.5]
                    role=f'pyramid/floor{floor}/{label}/lane{lane}'
                    local.append(add(first,role,floor,drop=.65 if stair else .12))
                    local.append(add(last,role,floor,drop=.65 if stair else .12))
                    # A stair has two real heights; mid-edge support is measured
                    # at the upper integer foot datum, with the actual half-riser
                    # tolerance. No fake flat bearing is implied.
                    middle=[(first[0]+last[0])/2,max(first[1],last[1]),(first[2]+last[2])/2]
                    local.append(add(middle,role+'/native_boundary_midpoint',floor,drop=.65 if stair else .12))
                for side in(-2,2):
                    at=(q[0]-dz*side,q[1],q[2]+dx*side);s=static(at)
                    if any(name in s for name in('guard','iron_bars','edge_rail','clear_glass','wall_panel','one_way_glass')):
                        barriers.setdefault(at,dict(pos=list(at),role=f'original_named_ring/floor{floor}/existing_enclosure_or_guard',expected_state=s,native_shape_nonempty_required=True,not_an_entry_or_walk_target=True))
        groups.append(dict(id=f'pyramid/floor{floor}/complete_named_ring_all3_lanes',named_floor_y=floor,points=sorted(set(local)),source='Existing valid ten-floor ring proof; every cardinal edge plus both transverse lanes and actual midpoint; no new public area'))
    stair=[]
    for i in range(24):
        for x in range(5,8):stair.append(add([x+.5,-457+i,301+i+.5],'highest/24_original_approved_treads_all3_lanes',-434,drop=.65))
    groups.append(dict(id='highest/internal24treads_all3_lanes',points=stair,source='Root-applied218 exact candidate'))
    for name in('HIGHEST_INTERNAL_STAIR_CANDIDATE_V2.json','R47_DRY_BRIDGES_CANDIDATE.json'):
        candidate=json.loads((peer/name).read_text('utf8'))
        for r in candidate['cells']:
            if 'tv_personnel_guard_r44' in r['after']:barriers[tuple(r['pos'])]=dict(pos=r['pos'],role='new_highest_stair_guard'if'stair'in name.lower()else'new_named_dry_bridge_guard',expected_state=r['after'],native_shape_nonempty_required=True,not_an_entry_or_walk_target=True)
    for x in(24,57):
        local=[]
        for xx in range(x,x+4):
            for z in range(-115,-89):local.append(add([xx+.5,-468,z+.5],f'r47/two_named_dry_bridge/core{x}/whole4wide',-468))
            for z in range(-115,-90):local.append(add([xx+.5,-468,z+1.],f'r47/two_named_dry_bridge/core{x}/actual_boundary_midpoint',-468))
        groups.append(dict(id=f'r47/named_bridge{x}_whole4lanes_and_two_original_ports',points=local,source='Root-applied334 candidate and actual original landings; all LCL cells excluded'))
    lift=json.loads((world/'personnel_lifts_r52.json').read_text('utf8'));be=[];landing=[]
    for item in lift['lifts']:
        for f in item['floors']:
            door=np.array([d['pos']for d in f['landing_doors']],float);at=door.mean(0);at[1]=f['approach_y'];at+=dict(north=[0,0,-1],south=[0,0,1],west=[-1,0,0],east=[1,0,0])[f['exit']]
            block=np.floor(at).astype(int);point=[block[0]+.5,f['approach_y'],block[2]+.5]
            sid=add(point,'native_registered_lift25/ordinary_outside_port',f['approach_y'])
            landing.append(dict(lift_id=item['id'],label=f['label'],controller=f['controller'],sample=sid,restricted=f['restricted'],landing_door_cells=f['landing_doors'],cabin_door_cells=f['cabin_doors'],closed_or_open_is_observed_actual_state_only=True))
            be.append(dict(pos=f['controller'],role='native_original_controller',expected_id='movingelevators:elevator_tile',expected_fields={'data.name':f['label']},native_group_axes=[f['controller'][0],f['controller'][2]],native_floor_y=f['cabin'][1]))
    interactions=json.loads((peer/'NATIVE_VANILLA_INTERACTION_PLAN.json').read_text('utf8'))
    for t in interactions['three_meaningful_rides']:
        add(t['candidate_start']['feet'],'three_actual_lift_calls/safe_outside_stand',t['from_y'])
        call=t['outside_call'];q=call['position'];tag=dict(iter_block_entities(world,'projectseele:geofront',tuple(q),tuple(q))).get(tuple(q))
        be.append(dict(pos=q,role='vanilla_call_or_native_reader',expected_state=call['state'],expected_id=None if tag is None else str(tag['id']),expected_complete_nbt=None if tag is None else tag.snbt()))
        inside=t['inside_vanilla_useItemOn'];q=inside['fresh_original_button_at_initial_park'];tag=dict(iter_block_entities(world,'projectseele:geofront',tuple(q),tuple(q)))[tuple(q)]
        be.append(dict(pos=q,role='current_original_inside_button',expected_id='movingelevators:button_tile',expected_complete_nbt=tag.snbt(),facing_storage='3D ordinal; controllerFacing is separately2D'))
        for s in inside['safe_interior_stands']:add(s['feet'],'three_original_current_parked_cabins/inside_safe_stand',s['feet'][1],condition='Only expect this point when the same original native car is still parked at this initial Y; later rides require an actual re-observation')
    for reader in interactions['highest_room']['readers']:
        add(reader['standing']['feet'],'highest/original_reader_actual_safe_stand',-422)
        be.append(dict(pos=reader['position'],role='highest_original_reader',expected_id='projectseele:nerv_access_reader',expected_fields={'Gate':reader['gate_packed'],'Clearance':3,'ChamberRole':reader['role'],'AlongX':True,'Width':3,'Height':3,'Linked':True},expected_complete_nbt=reader['original_reader_nbt']))
    saved=np.load(peer/'current_navigation/combined/CURRENT_GRAPH.npz');coords=saved['coords'];g=sparse.csr_matrix((saved['walking_weights'],saved['walking_indices'],saved['walking_indptr']),shape=(len(coords),len(coords)))
    travel=json.loads((base/'current_travel/TRAVEL_CANDIDATE.json').read_text('utf8'));entry=next(r for r in travel['destinations']if r['key']=='station')['position'];ids={tuple(map(int,q)):i for i,q in enumerate(coords)}
    first=tuple(math.floor(c)for c in entry);last=(9,-541,258);s,t=ids[first],ids[last]
    dist,previous=dijkstra(g,directed=False,indices=s,return_predecessors=True);assert np.isfinite(dist[t]),'Current station-to-Main has no ordinary walking route'
    route=[t]
    while route[-1]!=s:route.append(int(previous[route[-1]]))
    path=coords[route[::-1]].astype(int).tolist();route_ids=[add([x+.5,y,z+.5],'station_travel_arrival_to_Main/walking_only',y,drop=.65 if any(abs(v[1]-y)==1 for v in path[max(0,i-1):i+2])else .12)for i,(x,y,z)in enumerate(path)]
    walk=dict(world_written=False,native_verified=False,start_travel_arrival=entry,start_node=list(first),end_node=list(last),walking_metres=float(dist[t]),points=path,physical_input_centres=[[x+.5,y,z+.5]for x,y,z in path],train_edges_used=0,lift_edges_used=0,teleport_traversal_pass=False,source='Current exact walking-only graph; use ordinary movement after arrival, doors retain real native operation/credential rules')
    (out/'STATION_TO_MAIN_ORDINARY_WALK.json').write_text(json.dumps(walk,ensure_ascii=False,indent=2)+'\n','utf8')
    groups.append(dict(id='station_travel_arrival_to_Main/ordinary_walking_only',points=route_ids,source='Walking graph only, no train or lift jump'))
    receipt=json.loads((root/'artifacts/r52_unified_candidate55/BUILD_RECEIPT.json').read_text('utf8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    plan=dict(schema='projectseele.r53.named-personnel-native-sampling.v1',world=str(world),world_written=False,native_verified=False,actual_traversal_verified=False,dimension='projectseele:geofront',final_jar_sha256=receipt['sha256'],final_build_receipt=str(root/'artifacts/r52_unified_candidate55/BUILD_RECEIPT.json'),navigation_sha256=sha(world/'nerv_routes_r24.json.gz'),personnel_manifest_sha256=sha(world/'personnel_lifts_r52.json'),directory_fingerprint=lift['directory_fingerprint'],sampling_policy='Read-only native collision and9 downward block-collision support rays on existing named floor/ring/port geometry only; unloaded chunks are NOT_LOADED, never forced; this is not actual traversal or permission success',body_probe_count=len(samples),barrier_probe_count=len(barriers),block_entity_count=len(be),named_groups=groups,body_probes=list(samples.values()),barrier_probes=list(barriers.values()),block_entity_probes=be,native25_landings=landing,highest_initial_state=interactions['highest_room']['initial_saved_state'],station_to_main_walk=str(out/'STATION_TO_MAIN_ORDINARY_WALK.json'),scope_counts=dict(actual_pyramid_floors=10,ring_width_lanes=3,highest_treads=24,new_guard_cells=130,named_dry_bridges=2,dry_width_lanes=4,native_lift_landings=25,real_lift_interactions=3,highest_readers=2))
    (out/'NATIVE_SAMPLING_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n','utf8')
    print(json.dumps(dict(native_verified=False,body_probes=len(samples),barriers=len(barriers),BEs=len(be),ordinary_walk_nodes=len(path),ordinary_walk_metres=float(dist[t]),output=str(out)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
