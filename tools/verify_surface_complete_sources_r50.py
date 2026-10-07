"""Check finite R50 full sources in the saved candidate NBT payloads, no writes.

Checks terminal states/NBT for every source cell, unmodified Static/Ground and
palette prefixes, exact inverses, and cross-source consistency. Not native QA.
"""
from pathlib import Path
from collections import defaultdict
import gzip,json
import nbtlib
from inspect_map_assets import palette_state
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r49/surface_r50'
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return[json.loads(s)for s in f if s.strip()]
def path(p):
    p=Path(p);return p if p.is_absolute()else ROOT/p
def packed(q):
    x,y,z=q;n=((x&67108863)<<38)|((z&67108863)<<12)|(y&4095);return n-(1<<64)if n>=1<<63 else n
def main():
    folders=[BASE/'c1_complete_generation',BASE/'recorded_67_complete_generation',BASE/'global_depressions/isolated_soil_pit_candidates',BASE/'global_depressions/current_rail_deck_gap_candidates'];seen={};proof=[];conflict=[];overlaps=0
    for folder in folders:
        source=rows(folder/'complete_generation_source.jsonl.gz');recipe=json.loads((folder/'generation_recipe/file_patch.json').read_text('utf8'));by_chunk=defaultdict(list)
        for r in source:
            q=tuple(r['pos']);by_chunk[q[0]//16,q[2]//16].append(r)
            if q in seen:
                overlaps+=1
                if seen[q]['after']!=r['after']or seen[q]['after_nbt']!=r['after_nbt']:conflict.append(dict(pos=q,earlier=seen[q]['owner'],later=r['owner']))
            seen[q]=r
        checked=0;untouched=0
        for op in recipe['operations']:
            p=path(op['after_file']);doc=nbtlib.load(p);assert str(doc['WorldUUID'])==recipe['WorldUUID'];palette=doc['Palette'];static={int(v['Pos']):v for v in doc['Static']};cx,cz=map(int,p.stem.split('_'));allowed={packed(tuple(r['pos']))for r in by_chunk[cx,cz]}
            for r in by_chunk[cx,cz]:
                v=static[packed(tuple(r['pos']))];state=canonical_state(palette_state(palette[int(v['StateId'])]));assert state==canonical_state(r['after']),('Terminal source state mismatch',folder,r['pos'],state,r['after'])
                nbt=v.get('NBT');actual=None if nbt is None else nbt.snbt();expected=r.get('after_nbt');assert actual==expected,('Terminal NBT mismatch',folder,r['pos']);checked+=1
            if op.get('before_file'):
                old=nbtlib.load(path(op['before_file']));assert doc['Ground']==old['Ground']and doc['Palette'][:len(old['Palette'])]==old['Palette']
                for v in old['Static']:
                    n=int(v['Pos'])
                    if n not in allowed:assert static[n]==v,('Foreign Static modified',folder,n);untouched+=1
        assert checked==len(source)
        inverseproof=[]
        for component in folder.glob('M40_*'):
            if not component.is_dir()or not(component/'forward.jsonl.gz').exists():continue
            f=rows(component/'forward.jsonl.gz');inv={tuple(r['pos']):r for r in rows(component/'inverse.jsonl.gz')};assert len(f)==len(inv)
            for r in f:
                v=inv[tuple(r['pos'])];assert(v['before'],v['after'],v.get('before_nbt'),v.get('after_nbt'))==(r['after'],r['before'],r.get('after_nbt'),r.get('before_nbt'))
            inverseproof.append(dict(component=component.name,exact_inverse_rows=len(f)))
        proof.append(dict(source_folder=str(folder.relative_to(ROOT)),full_source_cells_checked=checked,complete_NBT_payload_shards=len(recipe['operations']),unmodified_existing_Static_cells_compared=untouched,unmodified_Ground_palette_prefix_preserved=True,exact_inverses=inverseproof))
    report=dict(sources=proof,unique_combined_source_cells=len(seen),consistent_overlap_rows=overlaps,conflicting_source_rows=conflict,all_checks_passed=not conflict,world_written=False,native_verified=False,visual_acceptance=False);assert not conflict,conflict[:10]
    (BASE/'complete_sources_payload_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
