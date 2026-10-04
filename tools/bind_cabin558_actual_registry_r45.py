"""Bind exact558 to actual existing ID6 registry capture; offline outputs only."""
from pathlib import Path
import argparse,copy,json,hashlib,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
OWN=ART/'lifts_doors_lifecycle_sol_v2/tv_door_lift_construction_v1/root_v14_cabin558_entry_v1'
NAMES={'projectseele:tv_staff_lift_panel_r45','projectseele:tv_staff_lift_band_r45','projectseele:tv_utility_lift_ceiling_r45'}
FULL=[[0.0,0.0,0.0,1.0,1.0,1.0]]
read=lambda p:json.loads(Path(p).read_text('utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for v in iter(lambda:f.read(4*1024*1024),b''):h.update(v)
    return h.hexdigest()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def frozen(row):
    p=Path(row['path']);p=p if p.is_absolute()else ROOT/p
    if sha(p)!=row['sha256']:raise RuntimeError('Actual input bytes changed: '+str(p))
    return p

def bind(capture,out):
    capture=Path(capture).resolve();out=Path(out).resolve()
    if not capture.is_relative_to(ART) or not out.is_relative_to(ART) or out.exists()or 'world'in out.parts or 'saves'in out.parts:raise RuntimeError('Only new offline artifact output')
    template=OWN/'catalog.UNBOUND.json'
    if sha(template)!=template.with_suffix('.json.sha256').read_text('ascii').strip():raise RuntimeError('Frozen558 template changed')
    catalog=read(template)
    for row in [catalog['baseline'],catalog['actual_root_v14_receipt'],catalog['core'],catalog['codec'],catalog['exact_rows'],catalog['prior_native_traits'],*catalog['epochs']]:frozen(row)
    data=read(capture)
    if data.get('schema')!='projectseele.tv-cabin-registered-state-capture.r45.v1' or data.get('world_written') is not False or data.get('world_chunks_read_or_loaded')is not False or not data.get('native_registry_and_geometry_executed') or data.get('world_id')!=catalog['world_uuid']:raise RuntimeError('Actual same-run registered state capture required')
    binding_file=capture.parent/'native_binding.json';admission_file=capture.parent/'preworld_admission.json';binding=read(binding_file);admission=read(admission_file)
    if sha(binding_file)!=data['candidate_binding_sha256'] or admission.get('passed')is not True or admission.get('binding_sha256')!=sha(binding_file)or not binding.get('postrun_ID6_first_contact')or binding['active_scopes']!=['COMMAND17']:raise RuntimeError('Actual admitted one-lane runtime epoch required; functional PASS not inferred')
    actual_classes=data['actual_loaded_class_SHA256'];epoch_classes={}
    for resource,digest in actual_classes.items():
        suffix='/runtime_epoch/classes'+resource
        match=[r for r in binding['source_epoch']if str(r['path']).replace('\\','/').endswith(suffix)]
        if len(match)!=1 or match[0]['sha256']!=digest:raise RuntimeError('Loaded class differs from actual bound runtime: '+resource)
        frozen(match[0]);epoch_classes[resource]=match[0]
    wanted_classes={'/com/projectseele/registry/ModBlocks.class','/com/projectseele/registry/ModItems.class','/com/projectseele/world/TvLiftFinishR45.class','/com/projectseele/world/S20MovingElevatorsAdapter.class','/com/projectseele/client/visual/CommandDoorInteractionReviewR45.class'}
    if set(actual_classes)!=wanted_classes:raise RuntimeError('Incomplete actual producer/registry/consumer class set')
    rows={r['state']:r for r in data['states']}
    if set(rows)!=NAMES or len(data['states'])!=3:raise RuntimeError('Exactly three actual new registered states required')
    for state,r in rows.items():
        if r.get('registered')is not True or r.get('has_block_entity')is not False or r.get('entity_block_factory')is not False or r['state_count']!=1 or r['java_class']!='net.minecraft.world.level.block.Block' or r['native_collision_aabbs']!=FULL or r['native_outline_aabbs']!=FULL or r['native_context']!='EmptyBlockGetter.INSTANCE / BlockPos.ZERO / CollisionContext.empty':raise RuntimeError('Actual single-state plain fullcube withoutBE required: '+state)
    additions={state:dict(has_block_entity=False,registered=True,actual_native_capture=ref(capture),java_class=r['java_class'])for state,r in rows.items()}
    traits=read(frozen(catalog['prior_native_traits']))
    if set(traits)&NAMES:raise RuntimeError('Previous traits already contain these states; do not overwrite prior evidence')
    traits.update(additions);out.mkdir(parents=True)
    write(out/'native_state_traits.actual_3key_additions.json',additions);write(out/'native_state_traits.actual_merged.json',traits)
    write(out/'native_collision_shapes.actual_3key_additions.json',{state:r['native_collision_aabbs']for state,r in sorted(rows.items())});write(out/'native_outline_shapes.actual_3key_additions.json',{state:r['native_outline_aabbs']for state,r in sorted(rows.items())})
    catalog['native_state_contract']=ref(out/'native_state_traits.actual_merged.json');catalog['epochs']+=[ref(capture),ref(binding_file),ref(admission_file),*epoch_classes.values()];catalog['state_capture_REQUIRED_PENDING']=False;catalog['actual_native_material_capture']=ref(capture)
    write(out/'catalog.BOUND.json',catalog);(out/'catalog.BOUND.json.sha256').write_text(sha(out/'catalog.BOUND.json')+'\n',encoding='ascii')
    write(out/'bound_registry_and_exact558_receipt.json',dict(schema='projectseele.tv-cabin558-actual-registry-offline-binding.v1',native_capture=ref(capture),actual_registry_states3=True,actual_collision_outline_fullcube=True,world558_installed=False,new_world_or_world_metadata_written=False,Java_or_MC_started=False,code_sources_resources_Root_compiled216=True,combined_city100_and558_target_rows658=True,world_NBT_or_actor_task_MTR_progress_changed=False,visual_or_functional_gate_pass_inferred=False,shape_additions_candidates_only=True))
    print('Bound actual registered3/558 inputs only; no world/MC. '+str(out),flush=True)
    return catalog

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();bind(a.capture,a.out)
if __name__=='__main__':main()
