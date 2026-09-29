"""Make one native MTR staging copy and inspect it without touching live data."""
import json,msvcrt,shutil,subprocess
from pathlib import Path
from regional_voxels import ROOT,WORLD
from stage_native_transit_repair import hashes

def main(world=WORLD,out=None,stage=None,classes=None):
    world=Path(world);out=Path(out) if out else ROOT/'artifacts/world_rebuild_r20/transit'
    out.mkdir(parents=True,exist_ok=True);stage=Path(stage) if stage else ROOT/'.Codex/r20-transit-source'
    if not stage.exists():
        with (world/'session.lock').open('r+b') as f:
            msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);h=hashes(world/'mtr');shutil.copytree(world/'mtr',stage);assert h==hashes(stage)==hashes(world/'mtr')
        (out/'source_hashes.json').write_text(json.dumps(h,indent=2))
    java=Path.home()/'jdks/jdk-17.0.19+10/bin';classes=Path(classes) if classes else ROOT/'.Codex/r20-java';classes.mkdir(parents=True,exist_ok=True)
    libs=Path.home()/'.gradle/caches/modules-2/files-2.1/org.apache.logging.log4j';cp=';'.join(map(str,[ROOT/'.Codex/local-mods/MTR-forge-4.0.5+1.20.1.jar']+sorted(libs.glob('*/2.19.0/*/*.jar'))))
    subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(classes),str(ROOT/'tools/java/TransitSnapshotR20.java')],check=True)
    subprocess.run([str(java/'java.exe'),'-cp',cp+';'+str(classes),'TransitSnapshotR20',str(stage),str(out/'native_snapshot.json')],check=True)
    (out/'runtime.json').write_text(json.dumps({'java':str(java),'classes':str(classes),'classpath':cp,'stage':str(stage)},indent=2))

if __name__=='__main__':main()
