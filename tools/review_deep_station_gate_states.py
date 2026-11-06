"""Offline gate-state geometry and source-policy evidence for five deep stations."""
import argparse
from collections import Counter
import json
from pathlib import Path
import nbtlib
import numpy as np
from audit_hakone_station_walks import Walker
from review_underground_station_evidence import Overlay,strict_walk

def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')

def intersects(a,b):return all(a[i]<b[i+3]and a[i+3]>b[i]for i in range(3))

def main(a):
    a.out.mkdir(exist_ok=False)
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    rows=[];stations=[];errors=[];apg_pairs=[];other_dynamic=[]
    ownership=json.loads(a.manifest.read_text('utf8'))if a.manifest else None
    tags={tuple(int(t[k])for k in('x','y','z')):t for t in nbtlib.load(a.source/'devices.dat')['Devices']}
    if ownership and (ownership['schema']!=44 or ownership['service']!='existing_free_public_service'or ownership['dimension']!='projectseele:geofront'):errors.append(['public_gate_manifest_identity'])
    if ownership:
        positions=set()
        for g in ownership['gates']:
            p=tuple(g['position']);bounds=g['station_bounds']
            if p in positions or g['block']not in('mtr:ticket_barrier_entrance_1','mtr:ticket_barrier_exit_1')or not str(g['station_id']).strip()or not all(bounds[0][i]<=p[i]<=bounds[1][i]for i in range(3)):errors.append(['public_gate_manifest_global_contract',list(p)])
            positions.add(p)
    for file in sorted(a.review.glob('native-*.json')):
        report=json.loads(file.read_text('utf8'));station=dict(name=report['name'],gates=len(report['gates']));stations.append(station)
        reader=Walker(a.source,shapes).reader;arr,palette=reader.box(report['bounds']);door_states={}
        for index,state in enumerate(palette):
            if state.startswith('mtr:apg_door['):
                for iy,iz,ix in np.argwhere(arr==index):door_states[int(ix)+report['bounds'][0],int(iy)+report['bounds'][1],int(iz)+report['bounds'][2]]=state
            if state.startswith('projectseele:lift_door_interlock_r53'):
                for iy,iz,ix in np.argwhere(arr==index):other_dynamic.append(dict(station=report['name'],pos=[int(ix)+report['bounds'][0],int(iy)+report['bounds'][1],int(iz)+report['bounds'][2]],state=state,static_collision=shapes.get(state),runtime_opening_not_proved=True))
        paired=set()
        def prop(state,key):return next(s.split('=')[1]for s in state.split('[')[1][:-1].split(',')if s.startswith(key+'='))
        for p,state in sorted(door_states.items()):
            if 'half=lower'not in state or p in paired:continue
            x,y,z=p;neighbors=[(x+1,y,z),(x-1,y,z),(x,y,z+1),(x,y,z-1)]
            matches=[q for q in neighbors if q in door_states and 'half=lower'in door_states[q]and prop(door_states[q],'facing')==prop(state,'facing')and prop(door_states[q],'side')!=prop(state,'side')]
            if len(matches)!=1:errors.append(['apg_pair_geometry',list(p)]);continue
            q=matches[0];paired.update((p,q));cells=[p,q,(p[0],p[1]+1,p[2]),(q[0],q[1]+1,q[2])]
            upper_ok=all(door_states.get((cell[0],cell[1]+1,cell[2]))==door_states[cell].replace('half=lower','half=upper')for cell in(p,q))
            devices_ok=all(cell in tags and str(tags[cell]['id'])=='mtr:apg_door'for cell in cells)
            floor_ok=all((reader.state(cell[0],cell[1]-1,cell[2])or'').startswith('mtr:platform[')for cell in(p,q))
            if not upper_ok or not devices_ok or not floor_ok:errors.append(['apg_retained_pair_or_device_or_floor',list(p)])
            apg_pairs.append(dict(station=report['name'],cells=[list(c)for c in cells],states=[door_states.get(c)for c in cells],
                upper_halves_match=upper_ok,all_four_native_devices_present=devices_ok,platform_bearing_present=floor_ok,
                exported_empty_server_shapes=all(shapes.get(door_states.get(c))==[]for c in cells),
                native_open_state_not_inferred=True,live_vehicle_door_alignment_pending=True))
        for gate in report['gates']:
            x,y,z=gate['pos'];state=gate['state'];axis=0 if any(q in state for q in ('facing=east','facing=west'))else 2
            middle=[x+.5,y,z+.5];start=middle.copy();end=middle.copy();start[axis]-=1;end[axis]+=1
            route=[start,end];variants=[]
            for value in('closed','pending','open','open_concessionary'):
                key=state.replace('open=closed','open='+value)
                walker=Walker(a.source,shapes);observed=walker.reader.state(x,y,z)
                if observed!=state:errors.append(['source_gate_changed',gate['pos']])
                walker.reader=Overlay(walker.reader,{(x,y,z):key})
                forward=strict_walk(walker,route);reverse=strict_walk(walker,list(reversed(route)))
                closed=value in('closed','pending');bothclear=all(r['kind']=='strict_static_clear'for r in(forward,reverse))
                verdict=all(r['kind']!='strict_static_clear'for r in(forward,reverse))if closed else bothclear
                if not verdict:errors.append(['gate_state_geometry',gate['pos'],value])
                variants.append(dict(value=value,state=key,collision_boxes=shapes.get(key),path=route,forward=forward,reverse=reverse,
                    expected='blocking'if closed else'clear',expected_result=verdict))
            closed_boxes=shapes[state];body=[.2,0,.2,.8,1.8,.8]
            occupied=any(intersects([b[i]-.08 if i<3 else b[i]+.08 for i in range(6)],body)for b in closed_boxes)
            negative=any(intersects([b[i]-.08 if i<3 else b[i]+.08 for i in range(6)],[3.2,0,3.2,3.8,1.8,3.8])for b in closed_boxes)
            if not occupied or negative:errors.append(['occupancy_geometry',gate['pos']])
            rows.append(dict(station=report['name'],pos=gate['pos'],current_state=state,variants=variants,
                closing_sweep_contains_passenger=occupied,empty_distant_control_contains_passenger=negative,
                automatic_open_event_executed=False,occupied_hold_tick_executed=False,cold_reload_verified=False))
            if ownership:
                matches=[m for m in ownership['gates']if m['position']==gate['pos']]
                good=len(matches)==1 and matches[0]['block']==state.split('[')[0]and matches[0]['closed_state']==state
                if good:
                    row=matches[0];good=all(row['station_bounds'][0][i]<=gate['pos'][i]<=row['station_bounds'][1][i]for i in range(3))and (int(row['station_id'])%(1<<64)==int(report['native_station_id'])%(1<<64))
                rows[-1]['current_public_manifest_match']=good;rows[-1]['public_manifest_row']=matches[0]if matches else None
                if not good:errors.append(['public_manifest_gate_mismatch',gate['pos']])
    base=a.repo/'src/main/java/com/projectseele'
    code=[('world/PublicStationGatesR44.java',[
        ('finite_public_types','private static final Set<String> TYPES'),('open_schedule','private static final int OPEN_TICKS = 40'),
        ('secure_gate_precedence','if (SecureStationGateR48.collision'),('alive_player_or_staff','if (actor.isAlive()'),
        ('collision_opens','BlockState opened = withOpen'),('closed_shape_occupied_check','var shape = closed.getCollisionShape'),
        ('occupancy_margin','local.move(position).inflate(.08)'),('hold_reschedule','level.scheduleTick(position, state.getBlock(), 10)'),
        ('exact_owned_manifest','actual.equals(INSTALLED.computeIfAbsent'),('manifest_path','resolve("r44_public_station_gates.json")'),
        ('manifest_identity','document.get("schema").getAsInt() != 44')]),
        ('mixin/PublicStationGateR44Mixin.java',[('native_collision_hook','@Inject(method = "onEntityCollision2'),('native_tick_hook','@Inject(method = "scheduledTick2')]),
        ('world/SecureStationGateR48.java',[('finite_secure_coordinates','private static final Map<BlockPos,String> GATES')])]
    code += [('client/visual/HakonePlatformLifecycleR45.java',[('server_shape_does_not_certify_apg','server_shape_cannot_certify_closed_leaf'),('client_native_door_value','actual_client_APG_door_value'),('client_closed_native_shape','if (value == 0 && !boxes.isEmpty())'),('client_open_native_shape','if (value > .8 && boxes.isEmpty())')]),
        ('world/LiftDoorInterlockR53.java',[('closed_interlock_is_solid_glass','extends GlassBlock')])]
    policy=[]
    for relative,needles in code:
        p=base/relative;lines=p.read_text('utf8').splitlines()
        for label,needle in needles:
            matches=[i+1 for i,s in enumerate(lines)if needle in s]
            policy.append(dict(claim=label,file=str(p),line=matches[0]if matches else None,source_only=True))
            if not matches:errors.append(['policy_source_anchor_missing',label])
    result=dict(errors=errors,stations=stations,gates=len(rows),state_variants=len(rows)*4,directions=len(rows)*8,
        per_gate=rows,policy_source_evidence=policy,world_opened=False,world_written=False,game_or_simulator_started=False,
        public_manifest=str(a.manifest),public_manifest_total_gates=len(ownership['gates'])if ownership else None,
        apg_pairs=apg_pairs,apg_pairs_checked=len(apg_pairs),apg_leaf_blocks_checked=4*len(apg_pairs),other_dynamic_blocks=other_dynamic,
        actual_client_jar_read=False,repairs=0,live_acceptance=False,
        remaining=([]if ownership else['actual gate ownership manifest missing from supplied offline snapshots'])+['source-to-installed-class identity belongs to main agent',
            'historical collision export requires runtime confirmation','real entity collision trigger and native state update','occupied refusal tick and actor clearance',
            'exit crossing, closure and cold reload','vehicle-door alignment and live boarding'])
    write(a.out/'review.json',result)
    print('Deep gate offline checks:',len(rows),'gates,',len(rows)*4,'states,',len(errors),'errors',flush=True)
    for error in errors:print(str(error)[:500],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--manifest',type=Path)
    for n in('repo','source','review','metadata','out'):p.add_argument('--'+n,type=Path,required=True)
    main(p.parse_args())
