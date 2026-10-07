"""Exact candidate mask/inverse/NBT/future-source audit. Not a native game test."""
from pathlib import Path
import argparse,gzip,json,hashlib
import nbtlib
from regional_voxels import canonical_state

def digest(r,inverse=False):
    names=('after','before','after_nbt','before_nbt')if inverse else('before','after','before_nbt','after_nbt')
    return hashlib.sha256(json.dumps([r[k]for k in names],ensure_ascii=False,separators=(',',':')).encode()).digest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidates',type=Path,nargs='+',required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();results=[]
    for candidate in args.candidates:
        total=0;changed={};new_nbt=0
        for path in sorted(candidate.glob('*/forward.jsonl.gz')):
            points=set()
            with gzip.open(path,'rt',encoding='utf8')as f:
                for line in f:
                    r=json.loads(line);p=tuple(r['pos']);assert p not in changed
                    assert canonical_state(r['after'])==r['after']
                    for key in('before_nbt','after_nbt'):
                        if r[key]is not None:
                            t=nbtlib.parse_nbt(r[key]);assert [int(t[k])for k in('x','y','z')]==list(p)
                            if key=='after_nbt':new_nbt+=1
                    changed[p]=digest(r);points.add(p);total+=1
            mask=json.loads((path.parent/'positiveEditMask.json').read_text('utf8'))
            assert len(mask)==len(points) and set(map(tuple,mask))==points
            inverse_points=set()
            with gzip.open(path.parent/'inverse.jsonl.gz','rt',encoding='utf8')as f:
                for line in f:
                    r=json.loads(line);p=tuple(r['pos']);assert p in points and p not in inverse_points
                    assert digest(r,True)==changed[p];inverse_points.add(p)
            assert inverse_points==points
        future_points=set();remaining=dict(changed);generation_rows=0
        with gzip.open(candidate/'complete_generation_source.jsonl.gz','rt',encoding='utf8')as f:
            for line in f:
                r=json.loads(line);p=tuple(r['pos']);assert p not in future_points
                future_points.add(p);generation_rows+=1
                if p in remaining:assert digest(r)==remaining.pop(p)
        assert not remaining
        manifest=json.loads((candidate/'manifest.json').read_text('utf8'));assert manifest['changed_cells']==total
        recipe=json.loads((candidate/'generation_recipe/file_patch.json').read_text('utf8'))
        assert recipe['complete_desired_cells']==generation_rows and recipe['actual_world_changed_cells']==total
        results.append(dict(candidate=str(candidate),changed_cells=total,complete_generation_cells=generation_rows,
            exact_inverse_mask_and_NBT_valid=True,duplicate_positions=0,changed_cells_in_future_source=True,
            new_complete_BEs=new_nbt,world_written=False,native_verified=False,visual_verified=False))
        print(candidate.name,total,'changed;',generation_rows,'complete future cells; exact inverse/NBT/mask PASS; native NOT tested',flush=True)
    args.out.write_text(json.dumps(dict(schema=50,results=results,world_written=False,native_test_claimed=False),indent=2),'utf8')
if __name__=='__main__':main()
