"""Read back actual emitted NBT future shards against complete desired sources."""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,json,sys
import nbtlib
from inspect_map_assets import palette_state

def packed(p):
    x,y,z=p;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095)
    return n-(1<<64)if n>=1<<63 else n
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidates',type=Path,nargs='+',required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();results=[]
    for candidate in args.candidates:
        expected=defaultdict(dict)
        with gzip.open(candidate/'complete_generation_source.jsonl.gz','rt',encoding='utf8')as f:
            for line in f:
                r=json.loads(line);p=r['pos'];expected[p[0]//16,p[2]//16][packed(p)]=(sys.intern(r['after']),r['after_nbt'])
        patch=json.loads((candidate/'generation_recipe/file_patch.json').read_text('utf8'));seen=0;shards=0;old_outside=0
        for op in patch['operations']:
            target=Path(op['after_file']);cx,cz=map(int,target.stem.split('_'));wanted=expected[cx,cz]
            doc=nbtlib.load(target);assert str(doc['WorldUUID'])==patch['WorldUUID'];palette=[palette_state(r)for r in doc['Palette']]
            cells={int(r['Pos']):r for r in doc['Static']}
            for pos,(state,tag)in wanted.items():
                row=cells[pos];assert palette[int(row['StateId'])]==state
                actual=row.get('NBT');assert (actual is None and tag is None)or actual==nbtlib.parse_nbt(tag)
                seen+=1
            if op['before_file'] is not None:
                before=nbtlib.load(op['before_file']);assert doc['Palette'][:len(before['Palette'])]==before['Palette']
                for key in before:
                    if key not in {'Static','Palette'}:assert before[key]==doc[key],('Unrelated original shard field changed',candidate,target,key)
                for row in before['Static']:
                    pos=int(row['Pos'])
                    if pos not in wanted:assert cells[pos]==row;old_outside+=1
            shards+=1
        assert seen==sum(map(len,expected.values()))==patch['complete_desired_cells']
        results.append(dict(candidate=str(candidate),actual_NBT_shards=shards,complete_cells_read_back=seen,
            exact_state_and_typed_BE_NBT_match=True,unrelated_original_shard_fields_and_palette_prefix_retained=True,
            original_static_cells_outside_mask_retained=old_outside,world_written=False,native_verified=False))
        print(candidate.name,seen,'actual future cells read back;',shards,'shards; full NBT source/palette/retained fields PASS',flush=True)
    args.out.write_text(json.dumps(dict(schema=50,results=results,world_written=False,native_verified=False),indent=2),'utf8')
if __name__=='__main__':main()
