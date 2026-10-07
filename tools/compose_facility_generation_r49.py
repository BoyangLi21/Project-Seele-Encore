"""Merge finite cell sources into complete original static NBT shards; no world writes."""
from pathlib import Path
import argparse,gzip,json
from collections import defaultdict
import nbtlib
from prepare_facilities_r48 import Author,DIM
from query_blocks import read_box,iter_block_entities
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r49/combined_generation')
    ap.add_argument('--components',type=Path,nargs='+',required=True)
    ap.add_argument('--complete-sources',type=Path,nargs='+')
    ap.add_argument('--metadata',type=Path,nargs='+',required=True);args=ap.parse_args()
    if args.complete_sources and len(args.complete_sources)!=len(args.components):raise ValueError('One complete source per component required')
    a=Author(args.world.resolve(),args.out.resolve());a.out.mkdir(parents=True,exist_ok=True)
    owners=defaultdict(int);grouped=defaultdict(list);complete_sources={};overlap_count=0
    for index,component in enumerate(args.components):
        source=args.complete_sources[index]if args.complete_sources else component/'complete_generation_source.jsonl.gz'
        if not source.exists():
            if args.complete_sources:raise FileNotFoundError(source)
            source=component/'forward.jsonl.gz'
        complete_sources[str(component)]=source.name
        with gzip.open(source,'rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);q=tuple(r['pos'])
                if q in a.all:
                    prior=a.all[q]
                    if any(prior.get(k)!=r.get(k)for k in('before','before_nbt','after','after_nbt')):
                        raise ValueError(('Conflicting exact component cells',q,prior['owner'],r['owner']))
                    overlap_count+=1
                    continue
                a.all[q]=r;owners[component.name]+=1;grouped[q[0]//16,q[2]//16].append(q)
    for (cx,cz),points in grouped.items():
        ys=[q[1] for q in points];lo=(cx*16,min(ys),cz*16);hi=(cx*16+15,max(ys),cz*16+15)
        states=read_box(a.world,DIM,lo,hi);tags=dict(iter_block_entities(a.world,DIM,lo,hi))
        for q in points:
            r=a.all[q];old=None if r['before_nbt'] is None else nbtlib.parse_nbt(r['before_nbt'])
            assert states[q]==r['before'] and tags.get(q)==old,('Source differs before static composition',q,states[q],r['before'])
    operations={}
    for path in args.metadata:
        for op in json.loads(path.read_text('utf8'))['operations']:
            target=op['relative_target']
            if target in operations:raise ValueError(('Repeated metadata target; compose explicitly before merging',target))
            operations[target]=op
    a.recipe()
    (a.out/'metadata_patch.json').write_text(json.dumps(dict(schema=49,operations=list(operations.values()),world_written=False),ensure_ascii=False,indent=2),'utf8')
    (a.out/'manifest.json').write_text(json.dumps(dict(schema=50,world=str(a.world),source_cells=len(a.all),changed_cells=sum(r['before']!=r['after']or r.get('before_nbt')!=r.get('after_nbt')for r in a.all.values()),owners=dict(owners),metadata_targets=list(operations),complete_sources=complete_sources,identical_overlap_cells=overlap_count,
        all_old_world_states_and_complete_NBT_matched=True,original_palette_static_ground_and_shard_NBT_preserved=True,source_cells_merged_not_whole_shards_overwritten=True,
        world_written=False),ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(merged_cells=len(a.all),owners=dict(owners),metadata_targets=list(operations),world_written=False),ensure_ascii=False))
if __name__=='__main__':main()
