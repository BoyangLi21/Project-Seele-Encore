"""Exact triangle tests and fingertip gaps; diagnostic scores, never approval."""
from pathlib import Path
import argparse,json,sys
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
from audit_native_knife_grip_r45 import crossing

p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
p.add_argument('--clearances',default='0')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);geometry={};reports=[]
clearances=[float(x)for x in a.clearances.split(',')]
assert all(0<=x<=.15 for x in clearances),'Do not compensate bad grip geometry with an arbitrary distant hand'
provenance=json.loads((a.input/'provenance.json').read_text('utf8'))
contract=json.loads((Path(provenance['candidate'])/'hand_rig_contract.json').read_text('utf8'))
for side in ['r','l']:
    d=np.load(a.input/f'{side}_geometry.npz');vertices=[Vector(v)for v in d['weapon']]
    faces=np.arange(len(vertices)).reshape(-1,3)
    geometry[side]=(d,vertices,faces,BVHTree.FromPolygons(vertices,faces.tolist(),all_triangles=True))
for row in json.loads((a.input/'cases.json').read_text('utf8')):
    d,gun,gf,gt=geometry[row['side']];case=np.load(a.input/(row['case']+'.npz'))
    normal=np.asarray(contract['hands'][row['side']]['palmar_normal_bind'])
    ids=np.flatnonzero(d['labels']==row['digit_index']);hf=d['faces'][ids]
    for clearance in clearances:
        hv=[Vector(v)for v in case['vertices']-normal*clearance]
        ht=BVHTree.FromPolygons(hv,hf.tolist(),all_triangles=True)
        hits=[(int(ids[h]),int(k))for h,k in ht.overlap(gt)if crossing([hv[i]for i in hf[h]],[gun[i]for i in gf[k]])]
        gaps=sorted(gt.find_nearest(hv[int(i)])[3] for i in case['tip_ids'])
        report=dict(row,clearance_native=clearance,crossings=len(hits),closest_tip_patch_gap_native=float(gaps[0]),
                    tip_patch_median_gap_native=float(np.median(gaps)),examples=hits[:8],visual_accepted=False)
        reports.append(report)
    print(row['case'],'clearance samples',len(clearances),flush=True)
output=a.input/('surface_scores.json'if len(clearances)==1 else 'surface_clearance_scores.json')
assert not output.exists(),'Preserve previous diagnostic result'
output.write_text(json.dumps(reports,indent=2),'utf8')
