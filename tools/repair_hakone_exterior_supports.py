"""Repair explicitly reviewed detached exterior fixtures without changing rooms.

Requires complete saved-voxel components. Supports fill only measured AIR down
to a solid footing. Removals are tiny, non-device smooth-stone remnants outside
occupied buildings. Every payload collar change has a chained exact exception.
"""
import argparse,json,os,shutil
from collections import Counter
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from detail_hakone_nerv_streets import preservation_mask
from map_pipeline.payload_exceptions import record_exception
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from prepare_hakone_togendai_neighbourhood import save_json,PAVE
from plan_ashi_landscape_r54 import SOIL
from query_blocks import AIR
from verify_hakone_togendai_neighbourhood import verify
from verify_hakone_station_connection import verify as station_verify

def repair(a):
    for name in ('functional-check.json','independent-check.json'):
        if json.loads((a.source/name).read_text('utf8'))['errors']:raise ValueError('Unverified source')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.source,a.out,copy_function=copy)
    e=Editor(a.out);spec=json.loads((a.out/'plan/authored-design.json').read_text('utf8'))
    protected=preservation_mask(a.out,spec)
    with np.load(a.out/'plan/network.npz') as f:d={k:f[k] for k in f.files}
    x,z,X,Z=map(int,d['bounds'])
    rows=json.loads((a.out/'plan/buildings.json').read_text('utf8'))
    tags={tuple(int(t[k]) for k in ('x','y','z')) for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    outdoor=json.loads((a.out/'outdoor-apron-corrections.json').read_text('utf8'))
    components={r['id']:r for r in json.loads((a.components/'floating-components.json').read_text('utf8'))['components']}
    changes=[];repairs=[]
    def points(row):
        result=[]
        for rx,rz,label in row['parts']:
            with np.load(a.components/f'r.{rx}.{rz}.npz') as f:
                yy,zz,xx=np.unravel_index(f['indices'][f['labels']==label],(448,512,512))
            result.extend((int(Q+rx*512),int(Y-128),int(R+rz*512)) for Q,Y,R in zip(xx,yy,zz))
        if len(result)!=row['cells']:raise ValueError('Incomplete component coordinates')
        return result
    def put(pos,state,kind):
        px,py,pz=pos
        if not(x<=px<=X and z<=pz<=Z and -128<=py<=319):raise ValueError(('Outside capture',pos))
        if pos in tags or protected(pos):raise ValueError(('Protected exterior cell',pos))
        if any(all(r['occupied_bounds'][k]<=pos[k]<=r['occupied_bounds'][k+3] for k in range(3)) for r in rows):raise ValueError(('Occupied building',pos))
        j,i=pz-z,px-x
        if d['walk'][j,i]:raise ValueError(('Public walkway obstruction',pos))
        before=e.state(*pos)
        for r in rows:
            if all(r['new_payload_bounds'][k]<=pos[k]<=r['new_payload_bounds'][k+3] for k in range(3)):
                record_exception(outdoor,dict(parcel=r['id'],kind=kind,pos=list(pos),before=before,after=state))
        changes.append(dict(pos=list(pos),before=before,after=state,kind=kind));e.put(*pos,state)
    for request in json.loads(a.plan.read_text('utf8'))['repairs']:
        row=components[request['component']]
        if row['unknown'] or row['cells']>32:raise ValueError(('Unbounded or large component',row['id']))
        cells=points(row)
        if dict(Counter(e.state(*p) for p in cells))!=row['materials']:raise ValueError(('Stale component material survey',row['id']))
        if request['action']=='support':
            q=tuple(request['base'])
            if q not in cells or (q[0],q[1]-1,q[2]) in cells:raise ValueError('Support is not a bottom face')
            material=request['material']
            if material not in {'minecraft:polished_andesite','minecraft:polished_deepslate','minecraft:gray_concrete','minecraft:smooth_stone'}:raise ValueError('Unsupported foundation material')
            pending=[]
            for depth in range(1,7):
                pos=q[0],q[1]-depth,q[2];state=e.state(*pos);mat=state.split('[')[0]
                if mat in AIR:pending.append(pos);continue
                if mat not in SOIL|PAVE or 'type=bottom' in state or mat.endswith('_stairs'):raise ValueError(('No sound full footing',pos,state))
                break
            else:raise ValueError(('Footing exceeds six-block survey',q))
            if not pending:raise ValueError('Component already has direct footing')
            for pos in reversed(pending):put(pos,material,'measured exterior fixture footing')
        elif request['action']=='retire':
            if len(cells)>2 or any(e.state(*p)!='minecraft:smooth_stone' for p in cells):raise ValueError('Removal exceeds reviewed tiny paving remnants')
            for pos in cells:put(pos,'minecraft:air','detached exterior paving remnant')
        else:raise ValueError('Unknown repair action')
        repairs.append(dict(component=row['id'],action=request['action'],original_cells=len(cells),bounds=row['bounds']))
    patches=e.save();e.regions.clear()
    d['ground']=ground(Editor(a.out),list(map(int,d['bounds'])));np.savez_compressed(a.out/'plan/network.npz',**d)
    m=json.loads((a.out/'manifest.json').read_text('utf8'));m.update(regions=patches,cells=sum(r['cells'] for r in patches))
    save_json(a.out/'manifest.json',m);save_json(a.out/'outdoor-apron-corrections.json',outdoor)
    save_json(a.out/'exterior-support-repairs.json',dict(components_source=str(a.components),repairs=repairs,changes=changes,rooms_changed=0,devices_changed=0))
    save_json(a.out/'launch-protection.json',check_candidate(load(Path(m['world'])),a.out))
    if verify(a.out)['errors'] or station_verify(a.out)['errors']:raise ValueError('Exterior repair regression')
    print('Repaired',len(repairs),'reviewed exterior components;',len(changes),'changed cells',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','components','plan','out'):p.add_argument('--'+name,type=Path,required=True)
    repair(p.parse_args())
