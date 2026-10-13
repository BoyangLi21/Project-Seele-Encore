"""Prepare/run one existing R10 fixture window with FPS-only hooks and JFR.

Default prepare does not touch the game/World. --run is Root's explicit switch.
Back up and exactly restore the entire named fixture, options and staged mod.
Never reads/writes WORLD_R52, launches another world or terminates another PID.
"""
from pathlib import Path
import argparse,hashlib,json,msvcrt,os,shutil,subprocess,time
from build_immutable_r52_candidate import frozen_build_class_pins
ROOT=Path(__file__).resolve().parents[1]
GAME=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game')
WORLD=GAME/'saves/SEELE_FIRST_BATTLE_REVIEW_R10'
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
def need(b,m):
    if not b:raise ValueError(m)
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,d):Path(p).write_text(json.dumps(d,indent=2)+'\n',encoding='utf8')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def inventory(folder):
    result={}
    for p in folder.rglob('*'):
        need(not p.is_symlink() and not p.is_junction(),'Linked fixture member refused')
        if p.is_file() and p.name!='session.lock':result[p.relative_to(folder).as_posix()]=sha(p)
    return result
def idle():
    r=subprocess.run(['powershell','-NoProfile','-Command',"@(Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | Select-Object ProcessId,CommandLine) | ConvertTo-Json -Compress"],capture_output=True,text=True,check=True);rows=json.loads(r.stdout) if r.stdout.strip() else [];rows=rows if isinstance(rows,list) else [rows]
    busy=[p['ProcessId'] for p in rows if GAME.as_posix().lower() in (p.get('CommandLine') or '').replace('\\','/').lower() or WORLD.name.lower() in (p.get('CommandLine') or '').lower()]
    need(not busy,'Relevant client/fixture already running: '+str(busy))
def lock():
    f=(WORLD/'session.lock').open('r+b');msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);return f
def unlock(f):f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);f.close()
def prepare(a):
    out=a.out.resolve();need(out.is_relative_to(ROOT/'artifacts') and not out.exists(),'Fresh repository artifacts output required')
    source=a.reference_run.resolve();launch=read(source/'launch.json');result=read(source/'RUN_RESULT.json');prepared=read(a.tools/'PREPARED.json')
    if a.build_receipt:
        build=a.build_receipt.resolve();actual=read(build);jar=Path(actual['jar']).resolve();need(sha(jar)==actual['sha256'],'Actual explicit final Jar changed')
    else:
        jar=Path(launch['immutable_jar']['path']);build=Path(result['build_receipt']);need(sha(jar)==launch['immutable_jar']['sha256']==result['immutable_jar']['sha256'],'Same actual reference Jar required')
    pins=frozen_build_class_pins(build,jar)
    need(Path(launch['world']).resolve()==WORLD.resolve() and Path(launch['workingDirectory']).resolve()==GAME.resolve(),'Exact existing flat R10 fixture only')
    need(prepared['instrumented_classes']==['net.minecraft.client.Minecraft','net.minecraft.client.renderer.GameRenderer'] and prepared['bone_or_foot_samples']==prepared['screenshots']==0,'Only lightweight FPS driver allowed')
    need(sha(prepared['agent'])==prepared['agent_sha256'],'Prepared FPS diagnostic agent changed')
    command=launch['command'];patch={'projectseele.ordinaryMotionOutputR52':str(out/'ordinary'),'projectseele.r47NativeCommandInbox':str(out/'commands.json'),'projectseele.r44NetworkClient':'false'}
    command=[s for s in command if not any(s.startswith('-D'+k+'=') for k in patch)]
    # JVM properties precede the main/module argument; insert immediately after java.
    command=command[:1]+['-D'+k+'='+v for k,v in patch.items()]+command[1:]
    preflight=Path(read(source/'STAGING_RECEIPT.json')['preflight']);attach=preflight.parent/'tool_classes'
    need((attach/'C10HandlingR52Attach.class').is_file(),'Existing qualified target verifier/attach helper required')
    out.mkdir();write(out/'PLAN.json',{'diagnostic_only':True,'game_started':False,'world_written':False,'world':str(WORLD),'workingDirectory':str(GAME),'command':command,'jar':str(jar),'jar_sha256':sha(jar),'build_receipt':str(build),'build_receipt_sha256':sha(build),'class_pins':pins,'reference_run':str(source),'tools_receipt':str(a.tools/'PREPARED.json'),'tools_receipt_sha256':sha(a.tools/'PREPARED.json'),'agent':prepared['agent'],'agent_sha256':prepared['agent_sha256'],'attach_classpath':str(attach),'control':'Same unit1 handling210/camera then idle to60s; no JPEG, per-bone readback, FootWitness or pose-graph hook. Full model/render/collision remain enabled.'});print(out/'PLAN.json')
def run(a):
    out=a.out.resolve();d=read(out/'PLAN.json');need(not (out/'RUN_RESULT.json').exists(),'Preserve previous actual diagnostic result');need(Path(d['world']).resolve()==WORLD.resolve(),'Exact flat fixture only');idle();held=lock();process=None;restored=False
    try:
        need(sha(d['jar'])==d['jar_sha256'] and sha(d['build_receipt'])==d['build_receipt_sha256'] and frozen_build_class_pins(d['build_receipt'],d['jar'])==d['class_pins'],'Actual selected reference build changed')
        need(sha(d['tools_receipt'])==d['tools_receipt_sha256'] and sha(d['agent'])==d['agent_sha256'],'Diagnostic tools changed')
        before=inventory(WORLD);shutil.copytree(WORLD,out/'fixture_before',ignore=shutil.ignore_patterns('session.lock'));need(inventory(out/'fixture_before')==before,'Complete fixture backup failed')
        options=GAME/'options.txt';jar=GAME/'mods/projectseele-0.1.0-all.jar';shutil.copyfile(options,out/'options.before.txt');shutil.copyfile(jar,out/'host_jar.before.jar')
        write(out/'BACKUPS_READY.json',{'fixture_files':before,'options_sha256':sha(options),'host_jar_sha256':sha(jar),'complete':True})
        if sha(jar)!=d['jar_sha256']:shutil.copyfile(d['jar'],jar)
        write(out/'commands.json',{'seq':1,'commands':[]});unlock(held);held=None
        env=dict(os.environ);env.pop('MOD_CLASSES',None)
        with (out/'process.log').open('w') as log,(out/'process.error.log').open('w') as error:
            process=subprocess.Popen(d['command'],cwd=GAME,env=env,stdout=log,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0);write(out/'RUNNING.json',{'owned_pid':process.pid,'plan_sha256':sha(out/'PLAN.json')})
            attached=False;jfr=False;deadline=time.monotonic()+420;last_attach=0;logged=None
            while process.poll() is None and time.monotonic()<deadline:
                text=(out/'process.log').read_text(errors='replace')
                if logged is None and 'logged in with entity id' in text:logged=time.monotonic()
                if not attached and logged is not None and time.monotonic()-logged>=2 and time.monotonic()-last_attach>=3:
                    last_attach=time.monotonic()
                    attach=subprocess.run([str(JDK/'java.exe'),'-Xmx128m','--add-modules','jdk.attach','-cp',d['attach_classpath'],'C10HandlingR52Attach',str(process.pid),d['agent']],capture_output=True,text=True,timeout=30)
                    with (out/'attach.log').open('a') as f:f.write(attach.stdout+attach.stderr)
                    attached=attach.returncode==0
                if not jfr and (out/'ordinary/FPS_PROFILE_READY.json').exists():
                    result=subprocess.run([str(JDK/'jcmd.exe'),str(process.pid),'JFR.start','name=R52FpsControl','settings=profile','duration=55s','dumponexit=true','filename='+str(out/'control.jfr'),'maxsize=128m'],capture_output=True,text=True,timeout=15);(out/'jfr-start.log').write_text(result.stdout+result.stderr);need(result.returncode==0,'Actual JFR start failed');jfr=True
                time.sleep(.2)
            if process.poll() is None:
                write(out/'commands.json',{'seq':1000,'commands':[],'quit':True})
                try:process.wait(timeout=30)
                except subprocess.TimeoutExpired:raise RuntimeError('Owned client did not quit normally; preserve backups and live PID for Root; no automatic kill')
        need(process.returncode==0 and attached and jfr and (out/'ordinary/FPS_ONLY_SUMMARY.json').is_file(),'Actual FPS/JFR diagnostic incomplete')
        write(out/'RUN_RESULT.json',{'diagnostic_only':True,'owned_pid':process.pid,'exit_code':process.returncode,'normal_exit':True,'jfr':str(out/'control.jfr'),'summary':read(out/'ordinary/FPS_ONLY_SUMMARY.json'),'native_visual_acceptance':False})
    finally:
        if process is None or process.poll() is not None:
            if held is None:held=lock()
            backup=out/'BACKUPS_READY.json'
            if backup.is_file():
                b=read(backup);current=inventory(WORLD)
                for name in set(current)-set(b['fixture_files']):
                    p=(WORLD/name).resolve();need(p.is_relative_to(WORLD.resolve()),'Fixture retirement escaped target');p.unlink()
                for name,h in b['fixture_files'].items():
                    p=(WORLD/name).resolve();need(p.is_relative_to(WORLD.resolve()),'Fixture restore escaped target');p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(out/'fixture_before'/name,p)
                shutil.copyfile(out/'options.before.txt',GAME/'options.txt');shutil.copyfile(out/'host_jar.before.jar',GAME/'mods/projectseele-0.1.0-all.jar')
                need(inventory(WORLD)==b['fixture_files'] and sha(GAME/'options.txt')==b['options_sha256'] and sha(GAME/'mods/projectseele-0.1.0-all.jar')==b['host_jar_sha256'],'Complete fixture/options/Jar restoration failed');restored=True
                write(out/'RESTORED.json',{'entire_fixture_exact_except_ephemeral_session_lock':True,'all_persisted_fixture_members_exact':True,'options_exact':True,'host_jar_exact':True,'source_WORLD_R52_untouched':True})
            unlock(held)
        else:write(out/'LIVE_PID_NEEDS_ROOT.json',{'owned_pid':process.pid,'restored':False,'reason':'Client still live; do not restore its World/options/Jar until normal close'})
    print(json.dumps({'out':str(out),'restored':restored}))
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reference-run',type=Path,default=ROOT/'artifacts/r52_native_handling_candidate11');ap.add_argument('--tools',type=Path,default=ROOT/'.Codex/r52_runtime_close/fps_only_tools_c11_20261012');ap.add_argument('--build-receipt',type=Path,help='Explicit final build for same-scene old/new performance comparison');ap.add_argument('--run',action='store_true');a=ap.parse_args()
    if a.run:run(a)
    else:prepare(a)
if __name__=='__main__':main()
