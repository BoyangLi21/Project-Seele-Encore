"""Find terminal branches in observed roads, then retain their 3D evidence.

The plan-view skeleton proposes inspection locations only. It does not connect
overpasses or authorize construction. Each proposal retains its actual floor.
"""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import convolve,binary_dilation,distance_transform_edt
from scipy.spatial import cKDTree
from map_pipeline.roads import layer_graph,keys


def complete_graph(a):
    from author_hakone_lakefront import Editor
    from repair_hakone_surface_ownership import load_grid
    from verify_hakone_network_candidate import PAVEMENT
    f=np.load(a.roads/'classification.npz');v=f['points'][f['retain']]
    d=load_grid(a.plan/'network.npz');iz,ix=np.where(d['walk']);x,z=ix+d['bounds'][0],iz+d['bounds'][1];g=d['grade2'][iz,ix]
    known=set(map(tuple,f['chunks']));saved=np.array([(int(px)//16,int(pz)//16)in known for px,pz in zip(x,z)])
    x,z,g=x[saved],z[saved],g[saved]
    existing=np.sort(keys(v[:,0],v[:,2],v[:,3]));k=keys(x,z,g+2);at=np.searchsorted(existing,k);found=at<len(existing);found[found]&=existing[at[found]]==k[found]
    x,z,g=x[~found],z[~found],g[~found];e=Editor(a.candidate);extra=[]
    regions={(int(px)//512,int(pz)//512)for px,pz in zip(x,z)}
    for rx,rz in sorted(regions):
        r=e.region(rx*512,rz*512)
        for j in np.flatnonzero((x//512==rx)&(z//512==rz)):
            px,pz,grade=map(int,(x[j],z[j],g[j]));y=(grade+1)//2
            state=e.state(px,y,pz);base=state.split('[')[0]
            if base not in PAVEMENT:continue
            fh=2*y+(1 if 'type=bottom'in state else 2)
            extra.append([px,y,pz,fh,int('asphalt'in base or base=='minecraft:black_concrete'),0,0,0])
        e.regions.clear()
    v=np.vstack((v,np.asarray(extra,np.int32)))if extra else v
    labels=layer_graph(v);size=np.bincount(labels);asphalt=np.bincount(labels,weights=v[:,4])
    lookup={(int(x),int(h),int(z)):int(c)for(x,y,z,h,*_),c in zip(v,labels)}
    report=json.loads((a.roads/'terminals.json').read_text('utf8'))
    for row in report['terminals']:
        x,y,z=row['endpoint'];c=lookup[x,int(2*y),z];row.update(component=c,component_size=int(size[c]))
        if 'target'in row:
            x,y,z=row['target'];k=lookup[x,int(2*y),z];row.update(target_component=k,target_component_size=int(size[k]))
            row['resolution']='same_3d_component'if c==k else 'decorative_boundary'if min(asphalt[c],asphalt[k])<25 else 'requires_3d_approach_review'
    from collections import Counter
    report['actual_floor_graph']=dict(supplemental_non_asphalt_pavement=len(extra),components=len(size),largest_components=sorted(map(int,size),reverse=True)[:12],resolution_counts=dict(Counter(r.get('resolution',r['classification'])for r in report['terminals'])))
    (a.roads/'terminals.json').write_text(json.dumps(report,indent=2),'utf8')
    np.savez_compressed(a.roads/'retained-components.npz',points=v,component=labels)
    print(report['actual_floor_graph'],flush=True)


def thin(mask):
    a=np.pad(mask,1).astype(np.uint8)
    while True:
        total=0
        for turn in (0,1):
            c=a[1:-1,1:-1]
            n=[a[:-2,1:-1],a[:-2,2:],a[1:-1,2:],a[2:,2:],a[2:,1:-1],a[2:,:-2],a[1:-1,:-2],a[:-2,:-2]]
            count=sum(n);trans=sum((n[i]==0)&(n[(i+1)%8]!=0)for i in range(8))
            remove=(c!=0)&(count>=2)&(count<=6)&(trans==1)
            if turn==0:remove&=(n[0]*n[2]*n[4]==0)&(n[2]*n[4]*n[6]==0)
            else:remove&=(n[0]*n[2]*n[6]==0)&(n[0]*n[4]*n[6]==0)
            total+=int(remove.sum());c[remove]=0
        if not total:return a[1:-1,1:-1].astype(bool)


def inspect(a):
    f=np.load(a.roads/'classification.npz');v=f['points'][f['retain']]
    x0,z0=v[:,[0,2]].min(0)-2;X,Z=v[:,[0,2]].max(0)+2
    mask=np.zeros((Z-z0+1,X-x0+1),bool);mask[v[:,2]-z0,v[:,0]-x0]=True
    if a.carriage_only:
        from repair_hakone_surface_ownership import load_grid,sampled
        paved=np.zeros_like(mask);p=v[v[:,4]!=0];paved[p[:,2]-z0,p[:,0]-x0]=True
        nearby=binary_dilation(paved,iterations=2)
        d=load_grid(a.plan/'network.npz');current=sampled(d,'road',v[:,0],v[:,2]).astype(bool)
        nearby[v[current,2]-z0,v[current,0]-x0]=True
        mask&=nearby
    radius=distance_transform_edt(mask)
    sk=thin(mask);degree=convolve(sk.astype(np.uint8),np.ones((3,3),np.uint8),mode='constant')-sk
    h=np.full(mask.shape,-10000,np.int16);np.maximum.at(h,(v[:,2]-z0,v[:,0]-x0),v[:,3])
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    coords=v[:,[0,2]];tree=cKDTree(coords);rows=[]
    for z,x in np.argwhere(sk&(degree==1)):
        branch=[(int(x),int(z))];prev=None;cur=branch[0]
        for _ in range(18):
            px,pz=cur;neighbors=[(px+dx,pz+dz)for dz in(-1,0,1)for dx in(-1,0,1)if(dx or dz)and sk[pz+dz,px+dx]and(px+dx,pz+dz)!=prev]
            if len(neighbors)!=1:break
            prev,cur=cur,neighbors[0];branch.append(cur)
        wx,wz=int(x+x0),int(z+z0);height=int(h[z,x]);y=height/2
        row=dict(endpoint=[wx,y,wz],branch_length=len(branch),classification='unresolved')
        row['branch_half_width']=float(np.median([radius[bz,bx]for bx,bz in branch]))
        if a.carriage_only and row['branch_half_width']<1.8:row['classification']='narrow_footway_or_paving';rows.append(row);continue
        if len(branch)<5:row['classification']='short_skeleton_spur';rows.append(row);continue
        vec=np.array(branch[0])-np.array(branch[-1]);vec=vec/np.linalg.norm(vec);row['outward']=vec.tolist()
        if any(bx-10<=wx<=bX+10 and bz-10<=wz<=bZ+10 and by-4<=y<=bY+4 for bx,by,bz,bX,bY,bZ in boxes):
            row['classification']='building_or_station_access';rows.append(row);continue
        # A proposed connection must face out from a terminal, remain at a
        # compatible height and cross a real gap, not its own rounded curb.
        ids=np.array(tree.query_ball_point([wx,wz],64),int)
        if len(ids):
            delta=coords[ids]-[wx,wz];distance=np.linalg.norm(delta,axis=1);along=delta@vec
            side=abs(delta[:,0]*vec[1]-delta[:,1]*vec[0]);dh=abs(v[ids,3]-height)/2
            valid=(along>9)&(side<8)&(dh<=distance*.22+1)
            for j in ids[valid][np.argsort(distance[valid])]:
                tx,tz=map(int,coords[j]);dx,dz=tx-wx,tz-wz;length=int(np.ceil(np.hypot(dx,dz)))
                xx=np.rint(np.linspace(wx,tx,length+1)).astype(int)-x0;zz=np.rint(np.linspace(wz,tz,length+1)).astype(int)-z0
                absent=~mask[zz,xx]
                if absent.sum()<3:continue
                row.update(classification='connection_candidate',target=[tx,float(v[j,3])/2,tz],gap_columns=int(absent.sum()))
                break
        rows.append(row)
    from collections import Counter
    result=dict(scope='all observed retained road layers',counts=dict(Counter(r['classification']for r in rows)),terminals=rows,
                note='Plan-view skeleton proposes cases; actual 3D width, structure ownership and terrain are required before writing. Unresolved endpoints are not counted as passed.')
    stem='carriage-terminals'if a.carriage_only else'terminals'
    (a.roads/(stem+'.json')).write_text(json.dumps(result,indent=2),'utf8')
    np.savez_compressed(a.roads/(stem+'-skeleton.npz'),bounds=[x0,z0,X,Z],skeleton=sk,height2=h)
    print(result['counts'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--roads',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--complete-graph',action='store_true');p.add_argument('--candidate',type=Path)
    p.add_argument('--carriage-only',action='store_true',help='Separate carriageway candidates from plot borders and narrow footways')
    a=p.parse_args();complete_graph(a)if a.complete_graph else inspect(a)
