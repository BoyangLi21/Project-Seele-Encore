"""Prepare exact edits for face-disconnected natural fragments and broken roof posts.

Pass the result of resolve_face_survey.py, the matching read-only region directory,
and the original world's authority tables. The output is a sparse plan for staging.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
from itertools import permutations, product
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from write_deep_cells import decode, read_chunk
from map_pipeline.city_protection import load as city_protection
from map_pipeline.lift_protection import load as lift_protection
from map_pipeline.launch_protection import load as launch_protection
from survey_r64_playtest_terrain import SOIL, PLANTS

AIR = {'minecraft:air', 'minecraft:void_air', 'minecraft:cave_air'}
SOILS = {'minecraft:' + s for s in SOIL}
PLANT = {'minecraft:' + s for s in PLANTS}
BOULDERS = {'minecraft:cobblestone', 'minecraft:mossy_cobblestone'}
POSTS = {'minecraft:' + wood + end for wood in ('oak','spruce','dark_oak','birch','acacia','jungle')
         for end in ('_planks','_fence','_log','_wood')}
NEIGHBORS = sorted((d for d in product((-1,0,1), repeat=3) if sum(bool(i) for i in d)>=2),
                   key=lambda d: (sum(bool(i) for i in d), abs(d[1]), d))

def bare(s):
    return s.partition('[')[0]

def load_reader(directory):
    @lru_cache(10)
    def region(rx,rz):
        path=directory/f'r.{rx}.{rz}.mca'
        return path.read_bytes() if path.is_file() else b''
    @lru_cache(48)
    def chunk(cx,cz):
        raw=region(cx//32,cz//32)
        offset=4*((cx&31)+(cz&31)*32)
        if not int.from_bytes(raw[offset:offset+3],'big'):return None
        nbt=read_chunk(raw,cx,cz)[3]
        if str(nbt.get('Status','')).split(':')[-1]!='full':return None
        return {int(s['Y']):s['block_states'] for s in nbt['sections'] if 'block_states' in s}
    @lru_cache(180)
    def section(cx,cz,sy):
        column=chunk(cx,cz)
        if column is None:return np.zeros(4096,np.uint8),['<unobserved>']
        states=column.get(sy)
        return decode(states) if states is not None else (np.zeros(4096,np.uint8),['minecraft:air'])
    def state(x,y,z):
        ids,p=section(x//16,z//16,y//16)
        return p[ids[(y&15)*256+(z&15)*16+(x&15)]]
    return state

def load_runs(directory):
    runs=defaultdict(list)
    detached=set()
    index=directory/'index.json'
    paths=([directory/name for name in json.loads(index.read_bytes())] if index.exists() else sorted(directory.glob('r.*.npz')))
    for path in paths:
        rx,rz=map(int,path.stem.split('.')[1:])
        with np.load(path) as data:
            palette=data['palette'].tolist()
            for gid,col,lo,hi,mat,gap,near in data['rows'].tolist():
                x,z=rx*512+(col%512),rz*512+(col//512)
                runs[gid].append((x,z,lo,hi,palette[mat],gap,bool(near)))
                detached.update((x,y,z) for y in range(lo,hi+1))
    return runs,detached

def category(record):
    names=set(record['materials'])
    if all(n.endswith('_leaves') for n in names): return 'foliage'
    if all(n.endswith(('_leaves','_log','_wood')) for n in names): return 'tree'
    is_wild_rock = bool(names & {'minecraft:dirt','minecraft:grass_block'}) and names <= SOILS | PLANT | BOULDERS | {
        n for n in names if n.endswith(('_leaves','_log','_wood','_ore','_sapling'))}
    if is_wild_rock or all(n in SOILS or n in PLANT or n.endswith(('_leaves','_log','_wood','_ore','_sapling')) for n in names):
        return 'geology' if names & SOILS else 'plants' if names<=PLANT else 'vegetation'
    if 'minecraft:deepslate_tile_stairs' in names and all(n.startswith('minecraft:') and
           n.endswith(('_stairs','_slab','_planks','_fence','_log','_wood')) for n in names):
        return 'roof'
    return 'authored'

def points(runs):
    for x,z,lo,hi,name,_,_ in runs:
        for y in range(lo,hi+1):
            yield (x,y,z),name

def footings(runs):
    feet={}
    for x,z,lo,_,name,gap,_ in runs:
        if (x,z) not in feet or feet[x,z][0]>lo:
            feet[x,z]=(lo,gap,name)
    return feet

def canopy_bridge(runs,detached,state):
    for x,z,lo,hi,name,_,near in runs:
        if not near or not name.endswith('_leaves'):continue
        for y in range(lo,hi+1):
            for dx,dy,dz in NEIGHBORS:
                target=x+dx,y+dy,z+dz
                if target in detached or not bare(state(*target)).endswith(('_leaves','_log','_wood')):continue
                steps=[step for step in ((dx,0,0),(0,dy,0),(0,0,dz)) if any(step)]
                for order in permutations(steps):
                    path=[];p=(x,y,z)
                    for step in order[:-1]:
                        p=tuple(a+b for a,b in zip(p,step))
                        if state(*p) not in AIR:break
                        path.append(p)
                    else:
                        leaf=state(x,y,z).replace('waterlogged=true','waterlogged=false')
                        return [(p,state(*p),leaf) for p in path]
    return []

def attach_posts(runs,detached,state):
    result=[]
    for (x,z),(y,gap,_) in footings(runs).items():
        if not 1<=gap<=3:continue
        p=(x,y-gap-1,z);post=state(*p);name=bare(post)
        if name not in POSTS or p in detached or bare(state(x,p[1]-1,z))!=name:continue
        # Uprights support an inner roof member or intact eave. Extend the
        # same vertical post, without introducing new material on the street.
        if name.endswith(('_log','_wood')) and 'axis=y' not in post:continue
        void=[(x,h,z) for h in range(p[1]+1,y)]
        if all(state(*n) in AIR for n in void):
            result.extend((n,state(*n),post) for n in void)
    return result

def repair_tree(runs,detached,state):
    # A cut may leave the lowest leaf one block below the original trunk.
    # Use the lowest actual vertical log, including on sloping shorelines.
    cells={p:state(*p) for p,_ in points(runs)}
    if any('waterlogged=true' in name for name in cells.values()):return '',[]
    trunks={}
    for (x,y,z),v in cells.items():
        if bare(v).endswith(('_log','_wood')) and 'axis=y' in v:
            if (x,z) not in trunks or y<trunks[x,z][0]:trunks[x,z]=(y,v)
    offsets=sorted(product(range(-6,7),repeat=2),key=lambda d:d[0]**2+d[1]**2)
    for dx,dz in offsets:
        for (x,z),(y,trunk) in trunks.items():
            a,c=x+dx,z+dz
            for floor in range(y-1,y-55,-1):
                dest=a,floor,c;old=state(*dest)
                if old in AIR or dest in cells:continue
                # Cross dead foliage and water while finding a natural bank;
                # the final shifted silhouette itself must fit without clearing them.
                if bare(old) in ('minecraft:water','minecraft:grass','minecraft:tall_grass') or bare(old).endswith('_leaves'):continue
                break
            else:continue
            if dest in detached or bare(old) not in SOILS:continue
            drop=y-floor-1
            if dx==dz==0 and 0<drop<=4:
                stem=[(x,h,z) for h in range(floor+1,y)]
                if all(state(*p) in AIR or p in cells and bare(cells[p]).endswith('_leaves') for p in stem):
                    return 'root-tree',[(p,state(*p),trunk) for p in stem]
            shifted={(u+dx,v-drop,w+dz):name for (u,v,w),name in cells.items()}
            collisions={p for p in shifted if p not in cells and state(*p) not in AIR}
            # Preserve the substrate and adjacent trees. Lower leaves in a
            # terrain-facing crown can be pruned, but the trunk must fit intact.
            if len(collisions)>min(5,len(cells)//10) or any(not bare(shifted[p]).endswith('_leaves') for p in collisions):continue
            for p in collisions:del shifted[p]
            if not drop and dx==dz==0:continue
            edits=[]
            for p in cells.keys()|shifted.keys():
                old=cells[p] if p in cells else state(*p);new=shifted.get(p,'minecraft:air')
                if old!=new:edits.append((p,old,new))
            return 'lower-tree',edits
    return '',[]

def geology(runs,detached,natural_cells,state):
    feet=footings(runs)
    actual=Counter()
    for (x,z),(y,gap,n) in feet.items():
        if gap>256:continue
        p=(x,y-gap-1,z)
        if p in natural_cells:
            # Several old, cut topsoil skins can sit one above the next.
            # Follow this exact column through all nested debris to stable ground.
            for yy in range(p[1]-1,max(-1345,y-256),-1):
                p=x,yy,z
                if p in natural_cells or state(*p) in AIR:continue
                break
        if p in detached:continue
        contact=bare(state(*p))
        if state(x,y-1,z) not in AIR:actual['fluid_or_plant']+=1
        elif contact in SOILS | BOULDERS or contact.endswith('_ore'):actual['soil']+=1
        else:actual['other']+=1
    # A whole upper layer of topsoil can cover an intact second natural
    # surface. Submerged islands and man-made supports need separate review.
    if actual['soil'] and actual['soil']>=0.80*sum(actual.values()) and not actual['fluid_or_plant']:
        return 'remove-detached-earth'
    # The former lake cut can leave a vertical wafer of untouched stone,
    # dirt and grass standing entirely above open water. Keep broad islets
    # and shoals. Only remove a narrow, tall remnant above the waterline.
    levels=[(lo,hi) for _,_,lo,hi,*_ in runs]
    tall=max(hi for lo,hi in levels)-min(lo for lo,hi in levels)+1
    widths=[max(p[k] for p in feet)-min(p[k] for p in feet)+1 for k in (0,1)]
    names={n for x,z,lo,hi,n,g,b in runs}
    if tall>=9 and min(widths)<=2 and max(widths)<=5 and {'minecraft:grass_block','minecraft:dirt','minecraft:stone'}<=names:
        if all(state(x,y-1,z).startswith('minecraft:water[') for (x,z),(y,g,n) in feet.items()):
            return 'remove-detached-earth'
    return 'retain-ambiguous-earth'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('survey','regions','guard-world','out'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    state=load_reader(a.regions)
    gs=[load(a.guard_world) for load in (city_protection,lift_protection,launch_protection)]
    guards=defaultdict(list)
    for g in gs:
        for k,v in g.by_chunk.items():guards[k].extend(v)
    def guarded(p):
        x,y,z=p
        return any(b[0]<=x<=b[3] and b[1]<=y<=b[4] and b[2]<=z<=b[5] for _,b in guards.get((x//16,z//16),()))
    records=[json.loads(s) for s in (a.survey/'floating-groups.jsonl').read_text().splitlines()]
    runs,detached=load_runs(a.survey/'floating-runs')
    natural_cells={p for r in records if category(r) in ('geology','plants','vegetation','tree','foliage')
                   for p,_ in points(runs[r['id']])}
    records.sort(key=lambda r:(r['bounds'][0]//16,r['bounds'][2]//16,r['bounds'][1],r['id']))
    changed=defaultdict(dict);stats=Counter();footprint=Counter()
    decisions=a.out/'decisions.jsonl'
    with decisions.open('w',encoding='utf8') as audit:
        for i,r in enumerate(records):
            seq=runs[r['id']];c=category(r);action='retain-'+c;proposals=[]
            if c!='authored':
                if any(guarded(p) for p,_ in points(seq)):
                    action='retain-protected'
                elif c=='roof':
                    proposals=attach_posts(seq,detached,state)
                    if proposals:action='extend-roof-posts'
                elif c=='foliage':
                    proposals=canopy_bridge(seq,detached,state) if r['diagonal'] else []
                    action='join-canopy' if proposals else 'remove-detached-foliage'
                elif c=='tree':
                    action,proposals=repair_tree(seq,detached,state)
                    if not proposals and r['diagonal']:proposals=canopy_bridge(seq,detached,state)
                    if proposals and not action:action='join-canopy'
                    if not proposals:action='remove-detached-tree-debris'
                elif c=='geology':action=geology(seq,detached,natural_cells,state)
                elif c in ('plants','vegetation'):action='remove-detached-plants'
                if action.startswith('remove-'):
                    proposals=[(p,name,'minecraft:air') for p,name in points(seq)]
            if proposals and any(guarded(p) for p,old,new in proposals):
                action='retain-protected';proposals=[]
            if any(p in changed[p[0]//512,p[2]//512] and changed[p[0]//512,p[2]//512][p][:2]!=(old,new)
                   for p,old,new in proposals):
                if c=='foliage':
                    # Two cut crowns can each choose the same bridging air
                    # cell with different leaf states. Prune the later fragment.
                    action='remove-detached-foliage'
                    proposals=[(p,name,'minecraft:air') for p,name in points(seq)]
                else:action='retain-overlap';proposals=[]
            for p,old,new in proposals:changed[p[0]//512,p[2]//512][p]=(old,new,r['id'])
            stats[action]+=1;footprint[action]+=r['size']
            audit.write(json.dumps([r['id'],action,r['size'],len(proposals)],separators=(',',':'))+'\n')
            if i%10000==0:print(i,len(records),dict(stats),flush=True)
    for (rx,rz),d in changed.items():
        if not d:continue
        palette=sorted({n for old,new,_ in d.values() for n in (old,new)});ids={s:i for i,s in enumerate(palette)}
        rows=np.array([(x,y,z,ids[old],ids[new],g) for (x,y,z),(old,new,g) in sorted(d.items())],np.int32)
        np.savez_compressed(a.out/f'r.{rx}.{rz}.npz',rows=rows,palette=np.array(palette))
    summary=dict(groups=dict(stats),group_cells=dict(footprint),planned=sum(map(len,changed.values())),
                 regions=sum(bool(d) for d in changed.values()))
    (a.out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(summary,flush=True)

if __name__=='__main__':main()
