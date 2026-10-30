"""Fit offline, full-width street links around retained three-dimensional works."""
import argparse,heapq,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageFilter
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import NATURAL


def fit(folder,pending_only=False):
    with np.load(folder/'district-surface.npz')as f:d={k:f[k]for k in('bounds','target','walk')}
    x0,z0,x1,z1=map(int,d['bounds']);shape=d['target'].shape
    houses=np.zeros(shape,bool)
    for row in json.loads((folder/'neighbourhood.json').read_text('utf8')):
        s=row['site'];x,z=s['centre'];hx,hz=s['half']
        if s['rotation']%2:hx,hz=hz,hx
        houses[z-hz-z0-3:z+hz-z0+4,x-hx-x0-3:x+hx-x0+4]=True
    work=json.loads((folder/'road-detours.json').read_text('utf8'))['retained_frontages'];plans=[]
    previous=[]
    if pending_only:
        work=json.loads((folder/'functional-check.json').read_text('utf8'))['subsurface_ports_pending']
        work=[{k:r[k]for k in('start','end','reason')}for r in work]
        previous=json.loads((folder/'retained-port-profiles.json').read_text('utf8'))
    retained=json.loads((folder/'retained-road-grades.json').read_text('utf8'))['anchors']
    anchors=[r['point']for r in retained if d['walk'][r['point'][2]-z0,r['point'][0]-x0]
             and abs(int(d['target'][r['point'][2]-z0,r['point'][0]-x0])-r['point'][1])<=1]
    replaceable={'minecraft:stone','minecraft:black_concrete','minecraft:white_concrete','minecraft:smooth_stone'}
    floors=replaceable|{'minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:stone_bricks','minecraft:polished_andesite'}
    for record in work:
        endpoints=[]
        for x,z in(record['start'],record['end']):
            pixels=np.argwhere(d['walk'][z-z0-12:z-z0+13,x-x0-12:x-x0+13])
            if not len(pixels):raise ValueError('No retained street endpoint '+str((x,z)))
            iz,ix=min(pixels,key=lambda q:(q[0]-12)**2+(q[1]-12)**2)
            X,Z=x+int(ix)-12,z+int(iz)-12;endpoints.append((X,int(d['target'][Z-z0,X-x0]),Z))
        start,goal=endpoints;result=None
        for pad in(32,64):
            left=max(x0,min(start[0],goal[0])-pad);right=min(x1,max(start[0],goal[0])+pad)
            top=max(z0,min(start[2],goal[2])-pad);bottom=min(z1,max(start[2],goal[2])+pad)
            low=max(32,min(start[1],goal[1])-20);high=min(290,max(start[1],goal[1])+20)
            height=high-low+1;size=(bottom-top+1,right-left+1)
            natural=np.zeros((height+6,*size),bool);floor_ok=np.zeros((height,*size),bool);e=Editor(folder)
            for cx in range(left//16,right//16+1):
                for cz in range(top//16,bottom//16+1):
                    r=e.region(cx*16,cz*16);names=r['names'];b=r['after'][r['index'][cx,cz]]
                    nat=np.asarray([s.split('[')[0]in NATURAL for s in names]);fl=np.asarray([s.split('[')[0]in floors for s in names]);pav=np.asarray([s in replaceable for s in names])
                    X,Z=max(left,cx*16),max(top,cz*16);R,B=min(right,cx*16+15),min(bottom,cz*16+15)
                    ys=np.arange(low,high+7)[:,None,None];local=np.s_[low+128:high+135,Z%16:Z%16+B-Z+1,X%16:X%16+R-X+1]
                    col=b[local];dest=np.s_[:,Z-top:B-top+1,X-left:R-left+1];area=np.s_[Z-z0:B-z0+1,X-x0:R-x0+1]
                    allowed=nat[col]|(d['walk'][area]&(ys>=d['target'][area]-1)&(ys<=d['target'][area])&pav[col])
                    natural[dest]=allowed;floor_ok[dest]=nat[col[:height]]|fl[col[:height]]
                # Local search never needs to retain another region's full data.
                if len(e.regions)>2:e.regions.clear()
            del e
            valid=floor_ok.copy()
            for dy in range(1,6):valid&=natural[dy:dy+height]
            forbidden=houses[top-z0:bottom-z0+1,left-x0:right-x0+1]
            for i in range(height):
                bad=np.asarray(Image.fromarray((~valid[i]|forbidden)).filter(ImageFilter.MaxFilter(7)),bool)
                valid[i]=~bad
            Z,X=np.mgrid[top:bottom+1,left:right+1]
            for ax,ay,az in anchors+endpoints:
                if left-40<=ax<=right+40 and top-40<=az<=bottom+40:
                    valid&=np.abs(np.arange(low,high+1)[:,None,None]-ay)<=(np.abs(X-ax)+np.abs(Z-az))
            valid[:,:3,:]=False;valid[:,-3:,:]=False;valid[:,:,:3]=False;valid[:,:,-3:]=False
            start=(start[0],start[1],start[2]);goal=(goal[0],goal[1],goal[2])
            if not valid[start[1]-low,start[2]-top,start[0]-left]or not valid[goal[1]-low,goal[2]-top,goal[0]-left]:
                continue
            def heuristic(p):return max(abs(p[0]-goal[0])+abs(p[2]-goal[2]),abs(p[1]-goal[1]))
            queue=[(heuristic(start),0,start)];cost={start:0};parent={}
            while queue:
                _,g,p=heapq.heappop(queue)
                if g!=cost[p]:continue
                if p==goal:
                    result=[p]
                    while p in parent:p=parent[p];result.append(p)
                    result.reverse();break
                for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                    x,z=p[0]+dx,p[2]+dz
                    if not left<=x<=right or not top<=z<=bottom:continue
                    for dy in(0,-1,1):
                        y=p[1]+dy
                        if not low<=y<=high or not valid[y-low,z-top,x-left]:continue
                        q=(x,y,z);ng=g+1+.025*abs(y-int(d['target'][z-z0,x-x0]))+.05*abs(dy)
                        if ng<cost.get(q,math.inf):cost[q]=ng;parent[q]=p;heapq.heappush(queue,(ng+heuristic(q),ng,q))
                if len(cost)>400000:break
            if result:break
        plans.append(dict(**record,points=result or [],width=3,walk_width=7))
        print(record['start'],record['end'],'fitted points',len(result or []),flush=True)
    replaced={(tuple(r['start']),tuple(r['end']))for r in plans}
    plans.extend(r for r in previous if(tuple(r['start']),tuple(r['end']))not in replaced)
    (folder/'retained-port-profiles.json').write_text(json.dumps(plans,indent=2),'utf8')
    if any(not r['points']for r in plans):raise ValueError('Some retained interfaces still need an explicit street design')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('candidate',type=Path);p.add_argument('--pending-only',action='store_true')
    a=p.parse_args();fit(a.candidate,a.pending_only)
