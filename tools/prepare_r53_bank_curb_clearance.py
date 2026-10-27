"""Author retained edge returns at all three banks without moving bearing rails.

The original source stays immutable. The independent overlay replaces exact
RGB facets in the shared drawing/collision input, with a continuous side return.
No save, installation metadata or live actor is edited.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def rotation(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def clip(poly,z,above):
    out=[];a=poly[-1];inside=lambda p:p[2]>=z if above else p[2]<=z
    for b in poly:
        if inside(a)!=inside(b):out.append(a+(b-a)*((z-a[2])/(b[2]-a[2])))
        if inside(b):out.append(b.copy())
        a=b
    return out


def bank_ports(units):
    # The vertical head crosses the floor before the turn-only return plateau.
    # Extend its leading transition 0.6 m; keep the bearing rails and head intact.
    return [dict(centre=72.5-42*u,side=side,knots=[z-48*bank for z in knots],unit=u,bank=bank+1)
            for u in units for bank in range(3) for side,knots in
            ((-1,[138.2,138.5,140.15,140.9]),(1,[108.7,109.3,110.65,111.25]))]


def prepare(asset,native):
    original=json.loads((asset/'mesh/legacy_running_heads_r52.json').read_text())
    bypass=json.loads((asset/'mesh/legacy_service_bypass_r52.json').read_text())
    compact=json.loads((asset/'mesh/legacy_compact_level_r52.json').read_text())
    retained=np.array(original['parts']['legacy_original_retained']).reshape(-1,3,6)
    retained=np.delete(retained,bypass['removed_triangle_indices'],axis=0)
    f=next(p['frame']for p in native['legacy']if p['name']=='legacy_original_retained')
    matrix=rotation(f['rotation']);origin=np.array(f['translation'])
    targets=[('legacy_original_retained',retained,matrix,origin,bank_ports(range(3)))]
    for u in range(3):
        part=next(p for p in compact['components']if p['name']==f'level_actual/{u}/compact_96m')
        targets.append((part['name'],np.array(part['triangles_rgb']).reshape(-1,3,6),np.eye(3),np.array([0,-384,0]),
                        bank_ports([u])))
    changes=[]
    for name,triangles,matrix,origin,ports in targets:
        removed=[];replacement=[]
        for index,source in enumerate(triangles):
            world=source.copy();world[:,:3]=source[:,:3]@matrix.T+origin
            candidates=[]
            for port in ports:
                edge=port['centre']+port['side']*15;lo,hi=sorted((edge,edge+port['side']*.14));knots=port['knots']
                if world[:,0].min()>=lo-.0001 and world[:,0].max()<=hi+.0001 and world[:,2].max()>knots[0] and world[:,2].min()<knots[-1]:
                    local=clip(clip(list(world),knots[0],True),knots[-1],False)
                    if local and min(p[1]for p in local)>-1031:candidates.append(port)
            if not candidates:continue
            pieces=[list(world)]
            for z in sorted(set(z for port in candidates for z in port['knots'])):
                divided=[]
                for poly in pieces:
                    if min(p[2]for p in poly)<z<max(p[2]for p in poly):
                        divided.extend([clip(poly,z,False),clip(poly,z,True)])
                    else:divided.append(poly)
                pieces=divided
            out=[]
            for poly in pieces:
                for p in poly:
                    p[0]+=sum(port['side']*.6*np.interp(p[2],port['knots'],[0,1,1,0]) for port in candidates)
                    p[:3]=(p[:3]-origin)@np.linalg.inv(matrix).T
                for i in range(1,len(poly)-1):
                    tri=np.array([poly[0],poly[i],poly[i+1]])
                    if np.linalg.norm(np.cross(tri[1,:3]-tri[0,:3],tri[2,:3]-tri[0,:3]))>1e-12:out.extend(tri.reshape(-1).tolist())
            removed.append(dict(index=index,original_rgb=source.reshape(-1).tolist()))
            replacement.extend(out)
        assert removed and replacement
        changes.append(dict(part=name,source_triangle_count=len(triangles),removed=removed,replacement_rgb=replacement))
    return dict(schema='projectseele.r53.original-bank-curb-return.v1',
                original_sources={key:json.loads((asset/key).read_text()).get('schema')for key in
                    ['mesh/legacy_running_heads_r52.json','mesh/legacy_service_bypass_r52.json','mesh/legacy_compact_level_r52.json']},
                mechanism='Continuous 0.6m outboard returns in the existing bank equipment edge; original lower floor and bearing heads retained.',
                ports=[dict(unit=p['unit'],bank=p['bank'],side=p['side'],z=p['knots'],outboard=.6)
                       for p in bank_ports(range(3))],
                targets=changes,world_written=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--assets',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=prepare(a.assets,json.loads(a.native.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,separators=(',',':'))+'\n')
    print('Prepared four exact source deltas across eighteen declared edge positions; absent edges, floor and bearing heads retained.')
