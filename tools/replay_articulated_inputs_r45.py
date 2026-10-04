"""Replay captured native physics inputs using current compiled classes and exact JBullet libraries."""
from pathlib import Path
import argparse, json, os, subprocess

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path);p.add_argument('--thin-floor',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--omit',default='');p.add_argument('--source-dir',type=Path);a=p.parse_args()
    assert a.thin_floor != bool(a.capture),'Choose one actual replay capture or the frozen thin-floor cases'
    a.out.mkdir(parents=True,exist_ok=False)
    java=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin')
    dependencies=list((ROOT/'artifacts/combat_direction_r36/packaged_physics').glob('*.jar'))
    assert len(dependencies)==3
    cache=Path.home()/'.gradle/caches/modules-2/files-2.1'
    for name in ['com.google.code.gson/gson/2.10.1','org.joml/joml/1.10.5']:
        found=[x for x in (cache/name).rglob('*.jar') if not x.name.endswith('-sources.jar')]
        assert len(found)==1,(name,found)
        dependencies+=found
    cp=os.pathsep.join(map(str,[a.out,ROOT/'build/classes/java/main',*dependencies]))
    if a.source_dir:
        sources=sorted(a.source_dir.glob('*.java'));assert sources
        subprocess.run([str(java/'javac.exe'),'-J-Xmx192m','-cp',cp,'-d',str(a.out),*map(str,sources)],check=True)
    if a.thin_floor:
        subprocess.run([str(java/'javac.exe'),'-J-Xmx192m','-cp',cp,'-d',str(a.out),str(ROOT/'tools/java/PackagedPhysicsR36Smoke.java')],check=True)
        subprocess.run([str(java/'java.exe'),'-Xmx256m','-cp',cp,'PackagedPhysicsR36Smoke',str(ROOT/'artifacts/combat_rebuild_r35/jbullet/articulated_bodies_r35.json'),str(a.out/'result.json')],check=True)
        return
    subprocess.run([str(java/'javac.exe'),'-J-Xmx192m','-cp',cp,'-d',str(a.out),str(ROOT/'tools/java/ReplayArticulatedInputsR45.java')],check=True)
    subprocess.run([str(java/'java.exe'),'-Xmx256m','-cp',cp,'ReplayArticulatedInputsR45',str(a.capture),str(a.out/'frames.json'),a.omit],check=True)
    result=json.loads((a.out/'frames.json').read_text())
    print(json.dumps(dict(steps=result['steps'],max_difference=result['max_capture_difference'],minimum_y_blocks=min(f['min_y_blocks'] for f in result['frames']),first_frames=result['frames'][:8])))

if __name__=='__main__':main()
