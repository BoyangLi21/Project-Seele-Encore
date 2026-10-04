"""Prepare a named City96 binding from a completed composition; no world writes."""
from pathlib import Path
import argparse, copy, hashlib, json, shutil
import nbtlib
from install_city_rigid_metadata_r45 import metadata_current_errors

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/rebuild_r45'
BASE=ART/'city_motion_sol_followup/install_bundle_v6'
CATALOG=ART/'integration_sol_followup/offline_composer_v4/catalog.json'
TOPO=ART/'city_motion/whole_topology_v2'
DATA='dimensions/projectseele/geofront/data/'
EXTRA_SOURCES=['src/main/java/com/projectseele/world/CityAtomicCandidateBindingR45.java','tools/prepare_city_atomic_binding_r45.py','tools/migrate_city_atomic_candidate_r45.py','tools/install_city_rigid_metadata_r45.py']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(4*1024*1024),b''):h.update(part)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text('utf8'))
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n','utf8')
def ref(path):return dict(path=str(Path(path).resolve()),sha256=sha(path))
def safe(base,relative):
    p=Path(relative);assert not p.is_absolute() and '..' not in p.parts
    target=(base/p).resolve();assert target.is_relative_to(base.resolve());return target

def candidate(world):
    world=world.resolve(strict=True)
    assert world.name=='world' and world.parent.parent==(ART/'composition_candidates').resolve(),'Named completed composition child required'
    return world

def files_match(world,expected):
    actual={p.relative_to(world).as_posix():p for p in world.rglob('*') if p.is_file() and p.name!='session.lock'}
    assert set(actual)==set(expected),'Candidate full inventory changed; preserve and investigate'
    for relative,digest in expected.items():assert sha(actual[relative])==digest,'Candidate file/progress changed: '+relative

def check_plan(plan_file):
    plan=read(plan_file);assert plan['schema']=='projectseele.city-atomic-binding-plan-r45.v1'
    world=candidate(Path(plan['world']))
    for row in [plan['composition_receipt'],plan['catalog'],plan['baseline'],plan['metadata_manifest'],plan['static_manifest'],*plan['source_epoch']]:
        assert sha(row['path'])==row['sha256'],'Binding dependency drift: '+row['path']
    receipt=read(plan['composition_receipt']['path'])
    assert receipt['status']=='OFFLINE_PARTIAL_CANDIDATE_NOT_NATIVE_NOT_RELEASE'
    assert Path(receipt['world']).resolve()==world and set(receipt['selected_components'])==set(plan['selected_components'])
    return plan,world

def prepare(world,out):
    world=candidate(world);receipt_path=world.parent/'composition.json';receipt=read(receipt_path);catalog=read(CATALOG)
    assert receipt['status']=='OFFLINE_PARTIAL_CANDIDATE_NOT_NATIVE_NOT_RELEASE','Composition incomplete; never bind a partially written candidate'
    assert Path(receipt['world']).resolve()==world and receipt['world_uuid']==catalog['world_uuid'] and receipt['seed']==catalog['seed']
    assert set(receipt['selected_components'])==set(catalog['default_components']) and len(receipt['selected_components'])==21
    baseline=read(ROOT/catalog['baseline']['path']);assert sha(ROOT/catalog['baseline']['path'])==catalog['baseline']['sha256']
    expected={k:v for k,v in baseline['files'].items() if Path(k).name!='session.lock'}
    for row in [*receipt['regions'],*receipt['files']]:
        assert row['before_sha256']==expected.get(row['target']),'Composition before chain is not the original progress'
        expected[row['target']]=row['after_sha256']
    files_match(world,expected)
    old=read(BASE/'manifest.json');assert len(old['operations'])==807 and old['archive_objects']==96 and old['full_be']==1471
    assert not metadata_current_errors(world,old),'Original archive/depth epoch differs'
    assert not (world/old['marker_target']).exists() and not (BASE/'metadata_wal.json').exists()
    assert int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])==catalog['seed']
    assert str(nbtlib.load(world/(DATA+'projectseele_tokyo3_building_world_id_r44.dat'))['data']['WorldUUID'])==catalog['world_uuid']
    assert not out.exists();out.mkdir(parents=True)
    bundle=out/'metadata_bundle';bundle.mkdir()
    # Preserve all807 complete payloads and immutable original archives; no sparse geometry-only bundle.
    for name in ('payload','baseline'):shutil.copytree(BASE/name,bundle/name)
    (bundle/'source_epoch').mkdir();source_epoch=[]
    sources=list(dict.fromkeys([r['repository_path'] for r in old['source_epoch']]+EXTRA_SOURCES))
    for i,relative in enumerate(sources):
        path=ROOT/relative;frozen=bundle/'source_epoch'/f'{i}_{path.name}';shutil.copyfile(path,frozen)
        source_epoch.append(dict(repository_path=relative,sha256=sha(path),frozen_copy=frozen.relative_to(bundle).as_posix()))
    new=copy.deepcopy(old);new['world_selector']['name']='world';new['world_selector']['absolute_world']=str(world);new['source_epoch']=source_epoch
    new['explicit_rebind']=dict(original_bundle=ref(BASE/'manifest.json'),composition_receipt=ref(receipt_path),entire_transaction=True)
    write(bundle/'manifest.json',new);shutil.copyfile(BASE/'required_root_static_proof_TEMPLATE.json',bundle/'required_root_static_proof_TEMPLATE.json')
    static=dict(schema='r45_disk_exact_region_transaction_v1',world=str(world),dimension='projectseele:geofront',derived_relight=True,
        baseline=dict(path=str(ROOT/catalog['baseline']['path']),sha256=catalog['baseline']['sha256']),
        native_state_contract=dict(path=str(ROOT/catalog['native_state_contract']['path']),sha256=catalog['native_state_contract']['sha256']),
        inputs=[dict(object_id='city96_whole',path=str(TOPO/'forward.jsonl.gz'),sha256=old['static_forward_sha256'],inverse=str(TOPO/'inverse.jsonl.gz'),inverse_sha256=old['static_inverse_sha256'],rows=2859160)],
        extra_epochs=[ref(receipt_path),ref(bundle/'manifest.json')])
    write(out/'static_manifest.json',static)
    plan=dict(schema='projectseele.city-atomic-binding-plan-r45.v1',world=str(world),world_id=catalog['world_uuid'],world_seed=catalog['seed'],
        composition_receipt=ref(receipt_path),catalog=ref(CATALOG),baseline=ref(ROOT/catalog['baseline']['path']),selected_components=receipt['selected_components'],
        metadata_manifest=ref(bundle/'manifest.json'),static_manifest=ref(out/'static_manifest.json'),source_epoch=[dict(path=str(ROOT/r['repository_path']),sha256=r['sha256']) for r in source_epoch],
        original_bundle=ref(BASE/'manifest.json'),composition_files=expected,original_archive_depth_preconditions=[*old['immutable_baseline'],*[dict(target=r['target'],sha256=r['before_sha256']) for r in old['operations'] if r['kind']=='archive']],
        city_cells=2859160,metadata_operations=807,full_BE=1471,archive_objects=96,production_runtime_enabled=False,world_written=False,
        journal=str(out/'static_journal'),metadata_bundle=str(bundle),required_root_static_proof=str(bundle/'required_root_static_proof_TEMPLATE.json'))
    write(out/'binding_plan.json',plan);print('Prepared exact entire City96 plan; no world writes:',out/'binding_plan.json')

def ready(plan_file,out,compiled_proof):
    plan,world=check_plan(plan_file);bundle=Path(plan['metadata_bundle']);wal_path=bundle/'metadata_wal.json';wal=read(wal_path)
    assert wal['phase']=='INSTALLED_DISABLED' and not metadata_current_errors(world,read(bundle/'manifest.json'))
    manifest=read(bundle/'manifest.json');run=read(Path(plan['journal'])/'run.json')
    assert run['phase']=='COMPLETE' and run['all_exact_final_actual_voxels_and_nbt_readback'] and run['final_exact_cells']==2859160
    expected=dict(plan['composition_files'])
    for row in run['regions']:expected[Path(row['current_region']).relative_to(world).as_posix()]=row['after_sha256']
    for row in manifest['operations']:expected[row['target']]=row['after_sha256']
    expected[manifest['marker_target']]=wal['marker_after_sha256'];files_match(world,expected)
    # The finish operation records the proof hash. Require the named original proof bytes, not replacement booleans.
    candidates=[p for p in plan_file.parent.rglob('*.json') if p.name!='binding_plan.json' and sha(p)==wal['root_proof_sha256']]
    assert len(candidates)==1,'Keep exactly one named Root static proof under this binding directory'
    proof=candidates[0];compiled=read(compiled_proof)
    assert compiled['schema']=='projectseele.city-atomic-compiled-proof-r45.v1' and compiled['passed'] is True
    assert {r['path']:r['sha256'] for r in compiled['source_epoch']}=={r['path']:r['sha256'] for r in plan['source_epoch'] if r['path'].endswith('.java')}
    for r in compiled['classes']:assert sha(r['path'])==r['sha256']
    required={'CityAtomicCandidateBindingR45','CityCreateDistrictR45','CityRigidQualityR45','CityCreateCargoR45','CityRigidTopologyR45','CityRigidGenerationR45'}
    assert required<={Path(r['path']).stem for r in compiled['classes']},'Every real City96 entry/owner class must be compiled and frozen'
    assert not out.exists();out.mkdir(parents=True)
    binding=dict(schema='projectseele.city-atomic-native-binding-r45.v1',world=str(world),world_id=plan['world_id'],world_seed=plan['world_seed'],
        composition_complete=True,installed_disabled=True,runtime_enabled=False,composition_receipt=plan['composition_receipt'],binding_plan=ref(plan_file),metadata_wal=ref(wal_path),root_static_proof=ref(proof),
        compiled_proof=ref(compiled_proof),source_epoch=[*plan['source_epoch'],ref(compiled_proof),*compiled['classes']],world_files=[dict(relative=k,sha256=v) for k,v in sorted(expected.items())])
    write(out/'native_binding.json',binding)
    # Each cold run needs its own actual current checkpoint binding, never reuse an old file snapshot after native writes.
    common=dict(world=str(world),world_id=plan['world_id'],world_seed=plan['world_seed'],candidate_binding=str(out/'native_binding.json'),candidate_binding_sha256=sha(out/'native_binding.json'))
    control=dict(schema='projectseele.actual96-native-control-job-r45.v1',**common,enable_native_district=True,request_on_start=True,retract=False,actual_existing_structures=True,helper_replacement=False,requires_installed_native_verified_topology=True,expected_source_endpoint=312)
    quality=dict(schema='projectseele.actual96-native-quality-job-r45.v1',**common,mode='travel',endpoint_depth=0,witness_indices=[43,64,93],timeout_ticks=6000,checkpoint_motion_tick=100,stop_server_when_done=True,actual_existing_structures=True,helper_replacement=False,output=str(out/'restore_all96_result'))
    write(out/'restore_all96.control.json',control);write(out/'restore_all96.quality.json',quality)
    write(out/'native_launch_requirements.json',dict(no_MC_launched=True,single_world_writer=True,absolute_world=str(world),
        java_properties=[f'-Dprojectseele.r45CityCreateDistrict={(out/"restore_all96.control.json").as_posix()}',f'-Dprojectseele.r45CityRigidQuality={(out/"restore_all96.quality.json").as_posix()}'],
        game_directory_must_mount_this_exact_world=True,minimum_Create_maxBlocksMoved=19382,reviewed_Create_maxBlocksMoved=32768,server_heap='-Xms2G -Xmx20G',timeout_seconds=420,
        old_review_launch_helper_compatible=False,no_progress_from_test_world_for_delivery=True))
    print('Prepared disabled real96 native binding; root launch with exact world mount:',out)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--candidate',type=Path);ap.add_argument('--plan',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--ready',action='store_true');ap.add_argument('--compiled-proof',type=Path);args=ap.parse_args()
    out=args.out.resolve();assert out.is_relative_to(ART) and not out.is_relative_to(ART/'source_world_backup')
    if args.ready:
        assert args.plan and args.compiled_proof;ready(args.plan.resolve(),out,args.compiled_proof.resolve())
    else:
        assert args.candidate and not args.plan;prepare(args.candidate,out)

if __name__=='__main__':main()
