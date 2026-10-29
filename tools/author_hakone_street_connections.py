"""Grade retired parcel edges and reconnect to measured existing public streets."""
import numpy as np


def grade_retired_edges(c,rows,cross,protected,frame,height):
    edge=np.where(cross,0,32).astype(np.int16)
    for _ in range(32):
        for dst,src in [(np.s_[1:,:],np.s_[:-1,:]),(np.s_[:-1,:],np.s_[1:,:]),
                        (np.s_[:,1:],np.s_[:,:-1]),(np.s_[:,:-1],np.s_[:,1:])]:
            edge[dst]=np.minimum(edge[dst],edge[src]+1)
    mask=np.zeros(cross.shape,bool)
    for r in rows:
        a,_,b,d,_,e=r['source_bounds_xyz'];mask[b-c.z0:e+1-c.z0,a-c.x0:d+1-c.x0]=True
    mask&=~cross&~protected&~frame
    t=np.clip(edge/24,0,1);target=np.rint(80+(height-80)*t*t*(3-2*t)).astype(int)
    c.layer(24,mask,'projectseele:nerv_structural_panel')
    for y in range(25,208):
        c.layer(y,mask&(y<target-3),'minecraft:stone')
        c.layer(y,mask&(y>=target-3)&(y<target),'minecraft:dirt')
        c.layer(y,mask&(y==target),'minecraft:grass_block[snowy=false]')
        c.layer(y,mask&(y>target),'minecraft:air')


def connect(c,protected,south_layout=False):
    # Endpoints are actual asphalt/centreline columns in the captured world,
    # not coordinates guessed from the former regional directory.
    routes=[('west', [(-310,200),(-318,200),(-318,176),(-344,176)],84),
            ('north',[(-50,40),(-110,40),(-110,-8)],80),
            ('south',[(30,560),(30,576)],80)]
    if south_layout:
        routes=[('west',[(-310,240),(-326,240),(-326,232),(-344,232)],84),
                ('north',[(-50,40),(-110,40),(-110,-8)],80),
                ('south',[(30,680),(30,688)],80)]
    paving={'minecraft:black_concrete','minecraft:white_concrete','minecraft:gray_concrete','minecraft:smooth_stone'}
    for name,anchors,end_y in routes:
        x,z=anchors[-1]
        actual=c.palette[int(c.before[end_y+128,z-c.z0,x-c.x0])].split('[')[0]
        if actual not in paving:raise ValueError(f'Unmeasured street endpoint {name}: {(x,end_y,z)} {actual}')
    result=[]
    for name,anchors,end_y in routes:
        path=[]
        for a,b in zip(anchors,anchors[1:]):
            n=max(abs(a[0]-b[0]),abs(a[1]-b[1]))
            path.extend((round(a[0]+(b[0]-a[0])*i/n),round(a[1]+(b[1]-a[1])*i/n))for i in range(n))
        path.append(anchors[-1]);levels=np.rint(np.linspace(80,end_y,len(path))).astype(int)
        pindex={p:i for i,p in enumerate(path)};cells={};distance={}
        for i,(x,z)in enumerate(path):
            for dz in range(-4,5):
                for dx in range(-4,5):
                    q=x+dx,z+dz
                    if not(c.x0<=q[0]<c.x0+c.blocks.shape[2]and c.z0<=q[1]<c.z0+c.blocks.shape[1]):continue
                    if protected[q[1]-c.z0,q[0]-c.x0]:
                        if q==(x,z):raise ValueError(f'Public street interface enters a preserved device: {name} {q}')
                        continue
                    d=max(abs(dx),abs(dz))
                    if d<distance.get(q,99):distance[q]=d;cells[q]=int(levels[pindex[q]]if q in pindex else levels[i])
        for (x,z),y in cells.items():
            c.fill(x,25,z,x,y-1,z,'minecraft:stone')
            c.put(x,y,z,'minecraft:gray_concrete'if distance[x,z]<=2 else 'minecraft:smooth_stone')
            c.fill(x,y+1,z,x,y+4,z,'minecraft:air')
        for i in range(1,len(path)):
            if levels[i]==levels[i-1]:continue
            hi=i if levels[i]>levels[i-1]else i-1;lo=i-1 if hi==i else i
            x,z=path[hi];dx=x-path[lo][0];dz=z-path[lo][1]
            facing={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}[dx,dz]
            for side in range(-4,5):
                q=x-dz*side,z+dx*side
                if q not in cells or cells[q]!=levels[hi]or(q in pindex and pindex[q]!=hi):continue
                block='polished_blackstone_stairs'if abs(side)<=2 else 'stone_brick_stairs'
                c.put(q[0],int(levels[hi]),q[1],f'minecraft:{block}[facing={facing},half=bottom,shape=straight,waterlogged=false]')
        result.append(dict(id=name,source_street_endpoint=[*anchors[-1]],points=[[x,int(y)+1,z]for (x,z),y in zip(path,levels)]))
    return result
