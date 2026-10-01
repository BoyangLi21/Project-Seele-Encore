"""Exact pre-fix renderer versus current renderer, with actual Oculus first-person screenshots."""
from pathlib import Path
import argparse,copy,hashlib,json,shutil,subprocess,sys,time
import nbtlib
from release_combat_r36 import guard
from freeze_native_r44 import freeze

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44'
WORLD=ROOT/'run/saves/SEELE_R44_SHADOW_REVIEW'


def world():
    if WORLD.exists():return
    WORLD.mkdir(parents=True)
    source=nbtlib.load(ROOT/'run/saves/SEELE_R44_NETWORK_REVIEW/level.dat')
    source['Data']['LevelName']=nbtlib.String('R44 static first-person shadow TEST')
    source['Data'].pop('Player',None)
    source['Data']['GameRules']['doDaylightCycle']=nbtlib.String('false')
    source['Data']['GameRules']['doMobSpawning']=nbtlib.String('false')
    overworld=source['Data']['WorldGenSettings']['dimensions']['minecraft:overworld']
    overworld['generator']=nbtlib.Compound(type=nbtlib.String('minecraft:flat'),settings=nbtlib.Compound(
        biome=nbtlib.String('minecraft:plains'),features=nbtlib.Byte(0),lakes=nbtlib.Byte(0),
        layers=nbtlib.List[nbtlib.Compound]([nbtlib.Compound(block=nbtlib.String(block),height=nbtlib.Int(height))
            for block,height in [('minecraft:bedrock',1),('minecraft:dirt',2),('minecraft:grass_block',1)]]),
        structure_overrides=nbtlib.List[nbtlib.String]()))
    source.save(WORLD/'level.dat');(WORLD/'session.lock').write_bytes(bytes([0xe2,0x98,0x83]))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--before',action='store_true');args=ap.parse_args();guard();world()
    out=ART/'shadows'/('before' if args.before else 'after')/time.strftime('%Y%m%d_%H%M%S');out.mkdir(parents=True)
    spec=json.loads((ROOT/'.Codex/client-r42-interiors-photos.json').read_text('utf8'))
    command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.r44ShadowReview=true']+(['-Dprojectseele.r44ShadowBefore=true'] if args.before else [])
    command[command.index('--quickPlaySingleplayer')+1]=WORLD.name;spec['command']=command
    if args.before:
        classes=out/'renderer_comparison_classes';shutil.copytree(ROOT/'build/classes/java/main',classes)
        old=ART/'shadows/before_renderer/EvaUnit01Renderer.class'
        target=classes/'com/projectseele/client/render'/old.name;shutil.copy2(old,target)
        entries=spec['environment']['MOD_CLASSES'].split(';')
        entries=[('projectseele%%'+str(classes)) if s.startswith('projectseele%%') and Path(s.split('%%',1)[1]).resolve()==(ROOT/'build/classes/java/main').resolve() else s for s in entries]
        spec['environment']['MOD_CLASSES']=';'.join(entries)
    spec=freeze(spec,out);launch=out/'launch.json';launch.write_text(json.dumps(spec),'utf8')
    cfg=ROOT/'run/config/oculus.properties';previous=cfg.read_bytes();options=ROOT/'run/options.txt';old_options=options.read_bytes();began=time.time()
    cfg.write_text(previous.decode('utf8').replace('enableShaders=false','enableShaders=true'),'utf8')
    try:
        with (out/'native.log').open('w',encoding='utf8') as log:
            process=subprocess.run([sys.executable,'-X','utf8','tools/launch_rendered_client_r17.py','--prepared-file',str(launch)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=900)
        marker=WORLD/'r44_shadow_review.json';assert process.returncode==0 and marker.stat().st_mtime>=began
        result=json.loads(marker.read_text());shutil.copy2(marker,out/'result.json');assert not result['error'],result['error']
        assert len(result['cases'])==5
        frames=[]
        for rig in range(5):
            name=f'r44_shadow_{"before" if args.before else "after"}_{rig}.png';image=ROOT/'run/screenshots'/name
            assert image.stat().st_mtime>=began;shutil.copy2(image,out/name)
            frames.append(dict(rig=rig,file=str(out/name),sha256=hashlib.sha256(image.read_bytes()).hexdigest()))
        (out/'frames.json').write_text(json.dumps(frames,indent=2),'utf8')
        (out/'scope.json').write_text(json.dumps(dict(before_renderer=args.before,standing_only=True,real_first_person=True,
            actual_shader='Oculus 1.8.0 with configured Complementary shader',caster_admission='Instrumented current renderer only; pre-fix exact class is not instrumented',
            actual_pixel_review=False,motion_quality_test=False,world=str(WORLD)),indent=2),'utf8')
        print('Actual first-person shadow pictures:',len(frames),out,flush=True)
        if not args.before:assert all(r['caster_admission_pass'] for r in result['cases'])
    finally:cfg.write_bytes(previous);options.write_bytes(old_options)


if __name__=='__main__':main()
