"""Read-only, all stored-region screening using the central block reader.

This is coverage/evidence, not an automatic demolition or art approval.
Exact terrain, road and below-ground surface maps are retained per region;
seams are compared across region boundaries, not just within each file.
"""
import argparse, json, time
from collections import Counter
from pathlib import Path
import numpy as np
from scipy import ndimage
from query_blocks import iter_matching_sections, AIR, dimension_dir

NATURAL = {'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel',
           'minecraft:sand','minecraft:clay','minecraft:coarse_dirt','minecraft:deepslate',
           'minecraft:podzol','minecraft:tuff','minecraft:bedrock'}
ROAD_TOKENS = ('asphalt','road','pavement','platform','floor_panel')
EMPTY = -32768


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    world=args.world.resolve();started=time.monotonic();stats={};counts=Counter()
    region_maps={};isolated=[];border=[];sections=0
    # Named dimensions all contain independent stored maps. This report does
    # not silently call one floor or one camera a whole-map scan.
    dims=['minecraft:overworld']
    for p in sorted((world/'dimensions').glob('*/*/region')):
        dims.append(p.parent.parent.name+':'+p.parent.name)
    for dim in ('minecraft:the_nether','minecraft:the_end'):
        if (dimension_dir(world,dim)/'region').exists():dims.append(dim)
    dim_reports=[]
    for dim in dims:
        directory=dimension_dir(world,dim)/'region'
        if not directory.exists():continue
        local_stats={};palette_counts=Counter();mapping={};last_region=None
        name=dim.replace(':','_').replace('/','_');folder=args.out/name;folder.mkdir(exist_ok=True)

        def newmap():
            return dict(surface=np.full((512,512),EMPTY,np.int16),
                natural_surface=np.full((512,512),EMPTY,np.int16),
                underground=np.full((512,512),EMPTY,np.int16),
                water=np.full((512,512),EMPTY,np.int16),
                roads=np.full((512,512),EMPTY,np.int16),
                known=np.zeros((512,512),bool))

        for cx,cz,sy,pal,idx in iter_matching_sections(world,dim,('',),local_stats):
            r=(cx//32,cz//32)
            if r not in mapping:mapping[r]=newmap()
            m=mapping[r];xx=(cx%32)*16;zz=(cz%32)*16;sl=np.s_[zz:zz+16,xx:xx+16]
            m['known'][sl]=True;sections+=1
            freq=np.bincount(idx,minlength=len(pal));palette_counts.update({s:int(freq[i]) for i,s in enumerate(pal) if freq[i]})
            if len(pal)==1 and pal[0] in AIR:continue
            names=[s.split('[')[0] for s in pal]
            solid=np.array([s not in AIR and s not in ('minecraft:water','minecraft:lava','minecraft:light')
                and not s.endswith(('_leaves','_log')) and not any(t in s for t in ('grass','fern','flower','sapling','vine'))
                or s=='minecraft:grass_block' for s in names])
            nat=np.array([s in NATURAL for s in names]);water=np.array([s=='minecraft:water' for s in names])
            road=np.array([any(t in s for t in ROAD_TOKENS) for s in names]);free=np.array([s in AIR for s in names])
            a=idx.reshape(16,16,16);yy=np.arange(sy*16,sy*16+16)[:,None,None]
            for key,predicate,valid in [('surface',solid,yy>=0),('natural_surface',nat,yy>=0),
                ('underground',solid,(yy>=-545)&(yy<=-380)),('water',water,(yy>=-545)&(yy<=-380)),
                ('roads',road,yy>=-600)]:
                m[key][sl]=np.maximum(m[key][sl],np.where(predicate[a]&valid,yy,EMPTY).max(axis=0))
            if nat.any() and free.any():
                empty=np.pad(free[a],1,constant_values=True);mask=nat[a].copy()
                for dy,dz,dx in [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]:
                    mask &= empty[1+dy:17+dy,1+dz:17+dz,1+dx:17+dx]
                for y,z,x in np.argwhere(mask):
                    rec=dict(dimension=dim,pos=[int(cx*16+x),int(sy*16+y),int(cz*16+z)],state=pal[a[y,z,x]])
                    (border if any(q in (0,15) for q in (x,y,z)) else isolated).append(rec)
            if sections%20000==0:print('scan',dim,'sections',sections,'elapsed',round(time.monotonic()-started,1),flush=True)
        records=[]
        for (rx,rz),m in sorted(mapping.items()):
            path=folder/f'r.{rx}.{rz}.npz';np.savez_compressed(path,origin=[rx*512,rz*512],**m)
            records.append(dict(region=[rx,rz],known_columns=int(m['known'].sum()),file=str(path)))
        (folder/'palette_census.json').write_text(json.dumps(dict(palette_counts.most_common()),indent=2),'utf8')
        dim_reports.append(dict(dimension=dim,stats=local_stats,regions=records))
        counts.update(palette_counts);region_maps[dim]=mapping
        print('dimension complete',dim,local_stats,flush=True)
    candidates=[]
    for dim,mapping in region_maps.items():
        for (rx,rz),m in mapping.items():
            for kind in ('natural_surface','underground','roads'):
                a=m[kind].astype(int);known=m['known']&(a!=EMPTY)
                edges=np.zeros_like(known)
                edges[:,:-1]|=known[:,:-1]&known[:,1:]&(abs(a[:,:-1]-a[:,1:])>=8)
                edges[:-1]|=known[:-1]&known[1:]&(abs(a[:-1]-a[1:])>=8)
                for offset,axis in [((1,0),1),((0,1),0)]:
                    other=mapping.get((rx+offset[0],rz+offset[1]))
                    if other is None:continue
                    b=other[kind].astype(int);valid=other['known']&(b!=EMPTY)
                    if axis:edges[:,-1]|=known[:,-1]&valid[:,0]&(abs(a[:,-1]-b[:,0])>=8)
                    else:edges[-1]|=known[-1]&valid[0]&(abs(a[-1]-b[0])>=8)
                labels,_=ndimage.label(edges,structure=np.ones((3,3),int));sizes=np.bincount(labels.ravel())
                for i,s in enumerate(ndimage.find_objects(labels),1):
                    if s is None or sizes[i]<3:continue
                    z,x=s;pos=np.argwhere(labels[z,x]==i);q=pos[len(pos)//2]+[z.start,x.start]
                    candidates.append(dict(dimension=dim,kind=kind,bounds_xz=[rx*512+x.start,rz*512+z.start,rx*512+x.stop-1,rz*512+z.stop-1],
                        columns=int(sizes[i]),example=[int(rx*512+q[1]),int(a[tuple(q)]),int(rz*512+q[0])],
                        status='REVIEW_REQUIRED_NOT_A_DEFECT_CERTIFICATE'))
    report=dict(world=str(world),world_written=False,scan_complete=True,dimensions=dim_reports,
        sections_read=sections,measured_cells=sum(counts.values()),
        isolated_natural_cells=isolated,section_boundary_candidates_unconfirmed=border,
        height_discontinuity_candidates=candidates,seconds=time.monotonic()-started,
        road_connectivity_passed=False,underground_dynamic_clearance_passed=False,art_passed=False,
        caveat='All stored dimensions and FULL block sections screened. Candidate geometry needs ownership and visual review. Natural cliffs, authored buildings and closed doors are not automatically errors. No native motion or visual acceptance is claimed.')
    (args.out/'GLOBAL_SCREEN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('COMPLETE',sections,'sections;',len(candidates),'height candidates;',len(isolated),'isolated cells',flush=True)


if __name__=='__main__': main()
