"""Focused read-only authority, controller-inventory and release-scope regression.

Synthetic gate/identity/archive data are never native or geometry acceptance.
The optional live authority test reads only the explicitly supplied Root files.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse,copy,hashlib,json,tempfile,uuid,zipfile
from root_bundle_authority_r53 import validate,validate_record,candidate,original_identities
from prepare_r52_runtime_deployment_candidate import expected_controllers,java_uuid
from wet_front_seal_manifest_r52 import sealed_front_specs
from package_release_r52 import validate_acceptance,world_payload,generated,SCOPE124_ACCEPTANCE,REQUIRED_ACCEPTANCE
from release_scope124_r53 import context,validate_context

checks=[]
def check(name,fn):
    fn();checks.append({'check':name,'passed':True})
def reject(fn):
    try:fn()
    except (ValueError,KeyError,TypeError,FileNotFoundError):return
    raise AssertionError('Invalid input was admitted')
def eq(a,b):assert a==b,(a,b)
def uid(name):return str(uuid.uuid5(uuid.NAMESPACE_URL,'scope124-test:'+name))
def fixture():
    units=[];roster=[];gates=[]
    for i in range(3):
        eva=uid('eva'+str(i));plug=uid('plug'+str(i));roster.append(dict(variant=i,eva=eva,plug=plug))
        units.append(dict(variant=i,eva=eva,plug=plug,gantry={'id':uid('gantry'+str(i))},carrier_controller={'id':java_uuid(f'projectseele:r52:original-carrier:53:{eva}')},crane={'visual':{'id':uid('crane'+str(i))}}))
        gate=dict(kind='HANGAR',resource=f'bay_{i}_front',visual=uid('front'+str(i)),variant=i,width=33,
            frame={'position':[i*200,0,0],'quaternion':[0,0,0,1]},supports=[],hangar_stack={'floor_seal':{'closed_boxes':[[1,0,0,8,1,2]],'drop_m':1,'retreat_local_z_m':30}})
        seal=sealed_front_specs([gate],False)[gate['resource']]
        gate['supports']=[{'position':row['at'],'state':'projectseele:nerv_structural_panel'} for row in seal['wall_bearings']];gates.append(gate)
    for i in range(38):gates.append(dict(kind='SILO',resource='test_gate_'+str(i),visual=uid('gate'+str(i))))
    owner=dict(units=units,gates=gates,ground_guides={'mode':'continuous_upright'})
    directory=dict(units=roster,routes=[{'motion_profile':{'type':'continuous_upright'}}],legs=[{'motion':'UPRIGHT_GUIDED'}],resources=[{'kind':'DOOR','id':g['resource']} for g in gates])
    return {'epoch':53},owner,directory

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--world',type=Path);ap.add_argument('--baseline',type=Path);ap.add_argument('--root-plan',type=Path);ap.add_argument('--design',type=Path)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    bundle,owner,directory=fixture()
    check('exact41_gate_50_controller_scope124',lambda:eq(len(expected_controllers(bundle,owner,directory)),50))
    co,cd=copy.deepcopy(owner),copy.deepcopy(directory);co['gates'].append({'kind':'SILO','resource':'yashima_cannon_hatch','visual':uid('cannon_gate')});cd['resources'].append({'kind':'DOOR','id':'yashima_cannon_hatch'})
    check('explicit_optional_cannon42_gate_52_controller',lambda:eq(len(expected_controllers(bundle,co,cd,{'cannon_uuid':uid('cannon')})),52))
    check('deferred_cannon_gate_rejected',lambda:reject(lambda:expected_controllers(bundle,co,cd)))
    for label,mutate in [
        ('duplicate_controller_uuid',lambda o,d:o['gates'][3].update(visual=o['gates'][0]['visual'])),
        ('missing_declared_door',lambda o,d:d['resources'].pop()),
        ('duplicate_declared_door',lambda o,d:d['resources'].append(copy.deepcopy(d['resources'][0]))),
        ('wrong_original_eva',lambda o,d:o['units'][0].update(eva=uid('wrong'))),
        ('wrong_carrier_named_id',lambda o,d:o['units'][0]['carrier_controller'].update(id=uid('wrongcarrier'))),
        ('duplicate_directory_roster',lambda o,d:d['units'].append(copy.deepcopy(d['units'][0]))),
        ('withdrawn_turn_station',lambda o,d:d['legs'][0].update(motion='FOOT_BEARING_TURN'))]:
        o,d=copy.deepcopy(owner),copy.deepcopy(directory);mutate(o,d)
        check(label+'_rejected',lambda o=o,d=d:reject(lambda:expected_controllers(bundle,o,d)))
    report=dict(release_ready=True,feature_scope='124',deferred_scope=['3_yashima_combat','6_unrelated_global_configuration'],known_implementation_blockers=[],world='READ_ONLY_SYNTHETIC',jar_sha256='a'*64)
    report['checks']={name:dict(status='PASS',evidence='SYNTHETIC_CONTRACT_TEST_NOT_NATIVE',current_round=True,world=report['world'],jar_sha256=report['jar_sha256']) for name in SCOPE124_ACCEPTANCE}
    check('124_coverage_does_not_require_deferred356',lambda:validate_acceptance(report))
    for label,mutate in [
        ('historical_native',lambda r:r['checks']['launch_three_destinations'].update(current_round=False)),
        ('wrong_world',lambda r:r['checks']['multi_air_transport'].update(world='OLD_WORLD')),
        ('wrong_jar',lambda r:r['checks']['hangar_departure_return'].update(jar_sha256='b'*64)),
        ('missing_current_check',lambda r:r['checks'].pop('required_migration_visual_review')),
        ('pending_native',lambda r:r['checks']['cold_restart_identity_restore'].update(status='USER_TEST_PENDING')),
        ('known_blocker',lambda r:r.update(known_implementation_blockers=['failure'])),
        ('invented_scope',lambda r:r.update(feature_scope='12'))]:
        r=copy.deepcopy(report);mutate(r);check(label+'_rejected',lambda r=r:reject(lambda:validate_acceptance(r)))
    full=dict(release_ready=True,checks={n:{'status':'PASS','evidence':'SYNTHETIC_LEGACY_TEST'} for n in REQUIRED_ACCEPTANCE})
    check('legacy_full_scope_preserved',lambda:validate_acceptance(full))
    full['checks'].pop('railway');check('legacy_full_scope_still_requires_railway',lambda:reject(lambda:validate_acceptance(full)))
    files={'level.dat':Path('READ_ONLY/level.dat'),'.owner_marker':Path('READ_ONLY/.owner_marker'),'dimensions/projectseele/geofront/region/r.0.0.mca':Path('READ_ONLY/r.0.0.mca')}
    check('client_and_server_reference_same_world_bytes',lambda:eq({n.removeprefix('overrides/saves/SEELE_R52_WORLD/'):p for n,p in world_payload(files,'client','124').items()},{n.removeprefix('SEELE_R52_WORLD/'):p for n,p in world_payload(files,'server','124').items()}))
    check('legacy_client_map_layout_unchanged',lambda:eq(world_payload(files,'client','full'),{}))
    check('unsafe_world_payload_name_rejected',lambda:reject(lambda:world_payload({'../other':Path('x')},'client','124')))
    actual_authority=None
    if args.world:
        args.baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest();args.root_plan_sha256=hashlib.sha256(args.root_plan.read_bytes()).hexdigest()
        design=json.loads(args.design.read_text('utf8'));actual_authority=validate(args,directory=design)
        check('actual_deep_root_world_plan_read_only',lambda:eq(validate_record(actual_authority,directory=design),actual_authority))
        a=copy.copy(args);a.world=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52')
        check('retired_world_rejected',lambda:reject(lambda:validate(a)))
        a=copy.copy(args);a.baseline_sha256='0'*64;check('authority_sha_mismatch_rejected',lambda:reject(lambda:validate(a)))
        d=copy.deepcopy(design);next(n for n in d['nodes'] if n['role']=='BANK')['foot_frame']['translation'][1]=-646
        check('old_bank_depth_rejected',lambda:reject(lambda:validate(args,directory=d)))
        d=copy.deepcopy(design);d['bank_roles'][0]['intent']='surface'
        check('wrong_bank_exit_role_rejected',lambda:reject(lambda:validate(args,directory=d)))
        d=copy.deepcopy(design);next(n for n in d['nodes'] if n['role']=='BANK')['foot_frame']['translation'][0]=0
        check('wrong_bank_lane_rejected',lambda:reject(lambda:validate(args,directory=d)))
        check('candidate_inside_actual_world_rejected',lambda:reject(lambda:candidate(args.world/'new_candidate',args.world)))
        check('candidate_inside_other_native_world_rejected',lambda:reject(lambda:candidate(Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52')/'new_candidate',args.world)))
        with tempfile.TemporaryDirectory(prefix='contract_only_',dir=args.out) as temporary:
            folder=Path(temporary);identity=folder/'IDENTITIES.json';rows={uid('original'+str(i)):dict(type='projectseele:nerv_staff',dimension='dimensions/projectseele/geofront') for i in range(678)}
            identity.write_text(json.dumps({'world':args.world.as_posix(),'managed_geofront':rows}),encoding='utf8');digest=hashlib.sha256(identity.read_bytes()).hexdigest()
            check('explicit678_identity_set_without680_lock',lambda:eq(original_identities(identity,digest,args.world),rows))
            check('identity_sha_mismatch_rejected',lambda:reject(lambda:original_identities(identity,'0'*64,args.world)))
            packs={}
            for side in ('server','client'):
                archive=folder/(side+'.zip')
                with zipfile.ZipFile(archive,'w') as z:z.writestr('synthetic-dependency.txt','CONTRACT_TEST_ONLY')
                packs[side]={'path':archive.as_posix(),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size}
            pins=folder/'PACKAGE_INPUTS.json';pins.write_text(json.dumps(packs),'utf8');runtime=folder/'runtime';runtime.mkdir();(runtime/'combat_bundle_r44.json').write_text('{"files":{}}','utf8')
            ctx=context(actual_authority,runtime,identity,digest,pins,hashlib.sha256(pins.read_bytes()).hexdigest())
            check('explicit_release_context_pins',lambda:eq(validate_context(ctx),ctx))
            Path(packs['server']['path']).write_bytes(b'changed')
            check('changed_dependency_archive_rejected',lambda:reject(lambda:validate_context(ctx)))
    result=dict(schema='projectseele.r53.scope124-release-regression.v1',passed=True,checks=checks,check_count=len(checks),actual_root_authority_read_only=actual_authority,world_written=False,game_started=False,production_package_built=False,native_acceptance=False)
    (args.out/'SCOPE124_RELEASE_REGRESSION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({'passed':True,'checks':len(checks),'world_written':False,'native_acceptance':False}))

if __name__=='__main__':main()
