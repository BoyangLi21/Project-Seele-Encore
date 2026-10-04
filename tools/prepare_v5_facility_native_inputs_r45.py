"""Prepare exact real-player/BE inputs for Root's actualv5; no world or JVM write."""
from pathlib import Path
import copy,gzip,json,sys,hashlib
sys.dont_write_bytecode=True
import nbtlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from prepare_school_hakone_native_r45 import ActualGeometry
from prepare_b2_stair_component_r45 import full_body_status
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45';PYR=ART/'pyramid_components_sol_v1';OUT=PYR/'v5_native_entry_preparation_v1';WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v5_01/world'
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def ref(p):return dict(path=str(p),sha256=sha(p))
def rows(p):return [json.loads(x)for x in gzip.open(p,'rt',encoding='utf8')if x.strip()]
def main():
    assert OUT.exists() and not(OUT/'real_player_cases165.UNBOUND.json').exists()
    baseline=read(OUT/'actual_v5_source_baseline.json');expected={r['relative']:r['sha256']for r in baseline['files']}
    def inventory():
        actual={p.relative_to(WORLD).as_posix():sha(p)for p in WORLD.rglob('*')if p.is_file()};assert actual==expected;return actual
    before=inventory();cases=copy.deepcopy(read(PYR/'registered_stair_complete_batch_v2/real_player_stair_requests.UNBOUND.json')['cases'])
    assert len(cases)==78
    for case in cases:case.update(kind='walk',claim='REAL_CLIENT_KEYS_AND_SERVER_OBSERVED_PLAYER_REQUIRED',native_pass=False)
    original_approaches=read(PYR/'registered_stair_complete_batch_v2/all6_original_entries_to_same_floor_actual_lift.json')
    for index,row in enumerate(original_approaches):
        points=row['actual_shape_points']
        cases.extend([dict(id=f'B2_original_entry_same_floor_lift/{index}/out',kind='walk',path=points,native_pass=False),dict(id=f'B2_original_entry_same_floor_lift/{index}/back',kind='walk',path=list(reversed(points)),native_pass=False)])
    for z in(-46,-45,-44):
        points=[[x+.5,-394,z+.5]for x in range(90,113)]
        for direction,path in [('east',points),('west',list(reversed(points)))]:cases.append(dict(id=f'enclosed_waiting354/row{z}/{direction}',kind='walk',path=path,native_pass=False))
    for x in range(90,113):
        points=[[x+.5,-394,z+.5]for z in(-46,-45,-44)]
        for direction,path in [('south',points),('north',list(reversed(points)))]:cases.append(dict(id=f'enclosed_waiting354/column{x}/{direction}',kind='walk',path=path,native_pass=False))
        cases.append(dict(id=f'enclosed_waiting354/closed_boundary{x}',kind='press_closed_boundary',start=[x+.5,-394,-44.5],target=[x+.5,-394,-42.5],expected_closed_boundary_z=-43,expected_max_player_z=-43.25,actual_keys_ticks_min=60,may_not_teleport_to_destination=True,native_pass=False))
    assert len(cases)==165 and len({r['id']for r in cases})==165
    m=MeasuredWorld(WORLD)
    for row in cases:
        for p in row.get('path')or[row['start'],row['target']]:m.around(p,2)
    m.load();assert all(s=='full'for s in m.status.values());g=ActualGeometry(m)
    body=sweeps=0
    for row in cases:
        points=row.get('path')
        if points:
            for p in points:assert full_body_status(g,p)=='CLEAR',(row['id'],p);body+=1
            for a,b in zip(points,points[1:]):assert full_body_status(g,a,b)=='CLEAR',(row['id'],a,b);sweeps+=1
        else:
            assert g.standing(row['start'])=='STATIC_STANDING'and full_body_status(g,row['start'])=='CLEAR'
            assert full_body_status(g,row['start'],row['target'])=='BODY_OBSTRUCTION'
    fixtures=read(PYR/'v5_combined_entry_v2/replacement_BE8.json');repairs=read(PYR/'v5_combined_entry_v2/reviewed_be_repairs9.json');be_cases=[]
    for category,records in [('repair',repairs),('replacement',fixtures)]:
        for index,r in enumerate(records):
            q=tuple(r['pos']if category=='repair'else r['position']);state=r['after']if category=='repair'else r['state'];tag=r['after_nbt']if category=='repair'else r['full_nbt'];probe=MeasuredWorld(WORLD);probe.around(q,0);probe.load();assert all(s=='full'for s in probe.status.values());actual=dict(iter_block_entities(WORLD,'projectseele:geofront',q,q)).get(q)
            assert probe.block(q)==state and actual==(nbtlib.parse_nbt(tag)if tag is not None else None)
            be_cases.append(dict(id=f'{category}/{index}',position=list(q),expected_full_state=state,expected_full_nbt=tag,expected_BE_absent=tag is None,required_real_loaded_chunk_ticks_min=100,required_registry_isValid=True if tag is not None else None,native_tick_pass=False,cold_relog_pass=False))
    assert len(be_cases)==17
    assert inventory()==before
    source=ref(OUT/'actual_v5_source_baseline.json')
    write(OUT/'real_player_cases165.UNBOUND.json',dict(schema='projectseele.v5-components-real-player-inputs.v1',bound=False,world=None,source_baseline=source,full_world_seed=-3816295015381828007,full_world_id='50ba377e-9053-5dfa-93be-9601e623037c',driver_scope='COMPONENT_WALK',root_runtime_consumer_pending=True,cases=cases,native_pass=False,real_player_required=True,FakePlayer_pass_is_not_equivalent=True,preserve_floating_feet=True,prestart_client_and_server_full3D_floor_ack_required=True,no_between_waypoint_teleports=True,no_jump_sprint_flight_noclip=True,limits='Actual keyed motion through every half-step/width lane; camera/model review separate. Source shape caches only establish the independent static plan.'))
    write(OUT/'BE9_and_replacements8.UNBOUND.json',dict(schema='projectseele.v5-components-BE-native-inputs.v1',bound=False,world=None,source_baseline=source,driver_scope='COMPONENT_BE',cases=be_cases,world_source_written=False,native_tick=False,cold_relog=False,actual_registry_capture=ref(ART/'native_facility_session_v1/native_lifts_third_v3/be_registry_actual.json'),note='Registry isValid/factory capture is not live tick. Load exact currentQA chunks, observe >=100 server ticks, record actual BE/type/state/fullNBT and invalid-ticking errors, then normal-save/relogin same QA with fresh postrun inventory. Do not recopy source for the relog claim.'))
    topology=next(p for p in expected if p.startswith('dimensions/projectseele/geofront/data/projectseele_city_rigid_topology_r45_'));city=nbtlib.load(WORLD/topology)['data'];assert str(city['Stage'])=='CANDIDATE_DISABLED'and not int(city['RuntimeEnabled'])and not int(city['NativeStructurePassed']);assert not any('projectseele_city_rigid_control_r45_'in p for p in expected)
    write(OUT/'scope_and_integration_pending.json',dict(root_actual_v5_apply_readback=True,source_files=1736,source_bytes=baseline['total_bytes'],static_real_player_body_points=body,static_real_player_segment_sweeps=sweeps,case_counts=dict(stair78=78,same_floor_lift_approach12=12,waiting_full_width52=52,closed_boundary23=23,BE_repair9=9,BE_replacement8=8),city_source_prestate=dict(topology_relative=topology,stage='CANDIDATE_DISABLED',runtime_enabled=False,native_structure_passed=False,runtime_control_absent=True,all_city_bytes_preserved=True),current_admission_incompatibility='FacilitySourceAdmissionR45 only admits physical25/2regions/marker; compiled scope list lacks COMPONENT_WALK/COMPONENT_BE. Inputs intentionally UNBOUND, cannot fake existing reader5/lift90.',proposed_minimal_next='One composed-v5 source branch using actual composition+readback and fresh exact QA copy1736; keep25 branch, City12 and normal production unchanged. Real key/Vec3 steering from current Lift/Security consumer in independent component-only input mode. Root must approve/apply/compile source patch and mint fresh exact binding.',source_written=False,Java_MC_started=False,new_native_pass=False,legacy90_24_only_corresponding_lift_implementation_inherited=True,model_dynamic_personnel_activation_or_public_nav_install_included=False))
    print('Prepared165 actual-client cases and9+8 BE tick/relog requests UNBOUND; Source v5 untouched.',flush=True)
if __name__=='__main__':main()
