"""Read-only full-width street routes in the actual raised city, never excavation."""
import collections,json,math
from pathlib import Path
import numpy as np
from scipy.ndimage import maximum_filter,minimum_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure

def main():
    out=BASE/'surface_angel_routes';out.mkdir(exist_ok=True)
    lo=(-230,80,-460);hi=(230,145,440);cache=out/'ACTUAL_RAISED_CITY.npz'
    if cache.exists():
        d=np.load(cache);a=d['states'];names=list(map(str,d['palette']));assert tuple(d['origin'])==lo
    else:
        a,names=measure(lo,hi);np.savez_compressed(cache,states=a,palette=names,origin=lo)
    # Treat unknown/partial solids conservatively. Only demonstrably empty
    # air, nonphysical grass and flowers are ignored in the 60m body corridor.
    free={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:grass','minecraft:fern','minecraft:dandelion','minecraft:poppy'}
    hard=np.asarray([s not in free for s in names]);blocked=hard[a[1:61]].any(axis=0)
    ground=np.asarray([s not in free and not any(t in s for t in('water','lava','slab','stairs','fence','wall['))for s in names])[a[0]]
    ground=minimum_filter(ground.astype(np.uint8),size=7,mode='constant',cval=0)>0
    fig,axes=plt.subplots(1,2,figsize=(13,10));reports=[]
    for ax,(name,width)in zip(axes,[('sachiel',18),('shamshel',20)]):
        clear=(maximum_filter(blocked.astype(np.uint8),size=width+1,mode='constant',cval=1)==0)&ground
        target=(355-lo[2],10-lo[0]);assert clear[target],(name,'proposed west street endpoint blocked')
        previous={target:None};queue=collections.deque([target])
        while queue:
            z,x=queue.popleft()
            for dz,dx in((1,0),(-1,0),(0,1),(0,-1)):
                q=(z+dz,x+dx)
                if 0<=q[0]<clear.shape[0]and 0<=q[1]<clear.shape[1]and clear[q]and q not in previous:previous[q]=(z,x);queue.append(q)
        candidates=[p for p in previous if math.hypot(p[0]-target[0],p[1]-target[1])>=350]
        report=dict(chapter=name,world_written=False,body_width=width,body_height=60,contact_patch=7,valid_component_cells=len(previous),remote_candidates=len(candidates),endpoint=[10.5,81,355.5])
        path=[]
        if candidates:
            start=min(candidates,key=lambda p:p[0]+abs(p[1]-target[1])*.25)if name=='sachiel'else min(candidates,key=lambda p:(-p[1],p[0]))
            q=start
            while q is not None:path.append(q);q=previous[q]
            # Keep every corner and bounded 8m links; no diagonal corner cut.
            chosen=[path[0]]
            for i in range(1,len(path)-1):
                direction=(path[i+1][0]-path[i][0],path[i+1][1]-path[i][1]);before=(path[i][0]-path[i-1][0],path[i][1]-path[i-1][1])
                if direction!=before or math.dist(path[i],chosen[-1])>=8:chosen.append(path[i])
            if chosen[-1]!=path[-1]:chosen.append(path[-1])
            report['route']=[[x+lo[0]+.5,81,z+lo[2]+.5]for z,x in chosen];report['spawn']=report['route'][0]
            report['distance']=len(path)-1
        ax.imshow(np.where(clear,1,np.where(blocked,0,.45)),origin='lower',extent=[lo[0],hi[0]+1,lo[2],hi[2]+1],cmap='gray',vmin=0,vmax=1)
        if path:ax.plot([p[1]+lo[0]+.5 for p in path],[p[0]+lo[2]+.5 for p in path],color='#ee6611',linewidth=2)
        ax.scatter([30.5],[355.5],color='red',s=20);ax.set_title(f'{name}: {len(path)} measured street metres');ax.set_xlabel('X');ax.set_ylabel('Z')
        reports.append(report)
    fig.tight_layout();fig.savefig(out/'ACTUAL_STREET_ROUTES.png',dpi=150);plt.close(fig)
    (out/'READ_ONLY_ROUTES.json').write_text(json.dumps(reports,indent=2),'utf8');print(json.dumps([{k:v for k,v in r.items()if k!='route'}for r in reports]),flush=True)

if __name__=='__main__':main()
