from pathlib import Path
R=Path('D:/eva');p=R/'tools/prepare_command17_short_art_v13_r45.py';s=p.read_text('utf8')
s=s.replace('"""Finite current v13 one-lane/three-photo preparation; root copies/binds/launches."""','"""Finite restored v13 ID6 sameQA precheck/bind. No world copy/write or JVM."""')
s=s.replace("read=reuse.read;write=reuse.write;sha=reuse.sha;ref=reuse.ref", "read=reuse.read;write=reuse.write;sha=reuse.sha;ref=reuse.ref\nDIAG=ART/'lifts_doors_lifecycle_sol_v2/command17_first_contact_postrun_job_v2'\nCOLD=ART/'lifts_doors_lifecycle_sol_v2/command17_first_contact_postrun_job_v1/postrun_inventory_and_firstcontact_job.UNBOUND.json'")
a='def copy_root():\n    reuse.old.WORLD=WORLD;reuse.old.BASELINE=BASELINE;reuse.old.source=source;reuse.old.copy_root(PLAN,True)\n';assert a in s
s=s.replace(a,'''def cold():
    b,source_files,total=source();snapshot=read(COLD)
    assert snapshot['schema']=='projectseele.ID6-restored-postrun-first-contact.v1' and Path(snapshot['world']).resolve()==TARGET.resolve()
    assert snapshot['file_count']==1739 and snapshot['parent_root_actual_exit0'] and snapshot['parent_restored']
    expected={r['relative']:r['sha256']for r in snapshot['files']};assert len(expected)==1739 and reuse.old.inv(TARGET)==expected,'Actual cold QA changed; no bind'
    parents={k:snapshot[k]for k in ('parent_binding','parent_admission','parent_result')}
    parents['parent_job']=ref(Path(parents['parent_binding']['path']).with_name('commands.bound.json'))
    for row in parents.values():assert sha(Path(row['path']))==row['sha256'],'Actual parent receipt changed'
    old=read(Path(parents['parent_binding']['path']));result=read(Path(parents['parent_result']['path']));admission=read(Path(parents['parent_admission']['path']));job=read(Path(parents['parent_job']['path']))
    assert result['actual_actor_restored'] and result['original_snapshot_captured'] and result['required_cases']==1 and result['completed_cases']==0
    assert result['first_failure']['current_input']['id']=='cross/6/lane1/from-1' and result['first_failure']['phase']=='WALK'
    assert admission['passed'] and admission['binding_sha256']==parents['parent_binding']['sha256']==job['candidate_binding_sha256']
    assert Path(job['world']).resolve()==TARGET.resolve() and 'postrun_ID6_first_contact'not in old
    assert job['inputs']==ref(INPUTS) and job['short_art_preview_v13']==ref(VIEWS)
    assert {r['relative']:r['sha256']for r in read(PLAN.parent/'copy_receipt.json')['files']}==source_files
    assert all(expected[r['relative']]==source_files[r['relative']]==r['sha256'] for r in old['fixed_city_files'])
    return b,expected,total,dict(cold_snapshot=ref(COLD),**parents),source_files

def precheck(a):
    b,actual,total,parent,source_files=cold()
    receipt=dict(schema='projectseele.ID6-sameQA-readonly-precheck.v1',world=str(TARGET),source_v13_diagnostic_only=True,formal_v14_world_written=False,files1739_exact=True,fixed_city_bytes_unchanged=True,parent=parent,root_confirmed_parent_exec75103_exit0=True,parent_functional_pass=False,parent_strict_restoration_pass=True,changed_since_original_v13_copy=[k for k,v in actual.items()if source_files[k]!=v],new_world_copy_or_world_write=False,Java_started=False,first_contact_scope={'case':'cross/6/lane1/from-1','gameTicks_limit_after_staging_ready':160,'photos':0,'full141':False,'stop_first_assigned_shape_clip':True})
    if a.out:assert not a.out.exists();write(a.out,receipt)
    print('Read-only precheck: exact1739 restored QA; original City bytes unchanged; parent failure retained.',flush=True)
''')
a="assert a.execute_root,'Root chooses actual compile and binding epoch';out=reuse.common.external(a.out);b,files,total=source();copied=read(PLAN.parent/'copy_receipt.json')\n    assert copied['copy_complete']and{r['relative']:r['sha256']for r in copied['files']}==files==reuse.old.inv(TARGET)";b="assert a.execute_root,'Root chooses actual compile and binding epoch';out=reuse.common.external(a.out);b,files,total,parent,source_files=cold()\n    copied=read(PLAN.parent/'copy_receipt.json');assert copied['copy_complete']and not copied['source_written']";assert a in s;s=s.replace(a,b)
a="assert sha(ROOT/f'src/main/java/com/projectseele/{rel}.java')==sha(OWN/f'root_actual202_source_epoch/{name}.java'),'Actual reviewed short source required'";b="assert (ROOT/f'src/main/java/com/projectseele/{rel}.java').read_text('utf8')==(DIAG/f'{name}.java.candidate.txt').read_text('utf8'),'Entire reviewed postrun source required; not a string presence check'";assert a in s;s=s.replace(a,b)
s=s.replace("[ref(a.compile_log),ref(INPUTS),ref(VIEWS),ref(BASELINE),*origin.values()]", "[ref(a.compile_log),ref(INPUTS),ref(VIEWS),ref(BASELINE),*origin.values(),*parent.values()]")
s=s.replace("active_scopes=['COMMAND17','SOURCE_PHOTOS']", "active_scopes=['COMMAND17']")
s=s.replace("composed_source_v13=origin,source_epoch", "composed_source_v13=origin,postrun_ID6_first_contact=parent,source_epoch")
s=s.replace("output=str(out/'ID6_one_crossing_three_art_images.native.json')", "first_contact_diagnostic=True,output=str(out/'ID6_first_contact_160tick.native.json')")
a="write(out/'prepared.json',dict(bound=True,actual_one_failed_lane_only=True,three_images_requested=True,full141_executed=False,Java_started=False,world_written_by_bind=False,cabin_trip_or_natural_entry_proven=False,full_lifecycle_pass=False))";b="write(out/'prepared.json',dict(bound=True,actual_one_failed_lane_only=True,same_restored_postrun_QA=True,photos_requested=0,actual_server_gameTicks_limit160=True,stop_first_assigned_shape_clip=True,full141_executed=False,Java_started=False,world_written_by_bind=False,cabin_trip_or_natural_entry_proven=False,full_lifecycle_pass=False))";assert a in s;s=s.replace(a,b)
s=s.replace("print('Root froze actual v13 one-lane/three-photo launch only; no Java started.')", "print('Root froze restored sameQA ID6 first-contact160tick launch only; no Java/world write.',flush=True)")
a=s.index('def main():');s=s[:a]+'''def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['precheck','bind']);p.add_argument('--execute-root',action='store_true');p.add_argument('--compile-log',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    if a.mode=='precheck':precheck(a)
    else:assert a.execute_root and a.compile_log and a.out;bind(a)
if __name__=='__main__':main()
'''
(R/'tools/prepare_command17_first_contact_sameQA_r45.py').write_text(s,encoding='utf8')
print('Prepared finite sameQA tool; no bind/copy/Java performed.')
