"""Read back every installed navigation node against current native shapes.

Do not run the old migration again: this file reads already-moved coordinates.
Declared operable doors remain conditional connections, never open world edits.
"""
import gzip,hashlib,json
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from scipy import sparse
from query_blocks import iter_selected_sections,AIR
from regional_voxels import canonical_state
from r52_spatial_plan import BASE


def main():
    world=BASE/'WORLD_R52';out=BASE/'final_map_audit/current_navigation';out.mkdir(parents=True,exist_ok=True)
    raw=(world/'nerv_routes_r24.json.gz').read_bytes();graph=json.loads(gzip.decompress(raw))
    points=np.array(graph['nodes'],np.int32)[:,:3];selected=defaultdict(set);wanted=defaultdict(set)
    for x,y,z in points:
        for dy in (-1,0,1):
            p=(int(x),int(y)+dy,int(z));key=(p[0]//16,p[2]//16,p[1]//16)
            wanted[key].add(p);selected[key[:2]].add(key[2])
    states={}
    for cx,cz,sy,pal,idx in iter_selected_sections(world,'projectseele:geofront',selected):
        for p in wanted[cx,cz,sy]:states[p]=pal[int(idx[(p[1]%16)*256+(p[2]%16)*16+p[0]%16])]
    shapes={canonical_state(k):v for k,v in json.loads((world/'native_collision_shapes.json').read_text('utf8')).items()}
    operated={};declared=[]
    for directory in (BASE/'navigation_rebuild/components').iterdir():
        if not directory.is_dir() or '_before_' in directory.name:continue
        for filename in ('operable_public_gates.json','geometry_graph_only.json'):
            p=directory/filename
            if not p.exists():continue
            d=json.loads(p.read_text('utf8'));d=d if isinstance(d,list) else d.get('operable_doors',[])
            for row in d:
                if 'position' in row and 'operated' in row:operated[tuple(row['position'])]=row['operated'];declared.append(row)
                else:
                    for i,q in enumerate(row.get('aperture',[])):
                        state=row.get('operated',[])
                        if state and isinstance(state,list):
                            measured=row.get('measured',[])
                            if measured and tuple(q) in states:assert states[tuple(q)] in (measured[i],state[i]),('Operable door changed',q,states[tuple(q)])
                            operated[tuple(q)]=state[i]
                        elif states.get(tuple(q)) in AIR|{'minecraft:barrier'}:operated[tuple(q)]='minecraft:air'
                    declared.append(row)
    # Only existing measured command apertures qualify, not arbitrary barrier.
    p=world/'r52/headquarters_command_doors.json'
    if p.exists():
        for row in json.loads(p.read_text('utf8'))['doors']:
            for q in row.get('aperture',[]):
                if states.get(tuple(q)) in AIR|{'minecraft:barrier'}:operated[tuple(q)]='minecraft:air'
    # Imported original pilot doors have exact paired states in the owner
    # manifest; their graph annotation intentionally stores aperture only.
    units=json.loads((BASE/'runtime_directory/units/ROOT_UNITS.json').read_text('utf8'))['units']
    for unit in units:
        for pair in unit['personnel_doors']:
            for cell in pair:
                q=tuple(cell['position']);closed=canonical_state(cell['closed']);opened=canonical_state(cell['open'])
                if q not in states:continue
                assert states[q] in (closed,opened),('Original pilot door differs from declaration',q,states[q])
                assert opened in shapes,('Missing original open-door collision shape',q)
                operated[q]=opened
    unknown=Counter();issues=[];conditional=0
    def shape(state):
        if state in shapes:return shapes[state]
        if state.split('[')[0] in AIR|{'minecraft:light'}:return []
        if state.startswith('projectseele:entry_plug_bridge_deck['):
            name,props=state[:-1].split('[',1);alias=name+'['+','.join(p for p in props.split(',') if not p.startswith('unit='))+']'
            if alias in shapes:return shapes[alias]
        unknown[state]+=1;return None
    def free(boxes,height):
        return boxes is not None and not any(b[3]>.205 and b[0]<.795 and b[5]>.205 and b[2]<.795 and b[4]>.01 and b[1]<height for b in boxes)
    for index,(x,y,z) in enumerate(points):
        positions=[(int(x),int(y)+dy,int(z)) for dy in (-1,0,1)]
        actual=[states.get(p,'UNMEASURED') for p in positions]
        values=[operated.get(p,s) for p,s in zip(positions,actual)]
        conditional+=values!=actual
        floor,foot,head=map(shape,values)
        solid=floor is not None and any(.9<=b[4]<=1.001 and b[0]<=.5<=b[3] and b[2]<=.5<=b[5] for b in floor)
        if not solid or not free(foot,1.) or not free(head,.79):
            issues.append(dict(node=index,position=[int(x),int(y),int(z)],actual=actual,operated=values,
                support=solid,foot_free=free(foot,1.),head_free=free(head,.79)))
    # Re-read the actual installed component graph order; do not manufacture
    # new neighbours or confuse a train/lift edge with walking.
    saved=np.load(BASE/'navigation_rebuild/combined/CURRENT_GRAPH.npz')
    kept=saved['kept'];coords=saved['coords'][kept]
    assert np.array_equal(points,coords),'Installed/current graph coordinates differ'
    walking=sparse.csr_matrix((saved['walking_weights'],saved['walking_indices'],saved['walking_indptr']),
        shape=(len(saved['coords']),len(saved['coords'])))[kept][:,kept].tocoo()
    boundary=np.zeros((len(points),4),bool);directions=[(1,0),(-1,0),(0,1),(0,-1)]
    for i,(x,y,z) in enumerate(points):
        for j,(dx,dz) in enumerate(directions):
            axis=0 if dx else 2;tangent=2 if dx else 0;positive=dx+dz>0
            for h,height in ((0,1.),(1,.79)):
                p=(int(x),int(y)+h,int(z));boxes=shape(operated.get(p,states.get(p,'UNMEASURED')))
                boundary[i,j]|=boxes is None or any(b[tangent]<.795 and b[tangent+3]>.205
                    and (b[axis+3]>.795 if positive else b[axis]<.205) and b[4]>.01 and b[1]<height for b in boxes)
    delta=points[walking.col]-points[walking.row];bad=np.zeros(len(delta),bool)
    for j,(dx,dz) in enumerate(directions):
        which=(delta[:,0]==dx)&(delta[:,2]==dz)
        bad[which]=boundary[walking.row[which],j]|boundary[walking.col[which],j^1]
    bad|=(abs(delta[:,0])+abs(delta[:,2])!=1)|(abs(delta[:,1])>1)
    edge_issues=[dict(start=points[walking.row[i]].tolist(),end=points[walking.col[i]].tolist()) for i in np.flatnonzero(bad)]
    report=dict(world_written=False,graph_sha256=hashlib.sha256(raw).hexdigest(),installed_nodes=len(points),
        conditional_operable_nodes=conditional,issues=issues,unknown_shapes=dict(unknown),
        every_installed_node_rechecked=True,node_geometry_passed=not issues and not unknown,
        full_width_edges_rechecked=True,walking_edges_rechecked=len(delta),walking_edge_issues=edge_issues,
        walking_edge_geometry_passed=not edge_issues,native_doors_lifts_and_trains_passed=False,
        note='Current source readback only. Registered movable door states remain permission/operation dependent. No old migration applied twice; no native play acceptance claimed.')
    (out/'CURRENT_NODE_READBACK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('issues','walking_edge_issues')},ensure_ascii=False),'issues',len(issues),flush=True)


if __name__=='__main__':main()
