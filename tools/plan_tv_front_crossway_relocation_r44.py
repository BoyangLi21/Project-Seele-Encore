"""Exact, reversible whole-component candidate; no apply and no floor invention."""
from pathlib import Path
from collections import Counter
import copy,hashlib,json
import argparse
import regional_voxels as v
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR,iter_block_entities
from rebuild_hangar_personnel_components_r44 import occupancy_contract,rail

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/facility_transit_r44/tv_front_crossway_relocation_v1'
EVIDENCE=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_shoulder_shells_v1'


def main(out=OUT):
    global OUT
    OUT=Path(out)
    OUT.mkdir(parents=True,exist_ok=True)
    assert not list(OUT.glob('*/applied_*/receipt.json')),'Applied proposals are immutable'
    w=MeasuredWorld(WORLD);lo,hi=(-33,-399,-274),(93,-390,-224);w.box(lo,hi);w.load();g=Geometry(w)
    tags={q:copy.deepcopy(t) for q,t in iter_block_entities(WORLD,v.DIM,lo,hi)}
    study=json.loads((EVIDENCE/'crossway_and_wet_surface_contract.json').read_text(encoding='utf8'))
    assert all(len(r['path_if_whole_front_crossway_removed'] or [])>0 for r in study['crossways'])
    assert all(c['all_static_standing'] for r in study['crossways'] for c in r['three_complete_front_alternative_rows'])
    changes={};rows=[];retained=[]
    def put(q,after,why):
        before=w.block(q)
        assert before is not None and q not in tags,('Native device/NBT ownership',q,before)
        if after.partition('[')[0] not in AIR:assert g.boxes(after) is not None
        if before!=after:changes[q]=(after,why)
    def east_arrival(q):
        # Expanded preservation includes the measured older approach apron,
        # rather than cutting its floor to a convenient rectangular patch.
        return 85<=q[0]<=98 and -399<=q[1]<=-390 and -264<=q[2]<=-248
    for variant,cx in enumerate((-12,30,72)):
        members=[]
        for x in range(cx-17,cx+18):
            for z in range(-264,-260):
                for y in range(-399,-392):
                    q=(x,y,z);state=w.block(q)
                    if state.partition('[')[0] in AIR|{'projectseele:lcl'}:continue
                    action='retain_other_original_owner'
                    if variant==2 and east_arrival(q):
                        action='retain_complete_original_east_lift_arrival_and_approach'
                    elif y==-395 and (abs(x-cx)==17 or z==-264):
                        action='retain_real_side_lip_or_new_front_guard_bearing'
                    elif y==-395:
                        assert state.partition('[')[0] in {'projectseele:nerv_machine_panel','minecraft:sea_lantern'},('Foreign bearing owner needs classification',q,state)
                        assert g.boxes(state)==[[0.,0.,0.,1.,1.,1.]]
                        put(q,'minecraft:air','retire_whole_obsolete_forward_shelf');action='retire_old_inner_three_rows'
                    elif y==-394 and state.startswith('projectseele:nerv_edge_rail'):
                        if abs(x-cx)==17:
                            put(q,rail('east' if x<cx else 'west'),'relocate_complete_side_guard_corner')
                            action='retain_side_lip_replace_old_front_facing_corner'
                        else:
                            put(q,'minecraft:air','retire_whole_obsolete_forward_shelf');action='retire_old_front_guard'
                    elif state.startswith('projectseele:nerv_ceiling_light') and z>-264:
                        put(q,'minecraft:air','retire_whole_obsolete_forward_shelf');action='retire_attached_old_inner_deck_light'
                    members.append({'position':q,'state':state,'action':action})
                    if action.startswith('retain'):retained.append({'variant':variant,'position':q,'state':state,'reason':action})
        # Keep three genuinely clear, fully measured circulation columns at
        # Z=-267/-266/-265. The new guard rests on the existing Z=-264 slab.
        for dx in range(-17,18):
            q=(cx+dx,-394,-264)
            if variant==2 and east_arrival(q):continue
            assert g.boxes(w.get(q[0],-395,q[2]))==[[0.,0.,0.,1.,1.,1.]]
            assert w.block(q).partition('[')[0] in AIR or w.block(q).startswith('projectseele:nerv_edge_rail')
            sides=['south']+(['east' if dx<0 else 'west'] if abs(dx)==17 else [])
            put(q,rail(*sides),'new_complete_supported_front_cross_guard')
        for side in (-1,1):
            for z in range(-263,-260):
                q=(cx+side*17,-394,z)
                if variant==2 and east_arrival(q):continue
                assert g.boxes(w.get(q[0],-395,z))==[[0.,0.,0.,1.,1.,1.]]
                assert w.block(q).partition('[')[0] in AIR or w.block(q).startswith(('projectseele:nerv_edge_rail','projectseele:nerv_ceiling_light')),('Side return occupied by another owner',q,w.block(q))
                put(q,rail('east' if side<0 else 'west'),'new_complete_supported_side_return_guard')
        if variant==2:
            # The retained original east arrival projects beyond the moved
            # front guard. Its measured left bearing edge needs a west-facing
            # drop guard, while every original slab/wall/device stays intact.
            for z in range(-263,-260):
                q=(85,-394,z)
                assert g.boxes(w.get(85,-395,z))==[[0.,0.,0.,1.,1.,1.]]
                assert w.block(q).partition('[')[0] in AIR or w.block(q).startswith('projectseele:nerv_edge_rail')
                put(q,rail('west'),'retained_east_arrival_newly_exposed_full_drop_edge')
        rows.append({'variant':variant,'original_complete_members':members,
            'three_clear_replacement_rows':[-267,-266,-265],'new_front_guard_bearing_z':-264,
            'retained_two_clear_side_lanes':[cx-19,cx-18,cx+18,cx+19],
            'operator_routes':study['crossways'][variant]['all_actual_control_and_rear_boarding_routes']})
    for row in rows:
        for member in row['original_complete_members']:
            q=tuple(member['position'])
            if q in changes:
                member['forward_state'],member['change_purpose']=changes[q]
                if member['action']=='retain_other_original_owner':
                    member['action']='replace_complete_old_fixture_on_retained_guard_bearing'
    retained=[r for r in retained if tuple(r['position']) not in changes]
    occupancy=occupancy_contract(WORLD,w,g,changes,tags,OUT)
    forward,inverse=v.Painter(),v.Painter();v.WORLD,v.OUT=WORLD,OUT
    for q,(after,why) in sorted(changes.items()):
        before=w.block(q)
        forward.match((*q,*q),before,after,'r44/tv_front_crossway/'+why)
        inverse.match((*q,*q),after,before,'inverse/r44/tv_front_crossway/'+why)
    producer_path=OUT/'producer_compatibility.json'
    producer=json.loads(producer_path.read_text(encoding='utf8')) if producer_path.exists() else {}
    source=ROOT/'src/main/java/com/projectseele/world/EvaHangarBuilder.java'
    source_ready=bool(producer.get('source_compatible') and producer.get('compiled_compatible')
                      and producer.get('source_sha256')==hashlib.sha256(source.read_bytes()).hexdigest())
    report={'world':str(WORLD),'world_write_performed':False,'cells':len(changes),'components':rows,
        'retained_original_owners':retained,'occupancy':occupancy,'complete_original_block_nbt':[
            {'position':q,'snbt':tag.snbt()} for q,tag in sorted(tags.items())],
        'source_model_sha256':hashlib.sha256((ROOT/'src/main/resources/assets/projectseele/mesh/tv_shoulder_shells_r44.json').read_bytes()).hexdigest(),
        'source_template_required':'EvaHangarBuilder FRONT_CROSS_Z_FROM_BED -24 -> -27; existing four-row front template then places its drop guard on the last Z=-264 bearing and keeps Z=-267..-265 clear. Preserve actual MTR/belt states and the complete east arrival; do not repaint those native objects.',
        'source_template_installed':source_ready,'apply_allowed':source_ready,
        'producer_compatibility':producer,'supersedes':str(ROOT/'artifacts/rebuild_r44/facility_transit_r44/tv_front_crossway_relocation_v1/contract.json'),
        'apply_preconditions':[
            'Root is sole writer; MC/active transient tasks must be stopped or quiesced before region edit',
            'At apply time every old complete block state/NBT matches the exact positive mask; inverse is present for every changed coordinate',
            'Producer source/class SHA still matches producer_compatibility.json; no stale Java rebuild is substituted',
            'Complete original east arrival, MTR state/identity, side lanes, operators, rear capsule/bridge and protected actor/player/NPC progress remain outside destructive mask'],
        'apply_then_native_gates':[
            '18 actual three-row forward/reverse trips after world migration',
            'Both original side lanes and all real prepare/status/cancel approaches/interactions',
            'Complete east lift arrival/door/exit and actual rear boarding/canonical capsule route',
            'Full machinery/LCL drain/open/transfer/return/close states, occupied travel refusal and active MTR directions',
            'Cold reload, two-client/multiplayer and actual whole TV views/user artistic acceptance'],
        'native_cases':str(EVIDENCE/'front_alternative_native_cases.json'),
        'native_gate':'All three clear rows both directions, both side lanes, all original prepare/status/cancel interfaces, original rear bridge/capsule docking, complete east lift arrival, all machinery states, active MTR directions, occupied travel stop and cold reload; then actual TV frame comparison',
        'status':'READY_FOR_ROOT_CONDITIONAL_EXACT_APPLY' if source_ready else 'EXACT_COMPONENT_CANDIDATE_PRODUCER_PENDING'}
    forward.meta.update(report);forward.save_plan('whole_front_crossway_relocation')
    inverse.meta.update({'forward':'whole_front_crossway_relocation','cells':len(changes),'complete_original_block_nbt':report['complete_original_block_nbt']});inverse.save_plan('inverse_whole_front_crossway_relocation')
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'cells':len(changes),'native_route_cases':18,'occupancy':occupancy,'apply_allowed':source_ready}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=OUT);args=p.parse_args();main(args.out)
