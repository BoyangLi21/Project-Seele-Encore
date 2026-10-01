"""Dedicated server + independent ordinary-client process, not an integrated-server fixture."""
from pathlib import Path
import argparse,json,os,queue,shutil,subprocess,sys,threading,time,zipfile,hashlib
from release_combat_r36 import guard
from launch_rendered_client_r17 import java_environment
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
WORLD='SEELE_R44_NETWORK_REVIEW';PORT=25576
LABEL='before'
WEAPON='fists'
BUNDLE=''
MEDIA=False
VIEW='gameplay'
HAND_WITNESS=''
PASSENGER_WITNESS=''
PASSENGER_BEFORE=False
POSE_LAYERS=False

def prepare(retry=False):
    guard();out=ART/'network_runtime'/LABEL;out.mkdir(parents=True,exist_ok=True)
    server=ROOT/'.Codex/r44-network-server';client=ROOT/'.Codex/r44-network-client';world=ROOT/'run/saves'/WORLD
    if retry:
        assert server.is_dir() and client.is_dir() and world.is_dir()
        if LABEL=='before' and (out/'client_samples.json').exists():raise RuntimeError('Frozen before evidence cannot be overwritten; choose a named candidate label')
        attempt=out/('attempt_'+time.strftime('%Y%m%d_%H%M%S'));attempt.mkdir()
        for name in ('server.log','client.log','server_samples.json','client_samples.json','fists_summary.json'):
            if (out/name).exists():shutil.copy2(out/name,attempt/name)
        for kind in ('server','client'):
            spec=json.loads((ART/'network_runtime/before'/(kind+'_launch.json')).read_text('utf8'))
            spec['environment']['MOD_CLASSES']='projectseele%%'+str(ROOT/'build/resources/main')+';projectseele%%'+str(ROOT/'build/classes/java/main')
            (out/(kind+'_launch.json')).write_text(json.dumps(spec),'utf8')
        (client/'r44_network_client.json').unlink(missing_ok=True)
        return
    assert not server.exists() and not client.exists() and not world.exists()
    source=Path(json.loads((ART/'baseline.json').read_text())['instance'])
    shutil.copytree(ART/'source_world_backup',world,ignore=shutil.ignore_patterns('session.lock'))
    server.mkdir();client.mkdir();(server/'mods').mkdir();(client/'config').mkdir()
    prior=ROOT/'.Codex/r43-native-server'
    for p in (prior/'mods').glob('*'):
        if p.is_file():shutil.copy2(p,server/'mods'/p.name)
    for kind in ('projectseele-local-maps','config'):
        if kind=='config':
            shutil.copytree(prior/kind,server/kind,dirs_exist_ok=True)
            shutil.copytree(source/kind,client/kind,dirs_exist_ok=True)
        else:
            shutil.copytree(source/kind,server/kind);shutil.copytree(source/kind,client/kind)
    # Private geometry is read from the exact installed resource pack, without
    # duplicating hundreds of MB or replacing the user's runtime files.
    subprocess.run(['powershell','-NoProfile','-Command',
                    'New-Item -ItemType Junction -Path '+ps(str(client/'resourcepacks'))+' -Target '+ps(str(source/'resourcepacks'))+' | Out-Null'],check=True)
    shutil.copy2(source/'options.txt',client/'options.txt')
    options=(client/'options.txt').read_text('utf8').splitlines()
    replacements={'renderDistance:':'renderDistance:6','simulationDistance:':'simulationDistance:5','pauseOnLostFocus:':'pauseOnLostFocus:false','maxFps:':'maxFps:90'}
    options=[next((v for k,v in replacements.items() if row.startswith(k)),row) for row in options]
    (client/'options.txt').write_text('\n'.join(options)+'\n','utf8')
    cfg=client/'config/oculus.properties'
    if cfg.exists():cfg.write_text(cfg.read_text('utf8').replace('enableShaders=true','enableShaders=false'),'utf8')
    (server/'eula.txt').write_text((ROOT/'run/eula.txt').read_text('utf8'),'utf8')
    (server/'server.properties').write_text(f'server-ip=127.0.0.1\nserver-port={PORT}\nlevel-name={WORLD}\nonline-mode=false\nwhite-list=false\nview-distance=8\nsimulation-distance=6\nspawn-protection=0\nallow-flight=true\nmax-tick-time=120000\ngamemode=creative\n','utf8')
    for kind,template,flag,heap,work in (
        ('server',ART.parent/'repair_r43/moving_devices/native_dry_route/launch.json','r44NetworkReview','2560M',server),
        ('client',ROOT/'.Codex/client-r42-interiors-photos.json','r44NetworkClient','3G',client)):
        spec=json.loads(template.read_text('utf8'));command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
        command=[s for s in command if not s.startswith(('-Xmx','-Xms'))];command[1:1]=['-Xms512M','-Xmx'+heap,'-Dprojectseele.'+flag+'=true']
        spec['workingDirectory']=str(work)
        if kind=='server':command[command.index('--world')+1]=WORLD
        else:
            command[command.index('--gameDir')+1]=str(client)
            at=command.index('--quickPlaySingleplayer');command[at]='--quickPlayMultiplayer';command[at+1]='127.0.0.1:'+str(PORT)
            command.extend(['--username','R44Probe'])
        spec['command']=command;(out/(kind+'_launch.json')).write_text(json.dumps(spec),'utf8')
    print('Dedicated-server and independent-client inputs prepared',flush=True)

def ps(text):return "'"+text.replace("'","''")+"'"

def exact_private_resources(out):
    source=Path(json.loads((ART/'baseline.json').read_text())['instance'])
    jar=next((source/'mods').glob('projectseele-*.jar'));resources=ART/'network_runtime/private_resources'
    if not resources.exists():
        shutil.copytree(ROOT/'build/resources/main',resources)
        with zipfile.ZipFile(jar) as z:
            for name in z.namelist():
                if name.startswith('assets/projectseele/') and not name.endswith('/'):
                    target=resources/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
        (resources/'source_jar.json').write_text(json.dumps({'source':str(jar),'sha256':hashlib.sha256(jar.read_bytes()).hexdigest()}),'utf8')
    # Frozen 'before' replays the installed R43 exactly. Subsequent candidates
    # keep the measured private meshes while taking new production code/assets.
    if LABEL!='before':
        for source_file in (ROOT/'build/resources/main').rglob('*'):
            if not source_file.is_file():continue
            relative=source_file.relative_to(ROOT/'build/resources/main');name=relative.as_posix()
            if name.startswith(('assets/projectseele/geo/','assets/projectseele/mesh/','assets/projectseele/animations/','assets/projectseele/textures/entity/')):continue
            # Old physical motion profiles stay identical to the measured
            # installed baseline; R44 has new explicit file identities.
            if name.startswith('assets/projectseele/motion/') and 'r44' not in name:continue
            target=resources/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source_file,target)
    for kind in ('server','client'):
        path=out/(kind+'_launch.json');spec=json.loads(path.read_text())
        old=str(ROOT/'build/resources/main');forms={old,old.replace('\\','/'),old.replace('\\','\\\\')}
        for key,value in spec['environment'].items():
            for form in forms:value=value.replace(form,resources.resolve().as_posix())
            spec['environment'][key]=value
        spec['command']=[s for s in spec['command'] if not s.startswith('-Dprojectseele.strictHighDetail=')]
        spec['command']=[s for s in spec['command'] if not s.startswith(('-Dprojectseele.r44NetworkWeapon=','-Dprojectseele.combatBundleDirectory='))]
        spec['command'].insert(1,'-Dprojectseele.r44NetworkWeapon='+WEAPON)
        if BUNDLE:spec['command'].insert(1,'-Dprojectseele.combatBundleDirectory='+BUNDLE)
        if kind=='client' and MEDIA:spec['command'].insert(1,'-Dprojectseele.r44NetworkMedia=true')
        if kind=='client':spec['command'].insert(1,'-Dprojectseele.r44NetworkView='+VIEW)
        if kind=='client':spec['command'].insert(1,'-Dprojectseele.strictHighDetail=true')
        if kind=='client' and POSE_LAYERS:
            spec['command']=[s for s in spec['command']if not s.startswith(('-Dprojectseele.r40PoseLayers=','-Dprojectseele.r44PoseLayerTickGap='))]
            spec['command'][1:1]=['-Dprojectseele.r40PoseLayers=true','-Dprojectseele.r44PoseLayerTickGap=20','-Dprojectseele.r44NetworkHandStances=true']
        if kind=='client' and HAND_WITNESS:
            spec['command']=[s for s in spec['command'] if not s.startswith(('-Dprojectseele.r44NetworkHandStances=','-Dprojectseele.r44HandWitnessPath=','-Dprojectseele.r44HandWitnessFrames='))]
            spec['command'][1:1]=['-Dprojectseele.r44NetworkHandStances=true','-Dprojectseele.r44HandWitnessPath='+str(Path(HAND_WITNESS).resolve()),'-Dprojectseele.r44HandWitnessFrames=240']
        if PASSENGER_WITNESS:
            directory=Path(PASSENGER_WITNESS).resolve();directory.mkdir(parents=True,exist_ok=True)
            spec['command']=[s for s in spec['command'] if not s.startswith(('-Dprojectseele.r44PassengerWitnessPath=','-Dprojectseele.r44PassengerCleanupBefore=','-Dprojectseele.r44PassengerReplay='))]
            spec['command'].insert(1,'-Dprojectseele.r44PassengerWitnessPath='+str(directory/(kind+'_callbacks.jsonl')))
            if kind=='server':spec['command'].insert(1,'-Dprojectseele.r44PassengerReplay=true')
            if kind=='client' and not any(s.startswith('-Dprojectseele.r44NetworkHandStances=')for s in spec['command']):spec['command'].insert(1,'-Dprojectseele.r44NetworkHandStances=true')
            if kind=='client' and PASSENGER_BEFORE:spec['command'].insert(1,'-Dprojectseele.r44PassengerCleanupBefore=true')
        path.write_text(json.dumps(spec),'utf8')

def main():
    global LABEL,WEAPON,BUNDLE,MEDIA,VIEW,HAND_WITNESS,PASSENGER_WITNESS,PASSENGER_BEFORE,POSE_LAYERS
    p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--retry',action='store_true');p.add_argument('--label',default='before');p.add_argument('--weapon',choices=('fists','knife'),default='fists');p.add_argument('--bundle',default='');p.add_argument('--media',action='store_true');p.add_argument('--view',choices=('gameplay','orbit'),default='gameplay');p.add_argument('--hand-witness',default='');p.add_argument('--passenger-witness',default='');p.add_argument('--passenger-before',action='store_true');p.add_argument('--pose-layers',action='store_true');args=p.parse_args();LABEL=args.label;WEAPON=args.weapon;BUNDLE=args.bundle;MEDIA=args.media;VIEW=args.view;HAND_WITNESS=args.hand_witness;PASSENGER_WITNESS=args.passenger_witness;PASSENGER_BEFORE=args.passenger_before;POSE_LAYERS=args.pose_layers
    if PASSENGER_BEFORE and not PASSENGER_WITNESS:raise ValueError('Old cleanup negative control requires an explicit passenger witness directory')
    assert LABEL.replace('_','').isalnum(),'Invalid review label'
    prepare(args.retry)
    # A detached orbit camera is outside the player's normal tracking centre.
    # Preserve ordinary-player settings in the immutable before recording.
    if VIEW=='orbit' and LABEL!='before':
        properties=ROOT/'.Codex/r44-network-server/server.properties'
        rows=properties.read_text('utf8').splitlines()
        rows=[('view-distance=12' if r.startswith('view-distance=') else r) for r in rows]
        properties.write_text('\n'.join(rows)+'\n','utf8')
    exact_private_resources(ART/'network_runtime'/LABEL)
    for kind in ('server','client'):
        launch=ART/'network_runtime'/LABEL/(kind+'_launch.json');spec=json.loads(launch.read_text('utf8'));spec=freeze(spec,launch.parent/kind);launch.write_text(json.dumps(spec),'utf8')
    if args.prepare_only:return
    out=ART/'network_runtime'/LABEL;server_spec=json.loads((out/'server_launch.json').read_text());env=java_environment()[1];env.update(server_spec['environment'])
    lifecycle_source=ROOT/'run/saves'/WORLD/'r44_actor_owner_lifecycle.jsonl'
    lifecycle_offset=lifecycle_source.stat().st_size if lifecycle_source.exists() else 0
    # Use the established Java argument-file quoting rather than a shell-built command.
    def quote(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
    argument_file=out/'server.args';argument_file.write_text('\n'.join(quote(s) for s in server_spec['command'][1:])+'\n','utf8')
    proc=subprocess.Popen([server_spec['command'][0],'@'+str(argument_file.resolve())],cwd=server_spec['workingDirectory'],env=env,
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
    ready=threading.Event()
    def consume():
        with (out/'server.log').open('w',encoding='utf8') as log:
            for line in proc.stdout:
                log.write(line);log.flush()
                if 'Done (' in line:ready.set()
    reader=threading.Thread(target=consume,daemon=True);reader.start()
    try:
        if not ready.wait(120):raise RuntimeError('Dedicated server did not reach ready state')
        print('Dedicated server ready; launching a separate client JVM',flush=True)
        with (out/'client.log').open('w',encoding='utf8') as log:
            child=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(out/'client_launch.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        client=ROOT/'.Codex/r44-network-client';result=client/'r44_network_client.json'
        assert child.returncode==0 and result.exists(),'Network client did not complete; preserve failed logs'
        shutil.copy2(result,out/'client_samples.json')
        if MEDIA:
            folders=sorted((client/'r44_network_media').glob('*'),key=lambda q:q.stat().st_mtime)
            assert folders,'No actual gameplay frames were recorded'
            frames=folders[-1];assert (frames/'frames.json').exists(),'Frame writer did not finish'
            (out/'media.json').write_text(json.dumps(dict(folder=str(frames),frames=len(json.loads((frames/'frames.json').read_text('utf8')))),indent=2),'utf8')
        server=ROOT/'run/saves'/WORLD;shutil.copy2(server/'r44_network_server.json',out/'server_samples.json')
        layers=client/'body_layers_r40.json'
        if layers.exists():shutil.copy2(layers,out/'body_layers_r40.json')
        lifecycle=server/'r44_actor_owner_lifecycle.jsonl'
        if lifecycle.exists():
            with lifecycle.open('rb') as source:
                source.seek(lifecycle_offset);fresh=source.read()
            (out/'server_actor_lifecycle.jsonl').write_bytes(fresh)
            actors=sorted({json.loads(line)['entity_uuid'] for line in fresh.decode('utf8').splitlines() if line.strip()})
            (out/'server_actor_lifecycle_scope.json').write_text(json.dumps(dict(source=str(lifecycle.resolve()),start_byte_offset=lifecycle_offset,
                end_byte_offset=lifecycle_offset+len(fresh),fresh_actor_uuids=actors,scope='Only bytes appended by this new server/client run; old process records excluded'),indent=2),'utf8')
        print('Fresh server/client state and final rendered bones captured',flush=True)
    finally:
        if proc.poll() is None:
            proc.stdin.write('execute as @a run seele review_r44 finish\nstop\n');proc.stdin.flush()
            try:proc.wait(timeout=60)
            except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=15)
        reader.join(timeout=5)

if __name__=='__main__':main()
