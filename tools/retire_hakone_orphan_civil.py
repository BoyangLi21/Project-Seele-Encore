"""Retire complete, unowned civil components from a current 3D survey.

Only surveyed components without building, transit, active-walk, actor, device,
unknown-material or crop-boundary contacts are eligible. Terrain and native
waters remain exact; buried civil cells become soil at their measured level.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation,binary_fill_holes
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from author_hakone_lakefront import Editor
from query_blocks import AIR,iter_block_entities
from install_r53_carrier_trays import stopped_world
from repair_hakone_funicular_civil import CIVIL
from plan_ashi_landscape_r54 import NATURAL,SOIL,PLANTS
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground

def run(a):
    cap=json.loads((a.source/'capture.json').read_text('utf8'));world=Path(cap['world']);x,z,X,Z=cap['bounds_xz']
    rows=json.loads((a.survey/'components.json').read_text('utf8'));selected=[r for r in rows if not(r['protected']or r['foreign_contact']or r['cropped'])]
    with np.load(a.survey/'components.npz')as f:
        bounds=list(map(int,f['bounds']));groups=f['groups'];guard=f['guard']
    if [bounds[0],bounds[2],bounds[3],bounds[5]]!=[x,z,X,Z]:raise ValueError('Different survey extent')
    active=np.isin(groups,[r['id']for r in selected]);lo=bounds[1]
    if np.any(active&guard):raise ValueError('Protected component selected')
    a.out.mkdir(parents=True,exist_ok=False)
    for name in ('source','delta','plan'):(a.out/name).mkdir()
    for p in (a.source/'source').glob('*.npz'):os.link(p,a.out/'source'/p.name)
    shutil.copy2(a.source/'capture.json',a.out/'capture.json')
    with np.load(a.source/'measured.npz')as f:old=f['top']
    e=Editor(a.out);launch=load(world);masks={};materials={}
    with stopped_world(world):
        shutil.copytree(world/'mtr',a.out/'preserved-native');devices={p for p,t in iter_block_entities(world,'projectseele:geofront',(x,-128,z),(X,319,Z))}
    for iy,iz,ix in zip(*np.nonzero(active)):
        px,py,pz=x+int(ix),lo+int(iy),z+int(iz);state=e.state(px,py,pz);bare=state.split('[')[0]
        if bare not in CIVIL:raise ValueError(('Survey source mismatch',px,py,pz,state))
        key=px//16,pz//16
        if key not in masks:masks[key]=launch.chunk_mask(*key)
        if (px,py,pz)in devices or masks[key][py+128,pz%16,px%16]:raise ValueError(('Native mechanism or device',px,py,pz))
        g=int(old[iz,ix]);replacement='minecraft:air'if py>g else'minecraft:grass_block[snowy=false]'if py==g else'minecraft:dirt'
        e.put(px,py,pz,replacement);materials[bare]=materials.get(bare,0)+1
    # Removing only pavement exposes the old brown road bed and leaves the
    # rectangular plot scars. Rejoin the complete footprint to surrounding
    # measured hillsides with a Dirichlet height solve, retaining tree roots,
    # current structures and actual native water cells.
    heal=binary_dilation(binary_fill_holes(active.any(0)),iterations=8)&~guard.any(0)
    heal[[0,-1],:]=False;heal[:,[0,-1]]=False;fixed=np.zeros(old.shape,bool)
    water=np.full(old.shape,-129,np.int16)
    for file in (a.source/'source').glob('*.npz'):
        rx,rz=map(int,file.stem.split('.')[1:]);r=e.region(rx*512,rz*512)
        bare=[s.split('[')[0]for s in r['names']];unknown=np.array([s not in NATURAL|{'minecraft:light','minecraft:barrier','minecraft:structure_void'}for s in bare]);trees=np.array([s.endswith(('_log','_leaves'))for s in bare]);wet=np.array([s=='minecraft:water'for s in bare]);yy=np.arange(-128,320)[:,None,None]
        for(cx,cz),v in zip(r['coords'],r['after']):
            ar=np.s_[cz*16-z:cz*16-z+16,cx*16-x:cx*16-x+16];g=old[ar]
            fixed[ar]=(unknown[v]&(yy>=g-20)&(yy<=g+20)).any(0)|trees[v].any(0)
            water[ar]=np.where(wet[v],yy,-129).max(0)
    heal&=~binary_dilation(fixed,iterations=2)
    izs,ixs=np.nonzero(heal);index=np.full(old.shape,-1,np.int32);index[heal]=np.arange(len(izs));rr=[];cc=[];dd=[];rhs=np.zeros(len(izs))
    for iz,ix in zip(izs,ixs):
        i=int(index[iz,ix]);rr.append(i);cc.append(i);dd.append(4.)
        for j,k in ((iz-1,ix),(iz+1,ix),(iz,ix-1),(iz,ix+1)):
            if heal[j,k]:rr.append(i);cc.append(int(index[j,k]));dd.append(-1.)
            else:rhs[i]+=float(old[j,k])
    target=old.copy()
    if len(izs):target[heal]=np.rint(spsolve(coo_matrix((dd,(rr,cc)),shape=(len(izs),len(izs))).tocsr(),rhs)).astype(np.int16)
    target[heal]=np.clip(target[heal],old[heal]-12,old[heal]+12)
    # Tiny old enclosed water pockets stay intact below the restored ground.
    target[heal]=np.maximum(target[heal],water[heal]+1)
    for iz,ix in zip(izs,ixs):
        px,pz=x+int(ix),z+int(iz);g,h=int(old[iz,ix]),int(target[iz,ix])
        for py in range(min(g,h)-6,max(g,h)+2):
            before=e.state(px,py,pz);bare=before.split('[')[0]
            if bare=='minecraft:water':continue
            if bare not in SOIL|AIR|PLANTS|{'minecraft:light'}:raise ValueError(('Restoration touches unclassified object',px,py,pz,before))
            state='minecraft:air'if py>h else'minecraft:grass_block[snowy=false]'if py==h else'minecraft:dirt'if py>=h-3 else'minecraft:stone'
            key=px//16,pz//16
            if key not in masks:masks[key]=launch.chunk_mask(*key)
            if before!=state and ((px,py,pz)in devices or masks[key][py+128,pz%16,px%16]):raise ValueError(('Restoration enters native device',px,py,pz))
            e.put(px,py,pz,state)
    regions=e.save();after=Editor(a.out);errors=[]
    # Compare all changed states to the immutable source, not a material count.
    for iy,iz,ix in zip(*np.nonzero(active)):
        px,py,pz=x+int(ix),lo+int(iy),z+int(iz)
        if after.state(px,py,pz).split('[')[0]in CIVIL:errors.append(['residual-component-cell',px,py,pz])
    actual=ground(Editor(a.out),cap['bounds_xz']);empty=np.zeros(old.shape,bool)
    np.savez_compressed(a.out/'plan/network.npz',bounds=cap['bounds_xz'],ground=actual,old_ground=old,walk=empty,road=empty,grade2=np.zeros(old.shape,np.int16),tunnel=empty,marking=empty)
    for iz,ix in zip(izs,ixs):
        if after.state(x+int(ix),int(target[iz,ix]),z+int(iz)).split('[')[0]!='minecraft:grass_block':errors.append(['restored-ground-surface-missing',int(ix+x),int(iz+z)])
    report=dict(errors=errors,retired_complete_components=len(selected),retired_cells=int(active.sum()),healed_hillside_columns=int(heal.sum()),retired_materials=materials,source_survey=str(a.survey),retired_components=selected,protected_component_edits=0,native_water_edits=0,visual_verified=False)
    (a.out/'functional-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    manifest=dict(world=str(world),bounds_xz=cap['bounds_xz'],regions=regions,cells=sum(r['cells']for r in regions),world_written=False,progress_files_written=[])
    (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8');(a.out/'launch-protection.json').write_text(json.dumps(check_candidate(launch,a.out),indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items()if k!='retired_components'}),flush=True)
    if errors:raise ValueError('Incomplete component retirement')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('source','survey','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
