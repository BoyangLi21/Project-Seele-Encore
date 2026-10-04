"""Prepare sealed root composition inputs; never copies/writes a world."""
from pathlib import Path
import ast,difflib,gzip,hashlib,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
OUT=ART/'pyramid_components_sol_v1/v5_combined_entry_v2'
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ref(p):return dict(path=Path(p).relative_to(ROOT).as_posix(),sha256=sha(p))
def write(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return [json.loads(x)for x in f if x.strip()]
def jsonl(p,records):
    with Path(p).open('wb')as raw,gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0)as f:
        for r in records:f.write((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8'))

def main():
    assert not OUT.exists(),'Existing candidate/artifact epoch is preserved'
    OUT.mkdir();(OUT/'core').mkdir();(OUT/'runs').mkdir()
    original=ROOT/'tools/compose_r45_candidate.py';source=original.read_text('utf8')
    # Two replaceable admission hooks keep shared codec/staging/copy unchanged.
    old="                for state,tag in [(b,bn),(a,an)]:\n                    if state not in traits or bool(traits[state]['has_block_entity'])!=(tag is not None):raise Hold('Missing exact native registry/complete BE contract: '+state)\n"
    new="                validate_cell_contract(policy,catalog,component,r,b,a,bn,an)\n"
    assert source.count(old)==1;candidate=source.replace(old,new)
    hook="def validate_cell_contract(policy,catalog,component,row,b,a,bn,an):\n    traits=read(policy.input(catalog['native_state_contract']))\n    for state,tag in [(b,bn),(a,an)]:\n        if state not in traits or bool(traits[state]['has_block_entity'])!=(tag is not None):raise Hold('Missing exact native registry/complete BE contract: '+state)\n\ndef validate_projected_chunk(policy,catalog,root,changes,states,codec):pass\n\n"
    candidate=candidate.replace('def stage_cells(',hook+'def stage_cells(',1)
    candidate=candidate.replace('                codec.validate_chunk(root,changes,reverse)\n','                codec.validate_chunk(root,changes,reverse)\n                validate_projected_chunk(policy,catalog,root,changes,reverse,codec)\n',1)
    old_source="catalog.get('source')!='artifacts/rebuild_r45/source_world_backup'"
    assert candidate.count(old_source)==1;candidate=candidate.replace(old_source,"catalog.get('source')!=policy.source.relative_to(policy.repo).as_posix()")
    ast.parse(candidate);(OUT/'core/compose_v5_core.py').write_bytes(candidate.encode('utf8'))
    (OUT/'core/composer_minimal_extension.patch').write_bytes(''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),fromfile='a/tools/compose_r45_candidate.py',tofile='b/tools/compose_r45_candidate.py')).encode('utf8'))
    baseline=ART/'city_atomic_integration_r45/qa_copy_revision_v1/copy_plan_v2/copy_plan.json'
    traits=ART/'integration_sol_followup/offline_composer_v2/native_state_traits_r44.json'
    registry=ART/'native_facility_session_v1/native_lifts_third_v3/be_registry_actual.json'
    be=ART/'be_state_mismatch_sol_v15';stairs=ART/'pyramid_components_sol_v1/registered_stair_complete_batch_v2';waiting=ART/'pyramid_components_sol_v1/middle_lift_waiting_enclosed_v2';physical=ART/'lifts_doors_lifecycle_sol_v2/physical25_combined_v4'
    specs=[('registered_stairs243',stairs,243),('middle_waiting354',waiting,354),('retired_fixture_be8',be/'registry_actual_addendum_v3a/retired_eight_exact_proposal_v4',8),('route_sign_be1',be/'one_upper_route_sign_proposal_v1',1),('device_physical25',physical,25)]
    components=[];combined=[];be_rows=[]
    for ident,path,count in specs:
        forward=rows(path/'forward.jsonl.gz');inverse=rows(path/'inverse.jsonl.gz');assert len(forward)==len(inverse)==count
        for a,b in zip(forward,inverse):
            assert a['pos']==b['pos'] and all(a[k]==b[v]for k,v in [('before','after'),('after','before'),('before_nbt','after_nbt'),('after_nbt','before_nbt')])
        components.append(dict(id=ident,classification='CLASSIFIED_CANDIDATE_NOT_NATIVE',owner_prefixes=sorted({r['owner'] for r in forward}),patches=[dict(forward=ref(path/'forward.jsonl.gz'),inverse=ref(path/'inverse.jsonl.gz'),rows=count)]))
        combined.extend(dict(r,component=ident)for r in forward)
        if ident in {'retired_fixture_be8','route_sign_be1'}:be_rows.extend(forward)
    assert len(combined)==len({tuple(r['pos'])for r in combined})==631
    combined.sort(key=lambda r:tuple(r['pos']));jsonl(OUT/'forward631.jsonl.gz',combined)
    jsonl(OUT/'inverse631.jsonl.gz',[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt'])for r in combined])
    write(OUT/'reviewed_be_repairs9.json',be_rows)
    evidence=json.loads((be/'registry_actual_addendum_v3a/retired_eight_exact_proposal_v4/complete_component_owner_and_replacements.json').read_text('utf8'))
    replacements={tuple(r['position']):r for item in evidence for r in item['actual_current_replacement_complete']};assert len(replacements)==8
    write(OUT/'replacement_BE8.json',list(replacements.values()))
    metadata=json.loads((waiting/'static_metadata_reversible_proposal.json').read_text('utf8'));bundle=json.loads((physical/'bundle.json').read_text('utf8'))
    components[1]['files']=[dict(target=metadata['target'],before_sha256=metadata['before_sha256'],after=ref(Path(metadata['after_file'])),kind='STATIC_SEMANTIC_METADATA')]
    marker=bundle['marker'];components[-1]['files']=[dict(target=marker['relative'],before_sha256=marker['before_sha256'],after=ref(Path(marker['after_path'])),kind='STATIC_DEVICE_MARKER')]
    codecs=[ROOT/'tools'/x for x in ['query_blocks.py','inspect_map_assets.py','transplant_s22_authority.py','apply_s20_approved_semantic_repairs.py','regional_voxels.py','validate_ecology_plans_r44.py','release_combat_r36.py','review_exported_be_validity_r45.py']]
    proofs=[be/'registry_actual_addendum_v3a/artifact_epoch_actual_registry_repairs_v4.json',be/'registry_actual_addendum_v3a/retired_eight_exact_proposal_v4/complete_component_owner_and_replacements.json',be/'registry_actual_addendum_v3a/nine_record_projection_v4/projection_checks_and_full_NBT.json',stairs/'batch_scope_and_hashes.json',waiting/'report.json',physical/'bundle.json']
    template_inputs=[ART/'pyramid_components_sol_v1/stair_producer_keepouts_v1/root_registered_stair_producer_protection.patch',waiting/'producer_patch/root_middle_lobby_enclosed_producers.patch',be/'template_guards_v2/station_text_valid_state_guard.forward.patch']
    merged=b''.join(p.read_bytes().replace(b'\r\n',b'\n')for p in template_inputs)
    (OUT/'root_templates_combined.forward.patch').write_bytes(merged)
    # Reconstruct the complete reverse patch without changing current sources.
    # Each individual frozen patch already includes only explicit source hunks.
    lines=merged.decode('utf8').splitlines(True);back=[]
    import re
    for line in lines:
        if line.startswith('--- a/'):back.append(line.replace('--- a/','+++ a/',1))
        elif line.startswith('+++ b/'):back[-1],line=line.replace('+++ b/','--- b/',1),back[-1];back.append(line)
        elif line.startswith('@@ '):
            m=re.match(r'@@ -(\d+(?:,\d+)?) \+(\d+(?:,\d+)?) @@(.*)',line);assert m
            back.append('@@ -'+m[2]+' +'+m[1]+' @@'+m[3]+'\n')
        elif line.startswith('+'):back.append('-'+line[1:])
        elif line.startswith('-'):back.append('+'+line[1:])
        else:back.append(line)
    (OUT/'root_templates_combined.inverse.patch').write_bytes(''.join(back).encode('utf8'))
    ast.parse((ROOT/'tools/compose_r45_candidate_v5.py').read_text('utf8'))
    catalog=dict(schema='projectseele.r45.offline-composition.v5-source1736',source='artifacts/rebuild_r45/composition_candidates/R45_source_candidate_20261003_v4_01/world',baseline=ref(baseline),codec=ref(ART/'terrain_global_agent/stream_exact_install_r45_v2.py'),core=ref(OUT/'core/compose_v5_core.py'),native_state_contract=ref(traits),native_be_valid_blocks=ref(registry),reviewed_be_repairs=ref(OUT/'reviewed_be_repairs9.json'),replacement_BE8=ref(OUT/'replacement_BE8.json'),identity_file='dimensions/projectseele/geofront/data/projectseele_tokyo3_building_world_id_r44.dat',seed=-3816295015381828007,world_uuid='50ba377e-9053-5dfa-93be-9601e623037c',dimension='projectseele:geofront',default_components=[s[0]for s in specs],allowed_file_targets=[metadata['target'],marker['relative']],components=components,epochs=[ref(p)for p in [ROOT/'tools/compose_r45_candidate.py',ROOT/'tools/compose_r45_candidate_v5.py',*codecs,*proofs,*template_inputs,OUT/'root_templates_combined.forward.patch',OUT/'root_templates_combined.inverse.patch']])
    write(OUT/'catalog.json',catalog);(OUT/'catalog.json.sha256').write_bytes((sha(OUT/'catalog.json')+'\n').encode('ascii'))
    file_ops=[dict(target=metadata['target'],before_file=metadata['before_file'],before_sha256=metadata['before_sha256'],after_file=metadata['after_file'],after_sha256=metadata['after_sha256']),dict(target=marker['relative'],before_file=marker['before_path'],before_sha256=marker['before_sha256'],after_file=marker['after_path'],after_sha256=marker['after_sha256'])]
    write(OUT/'static_files_forward_inverse.json',file_ops)
    write(OUT/'scope_prepared.json',dict(unique_coordinates=631,components={ident:count for ident,_,count in specs},NBT_removals=8,NBT_migrations=1,block_state_changes=622,static_files=2,source_written=False,new_world_created=False,installed=False,new_structure_native=False,visual_accepted=False,world_progress_or_QA_copy=False,model_changed=False,forward631=ref(OUT/'forward631.jsonl.gz'),inverse631=ref(OUT/'inverse631.jsonl.gz')))
    print('Prepared sealed v5 entry631; no source/world/JVM writes.',flush=True)
if __name__=='__main__':main()
