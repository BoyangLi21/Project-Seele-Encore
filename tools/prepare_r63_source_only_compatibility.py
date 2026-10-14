"""Exact Root final63 review and same-authority source-only association.

Root supplies real final BR, installed Source delta and saved frontier.
No Java/game/geometry export, World read/write, reset or native PASS.
"""
import argparse,copy,hashlib,json,shutil,sys,zipfile
from pathlib import Path
ROOT=Path('C:/Users/liboy/.codex/worktrees/r51-nonmap/eva')
sys.path.insert(0,str(ROOT/'tools'))
from accepted_authority_r61 import read,ref,sha,need,reference,READBACKS,PROC
CASE='r63-original-rig-nonphysical-scope-preserve-epoch53-and-progress'
MANIFEST_SHA='7bbd42bedeb459933c9f1775307f9e39cbb06910e79ef8181b028f14a2050b6f'
BASE=Path('D:/eva/artifacts/map_complete_20261013')
PREVIOUS=BASE/'current_runtime_bundle_release62_accepted_authority_final/CURRENT_BUNDLE_PIPELINE_RECEIPT.json'
RESTORE={'src/main/resources/'+PROC:('a12a1f1b47ddf852a8a6e5165def8739c6a1698a4c672ad55fa7d7b30985258b','366cbc5d927d4b6655d32deb40169313390725a44d61700321096d4d559f6ca2')}
REVIEWED_PATHS=set(RESTORE)|{
 'src/main/java/com/projectseele/client/render/PlugGantryRenderer.java',
 'src/main/java/com/projectseele/world/NervCraneGeometryR52.java',
 'src/main/java/com/projectseele/world/NervCranePoseR52.java',
 'src/main/java/com/projectseele/world/NervAssemblyOwnerR52.java'}

def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def pins():
    here=Path(__file__).resolve().parent;p=ROOT/'tools/data/r63_source_only_exact_delta.json' if here.name=='tools' else here/'r63_source_only_exact_delta.proposal.json'
    need(len(MANIFEST_SHA)==64 and sha(p)==MANIFEST_SHA,'Actual63 descriptor and Root review required');return read(p)
def exact_delta(a,b,w,kind):
    need(a.keys()==b.keys() and {k for k in a if a[k]!=b[k]}==set(w) and all(a[k]==v['before_sha256'] and b[k]==v['after_sha256']for k,v in w.items()),'Unreviewed '+kind+' delta')
def saved_frontier(row,world):
    d=read(reference(row));state=d['authority'];need(state['claimed'] and not state['fault'],'Actual cold saved authority required')
    need(Path(state['path']).resolve()==world/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat','Frontier belongs to another World')
    jobs=d['jobs'];need(len(jobs)==state['jobs']==2 and {int(j['variant'])for j in jobs}=={0,2},'Current two original internal preparation states required')
    need(all(j['phase']=='PREPARING' and j['preparation']=='INSERT' and int(j['preparation_age'])==138 for j in jobs),'Current actual saved preparation state differs')
    need(d['runtime_verified']is False and d['world_written']is False and d['replay_result']['exit_code']==1 and d['replay_result']['natural_exit']is False,'Current replay outcome must retain its actual unverified/non-normal exit facts')
    # PendingInstallation is the same accepted bundle asynchronous restore request.
    # Keep it intact; a current cold snapshot is not a normal-exit proof.
    return state,hashlib.sha256(json.dumps(jobs,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()

def validate(row,world,build_receipt):
    from release_scope124_r53 import saved_runtime_authority,safe
    from build_immutable_r52_candidate import frozen_build_class_pins
    d=read(reference(row));p=pins();world=Path(world).resolve();need(d['case']==CASE and Path(d['world']).resolve()==world and reference(p['current_build_receipt'])==Path(build_receipt).resolve(),'Exact current63 case/build/World required')
    new,old=read(reference(p['current_build_receipt'])),read(reference(p['previous_build_receipt']));need(new['sha256']==p['current63_jar_sha256'] and new['build_exit']==0 and not new['changed_during_build'],'Actual completed final63 required')
    exact_delta(read(reference(p['source_before'])),read(reference(p['source_after'])),p['source_delta'],'Source')
    # Read historical62 manifest, never its now-reused named class directory.
    exact_delta(read(reference(p['named_before'])),read(reference(p['named_after'])),p['named_delta'],'named class')
    frozen_build_class_pins(build_receipt,new['jar'])
    with zipfile.ZipFile(reference(dict(path=old['jar'],sha256=old['sha256'])))as a,zipfile.ZipFile(new['jar'])as b:
        aa={k:hashlib.sha256(a.read(k)).hexdigest()for k in a.namelist()};bb={k:hashlib.sha256(b.read(k)).hexdigest()for k in b.namelist()};exact_delta(aa,bb,p['jar_delta'],'Jar')
    previous=read(reference(p['previous_pipeline']));prior=read(reference(previous['compatible_accepted_authority']))
    for k in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):need(d[k]==prior[k],'Original accepted evidence changed')
    accepted,current=reference(d['accepted_bundle']),reference(d['current_candidate_bundle']);need(sha(accepted)==sha(current)==p['accepted_authority']['bundle_sha256'],'Accepted bundle bytes changed');bundle=read(accepted)
    for k in ('directory','mechanical_owner','upright_guideway','personnel_lifts','air_transport'):
        r=bundle[k];name=safe(r['file']);need(sha(accepted.parent/name)==r['sha256']==sha(current.parent/name)==sha(world/name),'Accepted definition changed')
    pipeline=read(reference(d['current_pipeline']));need(pipeline['source_inputs']['selected_build_receipt']==p['current_build_receipt'] and pipeline['source_inputs']['selected_jar']==ref(new['jar']),'Current63 pipeline links differ')
    for name in READBACKS:need(pipeline['reports'][name]==previous['reports'][name]==sha(reference(d['current_reports'][name])),'Unchanged declaration/guide report differs')
    state=saved_runtime_authority(world);need(state['claimed'] and not state['fault'] and state['sha256']==p['initial_saved_runtime']['sha256'] and state['pending_installation']==p['initial_saved_runtime']['pending_installation'] and all(state[k]==v for k,v in p['accepted_authority'].items()),'Actual accepted identity changed')
    need(d['original_restore']is True and d['all_geometry_equal']is False and d['native_verified']is False and d['native63_functional_pass']is False,'Restoration cannot import native PASS');return d
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('build-receipt','reviewed-source-delta','cold-frontier','out'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();need(not a.out.exists(),'Fresh external Source association required');previous=read(PREVIOUS);world=Path(previous['world']).resolve();need(not a.out.resolve().is_relative_to(world),'Output outside World required')
    reviewed=read(a.reviewed_source_delta);need(reviewed.get('draft')is not True and reviewed['schema']=='projectseele.r63.root-reviewed-source-delta.v1' and reviewed['original_r50_nonphysical_rig_scope_restored']is True and reviewed['capsule_pilot_continuous_occupancy_guards_retained']is True,'Root exact installation/scope review required')
    delta=reviewed['source_delta'];need(all(delta[k]==dict(before_sha256=x,after_sha256=y)for k,(x,y)in RESTORE.items()),'Exact motor/geometry original restoration differs')
    need(ref(a.reviewed_source_delta)['sha256']=='05530089e0a89ee0c8fdf346723c9b4952d45420c0e7008cccc4b634e3ca453d','Exact Root final5 installation review required')
    pose_path='src/main/java/com/projectseele/world/NervCranePoseR52.java';pose_row=next(x for x in reviewed['files']if x['path']==pose_path)
    def original_ground_method(text):
        at=text.index('public static RigidTransform ropeFrame(');start=text.index('{',at);depth=0
        for i in range(start,len(text)):
            if text[i]=='{':depth+=1
            elif text[i]=='}':
                depth-=1
                if depth==0:return text[at:i+1]
        raise ValueError('Unclosed original ground rope frame')
    need(original_ground_method(Path(pose_row['inverse']).read_text('utf8'))==original_ground_method((ROOT/pose_path).read_text('utf8')),'Original ground_bracket ropeFrame changed')
    need(set(delta)==REVIEWED_PATHS,'Review additional finalSource changes explicitly before using this minimal63 case')
    build=read(a.build_receipt);oldpath=reference(previous['source_inputs']['selected_build_receipt']);old=read(oldpath)
    need(build['build_exit']==0 and not build['changed_during_build'] and build['source_files']==old['source_files'],'Actual successful unchanged final63 build required')
    beforepath=oldpath.parent/'SOURCE_BEFORE.json';afterpath=a.build_receipt.resolve().parent/'SOURCE_BEFORE.json';before,after=read(beforepath),read(afterpath);exact_delta(before,after,delta,'Root-reviewed Source')
    namedoldpath=Path(old['named_class_manifest']);namednewpath=Path(build['named_class_manifest']);namedold,namednew=read(namedoldpath),read(namednewpath);need(namedold.keys()==namednew.keys(),'Unexpected63 class additions/removals')
    named_delta={k:dict(before_sha256=namedold[k],after_sha256=namednew[k])for k in namedold if namedold[k]!=namednew[k]};prefixes=[k.removeprefix('src/main/java/').removesuffix('.java')for k in delta if k.endswith('.java')]
    need(all(any(k==s+'.class' or k.startswith(s+'$')for s in prefixes)for k in named_delta),'Unreviewed63 class family changed')
    with zipfile.ZipFile(reference(dict(path=old['jar'],sha256=old['sha256'])))as z,zipfile.ZipFile(reference(dict(path=build['jar'],sha256=build['sha256'])))as w:
        aa={k:hashlib.sha256(z.read(k)).hexdigest()for k in z.namelist()};bb={k:hashlib.sha256(w.read(k)).hexdigest()for k in w.namelist()};need(aa.keys()==bb.keys(),'Unexpected63 Jar additions/removals');jar_delta={k:dict(before_sha256=aa[k],after_sha256=bb[k])for k in aa if aa[k]!=bb[k]}
        need(all(k in {'META-INF/MANIFEST.MF',PROC} or any(k==s+'.class' or k.startswith(s+'$')for s in prefixes)for k in jar_delta),'Unknown63 Jar resource/class change')
        manifest=lambda q:dict(x.split(': ',1)for x in q.read('META-INF/MANIFEST.MF').decode('utf8').splitlines()if ': 'in x);ma,mb=manifest(z),manifest(w);ma.pop('Implementation-Timestamp',None);mb.pop('Implementation-Timestamp',None);need(ma==mb,'Manifest changed beyond timestamp')
    need(build['source_mechanical_crane_r61']['source'].get('original_restore')is True and build['source_mechanical_crane_r61']['source']['source_gzip_sha256']==RESTORE['src/main/resources/'+PROC][1] and build['source_mechanical_crane_r61']['source']['source_json_sha256']=='3411018955aec9b8827dcfcc217275fffd3edbe8880d448500f06beefd216064','Actual63 original source/Jar mechanical row required')
    state,jobsha=saved_frontier(ref(a.cold_frontier),world);need(ref(a.cold_frontier)['sha256']=='0467b7021fe292f710c53074fb2b1f49357e21f37ef72f5338f67cb260214028','Exact current after-replay cold frontier required');authority={k:state[k]for k in ('epoch','directory_fingerprint','bundle_relative','bundle_sha256','guide_sha256')}
    need(authority==read(reference(previous['compatible_accepted_authority']))['accepted_authority'],'Current cold snapshot changed original accepted authority')
    a.out.mkdir(parents=True);prior=read(reference(previous['compatible_accepted_authority']));accepted=reference(prior['accepted_bundle']);copied=a.out/'accepted_authority_bundle';shutil.copytree(accepted.parent,copied);bound=copied/accepted.name
    for name in READBACKS:shutil.copyfile(PREVIOUS.parent/name,a.out/name)
    descriptor=dict(schema='projectseele.r63.exact-root-source-only-delta.v1',current_build_receipt=ref(a.build_receipt),current63_jar_sha256=build['sha256'],previous_build_receipt=ref(oldpath),previous_pipeline=ref(PREVIOUS),root_source_review=ref(a.reviewed_source_delta),source_before=ref(beforepath),source_after=ref(afterpath),named_before=ref(namedoldpath),named_after=ref(namednewpath),source_delta=delta,named_delta=named_delta,jar_delta=jar_delta,accepted_authority=authority,current_cold_frontier=ref(a.cold_frontier),initial_saved_runtime=state,current_jobs_projection_sha256=jobsha,original_restore=True,all_geometry_equal=False,native63_functional_pass=False)
    descriptorpath=a.out/'r63_source_only_exact_delta.proposal.json';write(descriptorpath,descriptor)
    current=copy.deepcopy(previous)
    for k in ('compatible_accepted_authority','original_current_pipeline','current62_source_association','historical61_source_association','source_geometry_delta_from60_retained','mechanical_geometry_changed_from61','actual_current62_cold_continuation','all_geometry_equal_from60','current_native_installation_directory','current_native_inputs_path','current_native_result_path','native_executed_by'):current.pop(k,None)
    current['source_inputs']['selected_build_receipt']=ref(a.build_receipt);current['source_inputs']['selected_jar']=ref(build['jar']);current.update(bundle=ref(bound),native_install_command=None,native_verified=False,game_started=False,world_written=False,original_restore=True,all_geometry_equal=False,progress_frontier=ref(a.cold_frontier),source_only_exact_delta=ref(descriptorpath),source_geometry_review_scope='Current original restore and dedicated legacy hoist frame code review; historical guide/nav/static reports only',historical_previous_source_pipeline=ref(PREVIOUS),next='Fixed private manual acceptance version; all17 runtime checks remain unverified.')
    currentpath=a.out/'CURRENT63_SOURCE_PIPELINE.json';write(currentpath,current)
    side=dict(schema='projectseele.r53.compatible-accepted-authority.v1',case=CASE,world=str(world),current_build_receipt=ref(a.build_receipt),current_pipeline=ref(currentpath),current_candidate_bundle=ref(bound),exact_accepted_bundle_copy=ref(bound),current_reports={n:ref(a.out/n)for n in READBACKS},accepted_authority=authority,initial_saved_runtime=state,progress_frontier=ref(a.cold_frontier),source_only_exact_delta=ref(descriptorpath),source_geometry_directory_fingerprint=read(a.out/'CURRENT_GUIDEWAY_REPORT.json')['directory_fingerprint'],original_restore=True,all_geometry_equal=False,native_verified=False,native63_functional_pass=False,world_written=False,game_started=False)
    for k in ('accepted_pipeline','accepted_bundle','accepted_build_receipt','accepted_physical_receipt'):side[k]=prior[k]
    sidepath=a.out/'CURRENT_R63_ACCEPTED_AUTHORITY_COMPATIBILITY.json';write(sidepath,side);current.update(compatible_accepted_authority=ref(sidepath),original_current_pipeline=ref(currentpath));wrapper=a.out/'CURRENT_BUNDLE_PIPELINE_RECEIPT.json';write(wrapper,current)
    # Candidate guard gets exact actual descriptor SHA, for Root review/adoption.
    source=Path(__file__).read_text('utf8').replace("MANIFEST_SHA='7bbd42bedeb459933c9f1775307f9e39cbb06910e79ef8181b028f14a2050b6f'","MANIFEST_SHA='"+sha(descriptorpath)+"'")
    (a.out/'prepare_r63_source_only_compatibility.pinned.proposal.py').write_text(source,'utf8')
    result=dict(current_pipeline=ref(wrapper),compatibility=ref(sidepath),descriptor=ref(descriptorpath),guard_candidate=ref(a.out/'prepare_r63_source_only_compatibility.pinned.proposal.py'),actual_source_and_jar_delta_verified=True,world_read=False,world_written=False,java_started=False,native63_functional_pass=False,root_review_required=True);write(a.out/'PREPARATION_RECEIPT.json',result);print(json.dumps(result,ensure_ascii=True))
if __name__=='__main__':main()
