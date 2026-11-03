"""Remove explicitly surveyed, fully isolated civil panels from a candidate.

Each selected connected assembly must be surrounded by air in all 26 directions,
clear of native protection, known devices and parcel volumes. No material-wide
world deletion is allowed. The original source and full inverse stay retained.
"""
import argparse,json,shutil,os
from pathlib import Path
import nbtlib
from author_hakone_lakefront import Editor
from detail_hakone_nerv_streets import preservation_mask
from map_pipeline.launch_protection import load,check_candidate
from query_blocks import AIR
from verify_hakone_togendai_neighbourhood import verify


def run(source,plan,out):
    selected=json.loads(plan.read_text('utf8'));points={tuple(r['pos']):r['state']for r in selected}
    if len(points)!=len(selected) or not points:raise ValueError('Empty or duplicated panel selection')
    spec=json.loads((source/'plan/authored-design.json').read_text('utf8'))
    protected=preservation_mask(source,spec);e=Editor(source)
    world=Path(json.loads((source/'manifest.json').read_text('utf8'))['world']);launch=load(world)
    tags=nbtlib.load(source/'captured-devices.dat')['Devices'];devices={tuple(int(t[k])for k in ('x','y','z'))for t in tags}
    masks={};components=[];pending=set(points)
    while pending:
        first=pending.pop();todo=[first];group=[]
        while todo:
            p=todo.pop();group.append(p);x,y,z=p
            if e.state(*p)!=points[p] or e.state(*p,original=True)!=points[p]:raise ValueError(('Changed source panel',p))
            key=x//16,z//16
            if key not in masks:masks[key]=launch.chunk_mask(*key)
            if p in devices or protected(p) or masks[key][y+128,z%16,x%16]:raise ValueError(('Protected panel',p))
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        q=x+dx,y+dy,z+dz
                        if q in points:
                            if q in pending:pending.remove(q);todo.append(q)
                        elif e.state(*q).split('[')[0] not in AIR|{'minecraft:light'}:
                            raise ValueError(('Panel touches another structure or terrain',p,q,e.state(*q)))
        components.append(dict(cells=len(group),bounds=[min(p[i]for p in group)for i in range(3)]+[max(p[i]for p in group)for i in range(3)]))
    out.mkdir(parents=True,exist_ok=False)
    for file in source.iterdir():
        if file.name=='source':
            (out/'source').mkdir()
            for p in file.glob('*.npz'):os.link(p,out/'source'/p.name)
        elif file.is_dir():shutil.copytree(file,out/file.name)
        else:shutil.copy2(file,out/file.name)
    e=Editor(out)
    for p in points:e.put(*p,'minecraft:air')
    regions=e.save();manifest=json.loads((out/'manifest.json').read_text('utf8'))
    manifest.update(regions=regions,cells=sum(r['cells']for r in regions));(out/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf8')
    (out/'retired-isolated-panels.json').write_text(json.dumps(dict(components=components,members=selected,device_edits=0),indent=2),'utf8')
    (out/'launch-protection.json').write_text(json.dumps(check_candidate(launch,out),indent=2),'utf8')
    report=verify(out)
    if report['errors']:raise ValueError('Post-retirement verification failed')
    print('Retired complete isolated panels',len(components),'cells',len(points),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','plan','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.source,a.plan,a.out)
