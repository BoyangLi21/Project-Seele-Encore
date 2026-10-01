"""Current full-component readback of documented road/rail retirements, no cleanup."""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/surface_network'
SOURCES=[ROOT/'artifacts/facility_r24/residue/verified_rail_fragment_retirement/ops.json.gz',
         ROOT/'artifacts/world_quality_r02/exposed_road_tunnel_cleanup/ops.json.gz']

def main():
    objects=[];manifest=[]
    for source in SOURCES:
        with gzip.open(source,'rt',encoding='utf8') as stream:ops=json.load(stream)
        retire=[o for o in ops if o['state']=='minecraft:air' and o['mode']=='match']
        if source.parent.name=='exposed_road_tunnel_cleanup':
            record=ROOT/'artifacts/world_quality_r02/exposed_road_tunnels.json'
            retire=[dict(box=[*q[:3],*q[:3]],state='minecraft:air',owner='r02/documented_exposed_tunnel_retirement',extra=[q[3]]) for q in json.loads(record.read_text('utf8'))['removed']]
            manifest.append(dict(path=str(record),sha256=hashlib.sha256(record.read_bytes()).hexdigest(),role='Exact recorded old tunnel-shell state and complete retirement coordinates'))
        by_point={}
        for op in retire:
            x0,y0,z0,x1,y1,z1=op['box']
            for x in range(x0,x1+1):
                for z in range(z0,z1+1):
                    for y in range(y0,y1+1):by_point[x,y,z]=op['extra'][0]
        manifest.append(dict(path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),exact_retirement_ops=len(retire)))
        w=MeasuredWorld(WORLD)
        for op in retire:w.box(tuple(op['box'][:3]),tuple(op['box'][3:]))
        w.load()
        if not retire:continue
        lo=tuple(min(o['box'][i] for o in retire) for i in range(3));hi=tuple(max(o['box'][i+3] for o in retire) for i in range(3))
        tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
        remaining=set(by_point);index=0
        while remaining:
            first=min(remaining);remaining.remove(first);stack=[first];group=[]
            while stack:
                x,y,z=stack.pop();group.append((x,y,z))
                for dx in (-1,0,1):
                    for dy in (-1,0,1):
                        for dz in (-1,0,1):
                            if (x+dx,y+dy,z+dz) in remaining:remaining.remove((x+dx,y+dy,z+dz));stack.append((x+dx,y+dy,z+dz))
            events=[];count=Counter()
            for q in group:
                current=w.block(q);before=by_point[q]
                status='UNMEASURED' if current is None else 'OLD_COMPONENT_STATE_REMAINS' if current==before else 'EXACT_RETIRED_AIR' if current in AIR else 'NEW_USE_REQUIRES_OWNERSHIP_REVIEW'
                if q in tags:status='FULL_NBT_NEW_USE_PRESERVED'
                count[status]+=1
                if status!='EXACT_RETIRED_AIR':events.append(dict(pos=q,current=current,before=before,has_nbt=q in tags,status=status))
            bounds=[tuple(min(q[d] for q in group) for d in range(3)),tuple(max(q[d] for q in group) for d in range(3))]
            objects.append(dict(id=f'retirement/{source.parent.name}/{index}',source_owner=retire[0]['owner'],bounds=bounds,complete_recorded_component_cells=len(group),counts=dict(count),events=events,
                whole_recorded_component_retired=set(count)=={'EXACT_RETIRED_AIR'},quality_scope='Exact documented whole sparse retirement mask; nearby active bridge/city/railway components retain their own QA',world_written=False))
            index+=1
    result=dict(world=str(WORLD),sources=manifest,objects=objects,exact_masks=len(objects),
        recorded_components_no_old_material=sum(o['whole_recorded_component_retired'] for o in objects),
        unresolved_objects=[o['id'] for o in objects if not o['whole_recorded_component_retired']],world_written=False,global_rail_road_quality_passed=False)
    (OUT/'retired_component_readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print({k:v for k,v in result.items() if k not in ('sources','objects')},flush=True)

if __name__=='__main__':main()
