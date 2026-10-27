"""Diagnose source-body/rail crossings using exported production bank frames.

An edge-crossing audit is a design diagnostic, not complete continuous or
enclosed-volume clearance certification.
"""
import argparse
import json
import zipfile
from pathlib import Path
import numpy as np
from audit_r53_carrier_fit import intersections
from audit_r53_rear_guides_gates import transform


def audit(hardware,frames,rails,jar,output):
    source=json.loads(hardware.read_text('utf8'));poses=json.loads(frames.read_text('utf8'));fixed=json.loads(rails.read_text('utf8'))
    parts={'rear/'+p['name']:(p,np.asarray(p['triangles_rgb']).reshape(-1,3,6)[:,:,:3]) for p in source['parts']}
    with zipfile.ZipFile(jar) as archive:body=json.loads(archive.read('assets/projectseele/mesh/carrier_mk2_r53.json'))
    body=np.concatenate([np.asarray(v).reshape(-1,3,8)[:,:,:3] for v in body['parts'].values()])
    body=transform(body,poses['body_root']);blo,bhi=body.min(1),body.max(1)
    fixed_tri=[]
    for p in fixed['pieces']:
        a=np.asarray(p['triangles_rgb']).reshape(-1,3,6)[:,:,:3]+p['origin']
        if np.all(a.max((0,1))>=body.min((0,1))-3) and np.all(a.min((0,1))<=body.max((0,1))+3):fixed_tri.append(a)
    fixed_tri=np.concatenate(fixed_tri);flo,fhi=fixed_tri.min(1),fixed_tri.max(1)
    rows=[]
    for frame in poses['frames'][::4]:
        hits=[]
        for name,pose in frame['parts'].items():
            p,xyz=parts[name]
            if p['frame']=='ROOT':continue
            v=transform(xyz,pose);lo,hi=v.min((0,1)),v.max((0,1))
            for label,obstacles,L,H in [('carrier',body,blo,bhi),('fixed',fixed_tri,flo,fhi)]:
                near=obstacles[np.all(H>=lo,axis=1)&np.all(L<=hi,axis=1)]
                if len(near):
                    count=intersections(v,near)
                    if count:hits.append(dict(part=name,obstacle=label,crossings=count))
        rows.append(dict(clock=frame['clock'],hits=hits))
        if hits:print('clock',frame['clock'],hits,flush=True)
    output.write_text(json.dumps(dict(world_written=False,frames=len(rows),crossing_frames=sum(bool(r['hits'])for r in rows),rows=rows),indent=2),'utf8')
    print('frames',len(rows),'crossing frames',sum(bool(r['hits'])for r in rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('hardware','frames','rails','jar','output'):parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();audit(args.hardware,args.frames,args.rails,args.jar,args.output)
