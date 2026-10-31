"""One surface field for installed terrain migration and future chunk generation.

Existing engineered city, commissioned street grades and the installed lake bed
override geographic relief. A shared soil transition connects their boundaries.
No roads, houses or new districts are added by this command.
"""
import argparse,gzip,json,struct
from pathlib import Path
import numpy as np
from hakone_earthworks import grade_ground
from prepare_hakone_main_terrain import sample_grid
from plan_hakone_main_districts import ROAD_MATERIALS


def compile_atlas(gis,out,source,seams):
    out.mkdir(exist_ok=False)
    with np.load(gis/'runtime-surface-field.npz')as f:d={k:f[k]for k in f.files}
    zz,xx=np.meshgrid(d['z'],d['x'],indexing='ij');height=d['height_y'].copy()
    owned=np.zeros(height.shape,bool);owners=np.zeros(height.shape,np.uint8)
    def overlay(file,key,owner,valid=None):
        nonlocal height,owned
        with np.load(file)as f:v={k:f[k]for k in f.files}
        x0,z0,x1,z1=map(int,v['bounds']);mask=(xx>=x0)&(xx<=x1)&(zz>=z0)&(zz<=z1)
        z,x=np.nonzero(mask);localz=zz[z,x]-z0;localx=xx[z,x]-x0
        if valid is not None:
            keep=valid(v,localx,localz,xx[z,x],zz[z,x]);z,x,localz,localx=z[keep],x[keep],localz[keep],localx[keep]
        height[z,x]=v[key][localz,localx];owned[z,x]=True;owners[z,x]=owner
    with np.load(gis/'main-district-integration-v1/coupled-grading.npz')as f:main={k:f[k]for k in f.files}
    # A planned road mask can contain pixels skipped during native-station or
    # lake composition. Only actual saved pavement may fix the terrain grade.
    valid_walk=np.zeros(main['walk'].shape,bool);mx,mz,mX,mZ=map(int,main['bounds'])
    for file in (source/'source').glob('*.npz'):
        with np.load(file)as f:
            names=[str(s).split('[')[0]for s in f['palette']];road=np.array([s in ROAD_MATERIALS for s in names])
            clear=np.array([s in {'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light','minecraft:grass','minecraft:tall_grass'}for s in names])
            for (cx,cz),b in zip(f['coordinates'],f['blocks']):
                if not(mx<=cx*16<=mX and mz<=cz*16<=mZ):continue
                area=np.s_[cz*16-mz:cz*16-mz+16,cx*16-mx:cx*16-mx+16];h=main['target'][area]+128
                z,x=np.mgrid[:16,:16]
                valid_walk[area]=road[b[h,z,x]]&clear[b[h+1,z,x]]&clear[b[h+2,z,x]]&main['walk'][area]&~main['tunnel'][area]
    overlay(gis/'main-district-integration-v1/coupled-grading.npz','final_ground',1,
        lambda v,x,z,X,Z:(valid_walk|v['footprint'])[z,x])
    overlay(gis/'valley-integration-v12/grading.npz','target',2,
        lambda v,x,z,X,Z:((X>=1024)|(Z>=1024))&(v['developed']&~v['bridge'])[z,x])
    overlay(gis/'lake-basin-ready/surface.npz','target',3,lambda v,x,z,X,Z:v['lake'][z,x])
    overlay(seams/'gora-seam.npz','target',5,
        lambda v,x,z,X,Z:(v['walk']|v['fixed']|v['plots'])[z,x])
    city=json.loads((gis/'city-south-layout-preserved/plan.json').read_text('utf8'))
    for x0,z0,x1,z1 in city['cross_rectangles_xz']:
        mask=(xx>=x0)&(xx<=x1)&(zz>=z0)&(zz<=z1)
        height[mask]=80;owned[mask]=True;owners[mask]=4
    # Only a boundary ring constrains surrounding geography. Interior bridges
    # and water banks can have intentional vertical faces and are not flattened.
    interior=owned.copy()
    interior[1:]&=owned[:-1];interior[:-1]&=owned[1:]
    interior[:,1:]&=owned[:,:-1];interior[:,:-1]&=owned[:,1:]
    anchors=owned&~interior
    # Two-block soil steps are permitted on mountain cuts; this raster has
    # two world blocks per cell. Traversable roads keep their separate grades.
    bank_height=height.copy()
    lake=(owners==3)&(d['water']!=-32768)
    bank_height[lake]=d['water'][lake]-1
    fitted,conflicts=grade_ground(height,anchors,bank_height,slope=4.0)
    if (conflicts&~owned).any():
        pts=np.column_stack((xx[conflicts&~owned],zz[conflicts&~owned]))
        (out/'conflicts.json').write_text(json.dumps(pts.tolist()),'utf8')
        np.savez_compressed(out/'conflict-design.npz',x=d['x'],z=d['z'],height=height,bank=bank_height,owner=owners,anchors=anchors)
        raise ValueError('Installed boundary elevations need a coherent transition')
    height[~owned]=fitted[~owned]
    water=d['water'].copy();water[owned&(owners!=3)]=-32768
    # Road/river authors keep their explicit flowing channels. The broad field
    # owns geology and full lakes/sea; it does not replace narrow rivers.
    fixed=np.rint(np.clip(height,-120,305)*16).astype('>i2')
    np.savez_compressed(out/'surface-atlas.npz',x=d['x'],z=d['z'],height_y=fixed.astype(np.float32)/16,water=water,owner=owners)
    with gzip.open(out/'hakone_surface.bin.gz','wb',compresslevel=6)as f:
        f.write(struct.pack('>6i',0x484B3535,int(d['x'][0]),int(d['z'][0]),int(d['x'][1]-d['x'][0]),len(d['x']),len(d['z'])))
        f.write(fixed.tobytes());f.write(water.astype('>i2').tobytes())
    (out/'authority.json').write_text(json.dumps(dict(schema='projectseele.hakone.surface-authority.v2',
        purpose='Repair already installed surfaces and their old/new terrain seams',
        owners={'1':'measured installed main-city pavement/plots','2':'installed valley grades','3':'installed lake bed','4':'engineered cross-city datum','5':'joint Gora boundary grade'},
        geographic_source='cached GSI DEM; no redownload',runtime_checks=False,
        field=str(out/'surface-atlas.npz'),future_resource=str(out/'hakone_surface.bin.gz')),indent=2),'utf8')
    print('Shared surface field compiled',height.shape,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--gis',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--seams',type=Path,required=True)
    a=p.parse_args();compile_atlas(a.gis,a.out,a.source,a.seams)
