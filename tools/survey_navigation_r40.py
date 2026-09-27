"""Independent measured circulation census, without the legacy route mask.

Components are evidence, not permissions to delete rooms or roofs. Static
cabins, controlled doors and partial collision shapes are reported explicitly.
"""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import label,find_objects
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from regional_voxels import canonical_state
from query_blocks import AIR

OUT=ROOT/'artifacts/world_combat_r40/navigation'
AREAS={
 'pyramid':((-90,-580,210),(170,-330,455),[-566,-461,-448,-434,-420,-406,-392,-378,-364]),
 'hangars':((-75,-474,-310),(185,-330,210),[-466,-442,-394,-370,-367]),
 'arrival':((-387,-474,714),(-326,-451,799),[-466]),
 'surface_lift':((104,68,243),(145,90,290)),
}

def survey(name):
    spec=AREAS[name];lo,hi=map(np.asarray,spec[:2]);dest=OUT/name;dest.mkdir(parents=True,exist_ok=True)
    w=MeasuredWorld();w.box(lo,hi);w.load()
    pal=['UNKNOWN','minecraft:air'];lut={s:i for i,s in enumerate(pal)}
    a=np.zeros(tuple((hi-lo+1)[[1,2,0]]),np.uint16)
    for (cx,cz),ys in w.selected.items():
        if w.status.get((cx,cz))!='full':continue
        for sy in ys:
            base=np.array([cx,sy,cz])*16;low=np.maximum(base,lo);high=np.minimum(base+15,hi)
            dst=tuple(slice(int(low[i]-lo[i]),int(high[i]-lo[i]+1)) for i in (1,2,0))
            src=tuple(slice(int(low[i]-base[i]),int(high[i]-base[i]+1)) for i in (1,2,0))
            data=w.tiles.get((cx,sy,cz))
            if data is None:a[dst]=1;continue
            palette,ids=data;mapping=[]
            for s in palette:
                if s not in lut:lut[s]=len(pal);pal.append(s)
                mapping.append(lut[s])
            a[dst]=np.asarray(mapping,np.uint16)[ids.reshape(16,16,16)[src]]
    shapes={canonical_state(s):bs for s,bs in json.loads((WORLD/'native_collision_shapes.json').read_text()).items()}
    missing=[];free=[];head=[];floor=[];stairs=[]
    for s in pal:
        n=s.partition('[')[0]
        bs=shapes.get(s)
        if bs is None:
            if n in AIR|{'minecraft:light'}:bs=[]
            elif n=='minecraft:ladder':bs=[[0,0,0,1,1,.125]]
            elif n=='mtr:escalator_step' and 'orientation=flat' in s:bs=[[0,0,0,1,.9375,1]]
            else:bs=[[0,0,0,1,1,1]];missing.append(s)
        def collision(height):return any(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<height for b in bs)
        wet=any(t in n for t in ('water','lava','lcl'))
        free.append(not collision(1) and not wet and s!='UNKNOWN')
        head.append(not collision(.8) and not wet and s!='UNKNOWN')
        supported=any(.90<=b[4]<=1.001 and b[0]<=.5<=b[3] and b[2]<=.5<=b[5] for b in bs)
        floor.append(supported and not any(t in s for t in ('_wall[','_fence[','_bars[','_sign[','station_departure_board','nerv_direction_panel','escalator_side','chair','stool','command_seat','UNKNOWN')))
        stairs.append('stairs' in s or 'escalator_step' in s)
    free,head,floor,stairs=map(np.asarray,(free,head,floor,stairs))
    walk=np.zeros(a.shape,bool);walk[1:-1]=floor[a[:-2]]&free[a[1:-1]]&head[a[2:]]
    enclosed=np.zeros(a.shape,bool)
    for dy in range(2,13):enclosed[:-dy]|=~free[a[dy:]]
    # Six-neighbour components describe each level separately. A stair or
    # lift is a separate connection to be proven, never an inferred teleport.
    components=[]
    for y in range(1,a.shape[0]-1):
        lab,n=label(walk[y]);sizes=np.bincount(lab.ravel());objects=find_objects(lab)
        for i,sl in enumerate(objects,1):
            if sizes[i]<12:continue
            zz,xx=sl;mask=lab[sl]==i
            components.append(dict(y=int(y+lo[1]),cells=int(sizes[i]),bounds=[int(xx.start+lo[0]),int(zz.start+lo[2]),int(xx.stop-1+lo[0]),int(zz.stop-1+lo[2])],roof_fraction=round(float(enclosed[y][sl][mask].mean()),3)))
    np.savez_compressed(dest/'measured.npz',blocks=a,palette=np.asarray(pal),walk=walk,lo=lo,hi=hi,free=free,head=head,support=floor,stairs=stairs)
    (dest/'components.json').write_text(json.dumps(dict(bounds=[lo.tolist(),hi.tolist()],measured_chunks=len(w.status),unknown_cells=int((a==0).sum()),walk_cells=int(walk.sum()),missing_collision_states=missing,components=components),ensure_ascii=False,indent=2),encoding='utf8')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    levels=spec[2] if len(spec)>2 else list(range(75,83))
    for Y in levels:
        y=Y-lo[1];view=np.zeros((*a.shape[1:],3),np.float32)+.08
        view[~free[a[y]]]=[.43,.45,.49];view[walk[y]]=[.25,.8,.7]
        door=np.asarray(['door' in s or 'elevator' in s or 'button_block' in s for s in pal]);view[door[a[y]]|door[a[y+1]]]=[1,.7,.1]
        view[a[y]==0]=[.8,.1,.3]
        fig,ax=plt.subplots(figsize=(13,11));ax.imshow(view,origin='lower',extent=[lo[0]-.5,hi[0]+.5,lo[2]-.5,hi[2]+.5]);ax.set_title(f'{name} | feet Y={Y} | teal: supported 1.8m clearance / orange: door or lift')
        ax.set_xlabel('X');ax.set_ylabel('Z (north is decreasing)');ax.set_xticks(np.arange(np.ceil(lo[0]/20)*20,hi[0]+1,20));ax.set_yticks(np.arange(np.ceil(lo[2]/20)*20,hi[2]+1,20));ax.grid(alpha=.25)
        fig.savefig(dest/f'floor_{Y}.png',dpi=125);plt.close(fig)
    print(name,'walk',int(walk.sum()),'components >=12 cells',len(components),'unknown',int((a==0).sum()),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('areas',nargs='*');args=ap.parse_args()
    for name in args.areas or AREAS:survey(name)
