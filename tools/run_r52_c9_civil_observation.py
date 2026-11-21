"""One Root QA client: real chamber permission cycle and readiness-gated civil views."""
import json,os,subprocess,time
import nbtlib
from pathlib import Path
from run_r52_c8_targeted_native import GAME,sha,hide,atomic_bytes,properties
from run_r52_public_walk_candidate8 import QA,SOURCE,require_unlocked
from prepare_r52_terrain_observer_plan import build_plan

ROOT=Path(__file__).resolve().parents[1];BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
OUT=BASE/'native_r52_validation/civil_views_candidate9'
CAND=BASE/'runtime_directory/candidate';WORK=CAND/'civil_observation_candidate9'
JAR=ROOT/'artifacts/r52_unified_candidate9/projectseele-0.1.0-all.jar'
EXPECTED='43ae73510b139df1f36d1185a4b9b79965c8b8d141fdcd7916d7d4abacb07357'
JAVA='C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe'


def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,d):atomic_bytes(p,(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
def quote(v):return '"'+v.replace('\\','\\\\').replace('"','\\"')+'"'


def main():
    assert sha(JAR)==sha(GAME/'mods/projectseele-0.1.0-all.jar')==EXPECTED
    require_unlocked(QA);require_unlocked(SOURCE)
    feedback=str(nbtlib.load(QA/'level.dat')['Data']['GameRules']['sendCommandFeedback']);assert feedback in('true','false')
    assert read(BASE/'native_r52_validation/CLONE_RECEIPT.json')['ever_launched']
    assert not OUT.exists()and not WORK.exists();OUT.mkdir(parents=True);WORK.mkdir()
    prior=read(ROOT/'artifacts/r52_native_handling_candidate9_retry1/launch.json')
    command=[v for v in prior['command']if not v.startswith('-Dprojectseele.')]
    command[command.index('--quickPlaySingleplayer')+1]=QA.name
    inbox=OUT/'commands.json';command[1:1]=['-Dprojectseele.r47NativeCommandInbox='+str(inbox),'-Dprojectseele.combatBundleDirectory='+prior['bundle_directory']]
    properties(command);(OUT/'launch.args').write_text('\n'.join(quote(s)for s in command[1:])+'\n','utf8')
    write(OUT/'launch.json',dict(command=command,world=str(QA),jar_sha256=EXPECTED,source_world_opened=False))
    options=GAME/'options.txt';original=options.read_bytes();(OUT/'options.before.txt').write_bytes(original)
    text=original.decode('utf8');assert text.count('pauseOnLostFocus:true')==1
    atomic_bytes(options,text.replace('pauseOnLostFocus:true','pauseOnLostFocus:false').encode('utf8'))
    write(inbox,dict(seq=1,commands=[]));seq=1;process=None;failure=None;captures=[];started=time.monotonic()
    def issue(commands=(),screenshot=None,quit=False):
        nonlocal seq
        seq+=1;payload=dict(seq=seq,commands=list(commands))
        if screenshot:payload['screenshot']=str(screenshot)
        if quit:payload['quit']=True
        write(inbox,payload);return seq
    def ack(n,event,seconds=240):
        deadline=time.monotonic()+seconds;path=inbox.with_name(inbox.name+'.ack.jsonl')
        while time.monotonic()<deadline:
            assert process.poll()is None,'Client exited before observation';hide(process.pid)
            if path.exists():
                for row in map(json.loads,path.read_text('utf8').splitlines()):
                    if row['seq']==n and row['event']==event:return row
                    if row['seq']==n and row['event']in('rejected','screenshot_failed'):raise RuntimeError(row)
            time.sleep(.25)
        raise TimeoutError((n,event))
    def attach(classes,main,agent,plan,output):
        r=subprocess.run([JAVA,'--add-modules','jdk.attach','-cp',str(ROOT/classes),main,str(process.pid),str(ROOT/agent),str(plan),str(output)],capture_output=True,timeout=30)
        (output.with_suffix('.attach.log')).write_bytes(r.stdout+r.stderr);assert r.returncode==0,(r.stdout+r.stderr).decode('utf8','replace')
    def result(path,terminal,seconds):
        deadline=time.monotonic()+seconds;last=0
        while time.monotonic()<deadline:
            assert process.poll()is None,'Client exited before native result';hide(process.pid)
            if path.exists():
                d=read(path)
                if d.get('status')in terminal:return d
            if time.monotonic()-last>25:print('Waiting native observation',path.name,flush=True);last=time.monotonic()
            time.sleep(.5)
        raise TimeoutError(str(path))
    try:
        env=dict(os.environ);env.update(prior.get('environment',{}))
        with(OUT/'process.log').open('xb')as log:
            process=subprocess.Popen([command[0],'@'+str(OUT/'launch.args')],cwd=GAME,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
            write(OUT/'RUNNING.json',dict(pid=process.pid,world=str(QA),jar_sha256=EXPECTED,source_world_opened=False));print('C9 civil QA PID',process.pid,flush=True)
            ack(issue(['gamerule sendCommandFeedback false','gamemode spectator','execute in projectseele:geofront run tp @s 36.5 -422.0 337.5 0.0 0.0']),'submitted',360)
            time.sleep(3)
            plan=CAND/'highest_chamber_candidate9/C9_PLAN.json';dest=WORK/'HIGHEST_CHAMBER_RESULT.json'
            attach('.Codex/r52_owner_draft/chamber_probe_classes','R52HighestChamberNativeProbeAttach','.Codex/r52_owner_draft/r52_highest_chamber_native_probe_agent.jar',plan,dest)
            chamber=result(dest,{'PASS','HOLD'},115);print('Highest chamber',chamber['status'],chamber.get('error',''),flush=True)
            for name in('pyramid_west_lake','pyramid_east_original_interfaces','far_natural_lake','far_yashima_ridge'):
                item=read(CAND/'civil_landmarks'/f'{name}.json');plan=build_plan(JAR,name,item['position'],item['target'],item['required_sections'],120)
                pp=WORK/(name+'.plan.json');rp=WORK/(name+'.ready.json');write(pp,plan)
                args=[*item['position'],plan['camera_yaw'],plan['camera_pitch']]
                ack(issue(['execute in projectseele:geofront run tp @s '+' '.join(format(x,'.8f')for x in args)]),'submitted',45)
                attach('.Codex/r52_owner_draft/terrain_observer_classes','R52TerrainReadyReadOnlyAttach','.Codex/r52_owner_draft/r52_terrain_ready_readonly_agent.jar',pp,rp)
                ready=result(rp,{'READY','HOLD'},140);frame=OUT/(name+'.png')
                ack(issue(screenshot=frame),'screenshot_saved',40)
                captures.append(dict(name=name,status=ready['status'],readiness=str(rp),frame=str(frame),sha256=sha(frame)))
                print('Civil camera',name,ready['status'],ready.get('error',''),flush=True)
            ack(issue(['gamerule sendCommandFeedback '+feedback]),'submitted',30);issue(quit=True);process.wait(timeout=45)
    except BaseException as e:failure=repr(e)
    finally:
        if process is not None and process.poll()is None:
            issue(['gamerule sendCommandFeedback '+feedback],quit=True)
            try:process.wait(timeout=45)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=20)
        atomic_bytes(options,original)
        write(OUT/'RESULT.json',dict(exit_code=None if process is None else process.poll(),elapsed_seconds=time.monotonic()-started,
            failure=failure,captures=captures,source_world_opened=False,source_world_written=False,options_restored=options.read_bytes()==original,
            native_whole_map_acceptance=False,root_visual_review_pending=True))
    assert failure is None,failure
    assert process.returncode==0


if __name__=='__main__':main()
