"""Preserve commissioned transport volumes while fitting their surface bases.

This is an offline completion of a measured candidate, never a runtime scan.
Native curve envelopes retain their current blocks, including ballast and AIR.
Station bases constrain geology without freezing whole vertical columns.
"""
import argparse,gzip,json,struct
from collections import defaultdict
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from prepare_hakone_main_terrain import sample_grid
from hakone_earthworks import grade_ground,min_slope_envelope
from plan_ashi_landscape_r54 import NATURAL,SOIL
from query_blocks import AIR


def station_boxes(gis):
    rows=json.loads((gis.parent/'access_r22/transit/civil/station_contract.json').read_text('utf8'))['stations']
    result=[]
    for s in rows:
        x,y,z=s['center'];half=s['half'];dx,dz=(half+2,20)if s['horizontal']else(20,half+2)
        result.append([x-dx,s['ground'],z-dz,x+dx,max(y+16,151 if x==-1480 else y+16),z+dz])
    return result


def field(a):
    a.out.mkdir(exist_ok=False)
    d=load_grid(a.atlas/'surface-atlas.npz');h=d['height_y'].astype(float);owner=d['owner'].copy()
    fixed=owner>0;bank=h.copy();lake=(owner==3)&(d['water']!=-32768);bank[lake]=d['water'][lake]-1
    interior=fixed.copy();interior[1:]&=fixed[:-1];interior[:-1]&=fixed[1:];interior[:,1:]&=fixed[:,:-1];interior[:,:-1]&=fixed[:,1:]
    boundary=fixed&~interior
    upper=min_slope_envelope(np.where(boundary,bank,np.inf),4)
    lower=-min_slope_envelope(np.where(boundary,-bank,np.inf),4)
    pins=np.zeros(h.shape,bool);desired=h.copy();boxes=station_boxes(a.gis)
    for x,y,z,X,Y,Z in boxes:
        ix=np.flatnonzero((d['x']>=x)&(d['x']<=X));iz=np.flatnonzero((d['z']>=z)&(d['z']<=Z))
        if not len(ix)or not len(iz):continue
        area=np.ix_(iz,ix);flex=~fixed[area]
        # An existing upper roadway can share a footprint with a lower station.
        # Keep its grade and finite station room separately, rather than pulling
        # an upper street through the lower concourse.
        wanted=np.clip(np.full(flex.shape,y),lower[area],upper[area])
        view=desired[area];view[flex]=wanted[flex];desired[area]=view
        p=pins[area];p[flex]=True;pins[area]=p
    anchor=fixed|pins;values=bank.copy();values[pins]=desired[pins]
    interior=anchor.copy();interior[1:]&=anchor[:-1];interior[:-1]&=anchor[1:];interior[:,1:]&=anchor[:,:-1];interior[:,:-1]&=anchor[:,1:]
    terrain,errors=grade_ground(h,anchor&~interior,values,slope=4)
    if (errors&~anchor).any():raise ValueError('Station surface anchors conflict with commissioned grades')
    terrain[pins]=desired[pins]
    terrain[fixed]=h[fixed];owner[pins]=8
    np.savez_compressed(a.out/'surface-atlas.npz',x=d['x'],z=d['z'],height_y=terrain,water=d['water'],owner=owner)
    with gzip.open(a.out/'hakone_surface.bin.gz','wb')as f:
        f.write(struct.pack('>6i',0x484B3535,int(d['x'][0]),int(d['z'][0]),2,len(d['x']),len(d['z'])))
        f.write((terrain*16).astype('>i2').tobytes());f.write(d['water'].astype('>i2').tobytes())
    for name in('shore-seam.npz','retained-parcels.json'):(a.out/name).write_bytes((a.atlas/name).read_bytes())
    (a.out/'transport-volumes.json').write_text(json.dumps(dict(stations=boxes,previous_atlas=str(a.atlas),changed_field_pixels=int((terrain!=h).sum())),indent=2),'utf8')
    print('Station surface field',int((terrain!=h).sum()),'changed pixels',flush=True)


def complete(a):
    e=Editor(a.candidate);d=load_grid(a.atlas/'surface-atlas.npz');old=load_grid(a.previous/'surface-atlas.npz')
    railvol=defaultdict(dict)
    files=[a.gis.parent/'repair_r43/transit_resolved/native_snapshot.json',a.gis/'tozan-native/validated-v7/track_samples.json',a.gis/'ropeway-native/validated-v6/track_samples.json']
    for file in files:
        if not file.exists():continue
        rows=json.loads(file.read_text('utf8'));rows=rows['curves']if isinstance(rows,dict)else rows
        for r in rows:
            if r['mode']!='TRAIN' or str(r['id']).startswith(('HRW','HRE')):continue
            for px,py,pz in r['points']:
                x,y,z=map(int,np.floor([px,py,pz]))
                if not -120<y<310:continue
                for X in range(x-3,x+4):
                    for Z in range(z-3,z+4):
                        # Keep distinct decks separate at grade-separated crossings.
                        railvol[X//16,Z//16].setdefault((X,Z),set()).add(y)
    boxes=station_boxes(a.gis);occupied=defaultdict(list)
    retained=list(json.loads((a.atlas/'retained-parcels.json').read_text('utf8')).values())+[[-110,32,-120,225,160,15]]
    for box in boxes+retained:
        x,y,z,X,Y,Z=box
        for cx in range(x//16,X//16+1):
            for cz in range(z//16,Z//16+1):occupied[cx,cz].append(box)
    stationby=defaultdict(list)
    for box in boxes:
        x,y,z,X,Y,Z=box
        for cx in range(x//16,X//16+1):
            for cz in range(z//16,Z//16+1):stationby[cx,cz].append(box)
    affected=set();yy=np.arange(-128,320)[:,None,None];restored=graded=0
    sources=sorted((a.candidate/'source').glob('*.npz'))
    for number,file in enumerate(sources):
        rx,rz=map(int,file.stem.split('.')[1:]);X,Z=np.meshgrid(np.arange(rx*512,rx*512+512,2),np.arange(rz*512,rz*512+512,2))
        difference=sample_grid(d,'height_y',X,Z)!=sample_grid(old,'height_y',X,Z)
        hasrail=any(cx//32==rx and cz//32==rz for cx,cz in railvol)
        hasstation=any(cx//32==rx and cz//32==rz for cx,cz in stationby)
        if not difference.any()and not hasrail and not hasstation:continue
        r=e.region(rx*512,rz*512)
        for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'):
            if s not in r['ids']:r['ids'][s]=len(r['names']);r['names'].append(s)
        names=r['names'];natural=np.array([s.split('[')[0]in NATURAL for s in names]);soil=np.array([s.split('[')[0]in SOIL for s in names]);empty=np.array([s.split('[')[0]in AIR for s in names])
        air,stone,dirt,grass=[r['ids'][s]for s in ('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')]
        # The intended canopy repair is the only deliberate change to these rooms.
        station_offsets={};sf=a.candidate.parent/'stations-v1/delta'/file.name
        if sf.exists():
            with np.load(sf)as f:
                co,ra,at=f['coordinates'],f['ranges'],f['indices']
                station_offsets={tuple(q):at[ra[i]:ra[i+1]]for i,q in enumerate(co)}
        for (cx,cz),b,v in zip(r['coords'],r['before'],r['after']):
            key=int(cx),int(cz);zz,xx=np.mgrid[cz*16:cz*16+16,cx*16:cx*16+16]
            h=np.rint(sample_grid(d,'height_y',xx,zz)).astype(int);oh=np.rint(sample_grid(old,'height_y',xx,zz)).astype(int)
            distance=np.maximum.reduce([d['x'][0]-xx,xx-d['x'][-1],d['z'][0]-zz,zz-d['z'][-1],np.zeros((16,16),int)])
            radius=np.hypot(xx-30,zz-296);t=np.clip((radius-600)/1200,0,1)
            bottom=np.where(radius<1800,np.maximum(-128,-478+np.floor(502*np.sqrt(np.maximum(0,1-t*t)))+18),-128).astype(int)
            h=np.maximum(h,bottom);oh=np.maximum(oh,bottom)
            active=(h!=oh)&(distance==0)
            protect=np.zeros(v.shape,bool)
            for x,y,z,X,Y,Z in occupied[key]:protect|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y-3)&(yy<=Y)
            if active.any():
                foreign=(~natural[v])&(yy>=bottom);lo=np.where(foreign,yy,320).min(0)-1;hi=np.where(foreign,yy,-129).max(0)+4
                volume=(yy>=lo)&(yy<=hi)
                band=active&natural[v]&(yy>=np.maximum(bottom,np.minimum(h,oh)-3))&~protect
                band&=~(empty[v]&volume&(yy<=h));band&=~(volume&~soil[v]&~empty[v])
                target=np.where(yy>h,air,np.where(yy==h,grass,np.where(yy>=h-3,dirt,stone)))
                changed=band&(v!=target);graded+=int(changed.sum());v[changed]=np.broadcast_to(target,v.shape)[changed]
            restore=np.zeros(v.shape,bool)
            for x,y,z,X,Y,Z in stationby[key]:restore|=(xx>=x)&(xx<=X)&(zz>=z)&(zz<=Z)&(yy>=y-3)&(yy<=Y)
            for (x,z),levels in railvol[key].items():
                for y in levels:restore[max(0,y-3+128):min(448,y+8+128),z%16,x%16]=True
            if key in station_offsets:restore.ravel()[station_offsets[key]]=False
            change=restore&(v!=b);restored+=int(change.sum());v[change]=b[change]
            if active.any()or change.any():affected.add(key)
        e.save();e.regions.clear();print('Transport completion',number+1,'/',len(sources),flush=True)
    manifest=json.loads((a.candidate/'manifest.json').read_text('utf8'));regions=e.save()
    manifest.update(regions=regions,cells=sum(r['cells']for r in regions),terrain_atlas=str(a.atlas),transport_volume_cells_restored=restored,station_ground_cells=graded)
    (a.candidate/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.candidate/'transport-changed-chunks.json').write_text(json.dumps(sorted(affected)),'utf8')
    print('Completed transport volumes',restored,'terrain',graded,'chunks',len(affected),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--phase',choices=('field','blocks'),required=True)
    for name in('atlas','gis','out','candidate','previous'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();field(a)if a.phase=='field'else complete(a)
