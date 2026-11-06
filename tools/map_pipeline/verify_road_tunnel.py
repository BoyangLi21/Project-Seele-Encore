"""Independently read tunnel crowns, exterior cover and retained old objects."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.corridors import alignment
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from verify_hakone_network_candidate import PAVEMENT


def verify(candidate):
    e=Editor(candidate);errors=[];rows=[]
    specs={r['id']:r for r in json.loads((candidate/'authored-design.json').read_text('utf8'))['streets']}
    for path in(candidate/'earthworks').glob('*.npz'):
        spec=specs[path.stem]
        if not spec.get('tunnel'):continue
        with np.load(path)as f:d={k:f[k]for k in f.files}
        x,z,X,Z=map(int,d['bounds']);floor,_=road_blocks(d['grade2']);n=int(d['clearance'])
        curve,s=alignment(spec);tree=cKDTree(curve[:,[0,2]]);covers=[];lights=0;roof=0;wall=0
        for j,i in np.argwhere(d['tunnel']):
            xx,zz,yy=x+int(i),z+int(j),int(floor[j,i]);_,near=tree.query([xx,zz]);station=float(s[near])
            for h in range(yy+n+1,yy+n+3):
                state=e.state(xx,h,zz).split('[')[0];roof+=1;lights+=int(state=='minecraft:sea_lantern')
                if state not in {'minecraft:stone_bricks','minecraft:sea_lantern'}:errors.append(['crown',xx,h,zz,state])
            cover=int(d['old'][j,i])-yy-n-2;covers.append(cover)
            # The two outermost portal rows may meet sloping ground in the
            # face. The body must remain buried, with no exposed roof box.
            a,b=spec['tunnel']['along']
            if a+3<station<b-3 and cover<0:errors.append(['exposed crown',xx,yy+n+2,zz,cover])
            if d['target'][j,i]!=d['old'][j,i]:errors.append(['ridge was regraded to tunnel floor',xx,zz])
        for j,i in np.argwhere(d['tunnel_wall']):
            xx,zz,yy=x+int(i),z+int(j),int(floor[j,i])
            for h in range(yy-1,yy+n+3):
                wall+=1
                if e.state(xx,h,zz)!='minecraft:stone_bricks':errors.append(['lining',xx,h,zz])
        # Grade is measured over ten metres, not a single half-block raster
        # step. The fitted interface may differ from the ideal design curve.
        heights=[]
        for xx,_,zz in curve:
            i,j=int(round(xx))-x,int(round(zz))-z;yy=int(floor[j,i]);state=e.state(int(round(xx)),yy,int(round(zz)))
            heights.append(yy+(.5 if 'type=bottom'in state else 1))
        distance=np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve[:,[0,2]],axis=0),axis=1))]
        maxgrade=0
        for i,t in enumerate(distance):
            j=int(np.searchsorted(distance,t+10))
            if j<len(distance):maxgrade=max(maxgrade,abs(heights[j]-heights[i])/(distance[j]-t))
        if maxgrade>spec.get('maximum_fitted_grade',.25):errors.append(['fitted longitudinal grade',maxgrade])
        if not lights:errors.append(['tunnel lighting missing'])
        wing=0
        for j,i in np.argwhere(d.get('portal_wing',np.zeros(d['walk'].shape,bool))):
            xx,zz,yy=x+int(i),z+int(j),int(floor[j,i])
            for h in range(yy-1,int(d['target'][j,i])):
                wing+=1
                if e.state(xx,h,zz)!='minecraft:stone_bricks':errors.append(['portal wing wall',xx,h,zz])
        for dz,dx in ((1,0),(0,1)):
            a=abs(d['old']-np.roll(d['old'],(-dz,-dx),(0,1)))
            b=abs(d['target']-np.roll(d['target'],(-dz,-dx),(0,1)))
            outside=~d['walk']&~np.roll(d['walk'],(-dz,-dx),(0,1))
            bad=outside&(b>a+1)&(b>3);bad[[0,-1]]=False;bad[:,[0,-1]]=False
            for j,i in np.argwhere(bad):errors.append(['new exterior cliff',x+int(i),z+int(j),int(a[j,i]),int(b[j,i])])
        rows.append(dict(id=path.stem,crown_cells=roof,wall_cells=wall,portal_wing_cells=wing,ceiling_lights=lights,
                         minimum_cover=min(covers),maximum_ten_metre_grade=maxgrade,ridge_surface_preserved=True))
    retirement=candidate/'retirement-check.json'
    if retirement.exists():
        r=json.loads(retirement.read_text('utf8'))
        for p in r['scope'].get('preserved_points',[]):
            if e.state(*p['pos'])!=p['state']:errors.append(['old retained object changed',p['pos']])
        with np.load(candidate/'plan/network.npz')as f:p={k:f[k]for k in ('bounds','walk','grade2')}
        x,z,_,_=map(int,p['bounds']);floors,_=road_blocks(p['grade2'])
        for xx,zz,lo,hi in r['observed_road_layers']:
            for yy in range(lo,hi+1):
                state=e.state(xx,yy,zz).split('[')[0]
                if state not in PAVEMENT or any(e.state(xx,h,zz).split('[')[0]not in AIR|PLANTS|{'minecraft:light'}for h in(yy+1,yy+2)):continue
                if not p['walk'][zz-z,xx-x] or yy!=int(floors[zz-z,xx-x]):
                    errors.append(['superseded clear road layer remains',xx,yy,zz,state])
    report=dict(errors=errors,tunnels=rows,actual_game_visual_acceptance=False,whole_map_complete=False)
    (candidate/'tunnel-check.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report if len(errors)<10 else dict(errors=len(errors),examples=errors[:10],tunnels=rows)),flush=True)
    if errors:raise ValueError('Road tunnel verification failed')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__);p.add_argument('--candidate',type=Path,required=True)
    verify(p.parse_args().candidate)
