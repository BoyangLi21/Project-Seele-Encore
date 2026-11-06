"""Line a measured covered road without excavating retained railway members."""
import argparse,json,os,shutil
from collections import deque
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation,distance_transform_edt,label,maximum_filter
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.rail_underpasses import editable_underpass_column,allowed_roof_infill_column,physical_deck_ceilings
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from prepare_hakone_togendai_neighbourhood import save_json
from verify_hakone_togendai_neighbourhood import verify
from verify_hakone_network_candidate import PAVEMENT

CONCRETE='minecraft:light_gray_concrete'
EMPTY=AIR|PLANTS|{'minecraft:light'}


def is_bearing(state):
    bare=state.split('[')[0]
    return (bare in SOIL or bare.endswith('_concrete') or
            bare in {'minecraft:stone_bricks','minecraft:deepslate_bricks','minecraft:sea_lantern'})


def check_structure(candidate):
    """Read saved material, actual footing contact and six-face load paths."""
    path=candidate/'underpass-structure.json'
    if not path.exists():return []
    report=json.loads(path.read_text('utf8'));e=Editor(candidate);errors=[]
    cells={tuple(p)for p in report['roof_cells']+report['wall_cells']}
    solid={p for p in cells if is_bearing(e.state(*p))}
    for p in cells-solid:errors.append(['underpass structural gap',*p,e.state(*p)])
    anchors=set()
    for x,y,z in report['footings']:
        if not is_bearing(e.state(x,y-1,z)):errors.append(['underpass footing has no ground bearing',x,y,z])
        elif (x,y,z)in solid:anchors.add((x,y,z))
    reached=set(anchors);queue=deque(anchors)
    while queue:
        x,y,z=queue.popleft()
        for q in ((x-1,y,z),(x+1,y,z),(x,y-1,z),(x,y+1,z),(x,y,z-1),(x,y,z+1)):
            if q in solid and q not in reached:reached.add(q);queue.append(q)
    unsupported=cells-reached
    if unsupported:errors.append(['underpass cells disconnected from founded walls',len(unsupported),list(min(unsupported))])
    for row in report['open_portals']:
        for x,y,z in row:
            for Y in range(y+1,y+5):
                if e.state(x,Y,z).split('[')[0]not in EMPTY:errors.append(['underpass portal blocked',x,Y,z])
    if len(report['open_portals'])!=2:errors.append(['underpass must have two road portals',len(report['open_portals'])])
    report['saved_verification']=dict(errors=errors,structural_cells=len(cells),founded_cells=len(reached),
                                     footing_columns=len(anchors),open_portals=len(report['open_portals']))
    save_json(path,report)
    return errors


def finish(source,out):
    functional=json.loads((source/'functional-check.json').read_text('utf8'))
    if functional.get('composition_errors',functional['errors']):raise ValueError('Composition must pass before lining')
    errors=json.loads((source/'independent-check.json').read_text('utf8'))['errors']
    if any(r[0]!='covered road has no continuous roof'for r in errors):raise ValueError(('Unresolved non-roof errors',errors[:5]))
    out.mkdir(parents=True,exist_ok=False);(out/'source').mkdir()
    for f in (source/'source').glob('*.npz'):os.link(f,out/'source'/f.name)
    for f in source.iterdir():
        if f.name=='source':continue
        if f.is_dir():shutil.copytree(f,out/f.name)
        else:shutil.copy2(f,out/f.name)
    with np.load(out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);e=Editor(out);spec=json.loads((out/'plan/authored-design.json').read_text('utf8'))
    covered=d['covered']&d['walk']
    if not covered.any():raise ValueError('No measured covered road')
    distance,near=distance_transform_edt(~covered,return_indices=True)
    walls=binary_dilation(covered,structure=np.ones((3,3),bool))&~d['walk']
    floor=np.asarray(road_blocks(d['grade2'])[0],int)
    wall_floor=floor[tuple(near)]
    roof_bottom=np.where(covered,floor+5,np.where(walls,wall_floor+5,-128))
    roof_top=np.maximum(roof_bottom,maximum_filter(roof_bottom,size=3))
    roof_cells=set();wall_cells=set();footings=[];proposed={};retained=[]
    for j,i in np.argwhere(covered|walls):
        px,pz=int(x+i),int(z+j);bottom=int(roof_bottom[j,i]);top=int(roof_top[j,i])
        for Y in range(bottom,top+1):roof_cells.add((px,Y,pz))
        if walls[j,i]:
            base=int(wall_floor[j,i])-3
            while base>int(wall_floor[j,i])-20 and not is_bearing(e.state(px,base-1,pz)):base-=1
            if not is_bearing(e.state(px,base-1,pz)):raise ValueError(('No foundation soil within 20m',px,pz))
            footings.append([px,base,pz])
            for Y in range(base,bottom+1):wall_cells.add((px,Y,pz))
    boxes=list(spec.get('protected_volumes',[]))
    boxes.extend([b[0]-2,b[1]-3,b[2]-2,b[3]+2,b[4]+8,b[5]+2]for b in json.loads((out/'plan/retained-buildings.json').read_text('utf8')))
    boxes.extend(r['new_payload_bounds']for r in json.loads((out/'plan/buildings.json').read_text('utf8')))
    rail={};curves=json.loads((out/'plan/native-curves.json').read_text('utf8'))
    for row in curves['trains']:
        for px,py,pz in row['points']:
            px,py,pz=map(int,np.floor([px,py,pz]))
            if px<x-8 or px>X+8 or pz<z-8 or pz>Z+8 or py<-100 or py>310:continue
            for Q in range(px-8,px+9):
                for R in range(pz-8,pz+9):
                    lo,hi=rail.get((Q,R),(320,-129));rail[Q,R]=min(lo,py-30),max(hi,py+7)
    all_cells=roof_cells|wall_cells
    bounds=[min(p[k]for p in all_cells)for k in range(3)]+[max(p[k]for p in all_cells)for k in range(3)]
    spec['train_underpass_roof_infill']=[bounds]
    deck_limits=physical_deck_ceilings(curves['trains'],[bounds[0],bounds[2],bounds[3],bounds[5]])
    with np.load(Path(spec['train_underpass_prior_plan'])/'network.npz')as f:prior={k:f[k]for k in ('bounds','walk','grade2')}
    ux,uz,_,_=map(int,prior['bounds']);rail_masks={};retired_surfaces=[]
    for p in sorted(all_cells):
        before=e.state(*p);bare=before.split('[')[0]
        px,Y,pz=p;old_floor,old_slab=road_blocks(prior['grade2'][pz-uz,px-ux])
        owned_surface=(prior['walk'][pz-uz,px-ux] and Y==int(old_floor) and bare in PAVEMENT
                       and ('type=bottom'in before)==bool(old_slab) and before==e.state(*p,original=True))
        # The ballast and structural members are never replaced by the lining.
        if bare not in EMPTY|SOIL and not owned_surface:
            if not is_bearing(before):raise ValueError(('Unowned nonbearing lining cell',p,before))
            retained.append(list(p));continue
        if any(all(b[k]<=p[k]<=b[k+3]for k in range(3))for b in boxes):raise ValueError(('Lining intersects retained room',p))
        if owned_surface:
            retired_surfaces.append(list(p))
            if (px,pz)in rail:
                spec.setdefault('train_underpasses',[]).append([px,Y,pz,px,Y,pz])
        proposed[p]=CONCRETE
    for p,state in proposed.items():e.put(*p,state)
    for p in proposed:
        px,Y,pz=p
        if (px,pz)not in rail:continue
        lo,hi=rail[px,pz];lo,hi=max(-128,lo),min(319,hi)
        if not lo<=Y<=hi:continue
        if (px,pz)not in rail_masks:
            mask=editable_underpass_column(e,px,pz,lo,hi,spec.get('train_underpasses',[]),prior['walk'][pz-uz,px-ux],prior['grade2'][pz-uz,px-ux])
            mask|=allowed_roof_infill_column(e,px,pz,lo,hi,spec['train_underpass_roof_infill'],deck_limits[px,pz]);rail_masks[px,pz]=mask
        if not rail_masks[px,pz][Y-lo]:raise ValueError(('Lining enters retained railway member or clearance',p,e.state(*p,original=True),lo,hi))
    lights=[]
    for px,base,pz in footings:
        j,i=pz-z,px-x;Y=int(wall_floor[j,i])+3;p=(px,Y,pz)
        if p not in proposed or any(abs(px-q[0])+abs(pz-q[2])<8 for q in lights):continue
        if (px,pz)in rail:
            lo,hi=rail[px,pz];lo,hi=max(-128,lo),min(319,hi)
            if lo<=Y<=hi:
                mask=editable_underpass_column(e,px,pz,lo,hi,spec.get('train_underpasses',[]),prior['walk'][pz-uz,px-ux],prior['grade2'][pz-uz,px-ux])
                if not mask[Y-lo]:continue
        proposed[p]='minecraft:sea_lantern';e.put(*p,proposed[p]);lights.append(list(p))
    portals=covered&binary_dilation(d['walk']&~covered)
    groups,n=label(portals,structure=np.ones((3,3),int));open_portals=[]
    for k in range(1,n+1):open_portals.append([[int(x+i),int(floor[j,i]),int(z+j)]for j,i in np.argwhere(groups==k)])
    patches=e.save()
    d['ground']=ground(e,list(map(int,d['bounds'])))
    np.savez_compressed(out/'plan/network.npz',**d);save_json(out/'plan/authored-design.json',spec)
    save_json(out/'underpass-structure.json',dict(bounds=bounds,roof_cells=[list(p)for p in sorted(roof_cells)],
        wall_cells=[list(p)for p in sorted(wall_cells)],footings=footings,open_portals=open_portals,lights=lights,
        retained_structural_cells=retained,retired_declared_surface_cells=retired_surfaces,changes=[]))
    # A compact audit records actual pre-lining cells without reopening a region per cell.
    before=Editor(source);record=json.loads((out/'underpass-structure.json').read_text('utf8'))
    record['changes']=[dict(pos=list(p),before=before.state(*p),after=s)for p,s in proposed.items()if before.state(*p)!=s]
    save_json(out/'underpass-structure.json',record)
    manifest=json.loads((out/'manifest.json').read_text('utf8'));manifest.update(regions=patches,cells=sum(r['cells']for r in patches));save_json(out/'manifest.json',manifest)
    save_json(out/'launch-protection.json',check_candidate(load(Path(manifest['world'])),out))
    report=verify(out)
    if report['errors']:raise ValueError(('Underpass verification failed',report['errors'][:10]))
    print(dict(lining_cells=len(record['changes']),roof_cells=len(roof_cells),wall_cells=len(wall_cells),lights=len(lights),portals=len(open_portals)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();finish(a.source,a.out)
