"""Reuse current proven HQ and remeasure only named changed lab/deep-gallery graphs."""
from pathlib import Path
import argparse, json, hashlib, sys, shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
PEER=ROOT/'.Codex/map_complete_20261013/coordinate_lift_audit'
sys.path.insert(0,str(PEER))
import audit_current_routes as a
import plan_pyramid_navigation_r22 as nav
from query_blocks import read_box, AIR


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--part',choices=('hq','lab','hangar'),required=True)
    arg=p.parse_args();base=arg.base.resolve();out=arg.out.resolve();out.mkdir(parents=True,exist_ok=True);a.WORLD=base/'WORLD';a.OUT=out/'components';a.OUT.mkdir(exist_ok=True)
    shape_file=out/'CURRENT_BOUND_SHAPES.json';assert shape_file.exists();nav.COLLISION_SHAPES_FILE=shape_file
    if arg.part=='hq':
        source=ROOT/'.Codex/map_complete_20261013/pyramid_connectivity_sol/ghost_highest_complete_ring/public_operated'
        graph=np.load(source/'CURRENT.npz');old=graph['states'];pal=list(map(str,graph['palette']));lo=tuple(map(int,graph['origin']));hi=(lo[0]+old.shape[2]-1,lo[1]+old.shape[0]-1,lo[2]+old.shape[1]-1)
        report=json.loads((source/'TARGET_CONNECTIVITY.json').read_text('utf8'))
        vol,current_pal=a.current(lo,hi);current_pal=list(current_pal);remap=np.array([current_pal.index(s)if s in current_pal else -1 for s in pal]);diff=vol!=remap[old]
        approved=np.zeros(old.shape,bool)
        for low,high in report['scope']:approved[low[1]-lo[1]:high[1]-lo[1]+1,low[2]-lo[2]:high[2]-lo[2]+1,low[0]-lo[0]:high[0]-lo[0]+1]=True
        assert not(diff&approved).any(),('Current HQ differs from the already-proven final ring/stair graph',int((diff&approved).sum()))
        dest=a.OUT/'hq';dest.mkdir(exist_ok=True)
        for name in ('walkable_graph.npz','TARGET_CONNECTIVITY.json','geometry_graph_only.json','operable_public_gates.json','boundary_collision_audit.json'):
            shutil.copyfile(source/name,dest/name)
        np.savez_compressed(dest/'CURRENT.npz',states=vol,palette=np.asarray(current_pal),origin=lo)
        evidence=dict(world_written=False,native_verified=False,valid_existing_ten_ring_proof_not_repeated=True,current_domain_block_difference_cells=0,reused_graph=str(source/'walkable_graph.npz'),reused_graph_sha256=hashlib.sha256((source/'walkable_graph.npz').read_bytes()).hexdigest(),source_exact_state_domains=report['scope'],current_only_unrelated_outside_domain_changes=int((diff&~approved).sum()))
        (dest/'CURRENT_ASSOCIATION.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8');print(json.dumps({k:v for k,v in evidence.items()if k!='source_exact_state_domains'}),flush=True)
    elif arg.part=='lab':
        a.SPATIAL=json.loads((a.WORLD/'spatial_contract_r21.json').read_text('utf8'));a.CURVES=json.loads((a.WORLD/'native_transit_r28.json').read_text('utf8'))['curves']
        result=a.old_station();dest=a.OUT/'lab';result[0].rename(dest)
        evidence=dict(world_written=False,native_verified=False,source='Original named R47 dry circulation, two originally named test platforms and retained original station/compact/east access; current retired west branch excluded',new_dry_bridge_positive_source=str(ROOT/'.Codex/map_complete_20261013/pyramid_connectivity_sol/R47_DRY_BRIDGES_CANDIDATE.json'),current_guard_and_two_four_by_three_original_ports=True)
        (dest/'CURRENT_ASSOCIATION.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n','utf8')
    else:
        old=json.loads((PEER/'whole_routes_v1/new_hangar_actual_galleries/TARGET_CONNECTIVITY.json').read_text('utf8'))
        lo=(-54,-1094,130);hi=(108,-978,386)
        domains=[([q[0],q[1]-384,q[2]],[Q[0],Q[1]-384,Q[2]])for q,Q in old['scope']]
        targets=[{k:v for k,v in r.items()if k not in('node','component','states')}for r in old['targets']]
        for t in targets:t['point'][1]-=384
        lifts=json.loads((a.WORLD/'personnel_lifts_r52.json').read_text('utf8'));ops=[]
        for door in lifts['office_access']['room_controls']['pilot_guard_doors']:
            q=tuple(door['lower']);actual=read_box(a.WORLD,'projectseele:geofront',q,(q[0],q[1]+1,q[2]));ops.append([dict(position=p,closed=s,open=s.replace('open=false','open=true'))for p,s in actual.items()])
        for lift in lifts['lifts']:
            for floor in lift['floors']:
                if floor['approach_y']not in(-1088,-1014,-987):continue
                q=tuple(floor['landing_doors'][0]['pos']);Q=tuple(floor['landing_doors'][-1]['pos'])
                actual=read_box(a.WORLD,'projectseele:geofront',tuple(min(d['pos'][i]for d in floor['landing_doors'])for i in range(3)),tuple(max(d['pos'][i]for d in floor['landing_doors'])for i in range(3)))
                ops.append([dict(position=d['pos'],closed=actual[tuple(d['pos'])],open='minecraft:air')for d in floor['landing_doors']])
        for y in(-1088,-1014,-987):targets.append(dict(id=f'current_internal/{y}',point=[89,y,373],kind='current_native_existing_original_lift_approach'))
        targets+=[dict(id='current_main/-987',point=[9,-987,258],kind='root_current_main_supported_landing'),dict(id='current_east/-987',point=[66,-987,307],kind='root_current_east_supported_landing')]
        result=a.run_graph('hangar',lo,hi,domains,targets,ops)
        (result[0]/'CURRENT_ASSOCIATION.json').write_text(json.dumps(dict(world_written=False,native_verified=False,source='Previous exact named hangar gallery domains plus its Root-approved main/internal handoffs; whole deep migration shifts only Y by -384',prior_domains=str(PEER/'whole_routes_v1/new_hangar_actual_galleries/TARGET_CONNECTIVITY.json'),root_plan_sha256=hashlib.sha256((base/'ROOT_SPATIAL_PLAN.json').read_bytes()).hexdigest(),raw_air_never_declares_public_space=True),ensure_ascii=False,indent=2)+'\n','utf8')


if __name__=='__main__':main()
