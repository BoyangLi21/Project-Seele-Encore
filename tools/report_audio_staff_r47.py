"""One finite source/save readback for the R47 audio/staff handoff; no JVM or writes."""
from pathlib import Path
import json
import nbtlib
from query_blocks import read_box, iter_block_entities
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/audio_staff'
WORLD=ROOT/'artifacts/rebuild_r47/baseline/SEELE_R46_WORLD'
data_path=WORLD/'dimensions/projectseele/geofront/data'
DIM='projectseele:geofront'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    marker=nbtlib.load(data_path/'projectseele_dead_sea_chamber_r45.dat')['data']
    bounds=((29,-330,338),(37,-322,347))
    blocks=read_box(WORLD,DIM,*bounds); bes=dict(iter_block_entities(WORLD,DIM,*bounds))
    gate=[dict(pos=[x,y,340],state=blocks.get((x,y,340))) for x in range(32,35) for y in range(-329,-326)]
    locations={'book':(30,-329,345),'outside_reader':(36,-328,339),'inside_reader':(35,-328,341),'tree_artwork':(30,-322,339)}
    chamber=dict(world=str(WORLD),configured=bool(marker['Configured']),mode=str(marker['Mode']),fault=str(marker['Fault']),
        width=int(marker['Width']),height=int(marker['Height']),open_ticks=int(marker['OpenTicks']),original_wall_images=len(marker['Images']),readers=len(marker['Readers']),
        gate=gate,locations={name:dict(pos=list(q),state=blocks.get(q),full_nbt=bes[q].snbt() if q in bes else None) for name,q in locations.items()},
        network_bridge_present='DeadSeaReadingR45.installBridge' in (ROOT/'src/main/java/com/projectseele/network/SeeleNetwork.java').read_text('utf8'),
        native_access_and_physical_reading='Not exercised this round; original highest-card aperture, 10-second lease, occupied hold and authenticated page receipt code remain.',world_written=False)
    (OUT/'dead_sea_current_state.json').write_text(json.dumps(chamber,ensure_ascii=False,indent=2)+'\n','utf8')
    topology=nbtlib.load(next(data_path.glob('projectseele_city_rigid_topology_r45_*.dat')))['data']
    raw=ROOT/'artifacts/rebuild_r45/city_transport_xhigh_r45/ground_contract2_roundtrip_v1/ready_after_oracle_frozen_v1/oracle_actual/full96_collider_oracle_actual.json'
    proof=json.loads(raw.read_text('utf8'))
    endpoint_path=ROOT/'artifacts/rebuild_r45/city_transport_xhigh_r45/ground_contract2_roundtrip_v1/actual_ground2_roundtrip_cold_v1/readback.json'
    endpoint=json.loads(endpoint_path.read_text('utf8'))
    performance=dict(
        source_closed=['compat/CityUnionPortableBootstrapR45 now configures before optional Create mixins','SeeleCompatibilityPlugin invokes the bootstrap before selection','CityExactShapeUnionR45 now reads the portable bootstrap and validates side-bound projection schema','Client/server enabled+required policy must match; enabled missing/foreign proof fails closed'],
        current_world_topology={key:str(topology.get(key,'')) for key in ['Stage','RuntimeEnabled','NativeStructurePassed','ExactCargoMigrationPassed','ExactStaticMigrationPassed','NativeTravelPassed','NativePerformancePassed']},
        previous_native_endpoint={key:endpoint.get(key) for key in ['depth','full_cargo_cells','complete_BE','current_actor_ids','errors','new_ground_contract2_roundtrip_passed','complete_roundtrip_passed','relogin_passed','client_visual_passed','performance_passed']},
        previous_native_proof=str(raw),mapped_create_producer=proof['complete_plan_results'][0]['actual_class_resource_SHA256s']['com.simibubi.create.content.contraptions.Contraption'],
        shipping_create_producer='07727b63607cd3c20ac3e7c0cb14ec996f5156971950b15d440b8682ad69f14d',
        mapped_receipt_cannot_authorize_shipping=True,release_profiles_enabled=False,
        missing=['Raw forgeserver full96 oracle bound to final R47 all.jar and shipping Create','Raw forgeclient full96 oracle bound to same final release classes','config/projectseele-city-union-client-r45.json and server-r45.json activation projections of actual corresponding raw receipts','Both enabled/required=true profiles with their respective frozen producer/proof fields','Actual mixin postApply activation plus runtime balanced_calls and zero unexpected stock/fallback; original endpoints/identities remain guarded'],
        no_QA_world_progress_copied=True,no_new_native_run=True)
    (OUT/'city_performance_closure.json').write_text(json.dumps(performance,ensure_ascii=False,indent=2)+'\n','utf8')
    remaining=dict(done=['55 licensed/original derived audio assets and 18 PA timing metadata entries','Continuous same-entity NERV/UN engine with movement-based throttle','Mechanical pressure/manual door sounds','LCL position/block tint handling','Command circuit 53 ceiling + 5 alert lamps; strip lights now switchable','24 roof-backed public pendant lamps /149 exact reversible block edits','Original236 roster retained,25 workposts +2 experiment researchers candidate','Short role conversations; named operator duty profile; pilot names/dummy-prefix/standby/leave-plug text commands','Portable city union source bridge integrated; authentic shipped-runtime proof gap recorded','Dead Sea chamber finite readback saved'],
        remaining=['Root one final compile and source-appropriate native checks; this agent did not build or start Java','Root apply world patches after experiment hall then rebuild only changed chunk lighting','Root connect EVA_ATTACK_ROAR to actual attack events','User listening and default/shader orange-red LCL /command-light visual acceptance','Final raw client/server city union proof and activation deployment; disabled policy retained until complete','Optional sparse civilian posts need actual public positions, no invented room/building purpose','Dead Sea highest-card entry, occupied close hold and authenticated physical-page reading native check'],
        ownership='Root is the only save writer; no actor UUID replacements, player/mission/traffic progress copy, model or action edits')
    (OUT/'remaining.json').write_text(json.dumps(remaining,ensure_ascii=False,indent=2)+'\n','utf8')
    sounds=json.loads((ROOT/'src/main/resources/assets/projectseele/sounds.json').read_text('utf8'))
    events=['transport_engine','personnel_door_open','personnel_door_close','pressure_door_motion','eva_attack_roar']
    missing=[s['name'] for name in events for s in sounds[name]['sounds'] if not (ROOT/'src/main/resources/assets/projectseele/sounds'/(s['name'].split(':',1)[1]+'.ogg')).is_file()]
    report=dict(new_events=events,missing_audio=missing,lab_skin='technician',lab_skin_exists=(ROOT/'src/main/resources/assets/projectseele/textures/entity/staff_technician.png').is_file(),world_written=False,Java_started=False)
    (OUT/'one_source_readback.json').write_text(json.dumps(report,indent=2)+'\n','utf8')
    print('Finite handoff readback:',report,'chamber',chamber['mode'])

if __name__=='__main__':main()
