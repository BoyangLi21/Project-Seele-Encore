"""Read current saved road surfaces, clearances and height-aware connectivity.

This audits the declared regional public-route frame, not every unregistered
road or underground rail in the world. Unknown/proto chunks remain unknown.
It does not write the save or turn the older plan into a completion claim.
"""
import argparse,json,collections
from pathlib import Path
import numpy as np
from scipy.ndimage import label,find_objects
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from query_blocks import AIR,chunk_statuses,iter_selected_sections
from install_r53_carrier_trays import stopped_world
from hakone_earthworks import road_blocks
from verify_hakone_network_candidate import PAVEMENT

def run(a):
    a.out.mkdir(parents=True,exist_ok=False)
    with np.load(a.authority/'network.npz')as f:d={k:f[k]for k in ('bounds','walk','road','grade2','tunnel')}
    x,z,X,Z=map(int,d['bounds']);zz,xx=np.nonzero(d['walk']);px,pz=xx+x,zz+z;h,slab=road_blocks(d['grade2'][zz,xx]);road=d['road'][zz,xx];count=len(xx)
    columns=collections.defaultdict(list)
    for i,(cx,cz)in enumerate(zip(px//16,pz//16)):columns[int(cx),int(cz)].append(i)
    columns={k:np.asarray(v,np.int32)for k,v in columns.items()};selection={k:set(((h[v,None]+np.arange(-1,5)[None])//16).ravel().tolist())for k,v in columns.items()}
    flags=np.zeros(count,np.uint8);seen=np.zeros(count,np.uint8);full=np.zeros(count,bool);examples=[];chunks=set();failure_materials=collections.Counter()
    # TrafficCraft roads sit on eighth layers, not half steps: a TrafficCraft block at the declared
    # floor is a floor, and so is clear air there over one, where the surface came down a little.
    lowered=np.zeros(count,bool);open_floor=np.zeros(count,bool)
    # Registry copies SMOOTH_STONE's full block shape for this native floor.
    floor_materials=PAVEMENT|{'projectseele:period_station_floor','projectseele:station_tactile_warning'}
    with stopped_world(a.world):
        statuses=chunk_statuses(a.world,'projectseele:geofront',columns)
        for key,v in columns.items():full[v]=statuses.get(key)=='full'
        print('Declared route columns',count,'FULL',int(full.sum()),'chunks',len(columns),flush=True)
        for cx,cz,sy,palette,ids in iter_selected_sections(a.world,'projectseele:geofront',selection,skip_unfinished=True):
            indexes=columns[cx,cz];bare=[s.split('[')[0]for s in palette];paved=np.array([s in floor_materials for s in bare]);empty=np.array([s in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}for s in bare]);bottom=np.array(['type=bottom'in s for s in palette])
            traffic=np.array([s.startswith('trafficcraft:')for s in bare]);layer=np.array([s.startswith('trafficcraft:')and'layers='in s for s in palette])
            q=indexes[(h[indexes]-1)//16==sy]
            if len(q):lowered[q]|=traffic[ids[((h[q]-1)%16)*256+(pz[q]%16)*16+px[q]%16]]
            for depth in range(5):
                q=indexes[((h[indexes]+depth)//16==sy)&((depth<3)|road[indexes])]
                if not len(q):continue
                at=((h[q]+depth)%16)*256+(pz[q]%16)*16+px[q]%16;state=ids[at];bit=1<<depth;seen[q]|=bit
                if depth==0:
                    okay=(paved[state]&(bottom[state]==slab[q]))|traffic[state];open_floor[q]|=empty[state]
                else:okay=empty[state]|(layer[state]if depth==1 else False)
                flags[q[okay]]|=bit
                for value,amount in zip(*np.unique(state[~okay],return_counts=True)):failure_materials['floor'if depth==0 else'headroom',bare[value]]+=int(amount)
                if len(examples)<300:
                    for i,v in zip(q[~okay][:8],state[~okay][:8]):examples.append(dict(pos=[int(px[i]),int(h[i]+depth),int(pz[i])],kind='floor-or-level'if depth==0 else'road-clearance'if road[i]else'pedestrian-clearance',state=palette[v]))
            if (cx,cz)not in chunks:
                chunks.add((cx,cz))
                if len(chunks)%1000==0:print('Read route chunks',len(chunks),'/',len(columns),flush=True)
    flags[lowered&open_floor]|=1
    required=np.where(road,31,7).astype(np.uint8)
    # In a confirmed FULL chunk, a missing section is canonical air. It is
    # allowed for headroom and still fails the required floor. Missing chunks
    # and proto chunks are never converted into air.
    flags[full]|=(~seen[full])&30
    floor_ok=full&((flags&1)!=0);body_ok=full&((flags&(required^1))==(required^1));valid=floor_ok&body_ok
    nodes=np.full(d['walk'].shape,-1,np.int32);nodes[zz[valid],xx[valid]]=np.arange(int(valid.sum()),dtype=np.int32);edges=[]
    for dz,dx in ((0,1),(1,0)):
        aa=np.s_[0:nodes.shape[0]-dz,0:nodes.shape[1]-dx];bb=np.s_[dz:nodes.shape[0],dx:nodes.shape[1]]
        ok=(nodes[aa]>=0)&(nodes[bb]>=0)&(abs(d['grade2'][aa].astype(np.int32)-d['grade2'][bb])<=1)
        edges.append((nodes[aa][ok],nodes[bb][ok]))
    u=np.concatenate([p[0]for p in edges]);v=np.concatenate([p[1]for p in edges]);n,labels=connected_components(coo_matrix((np.ones(len(u),np.uint8),(u,v)),shape=(int(valid.sum()),int(valid.sum()))).tocsr(),directed=False)
    sizes=np.bincount(labels);component=np.full(nodes.shape,-1,np.int32);component[zz[valid],xx[valid]]=labels
    goals=[]
    for row in json.loads((a.authority/'catalog.json').read_text('utf8')):
        pos=row.get('approach',row.get('door',row.get('entrance')))
        if not pos:continue
        gx,gy,gz=pos;gx,gz=round(gx),round(gz)
        if not(x<=gx<=X and z<=gz<=Z):continue
        candidates=[]
        for dz in range(-3,4):
            for dx in range(-3,4):
                j,i=gz-z+dz,gx-x+dx
                if 0<=j<nodes.shape[0]and 0<=i<nodes.shape[1]and nodes[j,i]>=0 and abs(float(d['grade2'][j,i])/2+1-gy)<=1.5:candidates.append((dx*dx+dz*dz,int(component[j,i]),[i+x,j+z]))
        q=min(candidates)if candidates else None
        goals.append(dict(id=row.get('id',row.get('label')),approach=pos,accessible_component=q[1]if q else None,matched_column=q[2]if q else None))
    bad=np.zeros(nodes.shape,bool);bad[zz[full&~valid],xx[full&~valid]]=True;groups,m=label(bad,np.ones((3,3),int));bs=np.bincount(groups.ravel());hotspots=[]
    for i,s in enumerate(find_objects(groups),1):
        if s is not None:hotspots.append(dict(columns=int(bs[i]),bounds_xz=[s[1].start+x,s[0].start+z,s[1].stop+x-1,s[0].stop+z-1]))
    hotspots.sort(key=lambda r:-r['columns'])
    report=dict(world=str(a.world),authority=str(a.authority),scope='declared regional public routes; original undeclared routes and native train envelopes require separate checks',bounds_xz=d['bounds'].tolist(),declared_columns=count,known_full_columns=int(full.sum()),unknown_columns=int((~full).sum()),floor_or_half_level_failures=int((full&~floor_ok).sum()),headroom_failures=int((full&~body_ok).sum()),valid_columns=int(valid.sum()),height_connected_components=n,largest_components=sorted(map(int,sizes),reverse=True)[:20],catalogued_goals=len(goals),goals_without_nearby_valid_approach=sum(q['accessible_component']is None for q in goals),clearance_metres=dict(pedestrian=2,road=4),hotspots=hotspots[:100],whole_map_acceptance=False,world_written=False)
    report['failed_cell_materials']=[dict(kind=k[0],state=k[1],cells=v)for k,v in failure_materials.most_common()]
    for name,value in [('audit.json',report),('destinations.json',goals),('obstacle-examples.json',examples)]:(a.out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf8')
    np.savez_compressed(a.out/'actual-routes.npz',bounds=d['bounds'],x=px,z=pz,grade2=d['grade2'][zz,xx],road=road,full=full,floor_ok=floor_ok,body_ok=body_ok,component=component)
    print(json.dumps({k:v for k,v in report.items()if k!='hotspots'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('world','authority','out'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
