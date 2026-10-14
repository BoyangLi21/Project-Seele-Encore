"""Exact Source61 motor geometry association, with the original two saved Jobs.

This validates Source/authority association only. It grants no native/release PASS.
Unknown bytes/cases fail; earlier compatibility cases are unchanged.
"""
import copy,gzip,hashlib,json,struct,zipfile
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
CASE='r61-reviewed-motor-fit-preserve-epoch53-and-two-jobs'
MANIFEST_SHA='0954d351eaa0a19d17230c10c108642ddad0ccc919a34dba903b17d71f4e439f'
REPORTS={'CURRENT_GUIDEWAY_REPORT.json','CURRENT_LEGACY_LEAD_REPORT.json','CURRENT_SOURCE_ENVELOPES.json','CURRENT_SPACE_DIRECTORY.json','CURRENT_AIR_SPACE_MERGE.json'}
READBACKS={'CURRENT_GUIDEWAY_REPORT.json','CURRENT_SOURCE_ENVELOPES.json','CURRENT_PHYSICAL_READBACK.json','CURRENT_CLOSED_GATE_READBACK.json'}
PROC='assets/projectseele/eva/actual_crane_procedural_triangles_r52.json.gz'
def need(value,message):
    if not value:raise ValueError(message)
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def reference(row):
    need(isinstance(row,dict) and {'path','sha256'}<=row.keys(),'Exact path/SHA evidence required')
    p=Path(row['path']).resolve();need(p.is_file() and sha(p)==row['sha256'],'Pinned evidence bytes differ: '+str(p));return p
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
def pins():
    here=Path(__file__).resolve().parent
    p=ROOT/'tools/data/r61_accepted_authority_exact_delta.json' if here.name=='tools' else here/'r61_accepted_authority_exact_delta.proposal.json'
    need(sha(p)==MANIFEST_SHA,'Unreviewed strict61 manifest');return read(p)
def frontier(p,world,require_current=False):
    import nbtlib
    path=reference(p['normal_saved_frontier']);d=read(path);s=d['authority']
    need(s['sha256']==p['saved_data_sha256'] and s['claimed'] and not s['fault'] and not s['pending_installation'] and s['jobs']==2,'Actual normal-saved two-Job frontier required')
    need(all(s[k]==v for k,v in p['accepted_authority'].items()),'Original accepted authority changed')
    need(hashlib.sha256(d['jobs_snbt'].encode('utf8')).hexdigest()==p['jobs_snbt_sha256'],'Original two-Job SNBT differs')
    jobs=nbtlib.parse_nbt(d['jobs_snbt']);need(len(jobs)==2 and {int(j['Snapshot']['Variant'])for j in jobs}=={0,2},'Original unit0/unit2 Jobs required')
    need(all(str(j['Phase'])=='PREPARING' and str(j['OwnerData']['Prepare'])=='INSERT' and int(j['OwnerData']['PrepareTicks'])==0 for j in jobs),'Original INSERT/PrepareTicks=0 frontier differs')
    need(all(int(j['Snapshot']['Epoch'])==53 and str(j['Snapshot']['DirectoryFingerprint'])==p['accepted_authority']['directory_fingerprint'] for j in jobs),'Original Jobs belong to another accepted authority')
    stop=read(d['normal_client_exit']);need(stop['exit_code']==0 and stop['natural_exit'] is True,'Actual normal60 exit0 required')
    actual=Path(world)/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat';need(Path(s['path']).resolve()==actual.resolve(),'Saved frontier belongs to another World')
    if require_current:need(sha(actual)==s['sha256'] and nbtlib.load(actual)['data']['Jobs']==jobs,'Actual two-Job frontier changed before native61')
    return s
def exact_build_delta(p,build_receipt):
    from build_immutable_r52_candidate import frozen_build_class_pins,snapshot
    newpath=reference(p['current_build_receipt']);oldpath=reference(p['previous_build_receipt']);need(newpath==Path(build_receipt).resolve(),'Strict61 selected build differs')
    old,new=read(oldpath),read(newpath)
    need(old['sha256']==p['previous60_jar_sha256'] and new['sha256']==p['current61_jar_sha256'] and new['build_exit']==0 and not new['changed_during_build'],'Actual frozen build61 required')
    oldsource,newsource=read(reference(p['source_before'])),read(reference(p['source_after']))
    need(len(newsource)==1868 and newsource==snapshot(),'Actual frozen Source61 bytes changed')
    def delta(a,b,expected,kind):
        need(a.keys()==b.keys() and {k for k in a if a[k]!=b[k]}==set(expected),'Unreviewed '+kind+' delta')
        need(all(a[k]==v['before_sha256'] and b[k]==v['after_sha256']for k,v in expected.items()),'Exact reviewed '+kind+' bytes differ')
    delta(oldsource,newsource,p['source_delta'],'Source');oldnamed,newnamed=read(reference(p['named_before'])),read(reference(p['named_after']))
    delta(oldnamed,newnamed,p['named_delta'],'named production class')
    need(new['named_class_manifest_sha256']==p['named_after']['sha256'] and all(sha(Path(new['named_class_directory'])/k)==v for k,v in newnamed.items()),'Actual named61 production classes differ')
    frozen_build_class_pins(newpath,reference(dict(path=new['jar'],sha256=new['sha256'])))
    with zipfile.ZipFile(reference(dict(path=old['jar'],sha256=old['sha256'])))as a,zipfile.ZipFile(new['jar'])as b:
        need(len(a.namelist())==len(set(a.namelist())) and len(b.namelist())==len(set(b.namelist())),'Duplicate Jar entries rejected')
        aa={k:hashlib.sha256(a.read(k)).hexdigest()for k in a.namelist()};bb={k:hashlib.sha256(b.read(k)).hexdigest()for k in b.namelist()};delta(aa,bb,p['jar_delta'],'Jar')
        def manifest(z):return dict(s.split(': ',1)for s in z.read('META-INF/MANIFEST.MF').decode('utf8').splitlines()if ': 'in s)
        ma,mb=manifest(a),manifest(b);ma.pop('Implementation-Timestamp',None);mb.pop('Implementation-Timestamp',None);need(ma==mb,'Unreviewed Jar manifest change')
        need(new['source_mechanical_crane_r61']==p['source_mechanical_crane_r61'] and bb[PROC]==p['source_mechanical_crane_r61']['source']['source_gzip_sha256'],'Mechanical Source/Jar row differs')
        before,after=gzip.decompress(a.read(PROC)),gzip.decompress(b.read(PROC))
    return new,before,after
def source_association(row,p,world,build_receipt):
    need(row['sha256']=='032eab3c864a4cd4701f08c70eb6cdc47154db40654f4bb29749c0a553628cfd','Exact Root actual61 pre-start association required')
    doc=read(reference(row));need(doc['schema']=='projectseele.r61.current-source-association-with-explicit-mechanical-delta.v1' and doc['current_build_receipt']==p['current_build_receipt'] and doc['previous_source_pipeline']==p['previous_pipeline'],'Source61 association refers to another actual build/pipeline')
    need(doc['unaffected_source_reports_equal'] is True and doc['all_geometry_equal'] is False and doc['source_geometry_delta'] is True,'Mechanical delta cannot be labelled all-geometry/cache equivalence')
    need(all(doc[k] is False for k in ('world_written','game_started','authority_reset','jobs_reset','native61_pass_imported','native61_functional_pass')),'Source61 proof cannot import native PASS or reset progress')
    need(set(doc['fresh_source_reports'])==REPORTS and set(doc['previous_source_reports'])==REPORTS,'Complete five unaffected reports required')
    previous=read(reference(p['previous_source_equivalence']))
    base_inputs=copy.deepcopy(read(reference(p['previous_pipeline']))['source_inputs']);base_inputs['selected_build_receipt']=p['current_build_receipt'];base_inputs['selected_jar']=doc['current_jar']
    need(doc['source_inputs']==base_inputs,'Unreviewed current Source inputs changed')
    need(doc['previous_source_reports']==previous['fresh_source_reports'],'Source61 previous five reports changed')
    for name in REPORTS:need(read(reference(doc['fresh_source_reports'][name]))==read(reference(doc['previous_source_reports'][name])),'Unaffected Source output differs: '+name)
    need(doc['progress_frontier']==p['normal_saved_frontier'] and doc['initial_saved_runtime']==frontier(p,world),'Actual saved two-Job frontier differs')
    build,before,after=exact_build_delta(p,build_receipt)
    need(doc['source_inputs']['selected_build_receipt']==p['current_build_receipt'] and doc['current_jar']==doc['source_inputs']['selected_jar']==ref(build['jar']),'Source inputs select another Jar')
    need(doc['mechanical_loader_check']['sha256']=='361760ce43448b4e7bc98f8983d2520cdf218f742384332167747a211d03220e','Exact actual61 production loader proof required')
    loader=read(reference(doc['mechanical_loader_check']));source=p['source_mechanical_crane_r61']['source'];grip='af16832dc6c143d3c6a23eb38811021b75c13860436682e8071b9990fc83067f'
    need(loader['source_gzip_sha256']==source['source_gzip_sha256'] and loader['source_json_sha256']==source['source_json_sha256'] and loader['gripper_sha256']==grip,'Actual compiled mechanical loader bytes differ')
    need(loader['source_fingerprint']==hashlib.sha256((source['source_json_sha256']+':'+grip).encode('utf8')).hexdigest() and loader['actual_named_class_origin']==Path(build['named_class_directory']).as_uri().replace('file:///','file:/')+'/', 'Actual compiled mechanical loader origin/fingerprint differs')
    need(loader['total_procedural_triangles']==28044 and loader['ordinary_offline_pose_part_count']==19 and loader['mechanical_geometry_changed'] is True and all(loader[k] is False for k in ('world_written','game_started','native61_action_pass')),'Complete actual loader proof required; native action remains pending')
    olddoc,newdoc=json.loads(before),json.loads(after);oldparts,newparts=olddoc.pop('parts'),newdoc.pop('parts');need(olddoc==newdoc and oldparts.keys()==newparts.keys(),'Crane metadata/part set changed')
    need(all(oldparts[k]==newparts[k]for k in oldparts if k!='top'),'Unreviewed five procedural parts changed')
    for k,a in newparts.items():
        row=loader['parts'][k];need(row==dict(triangles=len(a)//9,loaded_double_bits_sha256=hashlib.sha256(struct.pack('>'+str(len(a))+'d',*a)).hexdigest(),all_source_double_bits_exact=True),'Actual loaded procedural triangle bits differ: '+k)
    bits=lambda a:[struct.pack('>9d',*a[i:i+9])for i in range(0,len(a),9)]
    aa,bb=bits(oldparts['top']),bits(newparts['top']);need(len(aa)==len(bb)==23440 and sum(x!=y for x,y in zip(aa,bb))==11592,'Reviewed actual complete top delta differs')
    need(doc['mechanical_delta']==dict(before_raw_sha256=hashlib.sha256(before).hexdigest(),after_raw_sha256=hashlib.sha256(after).hexdigest(),top_total_triangles=23440,top_changed_triangles=11592,top_unchanged_triangles=11848,other_five_procedural_parts_unchanged=True,motor_center_y_before=.03,motor_center_y_after=.60,first_hose_reconnected=True),'Exact mechanical delta summary differs')
    return doc
def validate(row,world,build_receipt,require_initial_frontier=False,read_live_authority=True):
    from release_scope124_r53 import saved_runtime_authority,safe
    d=read(reference(row));p=pins();need(d.get('schema')=='projectseele.r53.compatible-accepted-authority.v1' and d.get('case')==CASE,'Unknown strict61 case')
    need(Path(d['world']).resolve()==Path(world).resolve() and d['accepted_authority']==p['accepted_authority'],'Strict61 World/accepted identity differs')
    prior=read(reference(p['previous_compatibility']));previous=read(reference(p['previous_pipeline']));reference(p['root_install_receipt'])
    need(previous['compatible_accepted_authority']==p['previous_compatibility'] and previous['current60_source_equivalence']==p['previous_source_equivalence'],'Exact validated Source60 association changed')
    need(d['current_build_receipt']==p['current_build_receipt'] and d['previous_compatibility']==p['previous_compatibility'],'Strict61 build/parent association differs')
    proof=source_association(d['current61_source_association'],p,world,build_receipt)
    need(all(d[k] is False for k in ('world_written','game_started','native_verified','native61_pass_imported','all_geometry_equal')) and d['source_geometry_delta'] is True,'Source61 association is not native acceptance')
    for key in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):need(d[key]==prior[key],'Original accepted proof changed: '+key)
    accepted=reference(d['accepted_bundle']);current=reference(d['current_candidate_bundle']);need(sha(accepted)==sha(current)==p['accepted_authority']['bundle_sha256'] and d['exact_accepted_bundle_copy']==d['current_candidate_bundle'],'Exact accepted bundle copy required')
    bundle=read(accepted);need(bundle['epoch']==53 and bundle['directory_fingerprint']==p['accepted_authority']['directory_fingerprint'],'Original accepted bundle identity differs')
    for key in ('directory','mechanical_owner','upright_guideway','personnel_lifts','air_transport'):
        value=bundle[key];relative=safe(value['file']);need(sha(accepted.parent/relative)==value['sha256']==sha(current.parent/relative) and (not read_live_authority or sha(Path(world)/relative)==value['sha256']),'Original accepted definition bytes differ: '+key)
    need(sha(reference(d['accepted_physical_receipt']))==read(accepted.parent/bundle['directory']['file'])['installation_receipt_sha256']==read(accepted.parent/bundle['mechanical_owner']['file'])['commissioning_receipt_sha256'],'Original accepted physical receipt binding differs')
    def cells(value):
        if isinstance(value,dict):
            if 'cells_file'in value:
                rel=safe(value['cells_file']);need(sha(accepted.parent/rel)==value['sha256']==sha(current.parent/rel) and (not read_live_authority or sha(Path(world)/rel)==value['sha256']),'Accepted component table bytes changed')
            for v in value.values():cells(v)
        elif isinstance(value,list):
            for v in value:cells(v)
    cells(read(accepted.parent/bundle['mechanical_owner']['file']))
    pipeline=read(reference(d['current_pipeline']));need(reference(pipeline['bundle'])==current and pipeline['source_inputs']==proof['source_inputs'],'Strict61 current Source/bundle selection differs')
    for name in READBACKS:need(sha(reference(d['current_reports'][name]))==pipeline['reports'][name]==previous['reports'][name],'Unaffected physical/guide readback changed: '+name)
    need(d['source_geometry_directory_fingerprint']==read(reference(d['current_reports']['CURRENT_GUIDEWAY_REPORT.json']))['directory_fingerprint'],'Current guide geometry fingerprint differs')
    need(d['initial_saved_runtime']==frontier(p,world,require_initial_frontier) and d['saved_data_unchanged_during_pre_start_source_proof_sha256']==p['saved_data_sha256'],'Strict61 prepared two-Job frontier differs')
    if read_live_authority:
        state=saved_runtime_authority(world);need(state['claimed'] and not state['fault'] and not state['pending_installation'] and all(state[k]==v for k,v in p['accepted_authority'].items()),'Actual persisted accepted authority changed; no reset permitted')
    need(d['actual_current61_cold_continuation'] is None and d['current61_native_status']=='PENDING','This immutable Source association grants no native continuation PASS')
    return d
