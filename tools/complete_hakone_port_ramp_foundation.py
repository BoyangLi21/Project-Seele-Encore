"""Complete only the finite submerged bearing under the reviewed quay ramp."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from hakone_earthworks import road_blocks
from map_pipeline.launch_protection import load,check_candidate
from query_blocks import AIR

def main(a):
    if a.out.exists():raise ValueError('New candidate required')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.source,a.out,copy_function=copy);e=Editor(a.out)
    with np.load(a.out/'earthworks/port-yard-to-quay-ramp.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);floor,_=road_blocks(d['grade2']);changes=[]
    for j,i in np.argwhere(d['walk']):
        px,pz=x+int(i),z+int(j)
        for py in range(min(int(d['old'][j,i]),int(floor[j,i]))-1,int(floor[j,i])):
            before=e.state(px,py,pz)
            if before.split('[')[0]not in AIR|{'minecraft:water'}:continue
            if not(3200<=px<=3239 and 1115<=pz<=1165 and -100<=py<=-76):raise ValueError('Foundation escaped the finite reviewed ramp')
            e.put(px,py,pz,'minecraft:gray_concrete');changes.append(dict(pos=[px,py,pz],before=before,after='minecraft:gray_concrete'))
    report=json.loads((a.out/'manifest.json').read_text('utf8'));report['regions']=e.save();report['cells']=sum(r['cells']for r in report['regions'])
    (a.out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    (a.out/'port-ramp-foundation.json').write_text(json.dumps(changes,indent=2),'utf8')
    (a.out/'launch-protection.json').write_text(json.dumps(check_candidate(load(Path(report['world'])),a.out),indent=2),'utf8')
    print('Completed submerged ramp bearing cells',len(changes),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in ('source','out'):p.add_argument('--'+k,type=Path,required=True)
    main(p.parse_args())
