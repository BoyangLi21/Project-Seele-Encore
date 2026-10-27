"""Uninstalled 0.65 m inward head telescope; retain all original head source faces."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
from build_r53_carrier_rear_guides import beam


def build(source, output):
    raw=source.read_bytes();doc=json.loads(raw);result=copy.deepcopy(doc)
    result['parts']=[p for p in result['parts'] if not p['name'].endswith('/mount/5')]
    for mount in doc['mounts']:
        name=mount['id'];side=mount['side'];ball=np.asarray(mount['ball']);y,z=ball[1:]
        def point(x,dy=0,dz=0):return np.asarray([side*x,y+dy,z+dz])
        def add(suffix,a,b,width,role='lateral_stator'):
            result['parts'].append(dict(name=name+'/lateral/'+suffix,frame='LIFT',role=role,triangles_rgb=beam(a,b,width)))
        add('support/0',point(13),point(13,.30),.12)
        add('support/1',point(13,.30),point(13.65,.30),.12)
        add('support/2',point(13.65,.30),point(13.65,.10),.08)
        for n,(dy,dz) in enumerate(((.08,0),(-.08,0),(0,.08),(0,-.08))):
            add('sleeve/'+str(n),point(13.65,dy,dz),point(14,dy,dz),.04)
            add('tie/'+str(n),point(13.95,dy-(.08 if dz else 0),dz-(.08 if dy else 0)),point(13.95,dy+(.08 if dz else 0),dz+(.08 if dy else 0)),.04)
        add('rod',point(13.76),point(14.86),.12,'lateral_rod')
    result.update(candidate_lateral_retraction_m=.65,candidate_installed=False,
        baseline_sha256=hashlib.sha256(raw).hexdigest(),candidate_removed_engineering_parts=['rear_l/mount/5','rear_r/mount/5'])
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,separators=(',',':')),'utf8')
    print('parts',len(result['parts']),'triangles',sum(len(p['triangles_rgb'])//18 for p in result['parts']))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.source,a.output)
