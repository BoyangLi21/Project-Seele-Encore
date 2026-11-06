"""Measure rail bed and reserved civil clearance in exact saved FULL arrays.

This is an engineering-envelope audit, not rendered vehicle collision testing.
It records native parts as obstructions for review; it never edits any cells.
"""
import argparse,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from author_hakone_lakefront import Editor
from query_blocks import AIR


def audit(a):
    a.out.mkdir(parents=True,exist_ok=False)
    cap=json.loads((a.source/'capture.json').read_text('utf8'));x,z,X,Z=cap['bounds_xz']
    curves=json.loads(a.curves.read_text('utf8'))['trains'];e=Editor(a.source)
    empty=AIR|{'minecraft:light','minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
    body={};bed={};samples=0;selected_curves=[]
    for index,row in enumerate(curves):
        p=np.asarray(row['points'],float);picked=[]
        for k,(px,py,pz)in enumerate(p):
            if not(x+3<=px<=X-3 and z+3<=pz<=Z-3 and -125<=py<313):continue
            tangent=(p[min(len(p)-1,k+1)]-p[max(0,k-1)])[[0,2]]
            length=np.linalg.norm(tangent)
            if length<1e-8:continue
            normal=np.array([-tangent[1],tangent[0]])/length;samples+=1;picked.append(k)
            for side in np.linspace(-a.half_width,a.half_width,9):
                q=np.floor(np.array([px,pz])+side*normal).astype(int);Q,R=map(int,q)
                for Y in range(math.floor(py),math.ceil(py+a.height)):
                    body.setdefault((Q,Y,R),(index,k,float(py)))
            for side in (-1,0,1):
                Q,R=map(int,np.floor(np.array([px,pz])+side*normal));Y=math.floor(py)-1
                bed.setdefault((Q,Y,R),(index,k,float(py)))
        if picked:selected_curves.append(dict(index=index,kind=row.get('kind'),samples=len(picked),
            first=p[picked[0]].tolist(),last=p[picked[-1]].tolist()))
    obstruction=[];gaps=[];unknown=set();types=Counter()
    for pos,(index,k,datum)in body.items():
        try:state=e.state(*pos)
        except KeyError:unknown.add((pos[0]//16,pos[2]//16));continue
        if state.split('[')[0]not in empty:
            obstruction.append(dict(pos=list(pos),state=state,curve=index,sample=k,rail_y=datum));types[state.split('[')[0]]+=1
    for pos,(index,k,datum)in bed.items():
        try:state=e.state(*pos)
        except KeyError:unknown.add((pos[0]//16,pos[2]//16));continue
        if state.split('[')[0]in empty|{'minecraft:water','minecraft:lava'}:
            gaps.append(dict(pos=list(pos),state=state,curve=index,sample=k,rail_y=datum))
    per_curve=[]
    for row in selected_curves:
        obs=[r for r in obstruction if r['curve']==row['index']];holes=[r for r in gaps if r['curve']==row['index']]
        per_curve.append(dict(**row,clearance_cells=len(obs),bed_gap_cells=len(holes),examples=(obs+holes)[:4]))
    report=dict(source=str(a.source),captured_bounds=[x,z,X,Z],sampled_native_curves=len(selected_curves),samples=samples,
        reserved_half_width=a.half_width,reserved_height_above_rail=a.height,body_cells_checked=len(body),bed_cells_checked=len(bed),
        clearance_obstruction_cells=len(obstruction),bed_gap_cells=len(gaps),materials=dict(types),unknown_chunks=sorted(unknown),
        curves=per_curve,world_written=False,rendered_vehicle_collision_checked=False,
        scope='Saved FULL capture only; civil minimum reserve, original native models require separate interpretation')
    for name,data in [('rail-civil-audit.json',report),('clearance-obstructions.json',obstruction),('bed-gaps.json',gaps)]:
        (a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:report[k]for k in ('sampled_native_curves','samples','body_cells_checked','bed_cells_checked','clearance_obstruction_cells','bed_gap_cells','materials','unknown_chunks')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('source','curves','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--half-width',type=float,default=1.75);p.add_argument('--height',type=float,default=5.)
    audit(p.parse_args())
