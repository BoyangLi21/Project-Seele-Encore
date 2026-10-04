"""Prepare all current transport/device obligations without launch or world writes."""
from pathlib import Path
from collections import Counter
import argparse
import copy
import hashlib
import json
import uuid
import nbtlib

from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45/transport_controls_agent'
WORLD=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text('utf8'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,default=WORLD);ap.add_argument('--out',type=Path,default=ART/'prepared_v1');a=ap.parse_args()
    assert ART.resolve() in a.out.resolve().parents and not a.out.exists();a.out.mkdir(parents=True)
    current=read(ART/'current_audit_v1/audit.json');native=read(ART/'current_native_snapshot.json')
    transport=read(ROOT/'artifacts/rebuild_r44/facility_transit_r44/native_transit_cases/cases.json')
    transport['world']=str(a.world.resolve());transport['current_native_snapshot_sha256']=sha(ART/'current_native_snapshot.json')
    transport['required_r45_trace']=True;transport['status']='CURRENT_PREPARED_NOT_NATIVE_VERIFIED'
    (a.out/'all38_cases.json').write_text(json.dumps(transport,ensure_ascii=False,indent=2),'utf8')
    old_lifts=read(ROOT/'artifacts/rebuild_r44/facility_transit_r44/measured_interfaces_v3/lifts.json')
    w=MeasuredWorld(a.world)
    hardware={tuple(h['position']) for lift in old_lifts for stop in lift['landings'] for h in stop['hardware']}
    points=hardware|{tuple(stop['controller']) for lift in old_lifts for stop in lift['landings']}
    for point in points:w.around(point,1)
    w.load();lo=tuple(min(p[k] for p in points) for k in range(3));hi=tuple(max(p[k] for p in points) for k in range(3))
    tags=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    lifts=copy.deepcopy(old_lifts)
    for lift in lifts:
        for stop in lift['landings']:
            q=tuple(stop['controller']);assert q in tags and str(tags[q]['id'])=='movingelevators:elevator_tile'
            stop['controller_nbt']=tags[q].snbt();stop['actual_controller_state']=w.block(q)
            stop['r45_lifecycle_verified']=False
            for h in stop['hardware']:
                q=tuple(h['position']);assert q in tags and str(tags[q]['id']).startswith('movingelevators:')
                h['nbt']=tags[q].snbt();h['actual_state']=w.block(q)
    (a.out/'all7_lift_groups_24_landings.json').write_text(json.dumps(lifts,ensure_ascii=False,indent=2),'utf8')
    staff_file=a.world/'dimensions/projectseele/geofront/data/projectseele_staff_r15.dat'
    staff=nbtlib.load(staff_file)['data']['Members'];roster=read(a.world/'nerv_staff_r15.json')
    posts={r['id']:r for r in roster['stations']};staff_rows=[]
    for member,raw in staff.items():
        value=sum((int(v)&0xffffffff)<<(96-32*i) for i,v in enumerate(raw));identity=str(uuid.UUID(int=value))
        staff_rows.append(dict(member_id=member,actual_registered_uuid=identity,registered_post=posts.get(member),entity_runtime_post_and_position_verified=False,required=['same_actual_UUID','role_permission_rejects_and_accepts','caller_owner_preserved_on_rejected_request','real_console_walk_and_press','cancel_pending_pilot_before_load','already_started_mechanics_continue_to_safe_state','return_to_registered_post','same_JVM_and_cold_reload_no_repeated_press']))
    (a.out/'all_registered_NPC_identities_and_control_obligations.json').write_text(json.dumps(staff_rows,ensure_ascii=False,indent=2),'utf8')
    gates=read(a.world/'r44_public_station_gates.json');assert len(gates['gates'])==80
    (a.out/'all80_actual_station_gates.json').write_text(json.dumps(gates,ensure_ascii=False,indent=2),'utf8')
    # R44's 50 predictions were all observed, but 49 were divergent/unverified.
    # Each old status remains explicit; no timing tolerance or source result is widened.
    inherited=[]
    for path in sorted((ROOT/'artifacts/rebuild_r44/transit_lifecycle').glob('*/result.json')):
        data=read(path)
        for item in data.get('cases',[]):
            if item.get('native_interface_pass'):inherited.append(dict(path=str(path.resolve()),sha256=sha(path),interface=item['id'],scope='One actual interface and supported exit; no all38/reload/station/gate proof'))
    inherited_lift=ROOT/'artifacts/rebuild_r44/lift_lifecycle/20261001_015604/result.json'
    inherited_boards=ROOT/'artifacts/rebuild_r44/facility_transit_r44/live_departure_audit_v1/preparation_after_owned_hangar_board_move/root_run_20261001_103506/native_result.json'
    prior=read(inherited_boards)
    evidence=dict(train_effective_inheritance=inherited,lift=dict(path=str(inherited_lift.resolve()),sha256=sha(inherited_lift),native_trips=25,unique_source_landings=24,valid_scope='Original native call, entry, car selection, ride and exit for the measured static hardware. R45 cache change, current nearby rebuilt geometry, reload, interruption, occupied doors and two clients require revalidation'),boards=dict(path=str(inherited_boards.resolve()),sha256=sha(inherited_boards),statuses=dict(Counter(b['status'] for b in prior['boards'])),all50_live_verified=False),F2=dict(last_failure='20261001_202045',same_source_epoch_last32_available=False,position_packets_were_filtered_out_by_old_riding_only_diagnostics=True,real_arrival_and_continuity_verified=False))
    (a.out/'inherited_evidence_limits.json').write_text(json.dumps(evidence,indent=2),'utf8')
    board_manifest=read(ROOT/'artifacts/rebuild_r44/facility_transit_r44/live_departure_audit_v2/preparation_current_full_board_faces/manifest.json')
    board_positions=[tuple(b['position']) for b in board_manifest['boards']]
    w=MeasuredWorld(a.world)
    for q in board_positions:w.around(q,0)
    w.load();lo=tuple(min(q[k] for q in board_positions) for k in range(3));hi=tuple(max(q[k] for q in board_positions) for k in range(3))
    actual=dict(iter_block_entities(a.world,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    for b in board_manifest['boards']:
        q=tuple(b['position']);assert str(actual[q]['id'])=='projectseele:station_departure_board'
        tag=actual[q];cfg={k:str(tag.get(k,'')) for k in ['Station','Route']};cfg.update({k:int(tag.get(k,-1 if k=='NativePlatformId' else 0)) for k in ['PlatformCentre','NativePlatformId']});cfg.update({k:bool(tag.get(k,False)) for k in ['Wayfinding','AirService']})
        b.update(state=w.block(q),actual_be_present=True,configuration=cfg,configuration_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest())
    board_manifest['world']=str(a.world.resolve());board_manifest['native_passed']=False;board_manifest['world_write_performed']=False
    board_manifest['runtime_properties']['projectseele.r44DepartureBoardManifest']=str((a.out/'all50_current_live_boards.json').resolve());board_manifest['runtime_properties']['projectseele.r44DepartureBoardOutput']=str((a.out/'all50_live_board_result.json').resolve())
    (a.out/'all50_current_live_boards.json').write_text(json.dumps(board_manifest,ensure_ascii=False,indent=2),'utf8')
    order=[dict(order=0,scope='Root compile current control classes and verify actual jar/resource/runtime hashes',run=False),dict(order=10,scope='Root install two native sign BE fixes and eight exact route corrections; apply station reader dispatch patch',run=False),dict(order=20,scope='All80 gates: real card/free-service boundary, occupied hold, close, both sides, another player and reconnect',input=str((a.out/'all80_actual_station_gates.json').resolve()),run=False),dict(order=30,scope='All50 source clocks/real predictions and complete native/authored diagrams, correct glyph side/topology/Chinese/order',input=str((a.out/'all50_current_live_boards.json').resolve()),run=False),dict(order=40,scope='Seven native lift groups and every24 floor lobby: call, enter, selector, arrive, exit, return, interruption, reload, two clients',input=str((a.out/'all7_lift_groups_24_landings.json').resolve()),run=False),dict(order=50,scope='First F2 both ways with same-epoch server/client/packet/relative-rider last64 logs, then all38 exact car-door/APG/air-stair journey and supported exit',input=str((a.out/'all38_cases.json').resolve()),run=False),dict(order=60,scope='All registered NPC authority/owner and actual mechanical console flows; cancel-before-pilot-load and denied-request identity regression',input=str((a.out/'all_registered_NPC_identities_and_control_obligations.json').resolve()),run=False)]
    flags={'projectseele.nativeReviewWorld':a.world.name,'projectseele.r45TransportTrace':'true','projectseele.r45StaffControlTrace':'true','projectseele.r44TransitCases':str((a.out/'all38_cases.json').resolve()),'projectseele.r44LiftInterfaces':str((a.out/'all7_lift_groups_24_landings.json').resolve())}
    result=dict(world=str(a.world.resolve()),readonly_native_snapshot_sha256=sha(ART/'current_native_snapshot.json'),MTR_jar_sha256=sha(ROOT/'.Codex/local-mods/MTR-forge-4.0.5+1.20.1.jar'),MovingElevators_jar_sha256=sha(ROOT/'.Codex/local-mods/movingelevators-1.4.12-forge-mc1.20.1.jar'),interfaces=38,train=34,air=4,lift_groups=7,lift_landings=24,registered_NPCs=len(staff_rows),NPC_registry_sha256=sha(staff_file),gate_count=80,ordered_root_work=order,required_optin_properties=flags,world_written=False,minecraft_started=False,build_started=False,native_verified=False,visual_verified=False,traffic_progress_replay_allowed=False)
    (a.out/'root_native_order_and_flags.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Prepared actual interfaces38/gates80/lift groups7/floors24/NPCs',len(staff_rows),'no launch or world writes',flush=True)


if __name__=='__main__':main()
