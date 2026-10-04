"""All operating-station belts and80gate buffers; native motion is separate from shape.

Reads finite authored station bounds and the installed gate manifest, using the
central query_blocks reader only. No world mutation and no guessed station.
"""
from pathlib import Path
from collections import defaultdict,deque,Counter
import argparse,hashlib,json,math
import numpy as np
from measure_world_r40 import MeasuredWorld,properties
from audit_facility_transit_r44 import Geometry
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/station_dynamic_waiting_v1'
GATES=ROOT/'artifacts/rebuild_r44/facility_transit_r44/public_station_gates_v2/r44_public_station_gates.json'
CASES=GATES.parent/'native_cases.json'
AHEAD={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
RIGHT={'north':(1,0),'south':(-1,0),'east':(0,1),'west':(0,-1)}


def main(gates_path=GATES,cases_path=CASES,out_path=OUT,world_path=WORLD):
    global GATES,CASES,OUT,WORLD
    GATES,CASES,OUT=map(Path,(gates_path,cases_path,out_path))
    WORLD=Path(world_path)
    OUT.mkdir(parents=True,exist_ok=True)
    gates=json.loads(GATES.read_text('utf8'))['gates'];cases=json.loads(CASES.read_text('utf8'))
    ids={r['station_id'] for r in gates};assert len(gates)==80 and len(ids)==19 and len(cases)==160
    assert {tuple(c['actualAutomaticGate']) for c in cases}=={tuple(r['position']) for r in gates},'Gate cases must match the exact current finite manifest revision'
    catalogue=json.loads((ROOT/'artifacts/repair_r43/facility_catalogue/catalogue.json').read_text('utf8'))
    stations=[s for s in catalogue['stations'] if s['id'] in ids];assert len(stations)==19
    w=MeasuredWorld(WORLD)
    for s in stations:
        lo,hi=np.array(s['bounds']);w.box(tuple(map(int,lo-6)),tuple(map(int,hi+6)))
    for gate in gates:w.around(gate['position'],6)
    w.load();steps={};sides={}
    def collect(tiles):
        for (cx,sy,cz),(palette,indices) in tiles.items():
            matches=np.array([s.startswith(('mtr:escalator_step[','mtr:escalator_side[')) for s in palette])
            if not matches.any():continue
            for iy,iz,ix in np.argwhere(matches[indices].reshape(16,16,16)):
                q=(cx*16+int(ix),sy*16+int(iy),cz*16+int(iz));state=palette[int(indices[(iy*16+iz)*16+ix])]
                (steps if state.startswith('mtr:escalator_step[') else sides)[q]=state
    collect(w.tiles)
    # Section palettes can expose part of an adjacent already-owned belt.
    # Follow its existing native mechanism, never truncate at an audit box.
    closure=[]
    for iteration in range(20):
        extra=MeasuredWorld(WORLD)
        for q in steps:extra.around(q,3)
        for chunk,ys in list(extra.selected.items()):
            ys.difference_update(w.selected.get(chunk,()))
            if not ys:del extra.selected[chunk]
        if not extra.selected:break
        extra.load();before=len(steps);collect(extra.tiles)
        for chunk,ys in extra.selected.items():w.selected[chunk].update(ys)
        w.tiles.update(extra.tiles);w.status.update(extra.status)
        closure.append({'iteration':iteration,'new_selected_sections':sum(map(len,extra.selected.values())),
            'new_native_step_cells':len(steps)-before})
    else:raise RuntimeError('Connected existing native belt did not close in20 measured iterations')
    g=Geometry(w)
    native_shapes=WORLD/'r44_public_station_gate_shapes.json'
    if native_shapes.exists():
        native=json.loads(native_shapes.read_text('utf8'))
        g.shapes.update({canonical_state(k):value for k,value in native['collision_shapes'].items()})
    # Delivery may merge these native states into the main shape snapshot.
    # Missing states remain UNKNOWN; an absent supplemental file is not air.
    def support(point):
        rows={}
        for dx in (-.299,0,.299):
            for dz in (-.299,0,.299):
                q=tuple(map(int,np.floor(np.array(point)+[dx,-.04,dz])))
                state=w.block(q);spec=properties(state) if state and state.startswith('mtr:escalator_step[') else None
                rows[q]={'position':q,'state':state,'native_step_status_enabled':bool(spec and spec.get('status')=='true'),
                    'native_orientation':None if spec is None else spec.get('orientation'),
                    'native_add_velocity_consumer':bool(spec and spec.get('status')=='true'),
                    'known_native_shapes':g.boxes(state)}
        return list(rows.values())
    gate_buffers=[];active_hits=[]
    for i,case in enumerate(cases):
        row={'case_index':i,'id':case['id'],'gate':case['actualAutomaticGate'],'endpoints':[]}
        for label,point in zip(('staging','finish'),case['path']):
            support_rows=support(point);enabled=[r for r in support_rows if r['native_step_status_enabled']]
            item={'role':label,'point':point,'actual_footprint_support':support_rows,
                'static_standing_is_not_motion_proof':bool(enabled),'requires_actual_stationary_native_check':bool(enabled)}
            row['endpoints'].append(item)
            if enabled:active_hits.append({'case_index':i,'id':case['id'],'gate':case['actualAutomaticGate'],**item})
        gate_buffers.append(row)
    remaining=set(steps);components=[];orphans=[]
    while remaining:
        seed=min(remaining);spec=properties(steps[seed]);facing=spec['facing'];direction=spec['direction'];ahead=AHEAD[facing];right=RIGHT[facing]
        seen={seed};queue=deque([seed]);remaining.remove(seed)
        while queue:
            x,y,z=queue.popleft()
            neighbours=[(x+sign*ahead[0],y+dy,z+sign*ahead[1]) for sign in (-1,1) for dy in (-1,0,1)]
            neighbours.extend((x+sign*right[0],y,z+sign*right[1]) for sign in (-1,1))
            for p in neighbours:
                if p not in remaining:continue
                peer=properties(steps[p])
                if peer['facing']!=facing or peer['direction']!=direction:continue
                remaining.remove(p);seen.add(p);queue.append(p)
        pairs={};component_orphans=[]
        for q in sorted(seen):
            p=properties(steps[q]);sign=1 if p['side']=='left' else -1
            peer=(q[0]+sign*right[0],q[1],q[2]+sign*right[1]);ps=properties(steps[peer]) if peer in seen else {}
            if ps.get('orientation')!=p['orientation'] or ps.get('side')==p['side'] or peer not in seen:
                error={'position':q,'state':steps[q],'expected_peer':peer,'actual':steps.get(peer)}
                orphans.append(error);component_orphans.append(error)
            elif p['side']=='left':pairs[q]=peer
        # Geometric start/end are separate from the opposite native travel
        # direction. Each complete two-width endpoint gets both buffer rows.
        endpoints=[]
        for sign in (-1,1):
            rank=max(sign*(q[0]*ahead[0]+q[2]*ahead[1]) for q in seen)
            tips=[q for q in seen if sign*(q[0]*ahead[0]+q[2]*ahead[1])==rank]
            buffer=[]
            for tip in tips:
                for distance in (1,2):
                    point=[tip[0]+sign*distance*ahead[0]+.5,tip[1]+1.,tip[2]+sign*distance*ahead[1]+.5]
                    q=tuple(map(math.floor,point));standing=g.standing(q);support_rows=support(point)
                    is_native=any(r['native_add_velocity_consumer'] for r in support_rows)
                    buffer.append({'distance_m':distance,'point':point,'standing':standing,
                        'native_motion_support':is_native,'ordinary_stationary_floor':standing['status']=='STATIC_STANDING' and not is_native,
                        'support':support_rows})
            endpoints.append({'geometric_sign':sign,'two_width_native_tip':tips,'two_rows_outside_mechanism':buffer,
                'full_static_two_width_two_row_buffer':len(tips)==2 and all(r['ordinary_stationary_floor'] for r in buffer)})
        lo=np.asarray(list(seen)).min(0);hi=np.asarray(list(seen)).max(0)
        owner=[s['id'] for s in stations if np.all(hi>=np.array(s['bounds'][0])) and np.all(lo<=np.array(s['bounds'][1]))]
        components.append({'id':f'r44/native_station_belt/{seed[0]}_{seed[1]}_{seed[2]}','station_ids':owner,
            'facing':facing,'direction':direction,'complete_step_cells':[[*q,steps[q]] for q in sorted(seen)],
            'actual_attached_side_cells':[[*q,sides[q]] for q in sorted(sides) if (q[0],q[1]-1,q[2]) in seen],
            'complete_native_pairs':len(pairs),'orphan_halves':component_orphans,'endpoints':endpoints,
            'operation_proof':'UNVERIFIED actual native travel, disembark, static wait and opposite direction must be tested'})
    report={'world':str(WORLD.resolve()),'operating_station_denominator':19,'gate_cells':80,'gate_cases':160,'gate_buffer_footprints':gate_buffers,
        'active_native_step_gate_buffers':active_hits,'station_native_belt_components':components,'orphan_step_halves':orphans,
        'step_count':len(steps),'side_count':len(sides),'connected_component_closure':closure,
        'retired_P1_excluded':True,'world_write_performed':False,
        'native_dynamic_consumer':'Pinned MTR4.0.5 BlockEscalatorStep.onEntityCollision2 calls addVelocity(.1 along facing/direction) whenever status=true; shapes alone do not encode it',
        'native_still_receipt':'public_gate_client_lifecycle/20261001_044009 case122 reproduced uncontrolled east drift with keys0/ACK NONE/vehicle NONE; landing_top case120 passed actual staging, but all enabled native surfaces remain separate audit entries',
        'scope_limit':'Finite whole authored19station bounds expanded6m for measured mechanism endpoints; overlapping adjacent circulation devices are included, not treated as station ownership by mere empty space',
        'unknown_shapes':sorted(g.unknown),'native_passed':False,'visual_passed':False,
        'source_sha256':{'gate_manifest':hashlib.sha256(GATES.read_bytes()).hexdigest(),'gate_cases':hashlib.sha256(CASES.read_bytes()).hexdigest()}}
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'components':len(components),'steps':len(steps),'sides':len(sides),'orphans':len(orphans),
        'gate_buffer_enabled_native_supports':len(active_hits),'affected_case_indices':sorted({r['case_index'] for r in active_hits}),
        'without_two_by_two_static_buffer':sum(not end['full_static_two_width_two_row_buffer'] for c in components for end in c['endpoints']),
        'unknown_shapes':len(g.unknown),'world_write_performed':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--gates',type=Path)
    parser.add_argument('--world',type=Path,default=WORLD)
    parser.add_argument('--cases',type=Path,default=CASES);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();main(args.gates or args.world/'r44_public_station_gates.json',args.cases,args.out,args.world)
