"""Compile/package reflection-only native observer; no game or attachment."""
from pathlib import Path
import argparse, hashlib, json, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[1]
NAMES=('NamedPersonnelReadOnlyAgentR53','NamedPersonnelReadOnlyAttachR53')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def package(out):
    classes=out/'observer_classes'
    agent=out/'named_personnel_readonly_agent_r53.jar'
    with zipfile.ZipFile(agent,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nAgent-Class: NamedPersonnelReadOnlyAgentR53\r\nCan-Redefine-Classes: false\r\nCan-Retransform-Classes: false\r\n\r\n')
        for p in sorted(classes.glob('NamedPersonnelReadOnlyAgentR53*.class')): z.write(p,p.name)
    inputs=[ROOT/'tools/java'/(n+'.java')for n in NAMES]
    result=dict(compile_passed=True,java_heap_cap_mb=128,agent=str(agent),agent_sha256=sha(agent),source_sha256={str(p.relative_to(ROOT)):sha(p)for p in inputs},class_sha256={n+'.class':sha(classes/(n+'.class'))for n in NAMES},attached_to_game=False,game_started=False,world_written=False,native_verified=False,actual_traversal_verified=False)
    for filename in ('NATIVE_SAMPLING_PLAN.json','STATION_TO_MAIN_ORDINARY_WALK.json'):
        if(out/filename).exists(): result[filename+'_sha256']=sha(out/filename)
    (out/'PROBE_COMPILE_RECEIPT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--package-existing',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);classes=out/'observer_classes';classes.mkdir(exist_ok=True)
    if not a.package_existing:
        subprocess.run(['C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javac.exe','-J-Xmx128m','--release','17','-encoding','UTF-8','-d',str(classes),*[str(ROOT/'tools/java'/(n+'.java'))for n in NAMES]],check=True)
    print(json.dumps(package(out),ensure_ascii=False))
if __name__=='__main__':main()
