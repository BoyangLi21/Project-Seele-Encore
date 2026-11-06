"""Compile isolated observer and prepare exact candidate6/copied-save QA. Never starts a game."""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
W=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52').resolve()
JDK=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
ASM=Path('C:/Users/liboy/AppData/Roaming/.minecraft/libraries/org/ow2/asm/asm/9.8/asm-9.8.jar')
CLASSES=['com.projectseele.world.SurfaceAngelAssaultR52','com.projectseele.world.NervArmorColumnR50',
         'com.projectseele.entity.SachielEntity','com.projectseele.entity.SachielArmorBeamR52',
         'com.projectseele.entity.SachielBodyPoseR35','com.projectseele.entity.ShamshelEntity',
         'com.projectseele.entity.ShamshelWhipMotion','com.projectseele.physics.ShamshelContactPoseR48',
         'com.projectseele.client.fx.SachielArmorChargeR52','com.projectseele.client.render.RiggedAngelLayer']
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def quote(s):
    assert not any(c in s for c in '\r\n\0')
    return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
def compile_tools(out):
    classes=out/'tool_classes';classes.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tools/java/SurfaceArmorNativeR52Agent.java',ROOT/'tools/java/SurfaceArmorNativeR52Attach.java']
    subprocess.run([str(JDK/'javac.exe'),'-encoding','UTF-8','-cp',str(ASM),'-d',str(classes),*map(str,sources)],check=True)
    jar=out/'surface_armor_observer.jar'
    with zipfile.ZipFile(jar,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nAgent-Class: SurfaceArmorNativeR52Agent\nCan-Retransform-Classes: true\n\n')
        for p in classes.glob('SurfaceArmorNativeR52Agent*.class'):z.write(p,p.name)
    receipt=dict(tool_sources={str(p.relative_to(ROOT)):sha(p) for p in sources},tool_agent_sha256=sha(jar),
                 game_started=False,production_build_invoked=False,world_written=False)
    (out/'TOOL_COMPILE_RECEIPT.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))
def prepare(args,out):
    world=args.world.resolve();assert world.is_dir() and (world/'level.dat').is_file()
    assert world!=W and not world.is_relative_to(W) and not W.is_relative_to(world)
    assert world.name.startswith('R52_SURFACE_QA_'), 'Explicit test clone name required'
    for filename in ('surface_angel_assault_r52.json','nerv_armor_column_r50.json'):
        p=world/filename;assert p.is_file(),f'Root final installation missing: {filename}'
        assert json.loads(p.read_text('utf-8-sig'))['installed'],f'Uninstalled design refused: {filename}'
    spec=json.loads(args.launch_template.read_text('utf-8-sig'));jar=Path(spec['staged_jar']['path']).resolve()
    assert sha(jar)==spec['staged_jar']['sha256'],'Exact Root staged candidate receipt required'
    assert args.candidate_jar.resolve()==jar,'Template must already be Root candidate6; no silent old-launch swap'
    with zipfile.ZipFile(jar) as z:
        hashes={n:hashlib.sha256(z.read(n.replace('.','/')+'.class')).hexdigest() for n in CLASSES}
    marker=dict(schema=52,test_only=True,candidate='candidate6',chapter=args.chapter,source_world=str(W),
                jar_sha256=sha(jar),class_sha256=hashes)
    marker_path=world/'R52_SURFACE_QA_COPY.json';assert not marker_path.exists(),'Preserve earlier attempted clone evidence'
    marker_path.write_text(json.dumps(marker,indent=2),'utf8')
    properties=dict(regionalBuild='surface-armor-r52',surfaceArmorCandidateR52='candidate6',surfaceArmorWorldR52=str(world),
                    surfaceArmorChapterR52=args.chapter,surfaceArmorJarSHA256R52=sha(jar),surfaceArmorOutputR52=str(out))
    command=[v for v in spec['command'] if not v.startswith('-Dprojectseele.') or not any(v.startswith('-Dprojectseele.'+k+'=') for k in ('regionalBuild','firstBattleReview','ordinaryMotionWorldR52','ordinaryMotionOutputR52'))]
    command[1:1]=['-XX:+EnableDynamicAgentLoading',*['-Dprojectseele.'+k+'='+v for k,v in properties.items()]]
    # The Root template must already target this copied save. The observer
    # never rewrites save selection, repairs HP or relocates original actors.
    assert str(world) in json.dumps(spec,ensure_ascii=False),'Root copied-save launch template required'
    spec.update(command=command,properties=properties,world=str(world),surface_armor_only=True,game_started=False)
    (out/'launch.json').write_text(json.dumps(spec,indent=2),'utf8')
    (out/'launch.args').write_text('\n'.join(quote(v) for v in command[1:])+'\n','utf8')
    (out/'PREPARED.json').write_text(json.dumps(dict(staged_jar=spec['staged_jar'],world=str(world),chapter=args.chapter,
        construction_world_written=False,game_started=False,observer_new_angels=0,production_entry='TvCampaignDirector.select/beginAssigned',
        true_route_uuid_continuity=True,real_top_plate_contacts=True,actual_client_weighted_palette_and_frames=True),indent=2),'utf8')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'.Codex/r52_surface_armor_native');p.add_argument('--compile-tools',action='store_true');p.add_argument('--prepare',action='store_true');p.add_argument('--world',type=Path);p.add_argument('--chapter',choices=['sachiel','shamshel']);p.add_argument('--launch-template',type=Path);p.add_argument('--candidate-jar',type=Path);a=p.parse_args();out=a.out.resolve();assert out.is_relative_to(ROOT/'.Codex') or out.is_relative_to(ROOT/'artifacts');out.mkdir(parents=True,exist_ok=True)
    if a.compile_tools:compile_tools(out)
    if a.prepare:
        assert all((a.world,a.chapter,a.launch_template,a.candidate_jar));prepare(a,out)
