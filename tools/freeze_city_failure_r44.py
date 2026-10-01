"""Preserve a first native city failure, all cargo baselines and exact controller data."""
from pathlib import Path
import argparse,hashlib,json,shutil
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('native_log',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    assert not args.output.exists(),'Keep the original failure evidence immutable'
    args.output.mkdir(parents=True)
    job=json.loads(args.input.read_text('utf8'));snapshots=Path(job['snapshot_dir']);metadata=[]
    def copy(source,target):
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        metadata.append(dict(source=str(source),frozen=str(target),bytes=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    for path in (args.input,Path(str(args.input)+'.failed.json'),args.native_log):copy(path,args.output/path.name)
    paths=sorted(snapshots.glob('tower_*.nbt'));assert len(paths)==93
    for path in paths:
        data=nbtlib.load(path);assert str(data['WorldID'])==job['world_id']
        copy(path,args.output/'cargo_before'/path.name)
    copy(snapshots/'world_identity.json',args.output/'cargo_before/world_identity.json')
    data_dir=WORLD/'dimensions/projectseele/geofront/data'
    saved={}
    for name in ('projectseele_tokyo3_building_world_id_r44.dat','projectseele_tokyo3_retraction.dat','projectseele_battlefield_r21.dat'):
        path=data_dir/name
        if path.exists():copy(path,args.output/'controller_data'/name);saved[name]=nbtlib.load(path).snbt()
    report=dict(world_id=job['world_id'],world=str(WORLD),preserved_snapshot_files=len(paths),files=metadata,actual_controller_snbt=saved,
        frozen_world_files_written=False,actual_world_written=False,
        interpretation='All 93 original full-NBT cargo snapshots, the first failed input/output/log, identity and current controller data are preserved. Current SavedData can postdate the first failed tick; its timestamp/hash distinguishes it from the fixture marker.')
    (args.output/'evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Frozen',len(metadata),'files /',len(paths),'cargo snapshots; world_id',job['world_id'],flush=True)


if __name__=='__main__':main()
