"""Join the measured coastal port to the commissioned inland road, offline."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from author_hakone_lakefront import Editor
from map_pipeline.corridors import compile_street
from map_pipeline.launch_protection import load,check_candidate
from query_blocks import AIR


def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf8')


def run(a):
    if a.out.exists():raise ValueError('A new immutable candidate is required')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.source,a.out,copy_function=copy)
    e=Editor(a.out);design=json.loads(a.design.read_text('utf8'));bx,bz,bX,bZ=design['bounds']
    shape=(bZ-bz+1,bX-bx+1);existing=dict(bounds=np.array(design['bounds']),walk=np.zeros(shape,bool),road=np.zeros(shape,bool),grade2=np.zeros(shape,np.int16))
    with np.load(a.authority/'network.npz')as f:
        x,z,X,Z=map(int,f['bounds']);l,t,R,B=max(x,bx),max(z,bz),min(X,bX),min(Z,bZ)
        for k in ('walk','road','grade2'):existing[k][t-bz:B-bz+1,l-bx:R-bx+1]=f[k][t-z:B-z+1,l-x:R-x+1]
    prior=a.source/'plan/port-access.npz'
    if prior.exists():
        with np.load(prior)as f:
            if not np.array_equal(f['bounds'],existing['bounds']):raise ValueError('Port access refinements require the same finite coordinate frame')
            for k in ('walk','road','grade2'):existing[k]=f[k]
    curves=json.loads((a.authority/'native-curves.json').read_text('utf8'))
    rail=np.asarray([p for r in curves['trains']for p in r['points']],float).reshape(-1,3)
    boxes=json.loads((a.authority/'station-volumes.json').read_text('utf8'))
    bearings=[r['occupied_bounds']for r in json.loads((a.authority/'catalog.json').read_text('utf8'))]
    boxes+=bearings
    for row in nbtlib.load(a.source/'block-entities.dat')['Changes']:
        if 'After'in row:
            tag=row['After'];p=[int(tag[k])for k in ('x','y','z')];boxes.append(p+p)
    rows=json.loads((a.source/'access-progress.json').read_text('utf8'))if(a.source/'access-progress.json').exists()else[]
    edits=json.loads((a.source/'port-civil-refinement.json').read_text('utf8'))if(a.source/'port-civil-refinement.json').exists()else[]
    (a.out/'earthworks').mkdir(exist_ok=True)
    for row in design['streets']:
        report,result=compile_street(e,row,boxes,rail,existing,bearings);rows.append(report)
        write(a.out/'access-progress.json',rows)
        if result is None:raise ValueError((row['id'],report['blockers'][:20]))
        writes,field=result
        for p,state in writes.items():
            before=e.state(*p)
            if before!=state:edits.append(dict(pos=list(p),before=before,after=state));e.put(*p,state)
        e.save();e.regions.clear()
        np.savez_compressed(a.out/'earthworks'/(row['id']+'.npz'),**field)
        x,z,X,Z=field['bounds'];area=np.s_[z-bz:Z-bz+1,x-bx:X-bx+1]
        for k in ('walk','road','grade2'):existing[k][area][field['walk']]=field[k][field['walk']]
        print('Prepared port corridor',row['id'],len(writes),flush=True)
    np.savez_compressed(a.out/'plan/port-access.npz',**existing)
    write(a.out/'port-civil-refinement.json',edits);shutil.copy2(a.design,a.out/'plan/port-access-design.json')
    report=json.loads((a.out/'manifest.json').read_text('utf8'));report['regions']=e.save();report['cells']=sum(r['cells']for r in report['regions']);report['port_access']=rows
    write(a.out/'manifest.json',report);write(a.out/'launch-protection.json',check_candidate(load(Path(report['world'])),a.out))
    write(a.out/'functional-check.json',dict(errors=[['pending independent port verification']],world_written=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in ('source','out','authority','design'):p.add_argument('--'+name,type=Path,required=True)
    run(p.parse_args())
