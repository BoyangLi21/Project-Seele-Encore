"""Prepare/run the isolated Forge combat API fixture; parent owns Java/GPU queue."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,threading,time
from freeze_native_r44 import freeze
from launch_rendered_client_r17 import java_environment

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44/combat/native_query_qa'
WORLD='SEELE_R44_COMBAT_QUERY_QA'
SPATIAL=['head','chest','feet','gap','crouch_chest','prone_head','wall','nearest_giant']
PATHS=['jab','cross','heavy','knife_forward','knife_reverse','kick','eva_rifle','eva_cannon','un_eye','player_rifle',
       'shamshel_whip','ramiel_beam','ramiel_drill','zeruel_paper','zeruel_eye','strategic_blast','native_explosion']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,default=ROOT/'artifacts/rebuild_r44/combat/locomotion_warp/motion')
    ap.add_argument('--run',action='store_true');ap.add_argument('--timeout',type=int,default=480);args=ap.parse_args()
    if subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()!='main':raise RuntimeError('Canonical source main is required')
    required=['visual/CombatQueryNativeR44.class','physics/CombatEntityQueryR44.class','mixin/GiantExplosionQueryMixinR44.class']
    absent=[name for name in required if not (ROOT/'build/classes/java/main/com/projectseele'/name).is_file()]
    if absent:raise RuntimeError('Compile latest combat native QA first: '+', '.join(absent))
    output=ART/time.strftime('%Y%m%d_%H%M%S');output.mkdir(parents=True);server=ROOT/'.Codex/r44-combat-query-server'
    prior=ROOT/'.Codex/r44-network-server';baseline=json.loads((ROOT/'artifacts/rebuild_r44/baseline.json').read_text());instance=Path(baseline['instance'])
    server.mkdir(parents=True,exist_ok=True)
    for kind in ('mods','config'):
        if not (server/kind).exists():shutil.copytree(prior/kind,server/kind)
    if not (server/'projectseele-local-maps').exists():shutil.copytree(instance/'projectseele-local-maps',server/'projectseele-local-maps')
    shutil.copy2(prior/'eula.txt',server/'eula.txt')
    (server/'server.properties').write_text('server-ip=127.0.0.1\nserver-port=25644\nlevel-name='+WORLD+'\nonline-mode=false\nlevel-type=minecraft:flat\ngenerate-structures=false\nview-distance=4\nsimulation-distance=4\nspawn-protection=0\nmax-tick-time=120000\n','utf8')
    spec=json.loads((ROOT/'artifacts/rebuild_r44/network_runtime/before/server_launch.json').read_text());command=[s for s in spec['command'] if not s.startswith('-Dprojectseele.')]
    command[1:1]=['-Dprojectseele.r44CombatQueryReview=true','-Dprojectseele.combatBundleDirectory='+args.bundle.resolve().as_posix()]
    universe=output/'worlds';universe.mkdir();command[command.index('--universe')+1]=str(universe);command[command.index('--world')+1]=WORLD
    spec['command']=command;spec['workingDirectory']=str(server)
    spec['environment']['MOD_CLASSES']='projectseele%%'+str(ROOT/'artifacts/rebuild_r44/network_runtime/private_resources')+';projectseele%%'+str(ROOT/'build/classes/java/main')
    spec=freeze(spec,output);(output/'launch.json').write_text(json.dumps(spec),'utf8')
    plan=dict(world=WORLD,loopback_only=True,tag='seele_r44_query_fixture',spatial_denominator=5*len(SPATIAL),damage_API_denominator=len(PATHS),
              server_handshake_negative_denominator=9,total_planned=5*len(SPATIAL)+len(PATHS)+9,
              spatial=[f'rig_{rig}_{name}' for rig in range(5) for name in SPATIAL],damage_APIs=PATHS,
              modes=dict(spatial='Production native pose/ray/block query',damage='Production method/API with seeded phase; input/cooldown/animation timing excluded',
                         handshake='Production server handler and native connected EmbeddedChannel, not a separate client screenshot'),
              not_in_denominator=['Actual five-rig player input animation performance','Client UI nine rejection screens','Source=null/TNT explosions','User artistic approval'])
    (output/'denominator.json').write_text(json.dumps(plan,indent=2),'utf8')
    print('Prepared isolated native combat API fixture:',output,flush=True)
    if not args.run:return
    marker=universe/WORLD/'r44_combat_query.json'
    if marker.exists():raise RuntimeError('Existing QA result is frozen; archive it explicitly before rerunning this world')
    def quote(s):return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'
    argument=output/'launch.args';argument.write_text('\n'.join(quote(s) for s in spec['command'][1:]),'utf8');env=java_environment()[1];env.update(spec['environment'])
    with (output/'server.log').open('w',encoding='utf8') as log:
        process=subprocess.Popen([spec['command'][0],'@'+str(argument.resolve())],cwd=server,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW)
        def read():
            for line in process.stdout:log.write(line);log.flush()
        worker=threading.Thread(target=read,daemon=True);worker.start();start=time.monotonic()
        try:
            while not marker.exists():
                if process.poll() is not None:raise RuntimeError('Forge exited without native result: '+str(output))
                if time.monotonic()-start>args.timeout:raise TimeoutError('Native query QA deadline; preserve first error/log')
                time.sleep(1)
            result=json.loads(marker.read_text());shutil.copy2(marker,output/'result.json')
            actual={row['case'] for row in result['cases']};wanted=set(plan['spatial']+PATHS+['mismatch_'+key for key in ('body','eva-profile-0','eva-profile-1','eva-profile-2','eva-profile-3','eva-profile-4','sachiel-profile','first-battle','physical-body-profiles')])
            contract=dict(missing=sorted(wanted-actual),unexpected=sorted(actual-wanted),duplicate_cases=len(actual)!=len(result['cases']))
            (output/'denominator_readback.json').write_text(json.dumps(contract,indent=2),'utf8')
            if contract['missing'] or contract['unexpected'] or contract['duplicate_cases']:result['passed']=False
            print(json.dumps(dict(native_pass=result['passed'],total=result['total'],passed_cases=result['passed_cases'],denominator=contract)),flush=True)
        finally:
            if process.poll() is None:
                process.stdin.write('stop\n');process.stdin.flush()
                try:process.wait(timeout=60)
                except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=15)
            worker.join(timeout=5)
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
