"""Add a dry sand/gravel foreshore and grounded rest points to the coast."""
import argparse,gzip,json,math,os,shutil
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point,shape
from shapely.ops import unary_union
from author_hakone_lakefront import Editor
from map_pipeline.corridors import alignment
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from verify_hakone_togendai_neighbourhood import verify

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')

def finish(a):
    for name in ('functional-check.json','independent-check.json'):
        if json.loads((a.source/name).read_text('utf8'))['errors']:raise ValueError('Unverified coast geometry')
    a.out.mkdir(parents=True,exist_ok=False);(a.out/'source').mkdir()
    for p in (a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    for p in a.source.iterdir():
        if p.name=='source':continue
        if p.is_dir():shutil.copytree(p,a.out/p.name)
        else:shutil.copy2(p,a.out/p.name)
    with np.load(a.out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    with np.load(a.design/'coastal-masks.npz')as f:beach=f['beach'];wet=f['wet'];parcels=f['parcels']
    with np.load(a.out/'plan/retained-public.npz')as f:retained=f['walk']
    x,z,X,Z=map(int,d['bounds']);e=Editor(a.out);empty=AIR|PLANTS|{'minecraft:light'}
    material_cells=[]
    for j,i in np.argwhere(beach&~(d['walk']|parcels|d['plots'])):
        px,pz=int(i+x),int(j+z);h=int(d['ground'][j,i])
        if e.state(px,h,pz).split('[')[0]not in SOIL:continue
        if any(e.state(px,h+k,pz).split('[')[0]not in empty for k in (1,2,3)):continue
        # The visible Sagami foreshore alternates darker shingle with sand;
        # keep its actual dry height and every existing water cell unchanged.
        top='minecraft:gravel'if ((px//4+pz//5)%7 in (0,1))else'minecraft:sand'
        for py in (h-1,h):
            if e.state(px,py,pz).split('[')[0]not in SOIL:break
        else:
            for py in (h-1,h):e.put(px,py,pz,top);material_cells.append([px,py,pz])
    fs=json.load(gzip.open(a.geography/'features.world.geojson.gz','rt',encoding='utf8'))['features']
    bypass=unary_union([shape(f['geometry'])for f in fs if f['properties']['source_layer']=='RdCL'and f['properties'].get('vt_tollsect')=='有料'])
    spec=json.loads((a.out/'plan/authored-design.json').read_text('utf8'));curve,along=alignment(spec['public_paths'][0])
    rest=[]
    for number,s in enumerate(np.linspace(25,float(along[-1])-25,6),1):
        k=int(abs(along-s).argmin());px,pz=map(int,np.rint(curve[k,[0,2]]));sites=[]
        for dx in range(-5,6):
            for dz in range(-5,6):
                cx,cz=px+dx,pz+dz
                if not 3<=math.hypot(dx,dz)<=5 or Point(cx,cz).distance(bypass)<6:continue
                area=np.s_[cz-1-z:cz+2-z,cx-1-x:cx+2-x]
                if np.any((wet|parcels|d['plots']|retained)[area])or d['walk'][cz-z,cx-x]:continue
                near=[(cx+di,cz+dj)for di in range(-2,3)for dj in range(-2,3)
                      if ((abs(di)==2 and abs(dj)<=1)or(abs(dj)==2 and abs(di)<=1))
                      and d['walk'][cz+dj-z,cx+di-x]and int(d['grade2'][cz+dj-z,cx+di-x])==-160]
                if not near:continue
                valid=True
                for qx in range(cx-1,cx+2):
                    for qz in range(cz-1,cz+2):
                        old=int(d['ground'][qz-z,qx-x])
                        if old>-80 or old<-83:valid=False;break
                        if any(e.state(qx,py,qz).split('[')[0]not in SOIL|empty|{'minecraft:smooth_stone','minecraft:smooth_stone_slab'}for py in range(old-2,-76)):valid=False;break
                if valid:sites.append((dx*dx+dz*dz,cx,cz))
        if not sites:continue
        _,cx,cz=min(sites)
        for qx in range(cx-1,cx+2):
            for qz in range(cz-1,cz+2):
                old=int(d['ground'][qz-z,qx-x]);e.fill(qx,old-2,qz,qx,-81,qz,'minecraft:stone');e.put(qx,-80,qz,'minecraft:stone_bricks')
                e.fill(qx,-79,qz,qx,-77,qz,'minecraft:air')
                d['walk'][qz-z,qx-x]=True;d['road'][qz-z,qx-x]=False;d['grade2'][qz-z,qx-x]=-160
        e.put(cx,-79,cz,'minecraft:oak_stairs[facing=west,half=bottom,shape=straight,waterlogged=false]')
        d['walk'][cz-z,cx-x]=False
        rest.append(dict(id='coastal-rest-'+str(number),seat=[cx,-79,cz],approach=[cx+1,-79,cz]))
    patches=e.save();e.regions.clear();d['ground']=ground(Editor(a.out),list(map(int,d['bounds'])))
    np.savez_compressed(a.out/'plan/network.npz',**d)
    manifest=json.loads((a.out/'manifest.json').read_text('utf8'));manifest.update(regions=patches,cells=sum(r['cells']for r in patches))
    manifest['neighbourhood_verification']['public_columns']=int(d['walk'].sum());save(a.out/'manifest.json',manifest)
    report=dict(dry_beach_surface_columns=len(material_cells)//2,material_cells=len(material_cells),rest_points=rest,water_cells_changed=0,
                future_bypass_reserved=True,world_written=False)
    save(a.out/'coastal-details.json',report);save(a.out/'launch-protection.json',check_candidate(load(Path(manifest['world'])),a.out))
    if verify(a.out)['errors']:raise ValueError('Coastal furnishing obstructed public space')
    print('Coastal finishes:',report['dry_beach_surface_columns'],'dry beach columns;',len(rest),'grounded rest points',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','design','geography','out'):p.add_argument('--'+n,type=Path,required=True)
    finish(p.parse_args())
