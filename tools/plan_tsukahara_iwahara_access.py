"""Route three-wide station footways using exact old blocks and street grades."""
import argparse,json,heapq,math
from pathlib import Path
import numpy as np
from scipy import ndimage
from shapely import intersects_xy
from shapely.geometry import shape,box,Point,LineString,mapping
from shapely.ops import unary_union
from shapely.prepared import prep
from author_hakone_lakefront import Editor
from author_kamonomiya_station import voxel_box
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from evaluate_tsukahara_iwahara_geometry import envelope

ALLOWED=SOIL|AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=lambda x:x.item()),'utf8')

def main(a):
    a.out.mkdir(exist_ok=False);e=Editor(a.source);capture=json.loads((a.source/'capture.json').read_text('utf8'));x,z,X,Z=capture['bounds_xz'];low,high=-84,-64
    arr,pal=voxel_box(e,[x,low,z,X,high,Z]);natural=np.asarray([s.split('[')[0]in ALLOWED for s in pal]);air=np.asarray([s.split('[')[0]in AIR|{'minecraft:light'}for s in pal]);yy=np.arange(low,high+1)[:,None,None]
    terrain=np.load(a.source/'measured.npz')['top']
    evidence=json.loads((a.geometry/'site-evidence.json').read_text('utf8'));review=json.loads(a.edges.read_text('utf8'));chosen=next(v for v in review['variants']if v['variant']==a.variant)
    samples={r['id']:r for r in json.loads((a.geometry/'native-samples.json').read_text('utf8'))};full=LineString(np.concatenate([np.asarray(samples[k]['points'])[:,[0,2]]if i==0 else np.asarray(samples[k]['points'])[1:,[0,2]]for i,k in enumerate(chosen['native_segments'])]));sweep=envelope(full)
    with np.load(a.authority/'network.npz')as f:
        ax,az,*_=f['bounds'];public=f['walk'][z-az:Z-az+1,x-ax:X-ax+1];grades=f['grade2'][z-az:Z-az+1,x-ax:X-ax+1]
    features={f['index']:f for s in evidence['stations']for f in s['nearby_gis']};water=unary_union([shape(f['geometry'])for f in features.values()if f['properties']['source_layer']in('WA','RvrCL','WStrL')]).buffer(3)
    zz,xx=np.mgrid[z:Z+1,x:X+1];wet=np.zeros(public.shape,bool);rail=np.zeros(public.shape,bool);water_query=prep(water);rail_query=prep(sweep.buffer(.08))
    for iz,ix in np.ndindex(public.shape):
        cube=box(x+ix,z+iz,x+ix+1,z+iz+1)
        wet[iz,ix]=water_query.intersects(cube);rail[iz,ix]=rail_query.intersects(cube)
    held=((~natural[arr])&(yy>=-79)&(yy<=-68)).any(0)&~public
    available=~(held|rail|(wet&~public))&(terrain>=-80)&(terrain<=-71)
    # All source-column changes stay outside the water strip. Existing public
    # bridge/walk columns are retained exactly, if an access path reaches them.
    safe=ndimage.minimum_filter(available.astype(np.uint8),size=3,mode='constant',cval=0).astype(bool)
    street=np.zeros(public.shape,bool)
    for iz,ix in np.argwhere(public):
        g=int(grades[iz,ix]);floor=(g+1)//2
        if not low<=floor<=high-3:continue
        state=e.state(x+int(ix),floor,z+int(iz))
        bearing=state in('minecraft:smooth_stone','minecraft:stone_bricks','minecraft:gray_concrete','minecraft:white_concrete','minecraft:light_gray_concrete','minecraft:black_concrete')or'slab[type=bottom'in state
        if bearing and air[arr[floor-low+1:floor-low+4,iz,ix]].all():street[iz,ix]=True
    results=[]
    for s in chosen['stations']:
        line=np.asarray(samples[s['rail_id']]['points'])[:,[0,2]];c=(line[0]+line[-1])/2;u=line[-1]-line[0];u/=np.linalg.norm(u);n=np.array([-u[1],u[0]])
        side=(xx+.5-c[0])*n[0]+(zz+.5-c[1])*n[1]
        # The shared railway curves between the stations: a global straight
        # half-plane incorrectly disconnects the real western bank. Its exact
        # swept obstacle, plus bounded ends, defines which side remains usable.
        allowed=safe&(zz>=-788)&(zz<=-651)
        start=[]
        for px,pz in s['platform_columns']:
            d=(np.asarray([px+.5,pz+.5])-c)@n;t=(np.asarray([px+.5,pz+.5])-c)@u
            if 4.2<d<6.5 and abs(t)<9 and allowed[pz-z,px-x]:start.append((px-x,pz-z))
        goals={tuple([int(ix),int(iz)])for iz,ix in np.argwhere(street&allowed)}
        heap=[];cost={};prev={}
        for q in start:cost[q]=0;prev[q]=None;heapq.heappush(heap,(0,q))
        reached=None;bridge=None;special={}
        if s['name']=='岩原駅':
            west=(2729-x,-685-z);east=(2744-x,-685-z)
            if not allowed[west[1],west[0]]or not allowed[east[1],east[0]]:raise ValueError('Bridge banks are not clear of the water buffer and protected objects')
            special={west:east,east:west}
            bridge=dict(west_bank_xz=[2729,-685],east_bank_xz=[2744,-685],walk_z=[-686,-684],girder_z=[-687,-683],deck_floor_y=-72,beam_bottom_y=-73,clear_span_metres=14,piers_outside_water_buffer=True,existing_channel_surface_preserved=True)
        while heap:
            value,q=heapq.heappop(heap)
            if value!=cost[q]:continue
            if q in goals:reached=q;break
            moves=[(q[0]+dx,q[1]+dz)for dx,dz in((1,0),(-1,0),(0,1),(0,-1))]
            if q in special:moves.append(special[q])
            for Q in moves:
                if not 0<=Q[0]<allowed.shape[1]or not 0<=Q[1]<allowed.shape[0]or not allowed[Q[1],Q[0]]:continue
                length=abs(Q[0]-q[0])+abs(Q[1]-q[1]);v=value+length+.2*abs(int(terrain[Q[1],Q[0]])-s['rail_y'])
                if v<cost.get(Q,1e30):cost[Q]=v;prev[Q]=q;heapq.heappush(heap,(v,Q))
        path=[]
        if reached is not None:
            q=reached
            while q is not None:path.append([q[0]+x,q[1]+z]);q=prev[q]
            path.reverse();expanded=[]
            for q in path:
                if expanded:
                    old=expanded[-1];length=abs(q[0]-old[0])+abs(q[1]-old[1])
                    if length>1:
                        if old[1]!=q[1]or old[1]!=-685:raise ValueError('Unrecognized graph jump')
                        direction=1 if q[0]>old[0]else-1
                        expanded.extend([[px,q[1]]for px in range(old[0]+direction,q[0],direction)])
                expanded.append(q)
            path=expanded;goal=path[-1];floorgrade=int(grades[goal[1]-z,goal[0]-x])
            target=dict(xyz=[goal[0]+.5,floorgrade/2+1,goal[1]+.5],grade2=floorgrade,floor=e.state(goal[0],(floorgrade+1)//2,goal[1]))
        else:target=None
        row=dict(name=s['name'],platform_rail_id=s['rail_id'],starts=len(start),public_goals=len(goals),explored=len(cost),path_xz=path,width=3,target=target,
            protected_current_objects_avoided=True,new_columns_outside_water_buffer=True,final_voxel_and_grade_checks_pending=True)
        row['bridge']=bridge if any(q==[2735,-685]for q in path)else None
        if row['bridge']:row['new_columns_outside_water_buffer']=False;row['only_high_clearspan_deck_over_reserved_water']=True
        results.append(row);print(s['name'],'route',len(path),'target',target,'starts',len(start),'goals',len(goals),flush=True)
    np.savez_compressed(a.out/'planning-masks.npz',bounds=[x,z,X,Z],public=public,grade2=grades,terrain=terrain,water=wet,rail=rail,held=held,available=safe)
    write(a.out/'access-plan.json',dict(variant=a.variant,source=str(a.source),authority=str(a.authority),paths=results,world_written=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','authority','geometry','edges','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--variant',required=True);main(p.parse_args())
