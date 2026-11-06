"""Map finite geographic water bodies and explicit open regional interfaces.

This is geometry-only planning. It neither fills water nor claims that a
clipped upstream reach is a complete, physically connected river system.
"""
import argparse,gzip,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from scipy.ndimage import label,distance_transform_edt,find_objects
from shapely.geometry import shape,box
from shapely.ops import unary_union
from shapely import contains_xy

def plan(a):
    a.out.mkdir(parents=True,exist_ok=False)
    source=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))
    if not source['provenance']['complete']:raise ValueError('Incomplete geographic source')
    x,z,X,Z=a.bounds;clip=box(x,z,X,Z);sea=[];inland=[];crossings=[]
    for f in source['features']:
        p=f['properties'];layer=p['source_layer']
        if layer not in ('WA','RailCL','RdCL'):continue
        g=shape(f['geometry'])
        if not g.intersects(clip):continue
        g=g.intersection(clip)
        if layer=='WA':(sea if p['vt_code']==5100 else inland).append(g)
        elif layer=='RailCL'or int(p.get('vt_code',0))in(2721,2731,2703,2713,2704,2714):crossings.append(g)
    zz,xx=np.mgrid[z:Z+1,x:X+1]
    river_geometry=unary_union(inland);sea_geometry=unary_union(sea)
    exact=contains_xy(river_geometry,xx,zz);sea_mask=contains_xy(sea_geometry,xx,zz)
    # A sub-block expansion converts diagonal/thin reference ribbons into
    # finite Minecraft channels. Its added cells require saved ownership QA.
    river=contains_xy(river_geometry.buffer(.75),xx,zz)&~sea_mask
    civil=contains_xy(unary_union(crossings).buffer(5),xx,zz)&river
    edge=(xx<=x+2)|(xx>=X-2)|(zz<=z+2)|(zz>=Z-2)
    outlet=river&(distance_transform_edt(~sea_mask)<=2)
    ids,count=label(river);rows=[]
    for k,ar in enumerate(find_objects(ids),1):
        if ar is None:continue
        local=ids[ar]==k;size=int(local.sum())
        if size<8:continue
        t,l=ar[0].start,ar[1].start;b,r=ar[0].stop-1,ar[1].stop-1
        ports=np.argwhere(local&edge[ar]);outlets=np.argwhere(local&outlet[ar])
        ports=[[int(x+l+i),int(z+t+j)]for j,i in ports]
        outlets=[[int(x+l+i),int(z+t+j)]for j,i in outlets]
        rows.append(dict(id=k,columns=size,bounds=[x+l,z+t,x+r,z+b],reference_columns=int((local&exact[ar]).sum()),
            widened_columns=int((local&~exact[ar]).sum()),regional_boundary_columns=ports,sea_outlet_columns=outlets,
            civil_crossing_columns=int((local&civil[ar]).sum()),open_regional_interface=bool(ports),
            reaches_geographic_sea=bool(outlets),water_level_and_bed_verified=False))
    rows.sort(key=lambda r:-r['columns'])
    np.savez_compressed(a.out/'watercourse-reference.npz',bounds=a.bounds,reference=exact,river=river,sea=sea_mask,civil=civil,outlet=outlet,labels=ids)
    report=dict(status='geographic watercourse programme only',bounds=a.bounds,source=str(a.geography),components=rows,
        reference_inland_columns=int(exact.sum()),proposed_inland_columns=int(river.sum()),minimum_reference_buffer=.75,
        regional_boundary_components=sum(r['open_regional_interface']for r in rows),sea_connected_components=sum(r['reaches_geographic_sea']for r in rows),
        unverified_closed_or_culverted_components=sum(not(r['open_regional_interface']or r['reaches_geographic_sea'])for r in rows),
        world_written=False,hydrology_complete=False,bridges_and_culverts_deferred_to_stage=3)
    (a.out/'watercourse-programme.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    rgb=np.empty((*river.shape,3),np.uint8);rgb[:]=[226,233,210];rgb[sea_mask]=[125,165,189];rgb[river]=[45,122,172];rgb[civil]=[153,87,119];rgb[river&edge]=[204,106,40]
    im=Image.fromarray(rgb);draw=ImageDraw.Draw(im);font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    for row in rows[:20]:
        l,t,r,b=row['bounds'];draw.text(((l+r)/2-x,(t+b)/2-z),str(row['id']),font=font,fill='black',stroke_width=1,stroke_fill='white')
    im.save(a.out/'watercourse-programme.png')
    print(json.dumps({k:v for k,v in report.items()if k!='components'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('geography','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--bounds',type=int,nargs=4,required=True);plan(p.parse_args())
