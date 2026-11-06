"""Actual asphalt and capture-frontier probes for legacy streets outside masks."""
import argparse,json,math
from pathlib import Path
from collections import Counter
import numpy as np
from audit_mountain_station_access import SupplementedSections
from audit_oldcity_surface_station_access import MainlineSweep,StationNav
from build_gora_protected_transfer import IndependentWalker
from propose_mountain_station_steps import Overlay
from review_oldcity_street_interfaces import component,trace
from review_underground_station_evidence import strict_walk

ASPHALT={'minecraft:black_concrete','projectseele:road_asphalt_slab'}

def run(a):
    a.out.mkdir(exist_ok=False);summary=[]
    shapes=json.loads((a.metadata/'native_collision_shapes.json').read_text('utf8'))
    evidence=json.loads((a.bridge/'functional-check.json').read_text('utf8'))
    for q in evidence['shape_aliases']:
        if q['state']not in shapes:shapes[q['state']]=shapes[q['same_collision_class_and_properties_as']]
    reader=Overlay(SupplementedSections(a.source),json.loads((a.bridge/'changes.json').read_text('utf8')))
    native=json.loads(a.native.read_text('utf8'));model=json.loads((a.models/'summary.json').read_text('utf8'))
    for site in a.sites:
        old=json.loads((a.review/(site+'.json')).read_text('utf8'));box=old['bounds'];x,y,z,X,Y,Z=box
        root=next(q['goal']for q in old['measurements']if q['key']==old['selected_graph_root'])
        sweep=MainlineSweep(native,model,box);nav=StationNav(reader,box,shapes,sweep);parents=component(nav,root)
        road=[q for q,state in nav.nodes.items()if state.split('[')[0]in ASPHALT and abs(q[1]/2-root[1])<8]
        road_reached=[q for q in road if q in parents];chosen=[];seen=set();w=IndependentWalker(reader,shapes,sweep)
        for q in sorted(road_reached,key=lambda q:(q[0]-root[0])**2+(q[2]-root[2])**2):
            key=(q[0]//12,q[2]//12)
            if key in seen:continue
            seen.add(key);path=trace(parents,q)
            chosen.append(dict(pos=[q[0],q[1]/2,q[2]],floor=nav.nodes[q],path=path,
                forward=strict_walk(w,path),reverse=strict_walk(w,list(reversed(path)))))
            if len(chosen)==5:break
        frontier=[q for q in parents if q[0]in(x,X)or q[2]in(z,Z)or q[1]/2<y+2 or q[1]/2>Y-3]
        # Compress neighboring frontier cells by chunk and approximate height,
        # but retain every exact coordinate in the evidence for follow-up.
        groups=Counter((q[0]//16,q[2]//16,math.floor(q[1]/2)//16)for q in frontier)
        row=dict(site=site,station=old['name'],root=root,bounds=box,root_component_nodes=len(parents),
            asphalt_nodes_near_ground=len(road),reachable_asphalt_nodes=len(road_reached),asphalt_paths=chosen,
            frontier_nodes=[[q[0],q[1]/2,q[2]]for q in frontier],
            frontier_groups=[dict(chunk=[cx,cz],section_y=sy,count=n)for(cx,cz,sy),n in sorted(groups.items())],
            network_mask_not_used=True,world_written=False,dynamic_gates_and_live_boarding_pending=True)
        (a.out/(site+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2),'utf8')
        short={k:row[k]for k in('site','station','root_component_nodes','asphalt_nodes_near_ground','reachable_asphalt_nodes')};short['frontier_count']=len(frontier)
        summary.append(short);(a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8');print(json.dumps(short,ensure_ascii=False)[:490],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('source','metadata','native','models','bridge','review','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--sites',nargs='+',required=True);run(p.parse_args())
