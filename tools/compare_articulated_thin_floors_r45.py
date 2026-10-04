"""Matched old/new angular solver regression on the unchanged captured R36 fixtures."""
from pathlib import Path
import json, os, subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r45/motion/physics_replay_v162/thin_floor_matched_comparison'

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    java=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
    jars=list((ROOT/'artifacts/combat_direction_r36/packaged_physics').glob('*.jar'))
    cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
    for name in ['com.google.code.gson/gson/2.10.1','org.joml/joml/1.10.5']:
        found=[p for p in (cache/name).rglob('*.jar') if not p.name.endswith('-sources.jar')];assert len(found)==1;jars+=found
    for name in ['before_ellipse_ratio','candidate_angular_error']:
        target=OUT/name;target.mkdir();sources=target/'sources';sources.mkdir()
        for f in ['ArticulatedBody.java','ArticulatedInputTraceR45.java','AngularConeConstraintR45.java']:
            text=(ROOT/'src/main/java/com/projectseele/physics'/f).read_text()
            if name=='before_ellipse_ratio' and f=='ArticulatedBody.java':text=text.replace('new AngularConeConstraintR45(','new ConeTwistConstraint(')
            (sources/f).write_text(text)
        cp=os.pathsep.join(map(str,[target,*jars]));files=[*sources.glob('*.java'),ROOT/'tools/java/PackagedPhysicsR36Smoke.java']
        subprocess.run([str(java/'javac.exe'),'-J-Xmx192m','-cp',cp,'-d',str(target),*map(str,files)],check=True)
        command=[str(java/'java.exe'),'-Xmx192m','-cp',cp,'PackagedPhysicsR36Smoke',str(ROOT/'artifacts/combat_rebuild_r35/jbullet/articulated_bodies_r35.json'),str(target/'result.json')]
        with (target/'run.log').open('w') as log:r=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report=json.loads((target/'result.json').read_text());print(name,r.returncode,[(x['rig'],x['minimum_y_blocks']) for x in report['cases']])

if __name__=='__main__':main()
