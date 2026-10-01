"""Remove only the two proven leaked R44 diagnostic actors, preserving the region."""
from pathlib import Path
import argparse, copy, hashlib, json, msvcrt, shutil, time, uuid
import nbtlib
from transplant_s22_authority import read_region, parse_chunk, build_region, chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace
from validate_ecology_plans_r44 import nbt_equal
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
PLAN=ROOT/'artifacts/rebuild_r44/central_towers/exact_probe_cleanup_v1/plan.json'
IDS={'b56ee386-294f-422b-aa50-9effe506e7ca','e2a0fb83-51a0-44c8-998b-0b3f19df98dc'}
TAG='r44_city_quality/4dee5b9d-ef54-4d89-9b16-f2556ca54867'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(entity):
    return str(uuid.UUID(int=sum((int(v)&0xffffffff)<<(32*(3-i)) for i,v in enumerate(entity['UUID']))))


def main(apply=False):
    guard();plan=json.loads(PLAN.read_text('utf8'))
    assert Path(plan['world']).resolve()==WORLD.resolve()
    region=Path(plan['region']);assert region.resolve().is_relative_to(WORLD.resolve())
    assert sha(region)==plan['region_sha256']
    before_path=Path(plan['before_complete_chunk']);after_path=Path(plan['after_complete_chunk'])
    assert sha(before_path)==plan['before_complete_chunk_sha256'] and sha(after_path)==plan['after_complete_chunk_sha256']
    before=nbtlib.load(before_path);after=nbtlib.load(after_path)
    assert {identity(e) for e in before['Entities']}==IDS and len(after['Entities'])==0
    assert all(str(e['id'])=='minecraft:armor_stand' and TAG in e.get('Tags',[]) for e in before['Entities'])
    expected=copy.deepcopy(before);expected['Entities']=copy.deepcopy(after['Entities'])
    assert nbt_equal(expected,after),'Cleanup changed fields outside the two actor records'
    cx,cz=plan['chunk'];slot=(cx&31)+(cz&31)*32
    stamps,blobs=read_region(region);assert nbt_equal(parse_chunk(blobs[slot]),before)
    if not apply:print('Exact probe cleanup preflight passed; world unchanged');return
    out=PLAN.parent/('applied_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir()
    lock=(WORLD/'session.lock').open('r+b');msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    try:
        assert sha(region)==plan['region_sha256']
        shutil.copy2(region,out/'before_region.mca')
        changed=list(blobs);changed[slot]=chunk_blob(after)
        atomic_replace(region,build_region(stamps,changed))
        actual_stamps,actual_blobs=read_region(region)
        assert actual_stamps==stamps
        assert all(actual_blobs[k]==v for k,v in enumerate(blobs) if k!=slot)
        assert nbt_equal(parse_chunk(actual_blobs[slot]),after)
        receipt=dict(removed_exact_uuids=sorted(IDS),removed_count=2,other_region_records_byte_identical=True,
            original_project_actors_changed=False,region=str(region),before_sha256=plan['region_sha256'],after_sha256=sha(region),
            inverse_complete_region=str(out/'before_region.mca'),inverse_chunk=str(before_path),verified=True,
            delivery_progress_policy='QA-only repair; never copy test entities or mission progress into release')
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2),'utf8')
        print('Exact two test actors removed with full inverse and readback:',out,flush=True)
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
