"""Current full-mask readback/source for the 67 documented road/rail retirements.

The historical report omitted AIR entries from `events`; this tool uses every
original retirement coordinate, retaining actual soil, water, later civil and NBT.
"""
from pathlib import Path
from collections import Counter
import argparse,gzip,json
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR
from prepare_facilities_r48 import Author

ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text('utf8'))
def rows(p):
    with gzip.open(p,'rt',encoding='utf8')as f:return[json.loads(s)for s in f if s.strip()]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args();world=args.world.resolve();base=ROOT/'artifacts/rebuild_r49/surface_r50';out=base/'recorded_67_complete_generation';out.mkdir(parents=True,exist_ok=True)
    path=ROOT/'artifacts/facility_r24/residue/verified_rail_fragment_retirement/ops.json.gz'
    with gzip.open(path,'rt',encoding='utf8')as f:rail=json.load(f)
    masks={}
    for op in rail:
        if op['mode']!='match'or op['state']!='minecraft:air':continue
        x0,y0,z0,x1,y1,z1=op['box']
        for x in range(x0,x1+1):
            for y in range(y0,y1+1):
                for z in range(z0,z1+1):masks[x,y,z]=dict(before=op['extra'][0],source='verified_rail_fragment_retirement')
    for q in load(ROOT/'artifacts/world_quality_r02/exposed_road_tunnels.json')['removed']:masks[tuple(q[:3])]=dict(before=q[3],source='exposed_road_tunnel_cleanup')
    common={tuple(r['pos']):r for r in rows(base/'c1_complete_generation/complete_generation_source.jsonl.gz')};w=MeasuredWorld(world)
    for q in masks:w.box(q,q)
    w.load();bad={q:w.status.get((q[0]//16,q[2]//16),'missing')for q in masks if w.status.get((q[0]//16,q[2]//16))!='full'}
    if bad:
        (out/'unread.json').write_text(json.dumps(dict(unread=[dict(pos=q,status=s)for q,s in bad.items()],world_written=False),indent=2),'utf8');raise RuntimeError(('Exact retirement masks include non-full chunks',Counter(bad.values())))
    lo=tuple(min(q[k]for q in masks)for k in range(3));hi=tuple(max(q[k]for q in masks)for k in range(3));bes=dict(iter_block_entities(world,w.dimension,lo,hi,selected_chunks=set(w.selected)))
    source=[];points={};counts=Counter()
    for q,old in sorted(masks.items()):
        current=w.block(q);tag=bes.get(q);snbt=None if tag is None else tag.snbt();final=common.get(q);after=current if final is None else final['after'];after_nbt=snbt if final is None else final['after_nbt']
        status='OLD_COMPONENT_STATE_REMAINS'if current==old['before']else'RETIRED_MASK_CURRENT_AIR'if current.partition('[')[0]in AIR else'CURRENT_OTHER_MATERIAL_OR_CIVIL_REUSE_PRESERVED'
        if snbt is not None:status='FULL_NBT_CURRENT_USE_PRESERVED'
        counts[status]+=1;points[q]=dict(pos=list(q),actual=current,original_old_before=old['before'],status=status,has_nbt=snbt is not None)
        source.append(dict(pos=list(q),before=current,after=after,before_nbt=snbt,after_nbt=after_nbt,owner='M40_recorded_67_terminal_source',reason='Complete recorded legacy retirement mask: freeze actual AIR/soil/water/civil/full NBT, with same terminal value as shared C1 source if masks overlap.',source_only=current==after and snbt==after_nbt))
    remaining=set(masks);objects=[]
    while remaining:
        first=min(remaining);remaining.remove(first);stack=[first];group=[]
        while stack:
            q=stack.pop();group.append(q)
            for dx in(-1,0,1):
                for dy in(-1,0,1):
                    for dz in(-1,0,1):
                        p=q[0]+dx,q[1]+dy,q[2]+dz
                        if p in remaining:remaining.remove(p);stack.append(p)
        c=Counter(points[q]['status']for q in group);objects.append(dict(id=f'recorded_retirement_current/{len(objects)}',complete_mask_cells=len(group),bounds=[[min(q[k]for q in group)for k in range(3)],[max(q[k]for q in group)for k in range(3)]],counts=dict(c),original_before_matches=[points[q]for q in group if points[q]['status']=='OLD_COMPONENT_STATE_REMAINS'],no_old_recorded_material_remains=c['OLD_COMPONENT_STATE_REMAINS']==0,retained_current_nonair_examples=[points[q]for q in group if points[q]['status']not in{'RETIRED_MASK_CURRENT_AIR','OLD_COMPONENT_STATE_REMAINS'}][:20]))
    assert len(objects)==67,('Historical/current exact component partition differs',len(objects))
    with gzip.open(out/'complete_generation_source.jsonl.gz','wt',encoding='utf8')as f:
        for r in source:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    author=Author(world,out);author.all={tuple(r['pos']):r for r in source};author.recipe();(out/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    report=dict(schema=50,world=str(world),complete_recorded_components=67,complete_recorded_mask_cells=len(masks),actual_current_counts=dict(counts),objects=objects,all_original_mask_chunks_full=True,physical_change_authorized_or_emitted=False,current_other_material_preserved=True,full_NBT_preserved=len(bes),source_shared_C1_overlap=sum(q in common for q in masks),world_written=False,source_written=False,native_verified=False,quality_acceptance=False)
    (out/'current_complete_mask_readback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    manifest=load(base/'M40_EXACT_CANDIDATE_MANIFEST.json');manifest['additional_recorded_67_complete_generation_source']=str((out/'complete_generation_source.jsonl.gz').relative_to(ROOT));manifest['additional_recorded_mask_cells']=len(masks);(base/'M40_EXACT_CANDIDATE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    h=load(base/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json');h['surface_40']['recorded_67_current_complete_mask_source']=manifest['additional_recorded_67_complete_generation_source'];h['surface_40']['recorded_67_current_complete_mask_readback']=dict(cells=len(masks),counts=dict(counts),no_old_material_remains=counts['OLD_COMPONENT_STATE_REMAINS']==0);(base/'R50_MARINE_ARMOR_SURFACE_HANDOFF.json').write_text(json.dumps(h,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(components=len(objects),mask_cells=len(masks),counts=dict(counts),shared_C1_overlap=report['source_shared_C1_overlap'],world_written=False)),flush=True)

if __name__=='__main__':main()
