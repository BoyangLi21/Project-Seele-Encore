"""Measured landscape design around whole public courts, with real outer anchors.

Emits a height-field proposal only. Never writes blocks, providers or worlds.
Known buildings, roads, trees, inventories and water remain separate objects.
"""
from pathlib import Path
from collections import Counter
import argparse,json,hashlib,heapq
import numpy as np
from scipy.ndimage import distance_transform_edt
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1]
SOIL={'minecraft:'+n for n in ['grass_block','dirt','coarse_dirt','rooted_dirt','stone','gravel','sand','clay','sandstone','mud']}
SMALL={'minecraft:'+n for n in ['grass','tall_grass','fern','large_fern','dandelion','poppy','azure_bluet','oxeye_daisy','cornflower','blue_orchid','lily_of_the_valley']}

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('output',type=Path);p.add_argument('--margin',type=int,default=64);p.add_argument('--public-datums',type=Path)
    a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    parcels=json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'))
    columns={tuple(r['pos']):r for r in parcels['columns']}
    roads={tuple(r['pos']):r['native_feet'] for r in json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']}
    x0=min(x for x,z in columns)-a.margin;x1=max(x for x,z in columns)+a.margin
    z0=min(z for x,z in columns)-a.margin;z1=max(z for x,z in columns)+a.margin
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((x0,32,z0),(x1,159,z1));w.load()
    shape=(z1-z0+1,x1-x0+1);soil=np.full(shape,-32768,np.int16);water=soil.copy();wood=np.zeros(shape,bool);foreign=wood.copy();body=wood.copy();full=wood.copy()
    for (cx,sy,cz),(pal,ids) in w.tiles.items():
        ax,bx=max(x0,cx*16),min(x1,cx*16+15);az,bz=max(z0,cz*16),min(z1,cz*16+15)
        if ax>bx or az>bz:continue
        data=ids.reshape(16,16,16)[:,az-cz*16:bz-cz*16+1,ax-cx*16:bx-cx*16+1]
        dest=slice(az-z0,bz-z0+1),slice(ax-x0,bx-x0+1);yy=np.arange(16)[:,None,None]+sy*16;names=[s.split('[')[0] for s in pal]
        soil[dest]=np.maximum(soil[dest],np.where(np.array([n in SOIL for n in names])[data],yy,-32768).max(0))
        water[dest]=np.maximum(water[dest],np.where(np.array([n=='minecraft:water' for n in names])[data],yy,-32768).max(0))
        wood[dest]|=np.array([n.endswith(('_log','_leaves')) for n in names])[data].any(0)
        foreign[dest]|=np.array([n not in SOIL|SMALL|{'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water'} and not n.endswith(('_log','_leaves')) for n in names])[data].any(0)
    for z in range(z0,z1+1):
        for x in range(x0,x1+1):full[z-z0,x-x0]=w.status.get((x//16,z//16))=='full'
    def mark(bounds):
        bx,bz,bX,bZ=bounds
        if bx>x1 or bX<x0 or bz>z1 or bZ<z0:return
        body[max(0,bz-z0):min(shape[0],bZ-z0+1),max(0,bx-x0):min(shape[1],bX-x0+1)]=True
    for b in district['buildings']:mark(b['bounds'])
    ownership=ROOT/'artifacts/rebuild_r44/city_buildings/actual_authored_ownership.json'
    for b in json.loads(ownership.read_text('utf8'))['buildings']:
        lo,hi=b['planned_bounds'];mark([lo[0]-1,lo[2]-1,hi[0]+1,hi[2]+1])
    tags=dict(iter_block_entities(w.world,w.dimension,(x0,32,z0),(x1,159,z1),selected_chunks=set(w.selected)))
    for x,y,z in tags:body[z-z0,x-x0]=True
    core=np.zeros(shape,bool)
    for x,z in columns:core[z-z0,x-x0]=True
    distance=distance_transform_edt(~core)
    natural=full&(soil>-32768)&(~body)&(~foreign)&(~wood)&(water==-32768)&(distance<=a.margin)
    # Existing authored garden is a design variable; public courts and actual
    # streets are fixed. The new outer ring inherits measured native contours.
    garden={q for q,r in columns.items() if r['role'].startswith('graded_')}
    public={q:r['feet'] for q,r in columns.items() if q not in garden};public.update(roads)
    if a.public_datums:public.update({tuple(r['pos']):r['feet']for r in json.loads(a.public_datums.read_text('utf8'))['solved_columns']})
    nodes={(int(i+x0),int(j+z0)) for j,i in zip(*np.where(natural))}|garden
    nodes-=set(public)
    seeds={};anchors=[];water_edges=[];retained_interfaces=[]
    for x,z in nodes:
        q=x,z;j,i=z-z0,x-x0
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            n=x+dx,z+dz;nj,ni=n[1]-z0,n[0]-x0
            tolerance=1
            if n in public:
                value=public[n]
                if distance[j,i]>32:tolerance=max(1,abs(int(soil[j,i]+1)-value))
                anchors.append(dict(pos=q,neighbour=n,feet=value,kind='PUBLIC',allowed_original_remote_edge=tolerance))
            elif n not in nodes and 0<=nj<shape[0] and 0<=ni<shape[1]:
                if wood[nj,ni] and soil[nj,ni]>-32768:
                    value=int(soil[nj,ni]+1)
                    anchors.append(dict(pos=q,neighbour=n,feet=value,kind='WHOLE_RETAINED_TREE_ROOT_DATUM'))
                elif body[nj,ni] or foreign[nj,ni]:
                    retained_interfaces.append(dict(pos=q,neighbour=n,kind='RETAINED_COMPLETE_COMPONENT'));continue
                elif water[nj,ni]>=soil[nj,ni] and water[nj,ni]>-32768:
                    water_edges.append(dict(pos=q,neighbour=n,water_feet=int(water[nj,ni]+1)));continue
                elif full[nj,ni] and soil[nj,ni]>-32768:
                    value=int(soil[nj,ni]+1)
                    # Original remote cliffs are not new garden lips. Preserve
                    # their measured edge magnitude; do not require the entire
                    # countryside to become a one-metre staircase.
                    tolerance=max(1,abs(int(soil[j,i]+1)-value))
                    anchors.append(dict(pos=q,neighbour=n,feet=value,kind='MEASURED_OUTER_CONTOUR',allowed_original_edge=tolerance))
                else:retained_interfaces.append(dict(pos=q,neighbour=n,kind='UNKNOWN'));continue
            else:continue
            # Constraint allows one metre from this neighboring fixed datum.
            lo=int(np.ceil(value-tolerance-1e-6));hi=int(np.floor(value+tolerance+1e-6))
            if q not in seeds:seeds[q]=[lo,hi]
            else:seeds[q]=[max(lo,seeds[q][0]),min(hi,seeds[q][1])]
    def edge_cost(q,n):
        j,i=q[1]-z0,q[0]-x0;J,I=n[1]-z0,n[0]-x0
        if min(distance[j,i],distance[J,I])<=32:return 1
        return max(1,abs(int(soil[j,i])-int(soil[J,I])))
    def envelope(values):
        field=dict(values);queue=[(h,q) for q,h in field.items()];heapq.heapify(queue)
        while queue:
            h,q=heapq.heappop(queue)
            if field[q]!=h:continue
            for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
                n=q[0]+dx,q[1]+dz
                if n not in nodes:continue
                H=h+edge_cost(q,n)
                if H<field.get(n,10**9):field[n]=H;heapq.heappush(queue,(H,n))
        return field
    upper=envelope({q:h[1] for q,h in seeds.items()});negative=envelope({q:-h[0] for q,h in seeds.items()})
    lower={q:-h for q,h in negative.items()};anchored=set(upper)&set(lower)
    shore_caps={};shore_structural_obligations=[]
    for edge in water_edges:
        q=tuple(edge['pos']);j,i=q[1]-z0,q[0]-x0
        # Retain an original natural bank, or meet the lake gently. Never
        # create a higher dry bank solely from the garden solver. A fixed
        # public terrace too close to water needs actual retaining structure.
        cap=max(int(soil[j,i]+1),edge['water_feet']+1)
        if q in lower and lower[q]>cap:
            shore_structural_obligations.append(dict(edge,minimum_terrace_feet=lower[q],natural_bank_cap=cap));continue
        shore_caps[q]=min(shore_caps.get(q,10**9),cap)
    if shore_caps:
        upper_seeds={q:h[1]for q,h in seeds.items()}
        for q,h in shore_caps.items():upper_seeds[q]=min(h,upper_seeds.get(q,h))
        upper=envelope(upper_seeds)
        anchored=set(upper)&set(lower)
    infeasible=[dict(pos=q,lower=lower[q],upper=upper[q]) for q in anchored if lower[q]>upper[q]]
    solved={};changes=[]
    if not infeasible:
        initial={q:max(lower[q],min(upper[q],int(soil[q[1]-z0,q[0]-x0])+1)) for q in anchored}
        cut=envelope(initial);fill={q:-h for q,h in envelope({q:-h for q,h in initial.items()}).items()}
        # A pure lower envelope lets every old dry pit flatten all neighboring
        # hills. Balance feasible cut and fill around the actual contour;
        # both fields obey the same fixed ports and full edge constraints.
        solved={q:int(np.floor((cut[q]+fill[q])/2+.5)) for q in cut}
        assert all(lower[q]<=h<=upper[q] for q,h in solved.items())
        assert all(abs(h-solved[n])<=edge_cost(q,n) for q,h in solved.items() for n in [(q[0]+1,q[1]),(q[0],q[1]+1)] if n in solved)
        for q,h in solved.items():
            old=columns[q]['feet'] if q in columns else int(soil[q[1]-z0,q[0]-x0])+1
            if h!=old:changes.append(dict(pos=q,before_feet=old,proposed_feet=h,owner=columns[q]['owner'] if q in columns else 'r44/kirisato/whole_natural_transition',purpose='graded_garden_edge'))
    after=soil.copy()
    for (x,z),h in solved.items():after[z-z0,x-x0]=h-1
    np.savez_compressed(a.output/'whole_landscape_heightfield.npz',origin=[x0,z0],before=soil,after=after,water=water,wood=wood,foreign=foreign,body=body,full=full,core=core)
    result=dict(source=str(a.plan.resolve()),margin_metres=a.margin,whole_bounds=[x0,32,z0,x1,159,z1],infeasible=infeasible,
                measured_natural_columns=int(natural.sum()),public_fixed_columns=len(public),solved_columns=len(solved),changed_garden_columns=changes,
                solved_garden_columns=[dict(pos=q,feet=h) for q,h in sorted(solved.items())],anchors=anchors,water_edges=water_edges,
                retained_interfaces=retained_interfaces,shore_structural_obligations=shore_structural_obligations,world_written=False,root_apply_ready=False,
                original_remote_edge_policy='Within 32m of whole parcels every adjoining natural column is limited to 1m; beyond that original measured cliff magnitude is retained as the edge limit, never increased.',
                pending='Exact material/transport checks and whole component tree/structure/shore design; a design field is not construction.',
                producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (a.output/'whole_landscape_design.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Whole landscape:',len(nodes),'nodes;',len(infeasible),'infeasible;',len(changes),'changes; water edges',len(water_edges),'NO WORLD WRITE',flush=True)

if __name__=='__main__':main()
