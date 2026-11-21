"""Create the sole R52 construction source from the actual delivered R51 world."""
from pathlib import Path
import hashlib,json,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009')
ARCHIVE=Path('D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip')
WORLD=BASE/'WORLD_R52'

def main():
    assert not BASE.exists(), 'Do not overwrite or reset an existing construction source'
    prefix='SEELE_R50_WORLD/';files=[]
    with zipfile.ZipFile(ARCHIVE) as archive:
        entries=[entry for entry in archive.infolist() if entry.filename.startswith(prefix) and not entry.is_dir()]
        assert len(entries)==3066 and len({e.filename for e in entries})==3066
        BASE.mkdir();WORLD.mkdir()
        for entry in entries:
            relative=entry.filename[len(prefix):];target=WORLD/relative
            assert target.resolve().is_relative_to(WORLD.resolve())
            raw=archive.read(entry);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            files.append(dict(path=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    report=dict(release='R52',source_commit='6f2d35c',source_archive=str(ARCHIVE),source_prefix=prefix,
        world=str(WORLD),code_root=str(ROOT),files=files,original_world_files=3066,
        rejected_geometry_or_QA_imported=False,world_copy_only=True,map_edits=0,design_and_write_owner='root')
    (BASE/'BASELINE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(world=str(WORLD),original_files=len(files),bytes=sum(r['bytes'] for r in files),map_edits=0)))

if __name__=='__main__':main()
