"""Prepare additive native stations from station-set-v1 JSON in an isolated copy.

Schema (all coordinates are integer native rail nodes, not rendered +0.5 centres):
  {"schema":"station-set-v1", "dimension":"projectseele/geofront",
   "expected_native_members":607,
   "rails":[{"id":"p1","kind":"platform","from":[0,60,0],"to":[24,60,24],
     "from_angle":"SE","to_angle":"NW","shape":"QUADRATIC",
     "vertical_radius":100,"expected_length":33.94112549695428,
     "length_tolerance":0.000001,"max_grade":0}],
   "stations":[{"id":"s1","name":"Example","color":5400426,
     "min":[-4,58,-4],"max":[28,68,28],
     "platforms":[{"rail_id":"p1","name":"1","dwell_ms":12000,
       "required_train_length":18.25,"minimum_end_margin":7}]}]}
Ordinary connecting rails use kind=rail and explicit speed/reverse_speed.
Each platform rail belongs to exactly one newly created station. No routes,
sidings, depots, vehicle dispatch, retirement, or existing-object updates exist.

Modes: validate (JSON only, default); compile (javac only); geometry (pure native
RailMath; never constructs Simulator); prepare (PARENT ONLY: copied Simulator,
no ticks); collect (verify and export only listed new members after a completed
prepare). --work must be a fresh purpose-specific directory beneath .Codex.
The output is independent of any frozen world candidate: output/additions/mtr/.
No existing native member is ever exported as an overwrite.
"""
import argparse, json, math, os, re, shutil, subprocess
from pathlib import Path

ANGLES={'E','SEE','SE','SSE','S','SSW','SW','SWW','W','NWW','NW','NNW','N','NNE','NE','NEE'}
KEY=re.compile(r'^[A-Za-z0-9_.-]+$')

def require(condition,message):
    if not condition:raise ValueError(message)

def integer(v):return type(v)is int
def finite(v):return type(v)in(int,float)and math.isfinite(v)
def pos(v):return isinstance(v,list)and len(v)==3 and all(integer(x)for x in v)
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')

def validate(spec):
    require(set(spec)=={'schema','dimension','expected_native_members','rails','stations'},'Unexpected root fields; this tool cannot change lines or existing objects')
    require(spec['schema']=='station-set-v1','Unsupported schema')
    require(re.fullmatch(r'[a-z0-9_.-]+/[a-z0-9_./-]+',spec['dimension'])and all(p not in('','..','.')for p in spec['dimension'].split('/')),'Invalid dimension path')
    require(integer(spec['expected_native_members'])and spec['expected_native_members']>=0,'Explicit expected native file count required')
    require(isinstance(spec['rails'],list)and isinstance(spec['stations'],list)and 1<=len(spec['stations'])<=128 and 1<=len(spec['rails'])<=1024,'Bounded nonempty station/rail arrays required')
    rails={};pairs=set();owners={};station_ids=set();station_names=set()
    for r in spec['rails']:
        needed={'id','kind','from','to','from_angle','to_angle','shape','vertical_radius','expected_length','length_tolerance','max_grade'}
        require(needed<=set(r)<=needed|{'speed','reverse_speed','tangent_tolerance_degrees'},'Unknown or missing rail fields')
        require(isinstance(r['id'],str)and KEY.fullmatch(r['id'])and r['id']not in rails,'Distinct nonempty rail id required')
        require(r['kind']in('rail','platform')and r['shape']=='QUADRATIC','Only TRAIN rail/platform QUADRATIC geometry supported')
        require(pos(r['from'])and pos(r['to'])and r['from']!=r['to'],'Distinct integral rail endpoints required')
        pair=tuple(sorted((tuple(r['from']),tuple(r['to']))));require(pair not in pairs,'Repeated or reversed rail endpoints');pairs.add(pair)
        require(r['from_angle']in ANGLES and r['to_angle']in ANGLES,'Unknown native tangent angle')
        for key in('vertical_radius','expected_length','length_tolerance'):require(finite(r[key])and r[key]>0,'Positive finite '+key+' required')
        require(r['length_tolerance']<=.01 and finite(r['max_grade'])and 0<=r['max_grade']<=1,'Length/grade tolerance is too loose')
        require(finite(r.get('tangent_tolerance_degrees',1))and 0<r.get('tangent_tolerance_degrees',1)<=2,'Tangent tolerance must be in (0,2] degrees')
        if r['kind']=='platform':require(r['from'][1]==r['to'][1]and r['max_grade']==0,'Platform must be level')
        else:
            for key in('speed','reverse_speed'):require(integer(r.get(key))and 1<=r[key]<=300,'Connecting rails require explicit bounded '+key)
        rails[r['id']]=r
    for s in spec['stations']:
        require(set(s)=={'id','name','color','min','max','platforms'},'Unknown or missing station fields')
        require(isinstance(s['id'],str)and KEY.fullmatch(s['id'])and s['id']not in station_ids,'Distinct station id required');station_ids.add(s['id'])
        require(isinstance(s['name'],str)and s['name'].strip()and s['name']not in station_names,'Distinct station name required');station_names.add(s['name'])
        require(integer(s['color'])and 0<=s['color']<=0xFFFFFF and pos(s['min'])and pos(s['max'])and all(a<b for a,b in zip(s['min'],s['max'])),'Valid nonzero station area/color required')
        require(isinstance(s['platforms'],list)and s['platforms'],'Station needs explicit owned platforms');names=set()
        for p in s['platforms']:
            require(set(p)=={'rail_id','name','dwell_ms','required_train_length','minimum_end_margin'},'Unknown or missing platform fields')
            rid=p['rail_id'];require(rid in rails and rails[rid]['kind']=='platform'and rid not in owners,'Every platform rail must have one station owner');owners[rid]=s['id']
            require(isinstance(p['name'],str)and p['name'].strip()and p['name']not in names,'Distinct platform names within a station required');names.add(p['name'])
            require(integer(p['dwell_ms'])and 0<=p['dwell_ms']<=3600000,'Invalid dwell milliseconds')
            require(finite(p['required_train_length'])and p['required_train_length']>0 and finite(p['minimum_end_margin'])and p['minimum_end_margin']>=0,'Explicit train length and stop margin required')
            rr=rails[rid];require(rr['expected_length']+rr['length_tolerance']>=p['required_train_length']+2*p['minimum_end_margin'],'Platform shorter than declared consist plus stop margins')
            for endpoint in(rr['from'],rr['to']):require(all(lo<=v<=hi for lo,v,hi in zip(s['min'],endpoint,s['max'])),'Platform endpoint outside intended station')
    require(set(owners)=={k for k,r in rails.items()if r['kind']=='platform'},'Unowned platform rail')
    return {'stations':len(station_ids),'platforms':len(owners),'rails':len(rails),'new_native_members':len(station_ids)+len(owners)+len(rails)}

def files(root):
    result={}
    require(root.is_dir(),'Missing directory '+str(root))
    for p in root.rglob('*'):
        require(not(p.lstat().st_file_attributes&1024 if hasattr(p.lstat(),'st_file_attributes')else p.is_symlink()),'Reparse/symlink entries are not accepted')
        if p.is_file():result[p.relative_to(root).as_posix()]=p
    return result

def equal_files(left,right):
    if left.stat().st_size!=right.stat().st_size:return False
    with left.open('rb')as a,right.open('rb')as b:
        while True:
            x,y=a.read(1024*1024),b.read(1024*1024)
            if x!=y:return False
            if not x:return True

def classpath(a):
    jars=sorted((Path.home()/'.gradle/caches/modules-2/files-2.1/org.apache.logging.log4j').glob('*/2.19.0/*/*.jar'))
    require(a.mtr and a.mtr.is_file()and jars,'MTR and Log4j compilation dependencies required')
    return os.pathsep.join(map(str,[a.work/'classes',a.mtr,*jars]))

def compile_author(a):
    require(a.java and(a.java/'bin/javac.exe').is_file(),'JDK directory required')
    (a.work/'classes').mkdir(exist_ok=True)
    with(a.work/'compile.log').open('w',encoding='utf8')as log:subprocess.run([str(a.java/'bin/javac.exe'),'-encoding','UTF-8','-cp',classpath(a),'-d',str(a.work/'classes'),str(Path(__file__).with_name('java')/'StationSetAuthor.java')],stdout=log,stderr=subprocess.STDOUT,check=True)

def collect(a,spec,counts):
    proof=json.loads((a.work/'output/native-station-set-proof.json').read_text('utf8'))
    require(proof['existing_loaded_objects_exact']and proof['existing_platform_station_membership_exact'],'Existing semantic objects changed')
    require(proof['input_plan']==spec and proof['expected_native_members']==spec['expected_native_members'],'Proof belongs to a different plan/baseline')
    require(len(proof['stations'])==counts['stations']and len(proof['platforms'])==counts['platforms']and len(proof['rails'])==counts['rails'],'Wrong native object counts')
    baseline=files(a.work/'baseline');stage=files(a.work/'native');source=files(a.native_source)
    require(len(baseline)==spec['expected_native_members']and baseline.keys()==source.keys()and all(equal_files(p,source[k])for k,p in baseline.items()),'Supplied read-only snapshot changed or differs from copied baseline')
    members=proof['members'];require(len(members)==len(set(members))==counts['new_native_members'],'Unexpected or repeated output members')
    prefixes=('mtr/'+spec['dimension']+'/'+k+'/'for k in('rails','platforms','stations'));prefixes=tuple(prefixes);listed={}
    for name in members:
        require(isinstance(name,str)and name.startswith(prefixes)and all(p not in('..','.','')for p in name.split('/'))and '\\'not in name,'Unsafe native output member')
        rel=name[4:];require(rel in stage and rel not in baseline,'Output missing or would overwrite an old member');listed[rel]=name
    require(set(stage)-set(baseline)==set(listed),'Unlisted new native files produced by engine')
    dest=a.work/'output/additions';require(not dest.exists(),'Additions already collected; use a new work directory')
    addition_checks=[]
    for rel,name in listed.items():
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(stage[rel],target)
        require(equal_files(stage[rel],target),'New member copy differs byte-for-byte')
        addition_checks.append({'member':name,'size':target.stat().st_size,'copied_native_bytes_equal':True})
    preservation={'baseline_members':len(baseline),'comparison_method':'Streaming direct byte comparison, no digest','installation_rule':'Retain every existing destination member byte-for-byte and append only output/additions/mtr members. Reject any addition whose destination already exists. Never publish old files rewritten by Simulator.',
                  'members':[{'member':'mtr/'+k,'size':p.stat().st_size,'original_snapshot_equals_copied_baseline_bytes':True,'absent_from_delivery_additions':k not in listed}for k,p in sorted(baseline.items())],
                  'new_member_checks':addition_checks,'existing_source_members_unchanged':True,'delivery_contains_only_new_members':True}
    dump(a.work/'output/baseline-preservation.json',preservation)
    report={'schema':'station-set-native-additions-v1','input_plan':spec,'baseline_members':len(baseline),'new_members':members,'preserved_source_files_exact':True,'delivery_overwrites_existing_members':False,'existing_loaded_objects_exact':True,'existing_platform_station_membership_exact':True,'byte_preservation_evidence':'baseline-preservation.json','staging_existing_files_rewritten':[k for k,p in baseline.items()if k not in stage or not equal_files(p,stage[k])],'world_written':False,'through_service_complete':False}
    dump(a.work/'output/collection.json',report)
    proof['preserved_source_member_bytes_exact']=True;proof['delivery_only_new_members']=True;proof['byte_preservation_evidence']='baseline-preservation.json'
    for name in('native-station-proof.json','native-station-set-proof.json'):dump(a.work/'output'/name,proof)
    print('Collected',len(members),'new members;',len(baseline),'original files preserved; no service authored')

def attach(a,spec,counts):
    require(a.candidate is not None,'--candidate required for attach')
    require(not any(p.lower()=='saves'for p in a.candidate.resolve().parts),'Candidate cannot be an actual save')
    output=a.work/'output';proof=json.loads((output/'native-station-proof.json').read_text('utf8'))
    require(proof['input_plan']==spec and proof['existing_loaded_objects_exact'],'Native proof belongs to a different plan')
    source=files(a.candidate/'preserved-native');baseline=files(a.work/'baseline')
    require(source.keys()==baseline.keys()and len(source)==spec['expected_native_members']and all(equal_files(p,baseline[k])for k,p in source.items()),'Candidate baseline differs from prepared native baseline')
    members=proof['members'];require(len(members)==len(set(members))==counts['new_native_members'],'Native addition scope differs')
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    require(not manifest.get('native_additions')and not(a.candidate/'native-station').exists(),'Candidate native additions already attached')
    for name in members:
        rel=Path(name)
        require(not rel.is_absolute()and '..'not in rel.parts and rel.parts[0]=='mtr','Unsafe native member path')
        require(rel.relative_to('mtr').as_posix()not in source and not(a.candidate/'after'/rel).exists(),'Native attachment would overwrite a member')
        require((output/'additions'/rel).is_file(),'Collected native addition is missing')
    for name in members:
        target=a.candidate/'after'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(output/'additions'/name,target)
    proof_target=a.candidate/'native-station';proof_target.mkdir()
    for name in('native-station-proof.json','native-station-set-proof.json','collection.json','baseline-preservation.json'):
        shutil.copy2(output/name,proof_target/name)
    manifest.update(native_additions=members,native_station_pending=False);dump(a.candidate/'manifest.json',manifest)
    print('Attached',len(members),'new native members to offline candidate; no actual world opened')


def main(a):
    spec=json.loads(a.plan.read_text('utf8'));counts=validate(spec)
    if a.mode=='validate':print('JSON valid:',counts);return
    require(a.work is not None,'--work required');a.work=a.work.resolve()
    require(any(p.lower()=='.codex'for p in a.work.parts)and not any(p.lower()=='saves'for p in a.work.parts),'Isolated .Codex work directory required')
    a.work.mkdir(parents=True,exist_ok=True)
    if a.mode=='attach':attach(a,spec,counts);return
    if a.mode in('compile','geometry','prepare'):compile_author(a)
    if a.mode=='compile':print('Compiled StationSetAuthor; Simulator not started');return
    if a.mode=='geometry':
        subprocess.run([str(a.java/'bin/java.exe'),'-cp',classpath(a),'StationSetAuthor','--validate-only',str(a.plan.resolve()),str(a.work/'geometry.json')],check=True);return
    if a.native_source is None and a.candidate is not None:a.native_source=a.candidate/'preserved-native'
    require(a.native_source is not None and a.expected_members==spec['expected_native_members'],'--candidate (preserved-native) or --native-source, and matching --expected-members required')
    a.native_source=a.native_source.resolve()
    require(not any(p.lower()=='saves'for p in a.native_source.parts)and a.native_source!=a.work and a.work not in a.native_source.parents and a.native_source not in a.work.parents,'Use a separate saved offline native snapshot, never a real save')
    if a.mode=='collect':collect(a,spec,counts);return
    source=files(a.native_source);require(len(source)==a.expected_members,'Snapshot member count differs from the requested batch')
    for name in('native','baseline','output'):require(not(a.work/name).exists(),'Never reuse a partially authored native staging copy')
    shutil.copytree(a.native_source,a.work/'baseline');shutil.copytree(a.work/'baseline',a.work/'native');(a.work/'output').mkdir()
    dump(a.work/'station-set-staging.json',{'schema':'station-set-offline-copy-v1','root':str(a.work/'native'),'source':str(a.native_source),'expected_native_members':a.expected_members,'input_plan':spec})
    dump(a.work/'plan.json',spec)
    with(a.work/'output/engine.log').open('w',encoding='utf8')as log:subprocess.run([str(a.java/'bin/java.exe'),'-cp',classpath(a),'StationSetAuthor',str(a.work/'plan.json'),str(a.work/'native'),str(a.work/'output')],stdout=log,stderr=subprocess.STDOUT,check=True)
    collect(a,spec,counts)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--mode',choices=('validate','compile','geometry','prepare','collect','attach'),default='validate')
    for name in('work','candidate','native-source','java','mtr'):p.add_argument('--'+name,type=Path)
    p.add_argument('--expected-members',type=int)
    main(p.parse_args())
