"""Stage a normal client against the sole current World, without copying the save."""
from pathlib import Path, PurePosixPath
import argparse,hashlib,json,os,shutil,subprocess,zipfile
from build_immutable_r52_candidate import frozen_build_class_pins
from launch_rendered_client_r17 import java_environment
from root_bundle_authority_r53 import candidate

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf-8')
def need(ok,message):
    if not ok:raise ValueError(message)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--dependency',type=Path,required=True);ap.add_argument('--dependency-sha256',required=True)
    ap.add_argument('--template',type=Path,required=True);ap.add_argument('--runtime',type=Path,required=True)
    ap.add_argument('--build-receipt',type=Path);ap.add_argument('--dependency-only',action='store_true')
    ap.add_argument('--max-heap-gib',type=int,choices=(6,8),default=6)
    a=ap.parse_args();world=a.world.resolve();out=candidate(a.out,world);game=out/'game'
    need(world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve() and (world/'level.dat').is_file(),'Sole current World required')
    need(sha(a.dependency)==a.dependency_sha256,'Exact delivered client dependency archive changed')
    stage=out/'DEPENDENCY_RECEIPT.json'
    if not stage.exists():
        need(not out.exists(),'Fresh dependency staging directory required');game.mkdir(parents=True)
        members={}
        with zipfile.ZipFile(a.dependency) as z:
            for info in z.infolist():
                name=info.filename
                if info.is_dir() or not name.startswith('overrides/'):continue
                rel=name.removeprefix('overrides/');p=PurePosixPath(rel)
                need(not p.is_absolute() and ':' not in rel and '\\' not in rel and all(q not in ('','.','..') for q in rel.split('/')),'Unsafe dependency member')
                if not (rel.startswith(('mods/','config/','defaultconfigs/','resourcepacks/','shaderpacks/')) or rel=='options.txt'):continue
                if rel.startswith('mods/projectseele-'):continue
                destination=game/rel;destination.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as source,destination.open('xb') as target:shutil.copyfileobj(source,target)
                members[rel]=sha(destination)
        need((a.runtime/'combat_bundle_r44.json').is_file(),'Selected complete original runtime required')
        shutil.copytree(a.runtime,game/'projectseele-local-maps')
        # Presentation settings affect this isolated host only, never the World.
        options=game/'options.txt';lines=options.read_text('utf-8').splitlines()
        settings={'pauseOnLostFocus':'false','renderDistance':'8','simulationDistance':'6','maxFps':'45'}
        lines=[s for s in lines if s.partition(':')[0] not in settings]
        options.write_text('\n'.join(lines+[k+':'+v for k,v in settings.items()])+'\n','utf-8')
        # A filesystem link selects the existing authoritative save. No QA
        # chunk/entity/player snapshot is created or imported.
        linked=game/'saves'
        subprocess.run(['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '"+str(linked).replace("'","''")+"' -Target '"+str(world.parent).replace("'","''")+"' | Out-Null"],check=True)
        need((linked/world.name).resolve()==world,'Actual native save parent link differs')
        write(stage,dict(dependency=str(a.dependency.resolve()),dependency_sha256=a.dependency_sha256,delivered_members=members,world=str(world),world_copies=0,world_written=False))
    else:
        old=read(stage);need(old['dependency_sha256']==a.dependency_sha256 and old['world']==str(world),'Prepared client authority changed')
    if a.dependency_only:print('Client dependency host prepared; no game or World write');return
    need(a.build_receipt is not None,'Final immutable build receipt required')
    receipt=read(a.build_receipt);jar=Path(receipt['jar']);frozen_build_class_pins(a.build_receipt,jar)
    shutil.copyfile(jar,game/'mods/projectseele-0.1.0-all.jar')
    spec=read(a.template);command=[str(v) for v in spec['command'] if not str(v).startswith(('-Dprojectseele.','-Xms','-Xmx'))]
    need(command[command.index('--launchTarget')+1]=='forgeclient','Normal Forge client template required')
    for flag,value in [('--gameDir',str(game)),('--quickPlaySingleplayer',world.name)]:
        if flag in command:command[command.index(flag)+1]=value
        else:command += [flag,value]
    java,_=java_environment();command[0]=str(java/'bin/java.exe')
    inbox=out/'commands.json';write(inbox,dict(seq=0,commands=[]))
    command[1:1]=['-Xms512m',f'-Xmx{a.max_heap_gib}G','-Dprojectseele.combatBundleDirectory=projectseele-local-maps','-Dprojectseele.r47NativeCommandInbox='+str(inbox)]
    need(not spec.get('environment'),'No inherited review environment required')
    spec.update(command=command,workingDirectory=str(game),environment={},max_heap_gib=a.max_heap_gib,world=str(world),jar_sha256=receipt['sha256'],protocol=receipt['protocol'],build_receipt=str(a.build_receipt.resolve()),no_save_copy=True,save_link_strategy='Parent saves junction; the sole current World is a real child directory',save_link=str(game/'saves'),save_link_target=str(world.parent))
    write(out/'launch.json',spec)
    def quote(value):
        need(not any(c in value for c in '\r\n\0'),'Unsafe JVM argument');return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
    (out/'launch.args').write_text('\n'.join(quote(v) for v in command[1:])+'\n','utf-8')
    print('Current final client prepared:',out/'launch.json','World unchanged')
if __name__=='__main__':main()
