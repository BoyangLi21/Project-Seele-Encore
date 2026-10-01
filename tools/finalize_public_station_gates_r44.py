"""Freeze v1 and prepare the exact active19-station stage for root's apply."""
from pathlib import Path
import copy,gzip,hashlib,json,shutil
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities
from audit_facility_transit_r44 import Geometry
from plan_public_station_gates_r44 import read,ART,WORLD,WALKS

ROOT=Path(__file__).resolve().parents[1]
BEFORE=ART/'public_station_gates_v1'
OUT=ART/'public_station_gates_v2'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def conflicts(gates,shapes,walks):
    bad=set()
    for row in gates:
        pos=row['position']
        for box in shapes[row['open_state']]:
            low=[pos[i]+box[i] for i in range(3)];high=[pos[i]+box[i+3] for i in range(3)]
            for case in walks:
                for a,b in zip(case['path'],case['path'][1:]):
                    if any(max(a[i],b[i])+(.3 if i!=1 else 1.8)<=low[i] or min(a[i],b[i])-(.3 if i!=1 else 0)>=high[i] for i in range(3)):continue
                    length2=sum((b[i]-a[i])**2 for i in range(3))
                    t=0 if length2==0 else max(0,min(1,sum(((low[i]+high[i])/2-a[i])*(b[i]-a[i]) for i in range(3))/length2))
                    step=min(1,.05/max(.05,length2**.5))
                    for k in range(-24,25):
                        sample=max(0,min(1,t+k*step));p=[a[i]+(b[i]-a[i])*sample for i in range(3)]
                        if all(p[i]+(.3 if i!=1 else 1.8)>low[i]+.001 and p[i]-(.3 if i!=1 else 0)<high[i]-.001 for i in range(3)):
                            bad.add(case['id']);break
    return sorted(bad)


def main():
    assert not list(OUT.glob('*/applied_*/receipt.json')),'Applied proposals are immutable'
    OUT.mkdir(parents=True,exist_ok=True)
    old=read(BEFORE/'contract.json');manifest=read(BEFORE/'r44_public_station_gates.json')
    gates=manifest['gates'];ids={r['station_id'] for r in gates}
    assert len(gates)==80 and len(old['whole_threshold_pairs'])==40 and len(ids)==19 and not old['unresolved_thresholds']
    retired='-5006129440173562183';assert retired not in ids
    unresolved=old['unresolved_station_regions'];assert len(unresolved)==1 and unresolved[0]['station_id']==retired and not unresolved[0]['platforms']
    export_path=WORLD/'r44_public_station_gate_shapes.json';native=read(export_path)
    assert len(native['collision_shapes'])==len(native['outline_shapes'])==32
    assert digest(export_path)==old['native_shape_export_sha256']
    w=MeasuredWorld(WORLD)
    for row in gates:w.around(row['position'],8)
    w.load();g=Geometry(w);g.shapes.update(native['collision_shapes'])
    gate_cells={tuple(r['position']) for r in gates};tags={}
    for pair in old['whole_threshold_pairs']:
        ps=[r['position'] for r in pair['actual_gate_pair']]
        lo=tuple(min(p[i] for p in ps)-8 for i in range(3));hi=tuple(max(p[i] for p in ps)+8 for i in range(3))
        tags.update((q,copy.deepcopy(tag)) for q,tag in iter_block_entities(WORLD,'projectseele:geofront',lo,hi))
    assert not gate_cells.intersection(tags),'A new gate would replace an actual BE/reader/controller'
    ops=read_gzip(BEFORE/'all_measured_public_gate_pairs/ops.json.gz')
    checks=[]
    for op in ops:
        q=tuple(op['box'][:3]);before=w.block(q)
        assert op['box'][:3]==op['box'][3:] and op['mode']=='match' and before in op['extra'],('Old-state gate precondition changed',q,before,op)
        assert g.boxes(w.get(q[0],q[1]-1,q[2]))==[[0.,0.,0.,1.,1.,1.]],('No current whole bearing',q)
        checks.append({'position':q,'current_complete_state':before,'before_expected':op['extra'],'actual_BE':False})
    walks=read(WALKS);assert len(walks)==501
    bad=conflicts(gates,native['collision_shapes'],walks);assert not bad,('Current full501 paths meet an open gate body',bad)
    for folder in ('all_measured_public_gate_pairs','inverse_all_measured_public_gate_pairs'):
        shutil.copytree(BEFORE/folder,OUT/folder,dirs_exist_ok=True)
    for name in ('r44_public_station_gates.json','merge_native_collision_shapes.json','native_cases.json','threshold_seeds.json','actor_post_open_body_check.json'):
        shutil.copy2(BEFORE/name,OUT/name)
    config=ROOT/'src/main/resources/projectseele.mixins.json'
    source=ROOT/'src/main/java/com/projectseele/world/PublicStationGatesR44.java'
    mixin=ROOT/'src/main/java/com/projectseele/mixin/PublicStationGateR44Mixin.java'
    bridge_class=ROOT/'build/classes/java/main/com/projectseele/world/PublicStationGatesR44.class'
    mixin_class=ROOT/'build/classes/java/main/com/projectseele/mixin/PublicStationGateR44Mixin.class'
    build_config=ROOT/'build/resources/main/projectseele.mixins.json'
    assert 'PublicStationGateR44Mixin' in read(config)['mixins']
    assert bridge_class.exists() and mixin_class.exists()
    assert bridge_class.stat().st_mtime>=source.stat().st_mtime and mixin_class.stat().st_mtime>=mixin.stat().st_mtime
    producer={'source_sha256':digest(source),'source_mixin_sha256':digest(mixin),'source_config_sha256':digest(config),
        'compiled_bridge_sha256':digest(bridge_class),'compiled_mixin_sha256':digest(mixin_class),
        'source_mixin_registered':True,'build_config_registered':build_config.exists() and 'PublicStationGateR44Mixin' in read(build_config)['mixins'],
        'actual_pinned_target':'org.mtr.mod.block.BlockTicketBarrier; actual4.0.5 javap confirmed declared onEntityCollision2/scheduledTick2 descriptors',
        'native_holder_data_runtime_verified':False,'native_scheduled_override_runtime_verified':False,
        'actual_behaviour':'Finite manifest only; server opens native property without fare/ticket calls; native closed shape +.08m actor occupancy reschedules closure; all ordinary MTR gates outside the80 keep original rules'}
    report=copy.deepcopy(old)
    report.update({'source_v1_contract_sha256':digest(BEFORE/'contract.json'),'world_write_performed':False,
        'operating_station_count':19,'whole_threshold_pairs_count':40,'cells':80,
        'unresolved_station_regions':[],'separate_retired_component':{'station_id':retired,'classification':'R22 retired P1 corridor; no native platform and no gate installed',
            'full_retirement_passed':False,'scope_note':'Old1584-component/state evidence and two stale derived routes remain a separate world-worker closure, not a blocker for these19 operating thresholds'},
        'current80_positive_mask_checks':checks,'actual_current_preserved_complete_nbt':[{'position':q,'snbt':t.snbt()} for q,t in sorted(tags.items())],
        'current_preserved_BE_count':len(tags),'affected_BE_count':0,'current501_path_source_sha256':digest(WALKS),
        'current501_open_native_body_conflicts':bad,'producer':producer,
        'apply_allowed':True,'status':'READY_FOR_ROOT_EXACT_ACTIVE19_APPLY_WITH_PRELAUNCH_PRODUCER_GATE',
        'apply_preconditions':['Root sole writer; MC/active actor and transit tasks quiesced before exact region patch',
            'Every80 old full state/NBT still matches expected match mask and inverse at apply time; preserve current surrounding BEs/reader/signs rather than copying stale v1 NBT',
            'No gate inserted in retired P1; existing floors/APG/rails/readers/cards and complete501 paths outside the80 unchanged'],
        'before_next_MC':['Root processResources/build must include registered PublicStationGateR44Mixin and exact producer source/classes',
            'Install r44_public_station_gates.json before first gate collision; actual native shape merge is QA metadata, not a new block writer',
            'Check actual client and server resource/class identity and Mixin application; no client is asked to walk a gate under missing/ordinary paid override'],
        'apply_then_native_gates':['Real client auto-open and passage for both native facing types at all80 cells/40 thresholds',
            'Occupied full body prevents close; opposite exit and cancellation/retry work; actual player MTR balance and ticket progress unchanged',
            'All19 station ingress/egress, actual native trains/APG/38 boarding interfaces and whole501 current walks, then full artistic views',
            'Cold restart/re-entry, client/server and multiplayer; retired P1 full-component status remains separately unverified']})
    (OUT/'contract.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/'producer_compatibility.json').write_text(json.dumps(producer,indent=2),encoding='utf8')
    print(json.dumps({'cells':80,'pairs':40,'operating_stations':19,'current_preserved_BEs':len(tags),'affected_BEs':0,
        'current501_open_body_conflicts':len(bad),'apply_allowed':True,'producer_build_config_registered':producer['build_config_registered'],'native_behaviour_passed':False}))


def read_gzip(path):return json.loads(gzip.decompress(Path(path).read_bytes()))


if __name__=='__main__':main()
