"""Prepare and, only when Root explicitly requests it, run the24 R52 walks.

Reuses the generation server's immutable libraries in an independent host.
It never copies a client or world, opens the source W in Minecraft, changes
map geometry, opens doors or invokes installation/teleport commands.
"""
from pathlib import Path
import argparse, ctypes, hashlib, json, os, shutil, socket, subprocess, time
from ctypes import wintypes

REPO=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
VALIDATION=BASE/'native_r52_validation'
QA=Path('D:/eva/artifacts/r51_nonmap_release/native_r51/game/saves/SEELE_R52_REVIEW').resolve()
SOURCE=(BASE/'WORLD_R52').resolve()
LIB_HOST=BASE/'native_generation/server'
JAR=REPO/'artifacts/r52_unified_candidate8/projectseele-0.1.0-all.jar'
C8_SHA='b613ca90f4429347accb193b64eeee8da17ef50325d4933c94ad819e4a6c623e'
JAVA=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/java.exe')
PROPERTIES={'projectseele.regionalBuild':'r44-collision','projectseele.nativeReviewWorld':'SEELE_R52_REVIEW','projectseele.r52NativeReviewCopy':'true'}

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def quote(value):
    if any(c in value for c in '\r\n\0'):raise ValueError('Unsafe Java argument')
    return '"'+value.replace('\\','/').replace('"','\\"')+'"'
def atomic_copy(source,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.r52-detached.tmp')
    if temporary.exists():raise RuntimeError('Preserve unexpected detached staging: '+str(temporary))
    shutil.copyfile(source,temporary)
    if sha(temporary)!=sha(source):raise RuntimeError('Detached copy SHA differs')
    os.replace(temporary,target)

def require_unlocked(world):
    """Read/probe existing session.lock; never create or write world files."""
    path=Path(world)/'session.lock'
    if not path.exists():return
    if os.name!='nt':
        import fcntl
        with path.open('rb') as stream:
            try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(stream,fcntl.LOCK_UN)
            except OSError as error:raise RuntimeError('Native world session is locked: '+str(world)) from error
        return
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    class OVERLAPPED(ctypes.Structure):
        _fields_=[('Internal',ctypes.c_size_t),('InternalHigh',ctypes.c_size_t),('Offset',wintypes.DWORD),('OffsetHigh',wintypes.DWORD),('hEvent',wintypes.HANDLE)]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.LockFileEx.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(OVERLAPPED)]
    kernel.UnlockFileEx.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(OVERLAPPED)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateFileW(str(path),0xC0000000,7,None,3,0x80,None)
    if handle==wintypes.HANDLE(-1).value:raise RuntimeError('Cannot prove native session unlocked: '+str(world))
    overlap=OVERLAPPED()
    try:
        if not kernel.LockFileEx(handle,3,0,0xFFFFFFFF,0x7FFFFFFF,ctypes.byref(overlap)):raise RuntimeError('Native world session is locked: '+str(world))
        kernel.UnlockFileEx(handle,0,0xFFFFFFFF,0x7FFFFFFF,ctypes.byref(overlap))
    finally:kernel.CloseHandle(handle)

def inputs():
    if sha(JAR)!=C8_SHA:raise ValueError('Exact immutable C8 JAR required')
    receipt=read(REPO/'artifacts/r52_unified_candidate8/BUILD_RECEIPT.json')
    if receipt.get('sha256')!=C8_SHA or receipt.get('build_exit')!=0:raise ValueError('Root C8 successful build receipt required')
    cases_path=VALIDATION/'PUBLIC_WALK_CASES.json';cases=read(cases_path)
    if len(cases)!=24 or len({c['id'] for c in cases})!=24 or any(not c['id'].startswith('r52/') or len(c['path'])<2 for c in cases):raise ValueError('Exact24 Root R52 public walk cases required; no historical8500-case catalogue')
    clone=read(VALIDATION/'CLONE_RECEIPT.json')
    if Path(clone['source_world']).resolve()!=SOURCE or Path(clone['target_world']).resolve()!=QA:raise ValueError('Root unique current W/QA clone receipt differs')
    if not (QA/'level.dat').is_file() or QA==SOURCE:raise ValueError('Root must refresh the one distinct QA copy')
    return cases_path,cases,clone

def prepare(out):
    cases_path,cases,clone=inputs();out.mkdir(parents=True,exist_ok=True)
    plan={'prepared_only':True,'world_written':False,'game_started':False,'native_walks_passed':False,'qa_world':str(QA),'source_world_opened':False,'source_world':str(SOURCE),'jar':str(JAR),'jar_sha256':C8_SHA,'cases':str(cases_path),'cases_sha256':sha(cases_path),'case_count':len(cases),'host':str(out/'host'),'library_source_host':str(LIB_HOST),'properties':PROPERTIES,'command_world_flags':['--universe',str(QA.parent),'--world',QA.name],'clone_ever_launched_at_prepare':clone.get('ever_launched'),'next_root_step':'Review this plan, mark Root CLONE_RECEIPT ever_launched=true, then explicitly use --run-approved. No world/client copy is performed.'}
    write(out/'PREPARED_PUBLIC_WALK_PLAN.json',plan);print(json.dumps({'prepared_only':True,'cases':24,'jar_sha256':C8_SHA,'qa_world':str(QA),'world_written':False}))

def stage_host(out):
    host=out/'host';host.mkdir(parents=True,exist_ok=True)
    if (host/'RUNNING.json').exists():raise RuntimeError('Preserve a prior host launch; use a new Root attempt directory')
    libraries=host/'libraries'
    if not libraries.exists():
        if os.name=='nt':subprocess.run(['powershell','-NoProfile','-Command','New-Item -ItemType Junction -Path $env:R52_LINK_PATH -Target $env:R52_LIBRARY_SOURCE | Out-Null'],env={**os.environ,'R52_LINK_PATH':str(libraries),'R52_LIBRARY_SOURCE':str(LIB_HOST/'libraries')},check=True,capture_output=True)
        else:libraries.symlink_to((LIB_HOST/'libraries').resolve(),target_is_directory=True)
    if libraries.resolve()!=(LIB_HOST/'libraries').resolve():raise RuntimeError('Shared read-only library root differs')
    for folder in ('config','defaultconfigs','projectseele-local-maps'):
        if not (host/folder).exists():shutil.copytree(LIB_HOST/folder,host/folder)
    eula=LIB_HOST/'eula.txt'
    if 'eula=true' not in eula.read_text():raise ValueError('Reuse the existing local EULA agreement; never auto-accept')
    shutil.copyfile(eula,host/'eula.txt')
    mods=host/'mods';mods.mkdir(exist_ok=True)
    for source in (LIB_HOST/'mods').glob('*.jar'):
        if source.name.startswith('projectseele-'):continue
        target=mods/source.name
        if not target.exists():os.link(source,target)
        if sha(source)!=sha(target):raise RuntimeError('Immutable shared dependency differs: '+source.name)
    target=mods/JAR.name;previous=None
    if target.exists():
        previous={'path':str(target),'sha256':sha(target),'backup':str(out/'previous_host_projectseele.jar')}
        shutil.copyfile(target,previous['backup'])
    atomic_copy(JAR,target)
    if sha(target)!=C8_SHA or target.stat().st_nlink!=1:raise RuntimeError('C8 project JAR must be detached private bytes')
    (host/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25581\nonline-mode=false\nview-distance=2\nsimulation-distance=2\nlevel-name=SEELE_R52_REVIEW\nmax-tick-time=180000\nallow-flight=true\nenable-rcon=false\nenable-query=false\nspawn-protection=0\n',encoding='utf-8')
    args=['-Xms1G','-Xmx6G','-XX:+UseG1GC','-XX:ActiveProcessorCount=4','-Dfile.encoding=UTF-8']+['-D'+k+'='+v for k,v in PROPERTIES.items()]
    # Keep actual normal collision/mechanism code. No door/lease/physics bypass.
    args+=['-Dprojectseele.r44TvCageReview=true','-Dprojectseele.combatBundleDirectory=projectseele-local-maps']
    jvm=out/'walk_jvm.args';jvm.write_text('\n'.join(quote(x) for x in args)+'\n',encoding='utf-8')
    command=[str(JAVA),'@'+str(jvm.resolve()),'@libraries/net/minecraftforge/forge/1.20.1-47.4.10/win_args.txt','nogui','--universe',str(QA.parent),'--world',QA.name]
    write(out/'LAUNCH.json',{'command':command,'working_directory':str(host),'jar_sha256':C8_SHA,'previous_project_jar':previous,'private_host':True,'libraries_shared_read_only':str(libraries.resolve()),'world_or_client_copied':False})
    return host,target,previous,command

def run(out,timeout):
    cases_path,cases,clone=inputs()
    if clone.get('ever_launched') is not True:raise RuntimeError('Root must mark the unique QA ever_launched before approving execution')
    if any((out/name).exists() for name in ('RUNNING.json','RUN_RESULT.json','LAUNCH.json','native_server.log')):raise RuntimeError('Preserve previous observations; a new Root attempt directory is required')
    require_unlocked(QA);require_unlocked(SOURCE)
    if not (QA/'regional_states.json').is_file():raise RuntimeError('Current Root QA registry states missing; do not fabricate map inputs')
    env=dict(os.environ)
    if any('-Dprojectseele.' in env.get(k,'') for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS')):raise RuntimeError('Inherited Java review/resource overrides require explicit Root cleanup')
    env.pop('MOD_CLASSES',None)
    with socket.socket() as probe:probe.bind(('127.0.0.1',25581))
    host,target,previous,command=stage_host(out);result=QA/'quality_native_walk_results.json';stale=None;case_target=QA/'r44_walk_cases.json';old_cases=None;process=None
    try:
        require_unlocked(QA);require_unlocked(SOURCE)
        if result.exists():stale=out/'previous_quality_native_walk_results.json';os.replace(result,stale)
        if case_target.exists():old_cases=out/'previous_r44_walk_cases.json';shutil.copyfile(case_target,old_cases)
        atomic_copy(cases_path,case_target);began=time.time_ns()
        if sha(case_target)!=sha(cases_path):raise RuntimeError('Fresh24-case input differs')
        with (out/'native_server.log').open('xb') as log:
            process=subprocess.Popen(command,cwd=host,env=env,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
            write(out/'RUNNING.json',{'pid':process.pid,'qa_world':str(QA),'source_world_opened':False,'jar_sha256':C8_SHA,'started_unix_ns':began,'cases_sha256':sha(cases_path)})
            try:code=process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.stdin.write(b'stop\n');process.stdin.flush()
                try:process.wait(timeout=60)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=30)
                raise RuntimeError('Bounded walk run timed out; logs retained, no result accepted')
        if not result.is_file() or result.stat().st_mtime_ns<began:raise RuntimeError('No fresh native quality result from this launch')
        rows=read(result);rows=rows if isinstance(rows,list) else rows.get('results',[])
        fresh={r['id'] for r in rows}=={c['id'] for c in cases} and len(rows)==24
        passed=code==0 and fresh and all(r.get('status')=='pass' for r in rows)
        shutil.copyfile(result,out/'quality_native_walk_results.json')
        write(out/'RUN_RESULT.json',{'passed':passed,'exit_code':code,'case_count':len(rows),'fresh_exact24_ids':fresh,'jar_sha256':C8_SHA,'source_world_opened':False,'world_or_client_copied':False,'source_map_written':False,'result_sha256':sha(result),'method':'Native FakePlayer.move and actual vanilla/Forge collision/support solver on the current Root QA24 paths','actual_client_key_input':False,'full_device_lifecycle':False,'native_mechanical_acceptance':False})
        print(json.dumps({'passed':passed,'cases':len(rows),'jar_sha256':C8_SHA,'source_world_opened':False}))
        if not passed:raise RuntimeError('Current native walk failures retained; no old results reused')
    finally:
        if process is not None and process.poll() is None:
            try:process.stdin.write(b'stop\n');process.stdin.flush();process.wait(timeout=60)
            except (OSError,subprocess.TimeoutExpired):process.terminate();process.wait(timeout=30)
        # Restore only this private host's previous bytes after its JVM stops.
        if previous:
            atomic_copy(previous['backup'],target)
            if sha(target)!=previous['sha256']:raise RuntimeError('Previous private host JAR SHA could not be restored')
            write(out/'HOST_JAR_RESTORED.json',previous)
        if old_cases and old_cases.exists():atomic_copy(old_cases,case_target)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=VALIDATION/'public_walk_candidate8');parser.add_argument('--prepare',action='store_true');parser.add_argument('--run-approved',action='store_true');parser.add_argument('--timeout',type=int,default=900);args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(VALIDATION.resolve()) or out.is_relative_to(QA) or out.is_relative_to(SOURCE):raise ValueError('Independent Root validation output required')
    if args.prepare:prepare(out)
    if args.run_approved:out.mkdir(parents=True,exist_ok=True);run(out,args.timeout)
    if not args.prepare and not args.run_approved:parser.error('Use --prepare, or explicit Root-approved --run-approved after clone refresh/ever_launched')
if __name__=='__main__':main()
