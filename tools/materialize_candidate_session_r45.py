"""Root-only auxiliary byte copies for the one named candidate QA session.

Never copies a world, overwrites an existing gameDir, or creates a junction.
The root creates the manifest's one world junction after this readback.
"""
from pathlib import Path
import argparse, hashlib, json, shutil
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--execute-root',action='store_true');a=p.parse_args();guard()
    m=json.loads(a.manifest.read_text('utf8'));assert m['schema']in ('projectseele.shared-candidate-qa-session-r45.v1','projectseele.shared-candidate-qa-session-r45.v2')
    game=Path(m['gameDir']).resolve();assert game in {ROOT/f'artifacts/rebuild_r45/native_candidate_session_v{v}/gameDir' for v in (1,2)}
    copied_world=m['schema'].endswith('.v2')
    assert m['role']=='QA_ONLY_NOT_A_RELEASE_SOURCE'and m['qa_progress_must_not_ship'if copied_world else'no_qa_progress_promotion']
    if game.exists():
        assert copied_world and game==ROOT/'artifacts/rebuild_r45/native_candidate_session_v2/gameDir'
        assert {p.name for p in game.iterdir()}=={'saves'},'Existing auxiliary session is protected'
        assert {p.name for p in(game/'saves').iterdir()}=={'SEELE_FIELD_R45_REVIEW'},'Unexpected save in new copy session'
    allowed={'config','mods','resourcepacks','shaderpacks','projectseele-local-maps','options.txt'}
    files=[]
    for batch in m['staged_gameDir_files']:
        source=Path(batch['source']);target=Path(batch['destination'])
        assert source.parent==ROOT/'run'and source.name in allowed
        assert target==game/source.name
        if 'files'in batch:
            actual={f.relative_to(source).as_posix()for f in source.rglob('*')if f.is_file()}if source.exists()else set()
            assert actual==set(batch['files']),'Auxiliary input set changed: '+source.name
            for relative,digest in batch['files'].items():
                item=Path(relative);assert not item.is_absolute()and '..'not in item.parts
                files.append((source/item,target/item,digest))
        else:files.append((source,target,batch['sha256']))
    for source,_,digest in files:assert sha(source)==digest,'Auxiliary bytes changed: '+str(source)
    world=Path(m['physical_world']).resolve()
    if copied_world:
        assert world==game/'saves/SEELE_FIELD_R45_REVIEW'and not world.is_symlink()
        ref=m['copy_receipt'];receipt_file=Path(ref['path']);assert sha(receipt_file)==ref['sha256']
        receipt=json.loads(receipt_file.read_text('utf8'))
        assert receipt['copy_complete'] and not receipt['source_written'] and receipt['role']=='QA_ONLY'
        assert Path(receipt['target_world']).resolve()==world
        lease_ref=m['city_native_binding'];lease_file=Path(lease_ref['path']);assert sha(lease_file)==lease_ref['sha256']
        lease=json.loads(lease_file.read_text('utf8'));assert lease['schema']=='projectseele.city-atomic-native-binding-r45.v2'
        assert lease['qa_copy']and Path(lease['world']).resolve()==world
        assert lease['world_id']==receipt['world_id']==m['world_uuid']and lease['world_seed']==receipt['world_seed']==m['seed']
        assert lease['copy_receipt']==m['copy_receipt']
    else:assert world.is_relative_to(ROOT/'artifacts/rebuild_r45/composition_candidates')
    expected={r['relative']:r['sha256']for r in (lease['world_files']if copied_world else m['world_files_initial'])}
    actual={f.relative_to(world).as_posix()for f in world.rglob('*')if f.is_file()and f.name!='session.lock'}
    assert actual==set(expected),'Cold candidate file set changed'
    for relative,digest in expected.items():assert sha(world/relative)==digest,'Cold candidate changed: '+relative
    assert a.execute_root,'Pass --execute-root to materialize the verified new auxiliary session'
    game.mkdir(parents=True,exist_ok=copied_world)
    for batch in m['staged_gameDir_files']:
        if 'files'in batch:Path(batch['destination']).mkdir(parents=True,exist_ok=True)
    for source,target,digest in files:
        target.parent.mkdir(parents=True,exist_ok=True);assert not target.exists()
        shutil.copy2(source,target);assert sha(target)==digest
    receipt=dict(schema='projectseele.shared-qa-auxiliary-copy-r45.v1',manifest=str(a.manifest.resolve()),
        manifest_sha256=sha(a.manifest),gameDir=str(game),files=len(files),copied_bytes=sum(s.stat().st_size for s,_,_ in files),
        all_auxiliary_bytes_read_back=True,world_copied=False,world_written=False,junction_created=False,
        role=m['role'],no_qa_progress_promotion=True)
    out=game.parent/'auxiliary_copy_receipt.json';assert not out.exists();out.write_text(json.dumps(receipt,indent=2),'utf8')
    print(json.dumps(receipt))


if __name__=='__main__':main()
