"""Restore finite original passenger paths after surrounding road earthworks.

Only the existing three-wide platform approach is eligible. Every touched
block must be known soil or pavement; station rooms, native railway corridors
and device payloads retain their independent full-volume checks.
"""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from plan_ashi_landscape_r54 import SOIL,PLANTS
from query_blocks import AIR
from prepare_hakone_togendai_neighbourhood import PAVE
from map_pipeline.launch_protection import load,check_candidate
from map_pipeline.launch_earthworks import ground
from verify_hakone_togendai_neighbourhood import verify
from verify_hakone_station_connection import verify as station_verify

def run(a):
    for name in('functional-check.json','independent-check.json'):
        if json.loads((a.candidate/name).read_text('utf8'))['errors']:raise ValueError('Road candidate is not verified')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.candidate,a.out,copy_function=copy);e=Editor(a.out)
    with np.load(a.out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);rows=json.loads((a.out/'plan/buildings.json').read_text('utf8'))
    tags={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']}
    outdoor={tuple(r['pos']):r for r in json.loads((a.out/'outdoor-apron-corrections.json').read_text('utf8'))};changes=[];links=[]
    for row in rows:
        if row.get('kind')!='station':continue
        paths=[p for p in row['original_approach_paths']if p[-1]==row['platform']]
        if len(paths)!=1:raise ValueError(('Original passenger path not unique',row['id']))
        cols={}
        for px,py,pz in paths[0]:
            for dx in(-1,0,1):
                for dz in(-1,0,1):cols[px+dx,pz+dz]=py
        for(px,pz),floor in cols.items():
            j,i=pz-z,px-x
            if d['walk'][j,i]and abs(int(d['grade2'][j,i])-floor*2)>1:raise ValueError(('Passenger path conflicts with new street',px,pz))
            for py in range(floor-2,floor+4):
                pos=px,py,pz;before=e.state(*pos);after='minecraft:stone'if py<floor else'minecraft:smooth_stone'if py==floor else'minecraft:air'
                # Existing sound bearing and existing pavement stay exact,
                # including every block inside retained station envelopes.
                if py<floor and before.split('[')[0]not in AIR|PLANTS|{'minecraft:water','minecraft:light'}:continue
                if py==floor and before.split('[')[0]in PAVE and 'type=bottom'not in before:continue
                if py>floor and before.split('[')[0]in AIR|{'minecraft:light'}:continue
                if before==after:continue
                if pos in tags or before.split('[')[0]not in SOIL|PAVE|AIR|PLANTS|{'minecraft:light'}:raise ValueError(('Passenger path would overwrite an unowned object',pos,before))
                old=outdoor.get(pos)
                if old and old['after']!=before:raise ValueError('Passenger path exception mismatch')
                rec=dict(parcel=row['id'],kind='original platform passenger path',pos=list(pos),before=old['before']if old else before,after=after)
                outdoor[pos]=rec;changes.append(rec);e.put(*pos,after)
            d['walk'][j,i]=True;d['grade2'][j,i]=floor*2
        links.append(dict(station=row['station_id'],columns=len(cols),original_path=paths[0]))
    patches=e.save();e.regions.clear();d['ground']=ground(Editor(a.out),list(map(int,d['bounds'])));np.savez_compressed(a.out/'plan/network.npz',**d)
    m=json.loads((a.out/'manifest.json').read_text('utf8'));m.update(regions=patches,cells=sum(r['cells']for r in patches));m['neighbourhood_verification']['public_columns']=int(d['walk'].sum())
    for name,data in [('manifest.json',m),('outdoor-apron-corrections.json',list(outdoor.values())),('station-platform-paths.json',dict(links=links,changed=changes)),('launch-protection.json',check_candidate(load(Path(m['world'])),a.out))]:(a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    if verify(a.out)['errors']or station_verify(a.out)['errors']:raise ValueError('Station path failed independent verification')
    print('Restored',len(links),'original passenger paths;',len(changes),'changed cells',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())
