"""Classify whole legacy TV forest components and plan native leaf behaviour.

Only complete, unchanged components matching the retired generator's exact
geometry may become non-persistent native leaves. Extra branches, pruning,
missing chunks, machinery/NBT and reservations preserve the entire component.
No tree is relocated, and this tool never writes the world.
"""
from pathlib import Path
from collections import defaultdict,Counter,deque
import math,json,gzip,time,argparse
from measure_world_r40 import MeasuredWorld,properties
from query_blocks import chunk_statuses,iter_block_entities

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
OUT=ROOT/'artifacts/rebuild_r44/ecology/legacy_tree_components';MASK=(1<<64)-1

def packed(x,y,z):return ((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&0xfff)
def point(p):
    x,z,y=p>>38,(p>>12)&0x3ffffff,p&0xfff
    return (x-(1<<26) if x>=1<<25 else x,y-4096 if y>=2048 else y,z-(1<<26) if z>=1<<25 else z)
def value(gx,gz):
    h=((gx*341873128712&MASK)^(gz*132897987541&MASK))&MASK;h^=h>>33;h=h*0xff51afd7ed558ccd&MASK;return h^(h>>33)
def rectangle(x,z,a,b,c,d):return math.hypot(max(a-x,0,x-c),max(b-z,0,z-d))
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def gauss(x,z,cx,cz,r):return math.exp(-((x-cx)**2+(z-cz)**2)/(r*r))
def lake(x,z):return ((x+310)/310)**2+((z-340)/200)**2+.075*math.sin((x+z)/47)+.045*math.cos(z/37)
def ground(x,z):
    y=-478+3.5*math.sin(x/137)*math.cos(z/193)+2.4*math.sin((x+z)/67)+29*gauss(x,z,420,830,310)+17*gauss(x,z,-230,1030,390)+11*gauss(x,z,720,330,290)
    if lake(x,z)<1.2:
        shelf=smooth((lake(x,z)-.60)/.60);y=-484*(1-shelf)-471*shelf
    campus=1-smooth(rectangle(x,z,-90,160,96,447)/64)
    return math.floor(y*(1-campus)-467*campus+.5)
def roof(x,z):
    r=math.hypot(x-30,z-296)
    if r<=600:return 24
    t=min(1,(r-600)/1200);return -478+math.floor(502*math.sqrt(max(0,1-t*t)))
def spec(gx,gz):
    h=value(gx,gz);signed=h-(1<<64) if h>=1<<63 else h
    x,z=gx*14+2+signed%10,gz*14+2+(h>>12)%10
    if rectangle(x,z,-85,190,75,425)<35 or lake(x,z)<1.28 or roof(x,z)<ground(x,z)+20:return None
    density=max(gauss(x,z,-520,810,420),gauss(x,z,370,860,350),gauss(x,z,730,230,420))
    if (h>>24)%1000>density*740:return None
    base,height=ground(x,z),7+(h>>34)%5;logs=set();leaves=set()
    for dy in range(1,height+3):
        for dz in range(-4,5):
            for dx in range(-4,5):
                q=packed(x+dx,base+dy,z+dz)
                if dx==dz==0 and dy<=height:logs.add(q)
                elif dy>=height-4 and (dx*dx+dz*dz)/16+((dy-height+1)/3.4)**2<1:leaves.add(q)
    return dict(root=[x,base,z],grid=[gx,gz],height=height,log='minecraft:birch_log' if signed%7==0 else 'minecraft:oak_log',logs=logs,leaves=leaves,mask=logs|leaves)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--retire-original-layout',action='store_true');parser.add_argument('--inspect-reserved',action='store_true');parser.add_argument('--output',type=Path);parser.add_argument('--underground-reservations-only',action='store_true');args=parser.parse_args()
    folder=args.output or (OUT/'retire_and_native_reseed' if args.retire_original_layout else OUT)
    folder.mkdir(parents=True,exist_ok=True);started=time.monotonic();trees=[];grid={}
    for gz in range(-115,152):
        for gx in range(-131,132):
            t=spec(gx,gz)
            if t is not None:grid[gx,gz]=len(trees);trees.append(t)
    parent=list(range(len(trees)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def union(i,j):parent[find(j)]=find(i)
    for i,t in enumerate(trees):
        gx,gz=t['grid']
        for dz in (-1,0,1):
            for dx in (-1,0,1):
                j=grid.get((gx+dx,gz+dz))
                if j is None or j<=i:continue
                a,b=t['mask'],trees[j]['mask'];touch=bool(a&b)
                if not touch:
                    for q in a:
                        x,y,z=point(q)
                        if any(packed(x+u,y+v,z+w) in b for u,v,w in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))):touch=True;break
                if touch:union(i,j)
    groups=defaultdict(list)
    for i in range(len(trees)):groups[find(i)].append(i)
    configuration=json.loads((ROOT/'artifacts/rebuild_r44/ecology/biome_source.completed.json').read_text('utf8'))
    reservations=configuration['underground_reserved_bounds'] if args.underground_reservations_only else configuration['reserved_bounds']+configuration['underground_reserved_bounds']
    unknown_grids=set();records=[];counts=Counter();changed=0
    all_masks=set().union(*(t['mask'] for t in trees))
    with gzip.open(folder/'forward.jsonl.gz','wt',encoding='utf8') as forward,gzip.open(folder/'inverse.jsonl.gz','wt',encoding='utf8') as inverse:
        for n,indices in enumerate(groups.values()):
            logs=set().union(*(trees[i]['logs'] for i in indices));leaves=set().union(*(trees[i]['leaves'] for i in indices))-logs;mask=logs|leaves
            points=[point(q) for q in mask];lo=tuple(min(q[d] for q in points) for d in range(3));hi=tuple(max(q[d] for q in points) for d in range(3))
            record=dict(id=f'legacy_tv_forest/{n:04d}',roots=[trees[i]['root'] for i in indices],bounds=[lo,hi],trees=len(indices),logs=len(logs),leaves=len(leaves))
            reserved=any(lo[0]<=r[2] and hi[0]>=r[0] and lo[2]<=r[3] and hi[2]>=r[1] for r in reservations)
            if reserved and not args.inspect_reserved:
                record.update(status='PRESERVE_AUTHORED_RESERVATION',reason='Whole crown/root component intersects a city, facility or virtual railway reservation')
            else:
                w=MeasuredWorld(WORLD);w.box(tuple(v-1 for v in lo),tuple(v+1 for v in hi));w.load();failures=[];actual={}
                for i in indices:
                    t=trees[i]
                    for q in t['logs']:
                        old=w.block(point(q));actual[q]=old
                        if old is None or old.partition('[')[0]!=t['log'] or properties(old).get('axis')!='y':failures.append([point(q),old,'Expected complete original vertical trunk'])
                    for q in t['leaves']-logs:
                        old=w.block(point(q));actual[q]=old
                        if old is None or old.partition('[')[0]!='minecraft:oak_leaves' or properties(old).get('persistent')!='true' or properties(old).get('waterlogged')!='false':failures.append([point(q),old,'Original crown state differs or was modified'])
                if not failures:
                    for q in mask:
                        x,y,z=point(q)
                        for u,v,r in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                            other=packed(x+u,y+v,z+r)
                            if other in all_masks:continue
                            old=w.block(point(other))
                            if old is None:failures.append([point(other),None,'Unmeasured whole-component boundary'])
                            elif old.partition('[')[0].endswith(('_log','_leaves')):failures.append([point(other),old,'Additional or user-authored connected branch/crown'])
                    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
                    for q in mask:
                        if point(q) in tags:failures.append([point(q),'NBT','Preserve complete block entity'])
                if failures:
                    record.update(status='PRESERVE_MODIFIED_OR_INCOMPLETE',reason='Geometry, state, connected boundary or full-chunk precondition did not prove the complete original component',failures=failures)
                else:
                    if reserved:
                        record.update(status='PRESERVE_VERIFIED_COMPLETE_TEMPLATE_IN_RESERVATION',reason='Complete original geometry/state and no block entity proved; actual 3D facility/rail/road relationship still requires ownership review, no retirement write mask',native_reseed_permission=False)
                        records.append(record);counts[record['status']]+=1
                        if n%100==0:print('Whole legacy tree component',n+1,'/',len(groups),dict(counts),flush=True)
                        continue
                    if args.retire_original_layout:
                        for q in sorted(mask):
                            old=actual[q]
                            row=dict(pos=point(q),before=old,after='minecraft:air',before_nbt=None,after_nbt=None,owner=record['id'],reason='Retire the complete unchanged retired 14-grid generator component; preserve natural ground and reseed using registered native placed features')
                            forward.write(json.dumps(row)+'\n');row['before'],row['after']=row['after'],row['before'];inverse.write(json.dumps(row)+'\n');changed+=1
                        record.update(status='RETIRE_VERIFIED_COMPLETE_GRID_COMPONENT',changed_cells=len(mask),native_reseed_required=True)
                        records.append(record);counts[record['status']]+=1
                        if n%100==0:print('Whole legacy tree component',n+1,'/',len(groups),dict(counts),flush=True)
                        continue
                    distance={q:0 for q in logs};queue=deque(logs)
                    while queue:
                        q=queue.popleft();d=distance[q]+1
                        if d>6:continue
                        x,y,z=point(q)
                        for u,v,r in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                            other=packed(x+u,y+v,z+r)
                            if other in leaves and other not in distance:distance[other]=d;queue.append(other)
                    for q in sorted(leaves):
                        old=actual[q];prop=properties(old);prop.update(distance=str(distance.get(q,7)),persistent='false')
                        after='minecraft:oak_leaves['+','.join(f'{k}={v}' for k,v in sorted(prop.items()))+']'
                        row=dict(pos=point(q),before=old,after=after,before_nbt=None,after_nbt=None,owner=record['id'],reason='Whole verified original tree component receives native support distance and natural leaf decay; geometry and trunk retained')
                        forward.write(json.dumps(row)+'\n');row['before'],row['after']=after,old;inverse.write(json.dumps(row)+'\n');changed+=1
                    record.update(status='NATURALIZE_VERIFIED_COMPLETE_COMPONENT',unconnected_native_decay_leaves=sum(q not in distance for q in leaves),changed_leaves=len(leaves))
            records.append(record);counts[record['status']]+=1
            if n%100==0:print('Whole legacy tree component',n+1,'/',len(groups),dict(counts),flush=True)
    result=dict(world=str(WORLD),source='TvWorldPreviewTerrain.plantForest (retired R44)',source_sha256=__import__('hashlib').sha256((ROOT/'src/main/java/com/projectseele/world/TvWorldPreviewTerrain.java').read_bytes()).hexdigest(),
        expected_original_trees=len(trees),components=len(records),classification=dict(counts),changed_leaf_cells=changed,world_changed=False,
        native_world_and_visual_passed=False,manual_user_vegetation_preserved=True,seconds=time.monotonic()-started,objects=records)
    result['changed_leaf_cells' if not args.retire_original_layout else 'complete_retirement_cells']=result.pop('changed_leaf_cells')
    result['native_reseed_required']=args.retire_original_layout
    result['layout_repaired']=False
    (folder/'audit.json').write_text(json.dumps(result,indent=2),'utf8');print({k:v for k,v in result.items() if k!='objects'},flush=True)

if __name__=='__main__':main()
