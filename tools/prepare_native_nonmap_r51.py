"""Prepare one test copy from the delivered R50 ZIPs; never import QA progress."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r51_nonmap_release')
OUT=BASE/'native_r51';GAME=OUT/'game';WORLD='SEELE_R50_NONMAP_QA_R51'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def quote_arg(value):return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'

def prepare():
    assert not OUT.exists(), 'Keep the existing test copy and its progress'
    OUT.mkdir();GAME.mkdir()
    with zipfile.ZipFile('D:/eva/delivery/Project_SEELE_Encore_R50_20261006_Client_PCL.zip') as z:
        for name in z.namelist():
            if not name.startswith('overrides/') or name.endswith('/'):continue
            target=GAME/name[len('overrides/'):]
            assert target.resolve().is_relative_to(GAME.resolve())
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
    hashes={};save=GAME/'saves'/WORLD
    with zipfile.ZipFile('D:/eva/delivery/Project_SEELE_Encore_R50_20261006_Server.zip') as z:
        for name in z.namelist():
            if not name.startswith('SEELE_R50_WORLD/') or name.endswith('/'):continue
            rel=name[len('SEELE_R50_WORLD/'):];target=save/rel
            assert target.resolve().is_relative_to(save.resolve())
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name));hashes[rel]=digest(target)
    assert len(hashes)==3066
    selection=json.loads((BASE/'RESOURCE_SELECTION.json').read_text('utf8'))
    for row in selection['operations']:
        if row['kind']=='pure_motion_runtime':shutil.copyfile(BASE/'selected_runtime'/row['relative'],GAME/row['relative'])
    shutil.copyfile(BASE/'selected_runtime/projectseele-local-maps/combat_bundle_r44.json',GAME/'projectseele-local-maps/combat_bundle_r44.json')
    # Reuse only the existing Forge/PCL bootstrap command and installed native
    # libraries. No world, options, mods or config come from the cancelled QA.
    template=json.loads(Path('D:/eva/artifacts/rebuild_r51/native_client_restart_from_R50/SEELE_R52_QA_R50_20261009/launch.json').read_text('utf8'))
    command=[v for v in template['command'] if not v.startswith('-Dprojectseele.r47NativeCommandInbox=')]
    for key,value in [('--gameDir',str(GAME)),('--quickPlaySingleplayer',WORLD),('--width','1280'),('--height','720')]:
        command[command.index(key)+1]=value
    command.insert(1,'-Dprojectseele.r47NativeCommandInbox='+str(OUT/'commands.json'))
    spec=dict(command=command,workingDirectory=str(GAME),environment=template.get('environment',{}),
        world=str(save),world_source='Original delivered R50 serverZIP, exact3066file copy',
        staged_jar=None,protocol='60',cancelled_QA_content_imported=False)
    (OUT/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
    (OUT/'ORIGINAL_WORLD_COPY.json').write_text(json.dumps(dict(files=hashes,map_changed=False,never_import_back=True),indent=2),'utf8')
    print('Prepared original R50 world:',len(hashes),'files; final JAR not yet staged; no Java started')

def stage():
    jar=ROOT/'build/libs/projectseele-0.1.0-all.jar'
    with zipfile.ZipFile(jar) as z:
        assert not any('NervFacilityLayoutR51' in n for n in z.namelist())
        assert json.loads(z.read('data/projectseele/dimension_type/geofront.json'))==json.loads((BASE/'baseline_assets/data/projectseele/dimension_type/geofront.json').read_text())
    shutil.copyfile(jar,GAME/'mods/projectseele-0.1.0-all.jar')
    spec=json.loads((OUT/'launch.json').read_text('utf8'));spec['staged_jar']=dict(path=str(jar),sha256=digest(jar))
    (OUT/'launch.json').write_text(json.dumps(spec,indent=2),'utf8');print('Staged non-map JAR',spec['staged_jar']['sha256'])

def start(seq):
    spec=json.loads((OUT/'launch.json').read_text('utf8'));assert spec['staged_jar']
    assert digest(GAME/'mods/projectseele-0.1.0-all.jar')==spec['staged_jar']['sha256']
    (OUT/'commands.json').write_text(json.dumps(dict(seq=seq,commands=['seele tp hanger','seele eva status all'],screenshot=str(OUT/'screens/initial.png'))),'utf8')
    args=OUT/'launch.args';args.write_text('\n'.join(quote_arg(v) for v in spec['command'][1:])+'\n','utf8')
    env=dict(os.environ);env.update(spec['environment']);log=(OUT/'process.log').open('wb')
    process=subprocess.Popen([spec['command'][0],'@'+str(args)],cwd=GAME,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
    (OUT/'RUNNING.json').write_text(json.dumps(dict(pid=process.pid,world=spec['world'],jar=spec['staged_jar']),indent=2),'utf8');print('R51 original-map QA PID',process.pid)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--stage',action='store_true');p.add_argument('--start',type=int);a=p.parse_args()
    if a.prepare:prepare()
    if a.stage:stage()
    if a.start is not None:start(a.start)
