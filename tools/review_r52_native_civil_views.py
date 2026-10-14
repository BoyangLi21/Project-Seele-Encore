"""Prepare or run bounded final art photos in the existing SEELE_R52_REVIEW.

Uses the game's command inbox and native framebuffer; never controls native
windows, stages a client, copies a world, or installs construction. READY means
the declared camera/block/light/mesh/source-GPU prerequisites were observed.
It does not mean visual acceptance or full mechanical/gameplay acceptance.
"""
from pathlib import Path
import argparse, hashlib, json, math, os, subprocess, time, uuid, zipfile
from build_immutable_r52_candidate import frozen_build_class_pins, SOURCE_ASSETS
from prepare_r52_terrain_observer_plan import build_plan, CANDIDATE
from run_r52_public_walk_candidate8 import require_unlocked
from query_blocks import read_box, iter_block_entities, AIR
from prepare_r52_final_art_views import original_units, GROUND

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
SOURCE=(BASE/'WORLD_R52').resolve()
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game').resolve()
QA=(GAME/'saves/SEELE_R52_REVIEW').resolve()
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
TOOLS=ROOT/'.codex/r52_final_art_capture'
def sha(p):
    with Path(p).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,data):
    p=Path(p);temp=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8');os.replace(temp,p)
def quote(s):
    if any(c in s for c in '\r\n\0'):raise ValueError('Unsafe Java argument')
    return '"'+s.replace('\\','/').replace('"','\\"')+'"'
def state(s):
    name,_,raw=s.partition('[')
    return name,dict(x.split('=',1) for x in raw.rstrip(']').split(',') if x)
def fingerprints(directory):return {p.relative_to(directory).as_posix():sha(p) for p in directory.rglob('*') if p.is_file()}

def verify_world_anchors(world,views):
    """Read only exact bounded source/QA anchors, including current artwork NBT."""
    blocks={tuple(b['position']):b for v in views for b in v['required_blocks']}
    blocks.update({tuple(v['eye_cell']):{'position':v['eye_cell'],'state':v['source_eye_state']} for v in views})
    groups={}
    for q in blocks:groups.setdefault((q[0]//16,q[2]//16),[]).append(q)
    for points in groups.values():
        low=tuple(min(p[i] for p in points) for i in range(3));high=tuple(max(p[i] for p in points) for i in range(3))
        actual=read_box(world,'projectseele:geofront',low,high)
        tags=None
        for q in points:
            b=blocks[q]
            if state(actual.get(q,'UNREAD'))!=state(b['state']):raise ValueError(('Current exact world block differs; refresh camera plan/QA delta',str(world),q,b['state'],actual.get(q)))
            if 'block_entity_fields' not in b:continue
            if tags is None:tags=dict(iter_block_entities(world,'projectseele:geofront',low,high))
            t=tags.get(q)
            if t is None:raise ValueError(('Artwork block entity missing',world,q))
            for key,spec in b['block_entity_fields'].items():
                if key not in t:raise ValueError(('Artwork NBT field missing',world,q,key))
                value=str(t[key]) if spec['type']=='string' else float(t[key]) if spec['type']=='float' else int(t[key])
                if value!=spec['value']:raise ValueError(('Artwork NBT differs',world,q,key,value,spec['value']))

def prepare(a):
    views_path=a.views.resolve();view_plan=read(views_path);views=view_plan['views']
    if view_plan['schema']!='projectseele.r52.final-art-camera-source.v1' or Path(view_plan['source_world']).resolve()!=SOURCE:raise ValueError('Current single construction save camera plan required')
    if not 12<=len(views)<=32 or len({v['name'] for v in views})!=len(views):raise ValueError('12..32 unique bounded current views required')
    if any(v['needs_camera_adjustment'] or v['source_eye_state'].split('[')[0] not in AIR for v in views):raise ValueError('Every proposed actual eye must be in source air')
    receipt_path=a.build_receipt.resolve();receipt=read(receipt_path);jar=Path(receipt['jar']).resolve()
    class_pins=frozen_build_class_pins(receipt_path,jar)
    if sha(GAME/'mods/projectseele-0.1.0-all.jar')!=receipt['sha256']:raise ValueError('Root must synchronize the actual host to the final unchanged built Jar')
    for path,digest in view_plan['source_inputs'].items():
        path=Path(path).resolve()
        if path==GROUND.resolve():
            if sha(path)!=digest:raise ValueError('Current explicit route source changed; refresh camera/source entity plan')
        elif not path.is_relative_to(SOURCE) or sha(path)!=digest or sha(QA/path.relative_to(SOURCE))!=digest:raise ValueError(('Current source/QA metadata differs; refresh plan and Root delta sync',path))
    verify_world_anchors(SOURCE,views);verify_world_anchors(QA,views)
    source_units=original_units(SOURCE);qa_units=original_units(QA)
    declared=[e for v in views for e in v.get('required_entities',[])]
    if len(declared)!=3 or {e['variant']for e in declared}!={0,1,2}:raise ValueError('Three exact original bay EVA identities required')
    for e in declared:
        actual=qa_units[e['variant']]
        if source_units[e['variant']]!=e or actual['uuid']!=e['uuid'] or actual['source_type']!=e['source_type'] or math.dist(actual['expected_position'],e['expected_position'])>e['position_tolerance_m']:raise ValueError(('Current source/QA original EVA identity or bay position differs',e['uuid']))
    runtime=a.runtime.resolve();host_runtime=GAME/'projectseele-local-maps'
    actual_runtime=fingerprints(runtime)
    if not actual_runtime or actual_runtime!=fingerprints(host_runtime):raise ValueError('Root must synchronize exact final client runtime resources; tool never stages them')
    compile_receipt=read(TOOLS/'OBSERVER_COMPILE_RECEIPT.json')
    if not compile_receipt['compile_passed'] or compile_receipt['game_started']:raise ValueError('Fresh offline observer compilation required')
    for path,digest in compile_receipt['files'].items():
        if sha(ROOT/path)!=digest:raise ValueError(('Tools observer source/class/Jar changed since target compile',path))
    for path,digest in compile_receipt['installed_bytecode'].items():
        if sha(path)!=digest:raise ValueError(('Actual client/Embeddium bytecode changed after API preflight',path))
    clone=read(BASE/'native_r52_validation/CLONE_RECEIPT.json')
    if Path(clone['source_world']).resolve()!=SOURCE or Path(clone['target_world']).resolve()!=QA or not clone['ever_launched']:raise ValueError('Reuse the one already used QA; no new clone')
    require_unlocked(QA);require_unlocked(SOURCE)
    prior=read(a.launch_template.resolve());command=[s for s in prior['command'] if not s.startswith('-Dprojectseele.')]
    if Path(command[0]).resolve()!=JDK/'java.exe' or Path(command[command.index('--gameDir')+1]).resolve()!=GAME:raise ValueError('Reuse existing actual client/library launch')
    command[command.index('--quickPlaySingleplayer')+1]=QA.name
    out=a.out.resolve()
    if not out.is_relative_to(CANDIDATE) or out.exists():raise ValueError('Fresh candidate-only photo output required')
    properties={'projectseele.r47NativeCommandInbox':str(out/'commands.json'),'projectseele.combatBundleDirectory':str(host_runtime),'projectseele.nativeReviewWorld':QA.name,'projectseele.r52NativeReviewCopy':'true'}
    command[1:1]=['-D'+k+'='+v for k,v in properties.items()]
    if len([s.split('=',1)[0] for s in command if s.startswith('-D')])!=len(set(s.split('=',1)[0] for s in command if s.startswith('-D'))):raise ValueError('Duplicate JVM property')
    with zipfile.ZipFile(jar)as archive:guide_sha=hashlib.sha256(archive.read(SOURCE_ASSETS[1])).hexdigest();model_sha=hashlib.sha256(archive.read(SOURCE_ASSETS[0])).hexdigest()
    out.mkdir(parents=True);write(out/'PLAN.json',dict(schema='projectseele.r52.final-art-native-plan.v1',jar=str(jar),jar_sha256=receipt['sha256'],build_receipt=str(receipt_path),build_receipt_sha256=sha(receipt_path),class_pins=class_pins,views=str(views_path),views_sha256=sha(views_path),world=str(QA),source_world=str(SOURCE),source_world_opened=False,source_world_written=False,game_started=False,client_copied=False,world_copied=False,visual_acceptance=False,guide_source_sha256=guide_sha,guide_model_sha256=model_sha,runtime_sha256=actual_runtime,observer_compile_receipt_sha256=sha(TOOLS/'OBSERVER_COMPILE_RECEIPT.json')))
    for v in views:
        p=build_plan(jar,v['name'],v['position'],v['target'],v['required_sections'],a.view_deadline)
        p['required_blocks']=v['required_blocks']+v.get('dynamic_required_blocks',[])
        if 'required_entities'in v:p['required_entities']=v['required_entities']
        p['capture_path']=str(out/(v['name']+'.png'))
        if 'guide_bounds' in v:p.update(guide_bounds=v['guide_bounds'],guide_source_sha256=guide_sha,guide_model_sha256=model_sha)
        write(out/(v['name']+'.plan.json'),p)
    (out/'launch.args').write_text('\n'.join(quote(s) for s in command[1:])+'\n','utf8')
    write(out/'launch.json',dict(command=command,workingDirectory=str(GAME),world=str(QA),properties=properties,environment=prior.get('environment',{})))
    return out,views,view_plan,command,prior

def run(a,prepared):
    out,views,view_plan,command,prior=prepared
    inbox=out/'commands.json';options=GAME/'options.txt';original=options.read_bytes()
    (out/'options.before.txt').write_bytes(original)
    lines=original.decode('utf8').splitlines();overrides={'pauseOnLostFocus':'false','renderDistance':str(view_plan['render_distance_chunks']),'perspective':'0'}
    lines=[s for s in lines if s.partition(':')[0] not in overrides]+[k+':'+v for k,v in overrides.items()]
    options.write_text('\n'.join(lines)+'\n','utf8')
    seq=1;write(inbox,dict(seq=seq,commands=[]));process=None;started=time.monotonic();results=[];failure=None;forced=False;original_mode=None
    def issue(commands=(),quit=False):
        nonlocal seq
        seq+=1;write(inbox,dict(seq=seq,commands=list(commands),quit=quit));return seq
    def ack(sequence,event,seconds=40):
        deadline=time.monotonic()+seconds;file=inbox.with_name(inbox.name+'.ack.jsonl')
        while time.monotonic()<deadline:
            if process.poll()is not None:raise RuntimeError('Client exited before observation')
            if file.exists():
                rows=[json.loads(s)for s in file.read_text('utf8').splitlines()if s.strip()]
                found=[r for r in rows if r['seq']==sequence and r['event']==event]
                if found:return found[-1]
                rejected=[r for r in rows if r['seq']==sequence and r['event']=='rejected']
                if rejected:raise RuntimeError(rejected)
            time.sleep(.25)
        raise TimeoutError(('Game inbox did not acknowledge',sequence,event))
    def attach(agent,plan,output):
        log=output.with_suffix('.attach.log')
        with log.open('x',encoding='utf8')as f:
            r=subprocess.run([str(JDK/'java.exe'),'-Xmx256m','--add-modules','jdk.attach','-cp',str(TOOLS/'observer_classes'),'R52TerrainReadyReadOnlyAttach',str(process.pid),str(TOOLS/agent),str(plan),str(output)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=30)
        if r.returncode:raise RuntimeError(('Native diagnostic attach failed',log))
    def result(path,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if process.poll()is not None:raise RuntimeError('Client exited before observer result')
            if path.exists():
                try:r=read(path)
                except(json.JSONDecodeError,OSError):time.sleep(.25);continue
                if r.get('status')in('PASS','READY','HOLD'):return r
            time.sleep(.25)
        return dict(status='HOLD',reason='No terminal actual observer result within declared deadline')
    def light(v,label,wanted):
        position=v['seele_use_stand'];ack(issue(['gamemode creative','execute in projectseele:geofront run tp @s '+' '.join(map(str,position))]),'submitted')
        plan=out/(label+'.light-plan.json');output=out/(label+'.light.json')
        write(plan,dict(seele_meeting_mode=wanted,seele_button=v['seele_button'],seele_use_stand=position))
        attach('r52_photo_room_light_agent.jar',plan,output)
        return result(output,30)
    try:
        env=dict(os.environ);env.update(prior.get('environment',{}))
        with(out/'process.log').open('xb')as log:
            process=subprocess.Popen([command[0],'@'+str(out/'launch.args')],cwd=GAME,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
            write(out/'RUNNING.json',dict(pid=process.pid,world=str(QA),source_world_opened=False))
            ack(issue(['gamemode spectator']),'submitted',360)
            for v in views:
                if 'seele_meeting_mode' in v:
                    l=light(v,v['name'],v['seele_meeting_mode'])
                    if original_mode is None and 'before_meeting_mode'in l:original_mode=l['before_meeting_mode']
                    if l['status']!='PASS':results.append(dict(name=v['name'],status='HOLD',light=l,photo_qualified=False));continue
                p=read(out/(v['name']+'.plan.json'))
                cmd='execute in projectseele:geofront run tp @s '+' '.join(map(str,[*v['position'],p['camera_yaw'],p['camera_pitch']]))
                submitted=ack(issue(['gamemode spectator',cmd]),'submitted')
                observation=out/(v['name']+'.readiness.json');attach('r52_terrain_ready_readonly_agent.jar',out/(v['name']+'.plan.json'),observation)
                r=result(observation,a.view_deadline+25);capture=r.get('capture',{});photo=out/(v['name']+'.png')
                qualified=r['status']=='READY' and r.get('ready_for_declared_camera_capture')is True and capture.get('file')==str(photo) and photo.is_file() and capture.get('sha256')==sha(photo)
                results.append(dict(name=v['name'],status=r['status'],readiness=str(observation),photo_qualified=qualified,capture=capture if qualified else None,inbox_submitted=submitted,visual_review_pending=True))
                print(v['name'],r['status'],'qualified='+str(qualified),flush=True)
            if original_mode is not None:
                restored=light(next(v for v in views if 'seele_meeting_mode'in v),'restore_seele_original',original_mode)
                write(out/'LIGHT_RESTORE.json',restored)
                if restored['status']!='PASS':raise RuntimeError('Original meeting mode was not restored through its real button')
            issue(quit=True);process.wait(timeout=45)
    except BaseException as e:failure=repr(e)
    finally:
        if process is not None and process.poll()is None and original_mode is not None and not(out/'LIGHT_RESTORE.json').exists():
            try:
                restored=light(next(v for v in views if 'seele_meeting_mode'in v),'restore_seele_after_failure',original_mode)
                write(out/'LIGHT_RESTORE.json',restored)
                if restored['status']!='PASS':failure=(failure or '')+' Original real-button lighting restoration HOLD.'
            except BaseException as e:failure=(failure or '')+' Lighting restoration: '+repr(e)
        if process is not None and process.poll()is None:
            issue(quit=True)
            try:process.wait(timeout=35)
            except subprocess.TimeoutExpired:forced=True;process.terminate();process.wait(timeout=20)
        options.write_bytes(original)
        write(out/'RESULT.json',dict(schema='projectseele.r52.final-art-native-result.v1',exit_code=None if process is None else process.poll(),elapsed_seconds=time.monotonic()-started,failure=failure,forced_stop=forced,views=results,qualified_photos=sum(r['photo_qualified']for r in results),requested_views=len(views),source_world_opened=False,source_world_written=False,options_restored=options.read_bytes()==original,native_function_acceptance=False,visual_acceptance=False,visual_review_pending=True,complete_observation=failure is None and not forced and len(results)==len(views) and all(r['photo_qualified']for r in results)))
    if failure:raise RuntimeError(failure)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-receipt',type=Path,required=True);ap.add_argument('--views',type=Path,default=TOOLS/'VIEWS_CURRENT_V6.json')
    ap.add_argument('--runtime',type=Path,default=ROOT/'artifacts/r52_runtime_candidate/projectseele-local-maps')
    ap.add_argument('--launch-template',type=Path,default=ROOT/'artifacts/r52_native_handling_candidate9_retry1/launch.json')
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--view-deadline',type=int,default=120);ap.add_argument('--run',action='store_true');a=ap.parse_args()
    if not 5<=a.view_deadline<=300:raise ValueError('5..300 second per-view observer deadline')
    p=prepare(a);print(p[0],flush=True)
    if a.run:run(a,p)
if __name__=='__main__':main()
