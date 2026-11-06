"""Root-invoked C8 stage/run. Consumes one qualified offline preflight; never auto-retries."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,shutil,subprocess,time,uuid

ROOT=Path(__file__).resolve().parents[1]
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game').resolve()
WORLD=GAME/'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
OUT=ROOT/'artifacts/r52_native_combined_candidate8'
C8=ROOT/'artifacts/r52_unified_candidate8/projectseele-0.1.0-all.jar'
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text('utf8'))
def new_json(path,value):
    with Path(path).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
def new_bytes(path,value):
    with Path(path).open('xb') as f:f.write(value)
def properties(command):
    found={}
    for value in command:
        if value.startswith('-D'):
            key,_,data=value[2:].partition('=');assert key not in found,'Duplicate JVM property: '+key;found[key]=data
    return found
def atomic_bytes(path,content):
    path=Path(path);temporary=path.with_name(path.name+'.r52-c8-'+uuid.uuid4().hex+'.tmp')
    new_bytes(temporary,content);os.replace(temporary,path)
def detached_replace(source,target,expected):
    source,target=Path(source).resolve(),Path(target).resolve();assert source!=target
    temporary=target.with_name(target.name+'.r52-c8-'+uuid.uuid4().hex+'.tmp')
    with source.open('rb') as src,temporary.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
    assert sha(temporary)==expected and not os.path.samefile(source,temporary)
    os.replace(temporary,target);assert sha(source)==sha(target)==expected and not os.path.samefile(source,target)
def verify(preflight):
    preflight=Path(preflight).resolve();assert preflight.is_relative_to(ROOT/'artifacts')
    receipt=read(preflight);assert receipt['schema']=='projectseele.r52.c8-offline-preflight.v1'
    assert receipt['C8_qualified'] is True and receipt['baseline_only'] is False,'C8 qualified preflight required'
    assert not receipt['reflection_failed'] and receipt['property_keys_unique'] and receipt['planned_outputs_entirely_new']
    tools=preflight.parent;launch_path=tools/'PLANNED_LAUNCH.json';args_path=tools/'PLANNED_LAUNCH.args'
    assert sha(launch_path)==receipt['planned_launch_sha256'] and sha(args_path)==receipt['planned_args_sha256']
    launch=read(launch_path);assert Path(launch['immutable_jar']['path']).resolve()==C8.resolve()
    assert launch['immutable_jar']==receipt['immutable_jar'] and sha(C8)==receipt['immutable_jar']['sha256']
    assert Path(launch['native_output']).resolve()==Path(receipt['expected_native_output']).resolve()==OUT.resolve()
    assert Path(launch['world']).resolve()==WORLD and WORLD.name=='SEELE_FIRST_BATTLE_REVIEW_R10' and 'WORLD_R52' not in str(WORLD)
    assert Path(launch['workingDirectory']).resolve()==GAME and Path(launch['staged_jar']['path']).resolve()==GAME/'mods/projectseele-0.1.0-all.jar'
    assert launch['staged_jar']['sha256']==launch['immutable_jar']['sha256']
    command=launch['command'];assert Path(command[0]).resolve()==(JDK/'java.exe').resolve()
    assert Path(command[command.index('--gameDir')+1]).resolve()==GAME
    assert command[command.index('--quickPlaySingleplayer')+1]==WORLD.name
    props=properties(command)
    assert launch['properties']=={k.removeprefix('projectseele.'):v for k,v in props.items() if k.startswith('projectseele.')}
    for key,value in {'regionalBuild':'r10-firstbattle','firstBattleThenOrdinaryR52':'true','firstBattleThenHandlingR52':'true',
        'ordinaryHandlingOnlyR52':'true','firstBattleFollowupOrdinaryReviewR52':'false','firstBattleMovieOnly':'true'}.items():assert props['projectseele.'+key]==value
    expected_outputs={'firstBattleCaptureOutputR52':OUT/'firstbattle/frames','firstBattleRuntimeWitnessR52Output':OUT/'firstbattle/native.jsonl',
        'ordinaryMotionOutputR52':OUT/'ordinary','r47NativeCommandInbox':OUT/'commands.json'}
    for key,path in expected_outputs.items():assert Path(props['projectseele.'+key]).resolve()==path.resolve()
    assert receipt['sequence']['final_C12_movies']==1 and receipt['sequence']['ordinary_variants']==[1] and receipt['sequence']['ordinary_ticks']==210
    bundle=Path(launch['bundle_directory']).resolve();assert bundle.is_relative_to(ROOT/'artifacts')
    assert sha(bundle/'combat_bundle_r44.json')==receipt['runtime_contract_sha256']
    for name,digest in launch['runtime_fingerprints'].items():assert sha(bundle/name)==digest,name
    assert sha(Path(props['projectseele.firstBattleReviewClip']))==receipt['selected_clip_sha256']==launch['candidate_sha256']
    assert sha(tools/'ordinary_motion_agent.jar')==receipt['tool_agent_sha256']
    expected={'tools/java/OrdinaryMotionR52Agent.java','tools/java/OrdinaryMotionR52Attach.java','tools/java/VerifyC8ToolModesR52.java'}
    assert {name.replace('\\','/') for name in receipt['tool_sources']}==expected
    for name,digest in receipt['tool_sources'].items():assert sha(ROOT/Path(name))==digest,'Prechecked tool source changed: '+name
    assert (tools/'tool_classes/OrdinaryMotionR52Attach.class').is_file()
    assert (WORLD/'level.dat').is_file() and not (WORLD/'r10_resume_expected.json').exists()
    return receipt,launch,tools,preflight
def stage(preflight):
    receipt,launch,tools,preflight=verify(preflight)
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'firstbattle/frames').mkdir(parents=True);(OUT/'ordinary').mkdir()
    target=Path(launch['staged_jar']['path']);expected=receipt['immutable_jar']['sha256']
    try:
        assert target.is_file();before=sha(target)
        if before!=expected:
            with target.open('rb') as src,(OUT/'previous_host_jar.jar').open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
            assert sha(OUT/'previous_host_jar.jar')==before
        new_bytes(OUT/'options.before.txt',(GAME/'options.txt').read_bytes())
        new_bytes(OUT/'fixture.level.dat.before',(WORLD/'level.dat').read_bytes())
        prior=WORLD/'r10_first_battle_review.json'
        if prior.is_file():new_bytes(OUT/'fixture_review.before.json',prior.read_bytes())
        detached_replace(C8,target,expected)
        launch.update(ready_to_launch=True,staging_pending=False,offline_only=False)
        new_json(OUT/'launch.json',launch);new_bytes(OUT/'launch.args',(tools/'PLANNED_LAUNCH.args').read_bytes());new_json(OUT/'commands.json',{'seq':1,'commands':[]})
        new_json(OUT/'STAGING_RECEIPT.json',{'preflight':str(preflight),'preflight_sha256':sha(preflight),
            'planned_launch_sha256':receipt['planned_launch_sha256'],'planned_args_sha256':receipt['planned_args_sha256'],
            'tool_agent_sha256':receipt['tool_agent_sha256'],'immutable_jar':receipt['immutable_jar'],'previous_host_jar_sha256':before,
            'staged_jar_sha256':sha(target),'detached_atomic_copy':True,'original_options_sha256':sha(OUT/'options.before.txt'),
            'output_CREATED_NEW':True,'authoritative_world_written':False,'game_started':False})
        print('C8 staged from qualified preflight; original options/host bytes preserved.',flush=True)
    except BaseException as error:
        new_json(OUT/'STAGING_FAILURE.json',{'error':repr(error),'game_started':False,'previous_evidence_retained':True})
        raise
def hide(pid):
    if os.name!='nt':return
    user=ctypes.windll.user32
    @ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
    def each(hwnd,arg):
        owner=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid:user.ShowWindow(hwnd,0)
        return True
    user.EnumWindows(each,0)
def quit_owned(process):
    if process.poll() is not None:return False
    new_bytes(OUT/'commands.before.quit.json',(OUT/'commands.json').read_bytes())
    atomic_bytes(OUT/'commands.json',(json.dumps({'seq':1000,'commands':[],'quit':True})+'\n').encode())
    try:process.wait(timeout=20);return False
    except subprocess.TimeoutExpired:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
        return True
def run(preflight):
    receipt,planned,tools,preflight=verify(preflight)
    staged=read(OUT/'STAGING_RECEIPT.json');assert staged['preflight_sha256']==sha(preflight)
    assert not(OUT/'RUNNING.json').exists(),'Retain every attempted game; no automatic retry'
    launch=read(OUT/'launch.json');assert launch['ready_to_launch'] and sha(OUT/'launch.args')==receipt['planned_args_sha256']
    assert sha(Path(launch['staged_jar']['path']))==receipt['immutable_jar']['sha256']
    original=(OUT/'options.before.txt').read_bytes();assert hashlib.sha256(original).hexdigest()==staged['original_options_sha256']
    assert (GAME/'options.txt').read_bytes()==original,'Options changed between stage and run; re-evaluate instead of overwriting'
    env=dict(os.environ);env.update(launch.get('environment',{}));process=None;attached=False;forced=False;timed_out=False;failure=None;begin=time.monotonic()
    log=(OUT/'process.log').open('xb');errorlog=(OUT/'process.error.log').open('xb')
    try:
        process=subprocess.Popen([launch['command'][0],'@'+str(OUT/'launch.args')],cwd=GAME,env=env,stdout=log,stderr=errorlog,creationflags=0x08000000 if os.name=='nt' else 0)
        new_json(OUT/'RUNNING.json',{'pid':process.pid,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'immutable_jar':receipt['immutable_jar'],'review_clip_sha256':receipt['selected_clip_sha256'],'world':str(WORLD),'original_options_sha256':staged['original_options_sha256']})
        print('C8 native PID',process.pid,'one C12 movie then Unit1 handling210.',flush=True)
        logged=None;last_status=0
        while process.poll() is None and time.monotonic()-begin<600:
            hide(process.pid);text=(OUT/'process.log').read_text('utf8',errors='replace')
            if logged is None and 'logged in with entity id' in text:logged=time.monotonic()
            if not attached and logged is not None and time.monotonic()-logged>=2:
                result=subprocess.run([str(JDK/'java.exe'),'-cp',str(tools/'tool_classes'),'OrdinaryMotionR52Attach',str(process.pid),str(tools/'ordinary_motion_agent.jar')],capture_output=True,text=True,encoding='utf8',errors='replace',timeout=30)
                with (OUT/'attach.log').open('x',encoding='utf8') as f:f.write(result.stdout+result.stderr)
                assert result.returncode==0,'Prechecked native attach failed; retain evidence'
                attached=True;print('Qualified tool attached; raw main draw metadata + native first battle precede Unit1 handling.',flush=True)
            if (OUT/'ordinary/FAILURE.json').exists():raise RuntimeError((OUT/'ordinary/FAILURE.json').read_text('utf8'))
            elapsed=time.monotonic()-begin
            if elapsed-last_status>=25:
                last_status=elapsed;phase='Unit1 handling' if (OUT/'ordinary/FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json').exists() else 'C12 native movie' if attached else 'boot'
                print('C8',round(elapsed,1),'seconds;',phase,flush=True)
            time.sleep(.5)
        timed_out=process.poll() is None
        if timed_out:raise TimeoutError('C8 native bounded review deadline exceeded')
    except BaseException as error:
        failure=repr(error);new_json(OUT/'RUNNER_FAILURE.json',{'error':failure,'evidence_retained':True,'native_acceptance':False})
    finally:
        try:
            if process is not None and process.poll() is None:forced=quit_owned(process)
        finally:
            log.close();errorlog.close();atomic_bytes(GAME/'options.txt',original)
            new_json(OUT/'OPTIONS_RESTORED.json',{'before_sha256':hashlib.sha256(original).hexdigest(),'after_sha256':sha(GAME/'options.txt'),
                'byte_equal':(GAME/'options.txt').read_bytes()==original,'process_exited_before_restore':process is None or process.poll() is not None})
            print('Original options restored byte-for-byte after process exit.',flush=True)
    first_path=OUT/'ordinary/FIRST_BATTLE_COMPLETED_BEFORE_ORDINARY.json';ordinary_path=OUT/'ordinary/CAPTURE_COMPLETE.json'
    first=read(first_path) if first_path.is_file() else {};ordinary=read(ordinary_path) if ordinary_path.is_file() else {}
    actual=read(OUT/'ordinary/ATTACHED.json') if (OUT/'ordinary/ATTACHED.json').is_file() else {}
    functional=process is not None and process.returncode==0 and failure is None and not forced and not timed_out and attached
    functional=bool(functional and first.get('passed') is True and first.get('clip_sha256')==receipt['selected_clip_sha256']
        and ordinary.get('input_sequence_complete') is True and ordinary.get('native_frames',0)>0 and actual.get('ordinary_variants')==[1] and actual.get('sequence_lengths_ticks')==[210])
    raw_path=OUT/'firstbattle/raw_draws.jsonl';raw=[]
    if raw_path.is_file():raw=[json.loads(line) for line in raw_path.read_text('utf8').splitlines() if line.strip()]
    result={'pid':process.pid if process else None,'elapsed_seconds':time.monotonic()-begin,'exit_code':process.returncode if process else None,
        'natural_exit':failure is None and not timed_out and not forced and process is not None and process.returncode==0,
        'attached':attached,'timed_out':timed_out,'forced_cleanup':forced,'failure':failure,'functional_capture_complete':functional,
        'first_battle_complete':bool(first),'ordinary_complete':bool(ordinary),'ordinary_variants':actual.get('ordinary_variants'),
        'ordinary_ticks':actual.get('sequence_lengths_ticks'),'immutable_jar':receipt['immutable_jar'],'review_clip_sha256':receipt['selected_clip_sha256'],
        'raw_main_draw_rows':len(raw),'first_raw_draw_age':raw[0]['synced_age_ticks'] if raw else None,
        'native_visual_acceptance':False,'raw_eye_pixel_visibility_verified':False,'whole_visible_skin_verified':False,
        'limits':'Successful natural capture is functional evidence only; inspect real C12 frames/submissions, raw eye visibility and handling support/guard convergence before visual acceptance.'}
    new_json(OUT/'RUN_RESULT.json',result);print(json.dumps(result,indent=2),flush=True)
    assert functional,'C8 capture incomplete; all evidence retained, no retry performed'
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--preflight',required=True,type=Path);parser.add_argument('--stage',action='store_true');parser.add_argument('--run',action='store_true');args=parser.parse_args()
    verify(args.preflight)
    if args.stage:stage(args.preflight)
    if args.run:run(args.preflight)
    if not args.stage and not args.run:print('Qualified C8 preflight and frozen tool/runtime/JAR bytes verified; no staging or game.',flush=True)
if __name__=='__main__':main()
