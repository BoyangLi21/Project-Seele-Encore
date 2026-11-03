"""Merge an installed neighbourhood into the current whole-map planning frame."""
import argparse,copy,json,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR
from prepare_hakone_togendai_neighbourhood import save_json

def publish(a):
    receipt=json.loads(a.installation.read_text('utf8'))
    if receipt['status']!='installed'or not receipt['changed_section_readback']:raise ValueError('Current-save installation required')
    if a.candidate.resolve()not in [Path(p).resolve()for p in receipt['candidates']]:raise ValueError('Receipt belongs to another candidate')
    shutil.copytree(a.previous,a.out)
    with np.load(a.previous/'network.npz')as f:g={k:f[k]for k in f.files}
    gx,gz,gX,gZ=map(int,g['bounds'])
    for plan in a.overlay_plan:
        with np.load(plan/'network.npz')as f:
            ox,oz,oX,oZ=map(int,f['bounds']);l,t,R,B=max(gx,ox),max(gz,oz),min(gX,oX),min(gZ,oZ)
            if l>R or t>B:continue
            for key in g:
                if key!='bounds'and key in f.files:g[key][t-gz:B-gz+1,l-gx:R-gx+1]=f[key][t-oz:B-oz+1,l-ox:R-ox+1]
    with np.load(a.candidate/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);bx,bz,_,_=map(int,g['bounds']);area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
    oldwalk=g['walk'][area].copy();e=Editor(a.candidate);retired=0
    for j,i in np.argwhere(oldwalk&~d['walk']):
        px,pz=int(i+x),int(j+z);h,_=road_blocks(g['grade2'][area][j,i]);h=int(h)
        if e.state(px,h,pz).split('[')[0]in PAVEMENT and all(e.state(px,Y,pz).split('[')[0]in AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern'}for Y in (h+1,h+2)):continue
        for key in ('road','walk','marking','tunnel'):g[key][area][j,i]=False
        retired+=1
    for key in ('road','walk','marking','tunnel'):g[key][area][d['walk']]=d[key][d['walk']]
    g['grade2'][area][d['walk']]=d['grade2'][d['walk']]
    for key in ('ground','old_ground'):g[key][area]=d[key]
    np.savez_compressed(a.out/'network.npz',**g)
    updated={r['id']:r for r in json.loads((a.candidate/'plan/buildings.json').read_text('utf8'))}
    footways={r['parcel']:r['points']for r in json.loads((a.candidate/'plan/footways.json').read_text('utf8'))}
    catalog={r['id']:r for r in json.loads((a.previous/'catalog.json').read_text('utf8'))}
    for plan in a.overlay_plan:
        if (plan/'catalog.json').exists():catalog.update({r['id']:r for r in json.loads((plan/'catalog.json').read_text('utf8'))})
    catalog=list(catalog.values())
    for row in catalog:
        if row.get('id')not in updated:continue
        revised=updated[row['id']];dy=revised['dy'];row['site']=copy.deepcopy(revised['site']);row['door']=revised['door'];row['approach']=revised['approach']
        for k in (1,4):row['occupied_bounds'][k]+=dy
        for device in row['devices']:device['target'][1]+=dy
        # Replace stale approach levels with the current installed path frame.
        points=footways[row['id']];path=[]
        for p,q in zip(points,points[1:]):
            steps=max(1,int(np.ceil(np.linalg.norm(np.asarray(q)[[0,2]]-np.asarray(p)[[0,2]]))))
            for t in np.linspace(0,1,steps+1):
                px,pz=map(int,np.rint(np.asarray(p)[[0,2]]*(1-t)+np.asarray(q)[[0,2]]*t));j,i=pz-z,px-x
                py=float(d['grade2'][j,i])/2+1 if d['walk'][j,i]else revised['site']['floor']+1
                if not path or path[-1]!=[px,py,pz]:path.append([px,py,pz])
        row['footway']=path;row['installed_neighbourhood']=a.candidate.name
    save_json(a.out/'catalog.json',catalog)
    save_json(a.out/'neighbourhood-authority.json',dict(installation=str(a.installation),candidate=str(a.candidate),previous=str(a.previous),overlaid_current_plans=[str(p)for p in a.overlay_plan],planning_bounds=g['bounds'].tolist(),outside_frame_keeps_its_separate_installed_authority=True,parcels_updated=len(updated),retired_unwalkable_old_columns=retired,current_neighbourhood_public_columns=int(d['walk'].sum()),parcel_moves_already_installed=True,whole_map_complete=False,global_legacy_connectivity_report_requires_refresh=True))
    print('Published current planning authority:',len(updated),'parcel addresses;',retired,'retired old surface columns',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','previous','installation','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--overlay-plan',type=Path,action='append',default=[])
    publish(p.parse_args())
