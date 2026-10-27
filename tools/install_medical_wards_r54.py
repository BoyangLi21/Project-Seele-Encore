"""Root-only, cold exact medical-wing migration with full NBT and rollback.

No decoder duplication: query_blocks reads and the common region writer applies.
No fingerprints, progress-file copy, entity writes, or runtime construction.
"""
import argparse,json,sys,shutil
from pathlib import Path
from collections import defaultdict
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
import nbtlib
from query_blocks import read_box,iter_block_entities,dimension_dir
from apply_s20_approved_semantic_repairs import Change,rewrite_region,atomic_replace
from install_r53_carrier_trays import stopped_world

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',type=Path,required=True);ap.add_argument('--world',type=Path,required=True);ap.add_argument('--backup',type=Path,required=True);ap.add_argument('--apply',action='store_true');ap.add_argument('--inverse',action='store_true');a=ap.parse_args()
    read=lambda n:json.loads((a.candidate/n).read_text('utf8'))
    m=read('installation_manifest.json');assert a.world.resolve()==Path(m['world']).resolve()
    rows=read('inversePatch.json' if a.inverse else 'forwardPatch.json');back=read('forwardPatch.json' if a.inverse else 'inversePatch.json')
    pairs={tuple(r['pos']):r for r in back};mask={tuple(p) for p in read('positiveEditMask.json')}
    assert len(rows)==len(pairs)==len(mask)==m['static_cells']
    for r in rows:
        q=tuple(r['pos']);b=pairs[q];assert q in mask
        assert (r['before'],r['after'],r['before_nbt'],r['after_nbt'])==(b['after'],b['before'],b['after_nbt'],b['before_nbt'])
    lo,hi=map(tuple,m['bounds']);dim=m['dimension']
    def tag_equal(a,b):return (a is None and b is None) or (a is not None and b is not None and a==nbtlib.parse_nbt(b))
    with stopped_world(a.world):
        states=read_box(a.world,dim,lo,hi);tags=dict(iter_block_entities(a.world,dim,lo,hi))
        for r in rows:
            q=tuple(r['pos']);assert states[q]==r['before'] and tag_equal(tags.get(q),r['before_nbt']),('Changed measured precondition',q,states[q])
        for r in read('preserved_block_entities.json'):
            q=tuple(r['pos']);assert states[q]==r['state'] and tag_equal(tags.get(q),r['snbt']),('Original non-bed equipment changed',q)
        expected={q:t for q,t in tags.items() if q not in mask}
        expected.update({tuple(r['pos']):nbtlib.parse_nbt(r['after_nbt']) for r in rows if r['after_nbt'] is not None})
        if not a.apply:print(json.dumps(dict(exact_preconditions=True,cells=len(rows),world_written=False)));return
        assert not a.backup.exists();a.backup.mkdir(parents=True)
        grouped=defaultdict(lambda:defaultdict(list));region=dimension_dir(a.world,dim)/'region'
        for r in rows:
            x,y,z=r['pos'];grouped[region/f'r.{x>>9}.{z>>9}.mca'][x>>4,z>>4].append(Change('r54-medical-wards',x,y,z,r['before'],r['after'],'authorized-medical-interior',r['reason']))
        removed={tuple(r['pos']) for r in rows if r['before_nbt'] is not None}
        additions={tuple(r['pos']):nbtlib.parse_nbt(r['after_nbt']) for r in rows if r['after_nbt'] is not None}
        original={p:p.read_bytes() for p in grouped}
        rewritten={p:rewrite_region(p,v,removed,additions) for p,v in grouped.items()}
        metadata=a.world/'r54_medical_wards.json';before_meta=metadata.read_bytes() if metadata.exists() else None
        if before_meta is not None:(a.backup/metadata.name).write_bytes(before_meta)
        for p,raw in original.items():(a.backup/p.name).write_bytes(raw)
        for n in ('forwardPatch.json','inversePatch.json','positiveEditMask.json','installation_manifest.json'):shutil.copy2(a.candidate/n,a.backup/n)
        written=[]
        try:
            for p,raw in rewritten.items():atomic_replace(p,raw);written.append(p)
            if a.inverse:
                if metadata.exists():metadata.unlink()
            else:atomic_replace(metadata,(a.candidate/metadata.name).read_bytes())
            actual=read_box(a.world,dim,lo,hi);final=dict(iter_block_entities(a.world,dim,lo,hi))
            assert all(actual[tuple(r['pos'])]==r['after'] for r in rows)
            assert final==expected,'Full local NBT readback failed'
            for r in read('preserved_block_entities.json'):assert actual[tuple(r['pos'])]==r['state']
            if not a.inverse:assert metadata.read_bytes()==(a.candidate/metadata.name).read_bytes()
        except Exception:
            for p in written:atomic_replace(p,original[p])
            if before_meta is not None:atomic_replace(metadata,before_meta)
            elif metadata.exists():metadata.unlink()
            raise
        receipt=dict(cells=len(rows),actual_cells_read_back=True,full_nbt_read_back=True,original_nonbed_nbt_preserved=len(read('preserved_block_entities.json')),metadata_read_back=not a.inverse,progress_files_written=[],inverse=a.inverse,native_and_visual_validation_pending=True)
        (a.backup/'installation.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt))
if __name__=='__main__':main()
