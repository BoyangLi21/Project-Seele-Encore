"""Run one explicitly scoped production replay of a road or station candidate.

Holds the cold-world lock itself. Road candidates carry their scope from
prepare; station candidates name the world with --world.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

from install_r53_carrier_trays import stopped_world
from map_pipeline.delivery_check import read


def groovy_path(path):
    value=str(Path(path).resolve()).replace('\\','/')
    if '\n'in value or '\r'in value:raise ValueError('Invalid path')
    return "'"+value.replace("'","\\'")+"'"


def run(a):
    control=a.candidate/'corridor-release-check.json'
    scope=read(control)['replay_scope'] if control.exists() else dict(candidate=str(a.candidate),world=str(a.world),
        expected=str(a.candidate/'recipe-replay-expected'))
    if Path(scope['candidate']).resolve()!=a.candidate.resolve():raise ValueError('Candidate replay identity differs')
    if Path(scope['expected']).resolve()!=(a.candidate/'recipe-replay-expected').resolve():raise ValueError('Replay expected directory differs')
    if a.log.exists():raise ValueError('Use a fresh production log')
    world=Path(scope['world']);work=a.repository/'.Codex'/('station-road-replay-'+a.candidate.name)
    work.mkdir(parents=True,exist_ok=True);init=work/'replay.init.gradle'
    text="""allprojects {
    afterEvaluate {
        tasks.register('verifyStationRoadReplay', JavaExec) {
            dependsOn testClasses
            classpath = files(TERRAIN) + sourceSets.test.runtimeClasspath
            mainClass = 'com.projectseele.world.SurfaceRepairReplayTest'
            args CANDIDATE, WORLD
            maxHeapSize = '512m'
            workingDir = file(WORK)
        }
    }
}
"""
    for key,path in [('TERRAIN',a.terrain/'terrain-delivery.jar'),('CANDIDATE',a.candidate),('WORLD',world),('WORK',work)]:
        text=text.replace(key,groovy_path(path))
    init.write_text(text,'utf8')
    env=os.environ.copy();env['JAVA_HOME']=str(a.java);env['PATH']=str(a.java/'bin')+os.pathsep+env['PATH']
    with stopped_world(world):
        with a.log.open('x',encoding='utf8')as output:
            output.write('CORRIDOR_PATCH_REPLAY_SCOPE '+json.dumps(scope,ensure_ascii=False,separators=(',',':'))+'\n');output.flush()
            result=subprocess.run([str(a.repository/'gradlew.bat'),'--offline','--no-daemon','--console=plain',
                '-I',str(init),'verifyStationRoadReplay'],cwd=a.repository,env=env,stdout=output,stderr=subprocess.STDOUT)
    for line in a.log.read_text('utf8',errors='replace').splitlines():
        if any(s in line for s in ('Production surface replay:','BUILD SUCCESSFUL','FAILED')):print(line[:400])
    raise SystemExit(result.returncode)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for key in ('candidate','repository','terrain','java','log'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--world',type=Path)
    run(p.parse_args())
