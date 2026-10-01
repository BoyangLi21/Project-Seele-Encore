"""Freeze exact two diagnosed fixture UUID removals; never modify a world."""
from pathlib import Path
from copy import deepcopy
from io import BytesIO
import argparse, hashlib, json, uuid
import nbtlib
from inspect_map_assets import region_chunks

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
EXPECTED={
    'b56ee386-294f-422b-aa50-9effe506e7ca':[-129.5,23.0,180.5],
    'e2a0fb83-51a0-44c8-998b-0b3f19df98dc':[-129.5,-54.0,180.5],
}
TAG='r44_city_quality/4dee5b9d-ef54-4d89-9b16-f2556ca54867'

def entity_uuid(tag):
    value=tag['UUID'];packed=b''.join((int(n)&0xffffffff).to_bytes(4,'big') for n in value)
    return str(uuid.UUID(bytes=packed))

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--live-report',type=Path,required=True);args=p.parse_args()
    assert not args.output.exists(),'Preserve earlier evidence; choose a new cleanup attempt'
    live=json.loads(args.live_report.read_text('utf8'));assert Path(live['world']).resolve()==WORLD.resolve()
    blockers={r['uuid']:r for envelope in live['production_envelopes'] for r in envelope['blockers']}
    assert set(blockers)==set(EXPECTED), 'Only the diagnosed exact probe pair can be retired'
    assert all(r['quality_probe'] and not r['original_actor'] and TAG in r['tags'] for r in blockers.values())
    source=WORLD/'dimensions/projectseele/geofront/entities/r.-1.0.mca'
    chunks=list(region_chunks(source,(-9,-9,11,11),{(-9,11)}));assert len(chunks)==1
    cx,cz,before=chunks[0];assert [cx,cz]==[-9,11]
    originals=list(before['Entities']);found={entity_uuid(e):e for e in originals if entity_uuid(e) in EXPECTED}
    assert set(found)==set(EXPECTED),'Saved exact UUID pair differs from live diagnosis'
    for uid,tag in found.items():
        assert str(tag['id'])=='minecraft:armor_stand' and TAG in map(str,tag.get('Tags',[]))
        assert list(map(float,tag['Pos']))==EXPECTED[uid] and not tag.get('Passengers')
    after=deepcopy(before);after['Entities']=nbtlib.List[nbtlib.Compound]([deepcopy(e) for e in originals if entity_uuid(e) not in EXPECTED])
    assert len(originals)-len(after['Entities'])==2
    preserved_before={entity_uuid(e):e.snbt() for e in originals if entity_uuid(e) not in EXPECTED}
    preserved_after={entity_uuid(e):e.snbt() for e in after['Entities']}
    assert preserved_before==preserved_after
    args.output.mkdir(parents=True)
    for name,value in [('before_chunk',before),('after_chunk',after)]:
        nbtlib.File(value).save(args.output/(name+'.nbt'),gzipped=False)
    rows=[]
    for uid,tag in found.items():
        file=args.output/(uid+'.nbt');nbtlib.File(tag).save(file,gzipped=False)
        rows.append(dict(uuid=uid,before_full_nbt=tag.snbt(),after_full_nbt=None,before_binary_nbt=str(file.resolve()),sha256=digest(file),reason='Exact original fixture probe diagnosed alive after prior teardown; never a project actor'))
    plan=dict(world=str(WORLD),dimension='projectseele:geofront',live_report=str(args.live_report.resolve()),live_report_sha256=digest(args.live_report),
        region=str(source),region_sha256=digest(source),chunk=[cx,cz],before_complete_chunk=str((args.output/'before_chunk.nbt').resolve()),
        after_complete_chunk=str((args.output/'after_chunk.nbt').resolve()),before_complete_chunk_sha256=digest(args.output/'before_chunk.nbt'),
        after_complete_chunk_sha256=digest(args.output/'after_chunk.nbt'),entities_before=len(originals),entities_after=len(after['Entities']),
        exactly_removed=rows,all_other_entities_full_nbt_preserved=True,world_written=False,
        writer_contract='Root only: require stopped world, same complete entity chunk NBT and exact two UUID/type/tag/positions; replace only chunk -9,11 with after_complete_chunk preserving all other region records. Inverse replaces the same chunk after exact after precondition with before_complete_chunk. Back up complete region first; reread both exact UUID absence and all other entity full NBT. No tag selector or broad entity wipe.')
    (args.output/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(plan=str((args.output/'plan.json').resolve()),removed=list(found),preserved_entities=len(preserved_before),world_written=False)),flush=True)

if __name__=='__main__':main()
