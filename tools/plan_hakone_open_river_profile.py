"""Fit a measured coastal river profile while keeping open interfaces explicit.

This is a design, never a construction mask. Its depths are authored Minecraft
depths, not measured bathymetry. Unmatched upstream ports prevent release.
"""
import argparse,json,heapq
from collections import deque
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image,ImageDraw

def fit_connected_water(wet,ground,outlets,sea,grade):
    """Slope-limit along the actual channel graph, then fill drainage sinks.

    A single distance profile incorrectly gives tributaries the same height.
    The lower envelope retains their local relief. A priority flood supplies
    a non-rising route to the measured sea for every wet column.
    """
    if not(0<grade<=.1)or not np.any(outlets&wet):raise ValueError('Valid river gradient and mouth required')
    h,w=wet.shape;raw=np.maximum(ground.astype(float)-1,sea);raw[outlets]=sea
    smoothed=np.where(wet,raw,np.inf);heap=[(float(raw[j,i]),int(j*w+i))for j,i in np.argwhere(wet)];heapq.heapify(heap)
    def neighbours(p):
        j,i=divmod(p,w)
        for J,I in((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
            if 0<=J<h and 0<=I<w and wet[J,I]:yield J,I,J*w+I
    while heap:
        value,p=heapq.heappop(heap);j,i=divmod(p,w)
        if value>smoothed[j,i]+1e-9:continue
        for J,I,q in neighbours(p):
            proposal=value+grade
            if proposal<smoothed[J,I]-1e-9:smoothed[J,I]=proposal;heapq.heappush(heap,(proposal,q))
    filled=np.full(wet.shape,np.inf);parent=np.full(wet.shape,-1,np.int32);heap=[]
    for j,i in np.argwhere(outlets&wet):filled[j,i]=sea;heapq.heappush(heap,(float(sea),int(j*w+i)))
    while heap:
        value,p=heapq.heappop(heap);j,i=divmod(p,w)
        if value>filled[j,i]+1e-9:continue
        for J,I,q in neighbours(p):
            proposal=max(value,smoothed[J,I])
            if proposal<filled[J,I]-1e-9:filled[J,I]=proposal;parent[J,I]=p;heapq.heappush(heap,(proposal,q))
    if not np.isfinite(filled[wet]).all():raise ValueError('Water component lacks a mouth route')
    for j,i in np.argwhere(wet&~outlets):
        q=int(parent[j,i]);J,I=divmod(q,w)
        if q<0 or filled[J,I]>filled[j,i]+1e-8:raise ValueError('Invalid drainage parent')
    return filled,parent

def plan(a):
    with np.load(a.programme/'watercourse-reference.npz')as f:p={k:f[k]for k in f.files}
    with np.load(a.measured/'measured-water.npz')as f:d={k:f[k]for k in f.files}
    if not np.array_equal(p['bounds'],d['bounds']):raise ValueError('Geometry and measurement frames differ')
    wet=p['labels']==a.component;outlets=wet&p['outlet'];ground=d['ground'];x,z,X,Z=map(int,p['bounds'])
    if not wet.any()or not outlets.any():raise ValueError('A complete sea-connected raster component is required')
    distance=np.full(wet.shape,-1,np.int32);distance[outlets]=0;queue=deque(map(tuple,np.argwhere(outlets)));h,w=wet.shape
    while queue:
        j,i=queue.popleft()
        for J,I in ((j-1,i),(j+1,i),(j,i-1),(j,i+1)):
            if 0<=J<h and 0<=I<w and wet[J,I]and distance[J,I]<0:distance[J,I]=distance[j,i]+1;queue.append((J,I))
    if np.any(wet&(distance<0)):raise ValueError('Raster water is disconnected from its declared outlet')
    sea_levels=d['water'][p['sea']&(d['water']>ground)]
    if not len(sea_levels):raise ValueError('Measured sea datum is missing')
    values,counts=np.unique(sea_levels,return_counts=True);sea=int(values[counts.argmax()])
    if np.any(outlets&(d['water']>ground)&(d['water']!=sea)):raise ValueError('Current mouth water disagrees with measured sea datum')
    step=8;maxdist=int(distance[wet].max());bands=maxdist//step+1;medians=np.full(bands,np.nan);sizes=np.zeros(bands,int)
    for k in range(bands):
        sample=ground[wet&(distance//step==k)];sizes[k]=len(sample)
        if len(sample):medians[k]=np.median(sample)-1
    good=np.flatnonzero(np.isfinite(medians));medians=np.interp(np.arange(bands),good,medians[good])
    continuous,parent=fit_connected_water(wet,ground,outlets,sea,a.maximum_grade)
    profile=np.asarray([np.median(continuous[wet&(distance//step==k)])if sizes[k]else np.nan for k in range(bands)])
    good=np.flatnonzero(np.isfinite(profile));profile=np.interp(np.arange(bands),good,profile[good])
    levels=np.full(wet.shape,-32768,np.int16);levels[wet]=np.floor(continuous[wet]+1e-8).astype(np.int16)
    depth=np.clip(2+(distance_transform_edt(wet)//12).astype(int),2,4);bed=ground.copy();bed[wet]=np.minimum(ground[wet],levels[wet]-depth[wet])
    away,nearest=distance_transform_edt(~wet,return_indices=True);near_level=levels[tuple(nearest)]
    bank=(away>0)&(away<=8)&~p['river']&~p['sea']&~(d['water']>ground)
    target=ground.copy();raised=np.ceil(near_level+1-np.maximum(0,away-1)).astype(np.int16);target[bank]=np.maximum(target[bank],raised[bank]);changed_bank=bank&(target!=ground)
    zz,xx=np.mgrid[z:Z+1,x:X+1];ports=wet&((xx<=x+2)|(xx>=X-2)|(zz<=z+2)|(zz>=Z-2))
    matching=ports&(d['water']==levels)&(d['water']>ground);changed_existing_water=wet&(d['water']>ground)&(d['water']!=levels)
    maximum_edge_step=0;uphill_paths=0
    for axis in(0,1):
        l=[slice(None),slice(None)];r=l.copy();l[axis]=slice(None,-1);r[axis]=slice(1,None);l,r=tuple(l),tuple(r);use=wet[l]&wet[r]
        maximum_edge_step=max(maximum_edge_step,int(np.abs(levels[l].astype(int)-levels[r])[use].max(initial=0)))
        if np.max(np.abs(continuous[l][use]-continuous[r][use]),initial=0)>a.maximum_grade+1e-7:raise ValueError('Unbounded local river gradient')
    for j,i in np.argwhere(wet&~outlets):
        J,I=divmod(int(parent[j,i]),w);uphill_paths+=int(levels[J,I]>levels[j,i])
    if uphill_paths or maximum_edge_step>1:raise ValueError('Profile contains reverse flow or a multi-block water wall')
    if np.any(changed_existing_water):raise ValueError('River design would change retained mouth water')
    report=dict(component=a.component,status='measured river profile design; not installed',bounds=p['bounds'].tolist(),river_columns=int(wet.sum()),
        measured_sea_datum=sea,flow_distance_range=[0,maxdist],water_level_range=[int(levels[wet].min()),int(levels[wet].max())],
        fitted_maximum_continuous_grade=a.maximum_grade,maximum_adjacent_water_step=maximum_edge_step,reverse_flow_edges=uphill_paths,
        authored_bed_depth_range=[int((levels-bed)[wet].min()),int((levels-bed)[wet].max())],maximum_dry_ground_cut=int((ground-bed)[wet].max()),
        changed_bank_columns=int(changed_bank.sum()),maximum_bank_raise=int((target-ground).max()),
        existing_water_columns_preserved=int((wet&(d['water']>ground)).sum()),
        preliminary_foreign_column_intersections=int(((wet|changed_bank)&d['near_bed_foreign']).sum()),
        actor_column_intersections=int(((wet|changed_bank)&d['actors']).sum()),
        open_boundary_columns=int(ports.sum()),matched_existing_boundary_water_columns=int(matching.sum()),unmatched_upstream_columns=int((ports&~matching).sum()),
        explicit_upstream_ports=[[int(x+i),int(z+j),int(levels[j,i]),int(d['water'][j,i])]for j,i in np.argwhere(ports&~matching)],
        world_written=False,release_allowed=False,remaining=['Upstream physical interface continuity','Exact changed XYZ ownership and retained devices','Actual bank faces and channel-bed support','Future recipe replay and runtime water stability','Bridge/culvert clearances in ordered civil phase'])
    a.out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(a.out/'river-profile.npz',bounds=p['bounds'],wet=wet,level=levels,bed=bed,bank=changed_bank,bank_ground=target,old_ground=ground,flow_distance=distance,ports=ports,drainage_parent=parent,continuous_level=continuous)
    (a.out/'river-profile.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    im=Image.new('RGB',(1100,430),'#f4f5ef');draw=ImageDraw.Draw(im)
    low=sea-4;high=max(float(medians.max()),float(profile.max()))+3
    def point(D,Y):return(55+D/maxdist*1000,370-(Y-low)/(high-low)*320)
    draw.line([point(k*step,v)for k,v in enumerate(medians)],fill='#82925e',width=2)
    draw.line([point(k*step,v)for k,v in enumerate(profile)],fill='#23739a',width=3)
    draw.text((55,15),'River profile design / green: measured ground minus 1 / blue: water surface',fill='black')
    draw.text((55,390),f'Distance to sea: 0..{maxdist} blocks. Upstream matching still pending; NOT INSTALLED.',fill='black')
    im.save(a.out/'river-profile.png')
    print(json.dumps({k:v for k,v in report.items()if k!='explicit_upstream_ports'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('programme','measured','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--component',type=int,required=True);p.add_argument('--maximum-grade',type=float,default=.02);plan(p.parse_args())
