"""Expose selected retained facades by removing only measured exterior soil.

Occupied room columns remain intact. The outer soil collar and soil above the
complete surveyed roof envelope are explicit payload exceptions with before
and after block states; device and railway invariants are verified afterward.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL
from map_pipeline.launch_earthworks import ground
from map_pipeline.launch_protection import load,check_candidate
from verify_hakone_togendai_neighbourhood import verify

def run(a):
    for file in ('functional-check.json','independent-check.json'):
        if json.loads((a.candidate/file).read_text('utf8'))['errors']:raise ValueError('Verify candidate before exterior excavation')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.candidate,a.out,copy_function=copy);e=Editor(a.out)
    rows=json.loads((a.out/'plan/buildings.json').read_text('utf8'));selected=[r for r in rows if r['id']in a.parcel]
    if len(selected)!=len(a.parcel):raise ValueError('Unknown or duplicated parcel')
    exceptions={tuple(r['pos']):r for r in json.loads((a.out/'outdoor-apron-corrections.json').read_text('utf8'))};report=[]
    for row in selected:
        s=row['site'];cx,cz=s['centre'];hx,hz=s['half'];hx,hz=(hz,hx)if s['rotation']%2 else(hx,hz)
        # occupied_bounds includes the whole roof rather than just windowed
        # storeys; no soil at an indoor or attic position is removed.
        wall=[cx-hx,cz-hz,cx+hx,cz+hz];roof=s['floor']+s['floors']*5+9
        box=row['new_payload_bounds'];changed=[]
        for px in range(box[0],box[3]+1):
            for pz in range(box[2],box[5]+1):
                outside=not(wall[0]<=px<=wall[2]and wall[1]<=pz<=wall[3])
                for py in range(max(box[1],s['floor']+1),box[4]+1):
                    if not outside and py<=roof:continue
                    before=e.state(px,py,pz)
                    if before.split('[')[0]not in SOIL:continue
                    pos=(px,py,pz)
                    if pos in {tuple(p)for p in row['devices']}:raise ValueError('Exterior soil intersects retained device')
                    old=exceptions.get(pos)
                    if old and old['after']!=before:raise ValueError('Exterior exception chain mismatch')
                    exceptions[pos]=dict(parcel=row['id'],kind='measured exterior soil collar',pos=list(pos),before=old['before']if old else before,after='minecraft:air')
                    changed.append(dict(pos=list(pos),before=before));e.put(*pos,'minecraft:air')
        report.append(dict(parcel=row['id'],room_columns_preserved=wall,roof_envelope_top=roof,soil_cells=len(changed),changes=changed))
    patches=e.save();e.regions.clear()
    with np.load(a.out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    d['ground']=ground(Editor(a.out),list(map(int,d['bounds'])));np.savez_compressed(a.out/'plan/network.npz',**d)
    m=json.loads((a.out/'manifest.json').read_text('utf8'));m.update(regions=patches,cells=sum(r['cells']for r in patches))
    for name,data in [('manifest.json',m),('outdoor-apron-corrections.json',list(exceptions.values())),('exterior-soil-excavation.json',report),('launch-protection.json',check_candidate(load(Path(m['world'])),a.out))]:(a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    if verify(a.out)['errors']:raise ValueError('Regression after exterior soil removal')
    print('Exposed',len(selected),'retained facades;',sum(r['soil_cells']for r in report),'exterior soil cells removed',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--parcel',action='append',required=True);run(p.parse_args())
