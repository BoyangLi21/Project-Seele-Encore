"""Cross-dimension object census, using the shared reader; no pass/fail from counts."""
from pathlib import Path
from collections import Counter
import gzip,json,time
import numpy as np
import query_blocks as q
from inventory_world_r40 import feature,authored

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'artifacts/repair_r43/source_world_backup';OUT=ROOT/'artifacts/repair_r43/object_inventory_v2'


def dimensions():
    values=[]
    for name,folder in [('minecraft:overworld',WORLD),('minecraft:the_nether',WORLD/'DIM-1'),('minecraft:the_end',WORLD/'DIM1')]:
        if (folder/'region').is_dir():values.append((name,folder))
    base=WORLD/'dimensions'
    if base.exists():
        for region in base.rglob('region'):
            parts=region.parent.relative_to(base).parts
            if len(parts)>=2:values.append((parts[0]+':'+('/'.join(parts[1:])),region.parent))
    return values


def classify(state):
    name=state.partition('[')[0]
    if name.startswith('mtr:') and any(s in name for s in ('ticket','barrier')):return 'fare_gate_or_ticket_fixture'
    if name=='minecraft:barrier':return 'invisible_barrier'
    if name.endswith('_fence_gate') or name.endswith(':gate'):return 'pedestrian_gate'
    if name.endswith('_pressure_plate') or name.endswith(':tripwire_hook'):return 'entry_sensor'
    if name.endswith('_fence') or name.endswith('_wall') or name.endswith(':iron_bars'):return 'edge_guard'
    if name in ('minecraft:rail','minecraft:powered_rail','minecraft:detector_rail','minecraft:activator_rail'):return 'vanilla_rail'
    if name.endswith(':ladder') or name.endswith(':scaffolding'):return 'vertical_access'
    if name.endswith('_torch') or name in ('minecraft:torch','minecraft:light','minecraft:sea_lantern','minecraft:shroomlight','minecraft:jack_o_lantern'):return 'lights'
    if 'wall_artwork' in name:return 'wall_art'
    if any(x in name for x in ('chair','seat','bench')):return 'seating'
    return feature(state)


def main():
    OUT.mkdir(parents=True,exist_ok=True);summary=[];began=time.monotonic()
    for dimension,folder in dimensions():
        stem=dimension.replace(':','_').replace('/','_');counts=Counter();statuses=Counter();state_counts=Counter();sections=[];chunks=[];nbt_count=0;palette_names=set();classified_names=set()
        with gzip.open(OUT/(stem+'_cells.jsonl.gz'),'wt',encoding='utf8') as cells,gzip.open(OUT/(stem+'_block_entities.jsonl.gz'),'wt',encoding='utf8') as tags:
            for cx,cz,chunk in q.iter_chunks(folder,(-1875000,1875000,-1875000,1875000)):
                status=str(chunk.get('Status','')).removeprefix('minecraft:');statuses[status]+=1
                ys=[int(s.get('Y',0)) for s in chunk.get('sections',[])];chunks.append([cx,cz,status,min(ys) if ys else None,max(ys) if ys else None])
                for tag in chunk.get('block_entities',[]):
                    row=dict(dimension=dimension,position=[int(tag.get(k,0)) for k in ('x','y','z')],id=str(tag.get('id','')),nbt=tag.snbt(),chunk_status=status)
                    tags.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n');nbt_count+=1
                for section in chunk.get('sections',[]):
                    raw=section.get('block_states',{}).get('palette',[])
                    for tag in raw:
                        name=str(tag.get('Name',''));palette_names.add(name)
                        if classify(name):classified_names.add(name)
                    if not any(authored(str(t.get('Name',''))) or classify(str(t.get('Name',''))) for t in raw):continue
                    palette,indices=q.decode_modern_section(section)
                    if not palette:continue
                    index=np.asarray(indices,dtype=np.int32);states=[q.palette_state(s) for s in palette];hist=np.bincount(index,minlength=len(states));built=0;sy=int(section.get('Y',0))
                    for n,state in enumerate(states):
                        count=int(hist[n]);state_counts[state]+=count
                        if authored(state):built+=count
                        kind=classify(state)
                        if not kind or not count:continue
                        counts[kind]+=count
                        for at in np.flatnonzero(index==n):
                            row=[cx*16+int(at&15),sy*16+int(at>>8),cz*16+int((at>>4)&15),state,kind,status]
                            cells.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
                    if built:sections.append([cx,cz,sy,built,status])
                if len(chunks)%10000==0:print(dimension,len(chunks),'chunks read;',nbt_count,'block entities; census only',flush=True)
        data=dict(dimension=dimension,source=str(WORLD),chunks=chunks,chunk_status_counts=dict(statuses),authored_sections=sections,
                  feature_block_counts=dict(counts),block_entities=nbt_count,state_counts=dict(state_counts),palette_names_seen=sorted(palette_names),classified_names=sorted(classified_names),unclassified_palette_names=sorted(palette_names-classified_names),quality_status='UNREVIEWED: raw census is not an object or quality denominator')
        (OUT/(stem+'_census.json')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),'utf8')
        summary.append({k:data[k] for k in ('dimension','chunk_status_counts','feature_block_counts','block_entities','quality_status')})
    (OUT/'census_summary.json').write_text(json.dumps(dict(dimensions=summary,seconds=time.monotonic()-began,scope='All stored dimension folders, all stored heights; unfinished chunk candidates retained explicitly'),ensure_ascii=False,indent=2),'utf8')
    print('Raw census complete; semantic objects and interfaces are still unreviewed',flush=True)


if __name__=='__main__':main()
