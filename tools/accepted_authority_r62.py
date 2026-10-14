"""Reviewed62 publisher delta plus retained61 mechanical proof; no native PASS.

Never invokes61 validation against its former mutable named directory.
"""
import copy,hashlib,sys,zipfile
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
sys.path.insert(0,str(ROOT/'tools'))
from accepted_authority_r61 import read,ref,sha,need,reference,READBACKS,PROC
CASE='r62-reviewed-publisher-deadband-preserve-epoch53-and-insert42'
MANIFEST_SHA='a7f550f24fcfe46bcc4cfe1907210135ffeacf31a61f9d02f11ae8eb6c2ad6f2'
def pins():
    here=Path(__file__).resolve().parent;p=ROOT/'tools/data/r62_accepted_authority_exact_delta.json' if here.name=='tools' else here/'r62_accepted_authority_exact_delta.proposal.json'
    need(len(MANIFEST_SHA)==64 and p.is_file() and sha(p)==MANIFEST_SHA,'Actual62 pinned descriptor and Root review required');return read(p)
def frontier(p,world,require_current=False):
    import nbtlib
    d=read(reference(p['normal_saved_frontier']));s=d['authority'];need(s['claimed'] and not s['fault'] and not s['pending_installation'] and s['jobs']==2 and s['sha256']==p['saved_data_sha256'],'Actual normal-saved INSERT42 frontier required')
    need(all(s[k]==v for k,v in p['accepted_authority'].items()),'Original accepted authority changed')
    need(hashlib.sha256(d['jobs_snbt'].encode('utf8')).hexdigest()==p['jobs_snbt_sha256'],'Exact two-Job INSERT42 SNBT differs')
    jobs=nbtlib.parse_nbt(d['jobs_snbt']);need(len(jobs)==2 and {int(j['Snapshot']['Variant'])for j in jobs}=={0,2} and all(str(j['Phase'])=='PREPARING' and str(j['OwnerData']['Prepare'])=='INSERT' and int(j['OwnerData']['PrepareTicks'])==42 for j in jobs),'Two original INSERT/PrepareTicks42 tasks required')
    old=read(reference(p['historical61_source_association']));oldjobs=nbtlib.parse_nbt(read(reference(old['progress_frontier']))['jobs_snbt'])
    def actors(rows):return {tuple(int(v)for v in j['Snapshot']['Task']):tuple(tuple(int(v)for v in j['Snapshot'][k])for k in ('Eva','Plug','Pilot','Owner'))for j in rows}
    need(actors(jobs)==actors(oldjobs),'Original task/actor UUIDs changed before62')
    stop=read(reference(p['normal_exit61']));need(Path(d['normal_client_exit']).resolve()==reference(p['normal_exit61']) and stop['exit_code']==0 and stop['natural_exit'] is True and stop['jar_sha256']==p['previous61_jar_sha256'],'Actual normal61 exit0 required')
    actual=Path(world)/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat';need(Path(s['path']).resolve()==actual.resolve(),'Frontier belongs to another World')
    if require_current:need(sha(actual)==s['sha256'] and nbtlib.load(actual)['data']['Jobs']==jobs,'Actual pre-start INSERT42 frontier changed')
    return s
def exact_build_delta(p,build_receipt,check_live_source=False):
    from build_immutable_r52_candidate import frozen_build_class_pins,snapshot
    need(reference(p['current_build_receipt'])==Path(build_receipt).resolve(),'Actual62 build selection differs');new=read(reference(p['current_build_receipt']));old=read(reference(p['previous_build_receipt']))
    need(p['status']=='PINNED_ACTUAL62_AWAITING_ROOT_REVIEW' and new['sha256']==p['current62_jar_sha256'] and old['sha256']==p['previous61_jar_sha256'] and new['build_exit']==0 and not new['changed_during_build'],'Exact frozen actual62 required')
    def delta(a,b,w,kind):
        need(a.keys()==b.keys() and {k for k in a if a[k]!=b[k]}==set(w) and all(a[k]==v['before_sha256'] and b[k]==v['after_sha256']for k,v in w.items()),'Unreviewed '+kind+' bytes')
    before,after=read(reference(p['source_before'])),read(reference(p['source_after']));need(len(after)==1868,'Source62 count differs');delta(before,after,p['source_delta'],'Source')
    if check_live_source:need(snapshot()==after,'Live frozen Source62 changed')
    named_before,named_after=read(reference(p['named_before'])),read(reference(p['named_after']));delta(named_before,named_after,p['named_delta'],'named class')
    need(set(p['named_delta'])=={'com/projectseele/entity/EntryPlugCarrierEntity.class'} and new['named_class_manifest_sha256']==p['named_after']['sha256'] and all(sha(Path(new['named_class_directory'])/k)==v for k,v in named_after.items()),'Actual named62 publisher bytes differ')
    # Historical61 manifest is immutable; its named_class_directory is deliberately never read.
    jar=reference(dict(path=new['jar'],sha256=new['sha256']));frozen_build_class_pins(build_receipt,jar)
    with zipfile.ZipFile(reference(dict(path=old['jar'],sha256=old['sha256'])))as a,zipfile.ZipFile(jar)as b:
        need(len(a.namelist())==len(set(a.namelist())) and len(b.namelist())==len(set(b.namelist())),'Duplicate Jar entries')
        aa={k:hashlib.sha256(a.read(k)).hexdigest()for k in a.namelist()};bb={k:hashlib.sha256(b.read(k)).hexdigest()for k in b.namelist()};delta(aa,bb,p['jar_delta'],'Jar')
        need(set(p['jar_delta'])=={'META-INF/MANIFEST.MF','com/projectseele/entity/EntryPlugCarrierEntity.class'},'Unknown62 compiled change')
        manifest=lambda z:dict(s.split(': ',1)for s in z.read('META-INF/MANIFEST.MF').decode('utf8').splitlines()if ': 'in s)
        ma,mb=manifest(a),manifest(b);ma.pop('Implementation-Timestamp',None);mb.pop('Implementation-Timestamp',None);need(ma==mb,'Manifest changed beyond timestamp')
    for k in ('asset_readbacks','source_asset_readbacks','source_sounds_catalog','source_launch_subtitles','source_mechanical_crane_r61'):need(new[k]==old[k],'Geometry/resource pin changed: '+k)
    historical=read(reference(p['historical61_source_association']));loader=read(reference(p['historical61_mechanical_loader']))
    need(p['historical61_source_association']['sha256']=='032eab3c864a4cd4701f08c70eb6cdc47154db40654f4bb29749c0a553628cfd' and p['historical61_mechanical_loader']['sha256']=='361760ce43448b4e7bc98f8983d2520cdf218f742384332167747a211d03220e','Historical61 actual mechanical proof changed')
    need(historical['current_build_receipt']==p['previous_build_receipt'] and historical['source_geometry_delta'] is True and historical['all_geometry_equal'] is False and loader['native61_action_pass'] is False,'61 mechanical delta cannot be erased or labelled native62 PASS')
    installation=read(reference(p['root_install_receipt']));proof=read(reference(p['deadband_proof']));regression=read(reference(p['pure_java_deadband_regression']))
    source='src/main/java/com/projectseele/entity/EntryPlugCarrierEntity.java';need(set(p['source_delta'])=={source} and installation['changed_source']==[source] and installation['after_sha256']==after[source] and installation['native62_functional_pass'] is False,'Root publisher Source authorization differs')
    reference(dict(path=proof['actual_witness'],sha256=proof['actual_witness_sha256']));need(proof['before_sha256']==before[source] and proof['candidate_sha256']==after[source] and proof['native_actuator_invoked'] is False and regression['exit_code']==0 and regression['game_executed'] is False,'Actual61 passive witness/pure checks differ')
    need(p['mechanical_geometry_changed_from61'] is False and p['mechanical_geometry_delta_from60_retained'] is True and p['all_geometry_equal_from60'] is False and p['native62_functional_pass'] is False,'Source62 behavior delta cannot grant geometry/native equivalence')
    return new,historical
def validate(row,world,build_receipt,read_live_authority=True,check_live_source=True):
    from release_scope124_r53 import saved_runtime_authority,safe
    d=read(reference(row));p=pins();need(d['case']==CASE and d['schema']=='projectseele.r53.compatible-accepted-authority.v1' and Path(d['world']).resolve()==Path(world).resolve(),'Unknown62 case/World')
    new,historical=exact_build_delta(p,build_receipt,check_live_source);previous=read(reference(p['previous_pipeline']));prior=read(reference(p['previous_compatibility']))
    need(previous['compatible_accepted_authority']==p['previous_compatibility'] and previous['current61_source_association']==p['historical61_source_association'],'Immutable61 association linkage differs')
    need(d['current_build_receipt']==p['current_build_receipt'] and d['historical61_source_association']==p['historical61_source_association'] and d['behavior_delta_from61']==p['behavior_delta'],'Actual62 Source evidence selection differs')
    need(d['accepted_authority']==p['accepted_authority'] and d['initial_saved_runtime']==frontier(p,world) and d['progress_frontier']==p['normal_saved_frontier'],'Original accepted identity/INSERT42 evidence differs')
    need(d['source_geometry_delta_from60_retained'] is True and d['mechanical_geometry_changed_from61'] is False and all(d[k] is False for k in ('world_written','game_started','native_verified','native62_pass_imported','all_geometry_equal_from60')),'Source62 proof cannot import native PASS')
    for key in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):need(d[key]==prior[key],'Original accepted evidence changed: '+key)
    accepted,current=reference(d['accepted_bundle']),reference(d['current_candidate_bundle']);need(sha(accepted)==sha(current)==p['accepted_authority']['bundle_sha256'] and d['exact_accepted_bundle_copy']==d['current_candidate_bundle'],'Exact accepted authority copy required');bundle=read(accepted)
    for key in ('directory','mechanical_owner','upright_guideway','personnel_lifts','air_transport'):
        value=bundle[key];rel=safe(value['file']);need(sha(accepted.parent/rel)==value['sha256']==sha(current.parent/rel) and (not read_live_authority or sha(Path(world)/rel)==value['sha256']),'Accepted definition changed: '+key)
    def cells(v):
        if isinstance(v,dict):
            if 'cells_file'in v:
                rel=safe(v['cells_file']);need(sha(accepted.parent/rel)==v['sha256']==sha(current.parent/rel) and (not read_live_authority or sha(Path(world)/rel)==v['sha256']),'Accepted component cells changed')
            for x in v.values():cells(x)
        elif isinstance(v,list):
            for x in v:cells(x)
    cells(read(accepted.parent/bundle['mechanical_owner']['file']))
    pipeline=read(reference(d['current_pipeline']));expected=copy.deepcopy(previous['source_inputs']);expected['selected_build_receipt']=p['current_build_receipt'];expected['selected_jar']=ref(new['jar'])
    need(reference(pipeline['bundle'])==current and pipeline['source_inputs']==expected and pipeline['native_install_command'] is None,'Source62 pipeline inputs or installation command differs')
    proof=read(reference(d['current62_source_association']));need(pipeline['current62_source_association']==d['current62_source_association'] and proof['schema']=='projectseele.r62.current-source-publisher-association.v1' and proof['current_build_receipt']==p['current_build_receipt'] and proof['current_jar']==ref(new['jar']) and proof['source_inputs']==expected and proof['exact_delta_manifest_sha256']==MANIFEST_SHA,'Actual62 Source association differs')
    need(proof['historical61_source_association']==p['historical61_source_association'] and proof['historical61_mechanical_loader']==p['historical61_mechanical_loader'] and proof['behavior_delta_from61']==p['behavior_delta'] and proof['progress_frontier']==p['normal_saved_frontier'] and proof['initial_saved_runtime']==d['initial_saved_runtime'],'Historical61 geometry/new42 frontier linkage differs')
    need(proof['source_geometry_reports_reused_from_actual61'] is True and proof['mechanical_geometry_changed_from61'] is False and proof['source_geometry_delta_from60_retained'] is True and all(proof[k] is False for k in ('all_geometry_equal_from60','geometry_production_export_reexecuted','world_written','live_world_read','game_started','java_started','authority_reset','jobs_reset','native62_pass_imported','native62_functional_pass')),'Source62 geometry reuse cannot import functional PASS')
    for name in READBACKS:need(sha(reference(d['current_reports'][name]))==pipeline['reports'][name]==previous['reports'][name],'Unchanged61 physical report differs: '+name)
    need(d['source_geometry_directory_fingerprint']==read(reference(d['current_reports']['CURRENT_GUIDEWAY_REPORT.json']))['directory_fingerprint'],'Source geometry directory identity differs')
    if read_live_authority:
        state=saved_runtime_authority(world);need(state['claimed'] and not state['fault'] and not state['pending_installation'] and all(state[k]==v for k,v in p['accepted_authority'].items()),'Current accepted authority changed; no reset permitted')
    need(d['current62_native_status']=='PENDING' and d['actual_current62_cold_continuation'] is None,'Immutable Source association grants no functional62 PASS');return d
