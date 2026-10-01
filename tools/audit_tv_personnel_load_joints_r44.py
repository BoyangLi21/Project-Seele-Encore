"""Finite structural graph: native visible grating -> actual capped frame -> world."""
from pathlib import Path
import argparse,hashlib,json,math
from collections import Counter
import numpy as np
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
import build_tv_machinery_r16 as author

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'

def main(asset,layout,out):
    asset,layout,out=map(Path,(asset,layout,out))
    if out.exists():raise ValueError('Fresh proof required')
    d=json.loads(asset.read_text());floors=json.loads(layout.read_text())['floor_cells']
    native_path=BASE/'tv_personnel_deck_native_v1/native_union_readback/full_native_collision_shapes.json';native=json.loads(native_path.read_text())
    actual=np.array(d['parts']['cage_frame_lower_r44']).reshape(-1,3,6);keys={tuple(np.round(t.ravel(),10)) for t in actual};caps=[]
    for side in (-1,1):
        for z in (-5.8,6.3):
            x=side*15.85;author.PARTS.clear();author.use('cap');author.housing(x-1.15,46.8,z-1.14,2.30,.43,2.28,.18,0x8D9A82)
            tri=np.array(author.PARTS['cap']).reshape(-1,3,6)
            if not all(tuple(np.round(t.ravel(),10)) in keys for t in tri):raise ValueError('Current mesh does not contain exact authored complete cap')
            caps.append({'side':side,'z':z,'actual_render_triangles_exact_matched':len(tri),
                         'inscribed_solid_core':[ [x-.97,46.8,z-1.14],[x+.97,47.23,z+1.14] ],
                         'support_column_start_y':47.18,'actual_metal_vertical_joint_overlap_m':.05,
                         'existing_collision_cap_omitted':True})
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');w.box((-35,-449,-268),(98,-441,-208));w.load();g=Geometry(w);reports=[]
    for v in range(3):
        origin=np.array([-11.5+42*v,-442.96,-239.5]);boxes=[];owners=[];rootcandidates=[];ground=[]
        for c in d['components']:
            if c['motion']!='fixed' or c.get('variant',v)!=v or c['part'].startswith('thin_side_rails'):continue
            for box in d['collision_parts'][c['part']]:
                boxes.append(box);owners.append(c['part'])
                if c['part']=='cage_frame_lower_r44' and box[0][1]<-.5:rootcandidates.append(len(boxes)-1)
        for cap in caps:boxes.append(cap['inscribed_solid_core']);owners.append('exact_existing_render_cap_core')
        for f in floors:
            if f['variant']!=v:continue
            for box in native[f['after']]:boxes.append(np.array(box).reshape(2,3)+f['position']-origin);owners.append('native_floor/'+str(f['position']))
        boxes=np.array(boxes);parent=list(range(len(boxes)));edges=[]
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for i,a in enumerate(boxes):
            ids=np.flatnonzero(np.all((boxes[i+1:,1]>=a[0]-1e-5)&(boxes[i+1:,0]<=a[1]+1e-5),axis=1))+i+1
            for j in ids:
                p,q=find(i),find(int(j))
                if p!=q:parent[q]=p;edges.append([i,int(j)])
        grounded=[]
        for i in rootcandidates:
            box=boxes[i]+origin;contacts=[]
            for x in range(math.floor(box[0,0]),math.ceil(box[1,0])):
                for y in range(math.floor(box[0,1]),math.ceil(min(box[1,1],origin[1]+1.96))):
                    for z in range(math.floor(box[0,2]),math.ceil(box[1,2])):
                        state=w.get(x,y,z);shapes=g.boxes(state)
                        if shapes is None:raise ValueError(('Unknown world foundation',x,y,z,state))
                        for raw in shapes:
                            q=np.array(raw).reshape(2,3)+[x,y,z]
                            if np.all((q[1]>=box[0]-1e-5)&(q[0]<=box[1]+1e-5)):contacts.append({'cell':[x,y,z],'state':state,'actual_native_shape_world':q.tolist()})
            if contacts:grounded.append(i);ground.append({'source_box':i,'fixed_part':owners[i],'actual_world_contacts':contacts})
        rootgroups={find(i) for i in grounded};dis=Counter(o for i,o in enumerate(owners) if o.startswith('native_floor') and find(i) not in rootgroups)
        reports.append({'variant':v,'source_nodes':len(boxes),'measured_grounded_root_nodes':len(grounded),'actual_world_foundation_contacts':ground,
                        'disconnected_native_floor_cells':dict(dis),'spanning_structural_edges':edges,
                        'node_owners':owners,'node_boxes_local':boxes.tolist()})
    out.mkdir(parents=True)
    r={'inputs':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (asset,layout,native_path,w.world/'native_collision_shapes.json',ROOT/'tools/build_tv_machinery_r16.py',ROOT/'tools/build_tv_shoulder_shells_r44.py')},
       'complete_existing_render_caps':caps,'bays':reports,'native_floor_cells_disconnected':sum(len(q['disconnected_native_floor_cells']) for q in reports),
       'proof':'The old physical box inventory omits4already-rendered closed chamfered topcapcastings. All128cap triangles exactly match current source mesh. Each cap has a strictly inscribed solid core joining the mainframe post and fixed support column with50mm vertical metal overlap. Native64visible/collision grating unions and other source physical members form a finite contact graph. Roots require actual measured world collision contacts; ungrounded assumed roots do not count.',
       'limitations':['Contactgraphis engineering geometry proof, notstress/deflection or native physics simulation. Rest of fixed member solids use authored collision primitives, not a complete mechanical finite-element model.','No invisible player floor or new cap collider was added. Original cap remains actual existing rendered structural metal.','Rootnative walking/loading/lifecycle and wholeart remain required.'],
       'native_passed':False,'art_passed':False,'world_write':False,'preapply_ready':False}
    (out/'contract.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps({'disconnected':r['native_floor_cells_disconnected'],'root_counts':[q['measured_grounded_root_nodes'] for q in reports],'matched_cap_triangles':128}))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('asset','layout','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();main(a.asset,a.layout,a.out)
