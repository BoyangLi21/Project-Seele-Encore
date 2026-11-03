"""Add station street furniture and frontage planting to a verified candidate."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.corridors import alignment
from map_pipeline.launch_protection import load,check_candidate
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from prepare_hakone_togendai_neighbourhood import save_json
from verify_hakone_togendai_neighbourhood import verify

def finish(source,out,detail_plan=None):
    for name in ('functional-check.json','independent-check.json'):
        if json.loads((source/name).read_text('utf8'))['errors']:raise ValueError('Unverified input '+name)
    out.mkdir(parents=True,exist_ok=False);(out/'source').mkdir()
    for file in (source/'source').glob('*.npz'):os.link(file,out/'source'/file.name)
    for file in source.iterdir():
        if file.name=='source':continue
        if file.is_dir():shutil.copytree(file,out/file.name)
        else:shutil.copy2(file,out/file.name)
    with np.load(out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);e=Editor(out);spec=json.loads((out/'plan/authored-design.json').read_text('utf8'));details=dict(crossings=[],bus_bays=[],lights=[],trees=[],awnings=[])
    if detail_plan is not None:
        overrides=json.loads(detail_plan.read_text('utf8'))
        if set(overrides)-{'bridge_details','tree_clusters','woodland_areas','native_frontage_details'}:raise ValueError('Finishing plan may not alter street or parcel geometry')
        spec.update(overrides);save_json(out/'plan/authored-design.json',spec)
    if spec.get('togendai_forecourt',True):
        for lo,hi in [(-321,-302),(-277,-258)]:
            for px in range(lo,hi+1):
                for pz in (981,985):e.put(px,109,pz,'minecraft:yellow_concrete')
            for pz in range(982,985):
                for px in (lo,hi):e.put(px,109,pz,'minecraft:yellow_concrete')
            details['bus_bays'].append([lo,981,hi,985])
        for px in (-289,-287,-285):
            for pz in range(980,986):e.put(px,109,pz,'minecraft:white_concrete');d['marking'][pz-z,px-x]=True
        details['crossings'].append(dict(centre=[-287,109,983],kind='station entrance'))
        for pz in (936,938,940):
            for px in range(-317,-308):
                j,i=pz-z,px-x
                if not d['road'][j,i]:continue
                y,slab=road_blocks(d['grade2'][j,i]);e.put(px,int(y),pz,'projectseele:road_marking_slab[type=bottom,waterlogged=false]'if slab else'minecraft:white_concrete');d['marking'][j,i]=True
        details['crossings'].append(dict(centre=[-313,106,938],kind='neighbourhood crossing'))
    from detail_hakone_nerv_streets import preservation_mask
    preserved=preservation_mask(out,spec)
    empty=AIR|PLANTS|{'minecraft:light'};distance=distance_transform_edt(~(d['walk']|d['plots']))
    for row in spec['streets']:
        curve,s=alignment(row)
        for at in np.arange(25,s[-1]-12,36):
            k=int(np.argmin(abs(s-at)));t=curve[k+1,[0,2]]-curve[k-1,[0,2]];t/=np.linalg.norm(t);n=np.array([-t[1],t[0]])
            for side in ((1,-1)if int(at)//36%2 else(-1,1)):
                px,pz=map(int,np.rint(curve[k,[0,2]]+n*side*(row['width']/2+4)));j,i=pz-z,px-x
                if not(0<=j<d['walk'].shape[0]and 0<=i<d['walk'].shape[1])or distance[j,i]<1.5:continue
                h=int(d['ground'][j,i])
                if any(preserved((px,Y,pz))for Y in range(h+1,h+7)):continue
                if e.state(px,h,pz).split('[')[0]not in SOIL or any(e.state(px,Y,pz).split('[')[0]not in empty for Y in range(h+1,h+7)):continue
                if any(abs(px-q[0])+abs(pz-q[2])<15 for q in details['lights']):continue
                e.put(px,h+1,pz,'minecraft:polished_deepslate')
                for Y in range(h+2,h+6):e.put(px,Y,pz,'minecraft:iron_bars[east=false,north=false,south=false,waterlogged=false,west=false]')
                head='minecraft:lantern[hanging=false,waterlogged=false]'if spec.get('togendai_forecourt',True)else'projectseele:street_light_head[facing=south]'
                e.put(px,h+6,pz,head);details['lights'].append([px,h+1,pz]);break
    rows=json.loads((out/'plan/buildings.json').read_text('utf8'));outdoor=json.loads((out/'outdoor-apron-corrections.json').read_text('utf8'))
    for row in rows:
        if not any(word in row['use']for word in ('喫茶','商店','书店','诊所')):continue
        px,py,pz=row['door'];ax,_,az=row['approach'];dx=int(np.sign(ax-px));dz=int(np.sign(az-pz));h=row['site']['floor']
        added=[]
        for along in (1,2):
            for side in range(-4,5):
                Q,R=px+dx*along-dz*side,pz+dz*along+dx*side;Y=h+4;before=e.state(Q,Y,R)
                if preserved((Q,Y,R))or before.split('[')[0]not in AIR:continue
                material='minecraft:dark_oak_slab[type=bottom,waterlogged=false]'if '喫茶'in row['use']else'minecraft:smooth_stone_slab[type=bottom,waterlogged=false]'
                e.put(Q,Y,R,material);added.append([Q,Y,R]);outdoor.append(dict(parcel=row['id'],kind='outside wall canopy',pos=[Q,Y,R],before=before,after=material))
        if added:details['awnings'].append(dict(parcel=row['id'],cells=len(added)))
    # Irregular groups with clear gaps around road sightlines and doorways.
    rng=np.random.default_rng(20261103)
    clusters=list(spec.get('tree_clusters',[(-410,854),(-347,904),(-337,928),(-270,891),(-242,922),(-204,903),(-354,956),(-273,973),(-227,1011)]))
    for a,b,A,B in spec.get('woodland_areas',[]):
        clusters.extend((cx,cz)for cx in range(a+15,A,40)for cz in range(b+15,B,40))
    for cx,cz in clusters:
        for _ in range(18):
            px,pz=map(int,np.rint(rng.normal([cx,cz],[12,9])));j,i=pz-z,px-x
            if not(3<=j<d['walk'].shape[0]-3 and 3<=i<d['walk'].shape[1]-3)or distance[j,i]<5 or d['wet'][j,i]:continue
            if any(np.hypot(px-q['base'][0],pz-q['base'][2])<6 for q in details['trees']):continue
            h=int(d['ground'][j,i]);height=int(rng.integers(5,9));species=str(rng.choice(['spruce','birch','oak'],p=[.55,.2,.25]));cells={}
            if e.state(px,h,pz).split('[')[0]not in SOIL:continue
            for Y in range(h+1,h+height):cells[px,Y,pz]=f'minecraft:{species}_log[axis=y]'
            for layer in range(4):
                radius=(2 if layer<3 else 1)if species!='spruce'else(2 if layer%2==0 else 1)
                Y=h+height-3+layer
                for dx in range(-radius,radius+1):
                    for dz in range(-radius,radius+1):
                        if abs(dx)+abs(dz)>radius+1 or (dx==0 and dz==0 and Y<h+height):continue
                        cells[px+dx,Y,pz+dz]=f'minecraft:{species}_leaves[distance=1,persistent=true,waterlogged=false]'
            if any(preserved(p)or e.state(*p).split('[')[0]not in empty for p in cells):continue
            for p,state in cells.items():e.put(*p,state)
            details['trees'].append(dict(base=[px,h+1,pz],species=species,height=height))
    if spec.get('nerv_west_details',False):
        from detail_hakone_nerv_streets import decorate
        decorate(e,d,spec,rows,out,details,outdoor,preserved)
    elif spec.get('native_frontage_details',False)or (out/'new-frontages.json').exists():
        from detail_hakone_nerv_streets import decorate_frontages
        fixture_rows=list(rows)
        if (out/'new-frontages.json').exists():
            fixture_rows.extend(dict(r,new_payload_bounds=r['occupied_bounds'])for r in json.loads((out/'new-frontages.json').read_text('utf8'))['buildings'])
        decorate_frontages(e,d,fixture_rows,out,details,outdoor,preserved)
    if spec.get('hillside_street_details',False):
        from detail_hakone_hillside_streets import decorate as hillside_details
        hillside_details(e,d,spec,rows,details,preserved)
    patches=e.save();save_json(out/'outdoor-apron-corrections.json',outdoor);save_json(out/'street-details.json',details)
    np.savez_compressed(out/'plan/network.npz',**d)
    manifest=json.loads((out/'manifest.json').read_text('utf8'));manifest.update(regions=patches,cells=sum(r['cells']for r in patches))
    manifest['neighbourhood_verification']['new_native_fixtures']=len(details.get('native_fixtures',[]));save_json(out/'manifest.json',manifest)
    save_json(out/'launch-protection.json',check_candidate(load(Path(manifest['world'])),out))
    if (out/'new-frontages.json').exists():
        from verify_hakone_hillside_frontages import check
        check(out)
    else:verify(out)
    print({k:len(v)for k,v in details.items()},flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--detail-plan',type=Path);a=p.parse_args();finish(a.source,a.out,a.detail_plan)
