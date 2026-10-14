"""Compile standalone reflection-only observers; never attach or launch a game."""
from pathlib import Path
import argparse,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
NAMES=('R52LifecycleReadOnlyAgent','R52LifecycleReadOnlyAttach','R52BundleReadOnlyParserAgent','R52BundleReadOnlyParserAttach')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out.resolve()
    from root_bundle_authority_r53 import candidate
    candidate(out,Path('D:/eva/artifacts/map_complete_20261013/WORLD'))
    out.mkdir(parents=True,exist_ok=True);classes=out/'observer_classes';classes.mkdir(exist_ok=True)
    sources=[ROOT/'tools/java'/(n+'.java') for n in NAMES];before={p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    javac=Path('C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javac.exe')
    with (out/'observer_compile.log').open('wb') as log:
        subprocess.run([str(javac),'-J-Xmx256m','-encoding','UTF-8','-d',str(classes),*[str(p) for p in sources]],check=True,stdout=log,stderr=subprocess.STDOUT)
    assert before=={p.relative_to(ROOT).as_posix():sha(p) for p in sources},'Observer sources changed during compile'
    agents={}
    for name,file in [('R52LifecycleReadOnlyAgent','r52_lifecycle_readonly_agent.jar'),('R52BundleReadOnlyParserAgent','r52_bundle_readonly_parser_agent.jar')]:
        with zipfile.ZipFile(out/file,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\r\nAgent-Class: '+name+'\r\nCan-Redefine-Classes: false\r\nCan-Retransform-Classes: false\r\n\r\n')
            archive.write(classes/(name+'.class'),name+'.class')
        agents[file]=sha(out/file)
    result=dict(compile_passed=True,java_heap_cap_mb=256,source_sha256=before,class_sha256={n+'.class':sha(classes/(n+'.class')) for n in NAMES},agent_sha256=agents['r52_lifecycle_readonly_agent.jar'],parser_agent_sha256=agents['r52_bundle_readonly_parser_agent.jar'],attached_to_game=False,world_written=False)
    (out/'OBSERVER_COMPILE_RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n','utf8');print(json.dumps(result))
if __name__=='__main__':main()
