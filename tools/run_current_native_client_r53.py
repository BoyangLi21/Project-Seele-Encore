"""Run the prepared normal client against the sole current World; stop via its inbox."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from launch_rendered_client_r17 import java_environment
from build_immutable_r52_candidate import frozen_build_class_pins
from run_r52_minimal_install_restart import check_world_unlocked

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--launch',type=Path,required=True);a=ap.parse_args()
    spec=json.loads(a.launch.read_text('utf-8-sig'));out=a.launch.resolve().parent;world=Path(spec['world']).resolve();game=Path(spec['workingDirectory']).resolve()
    assert world==Path('D:/eva/artifacts/map_complete_20261013/WORLD').resolve() and (game/'saves/WORLD').resolve()==world
    assert not (out/'RUNNING.json').exists(),'Preserve every native attempt'
    build=Path(spec['build_receipt']);jar=game/'mods/projectseele-0.1.0-all.jar'
    frozen_build_class_pins(build,Path(json.loads(build.read_text('utf-8-sig'))['jar']))
    assert sha(jar)==spec['jar_sha256'];check_world_unlocked(world)
    _,env=java_environment();env.pop('MOD_CLASSES',None)
    assert not any('-Dprojectseele.' in env.get(k,'') for k in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS'))
    log=(out/'process.log').open('xb')
    process=subprocess.Popen([spec['command'][0],'@'+str(out/'launch.args')],cwd=game,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    record=dict(pid=process.pid,world=str(world),jar_sha256=spec['jar_sha256'],started_utc_ms=int(time.time()*1000),world_copies=0,actual_functional_acceptance=False)
    (out/'RUNNING.json').write_text(json.dumps(record,indent=2)+'\n','utf-8');print('Actual current client PID',process.pid,flush=True)
    result=process.wait();log.close();record.update(exit_code=result,natural_exit=result==0)
    (out/'RESULT.json').write_text(json.dumps(record,indent=2)+'\n','utf-8');print('Current client exited',result,flush=True)
    assert result==0
if __name__=='__main__':main()
