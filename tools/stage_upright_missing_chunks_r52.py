"""Reuse the existing seed-identical native fixture for four measured proto chunks."""
import ast,hashlib,json,msvcrt,shutil
from pathlib import Path
from r52_spatial_plan import BASE
from query_blocks import chunk_statuses
from extend_world_depth_r52 import acquire_world_lock


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    world=BASE/'WORLD_R52';host=BASE/'native_generation/server';fixture=host/'R52_GENERATION_ONLY'
    out=BASE/'native_generation/upright_completion_20261012';assert not out.exists();out.mkdir()
    previous=json.loads((BASE/'native_generation/far_yashima/STAGED.json').read_text('utf8'))
    assert Path(previous['fixture']).resolve()==fixture.resolve()
    assert sha(host/'mods/projectseele-0.1.0-all.jar')==previous['mod_sha256']
    missing=json.loads((BASE/'continuous_upright/civil_measurement/MISSING_CHUNKS.json').read_text('utf8'))
    requested={ast.literal_eval(k) for k in missing};assert len(requested)==4
    targets=chunk_statuses(world,'projectseele:geofront',requested);assert all(s!='full' for s in targets.values())
    regions={(x//32,z//32) for x,z in targets};sources={};lock=acquire_world_lock()
    fixture_lock=(fixture/'session.lock').open('r+b');msvcrt.locking(fixture_lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        for rx,rz in sorted(regions):
            rel=Path(f'dimensions/projectseele/geofront/region/r.{rx}.{rz}.mca')
            src=world/rel;dst=fixture/rel;assert src.is_file() and src.stat().st_size>=8192
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);assert sha(src)==sha(dst)
            sources[rel.as_posix()]=sha(src)
    finally:
        msvcrt.locking(fixture_lock.fileno(),msvcrt.LK_UNLCK,1);fixture_lock.close()
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    result=dict(world_written=False,fixture=str(fixture),host=str(host),source_world=str(world),
        mod_sha256=previous['mod_sha256'],targets=[dict(x=x,z=z,status=s) for (x,z),s in sorted(targets.items())],
        region_source_sha256=sources,source_level_sha256=sha(world/'level.dat'),
        reused_generator='Same already-verified native generator and 1280-height fixture as prior far-ridge completion',
        protected_progress='No original entity/player/MTR/SavedData copied or merged; only exact declared non-FULL target chunks may later merge')
    (out/'STAGED.json').write_text(json.dumps(result,indent=2),'utf8');print('staged',len(targets),'proto chunks in reused fixture',flush=True)


if __name__=='__main__':main()
