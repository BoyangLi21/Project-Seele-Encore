"""Whole natural-tree cleanup of the actual attempt07 EVA entry, candidate only."""
from pathlib import Path
import argparse,json,math
import numpy as np
from prepare_facilities_r48 import Author
from prepare_battle_civil_r50 import complete_recipe
from query_blocks import AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r50/yashima/attempt07_approach/corridor_tree_candidate_v2'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);args=ap.parse_args()
    a=Author(args.world.resolve(),OUT);OUT.mkdir(parents=True,exist_ok=True)
    a.read((-150,74,398),(175,181,583))
    start=(-78.95420399087843,83,450.5);end=(-85.5,82,498.5)
    site=json.loads((a.world/'tv_encounter_sites_r45.json').read_text('utf8'))['sites']['ramiel']
    routes=[[list(start),list(end)]]+[site[k]for k in('eva_supply_access_route','cover_after_supply_route','cannon_after_supply_route')]
    wood=[p for p,s in a.s.items()if s.split('[')[0].endswith(('_log','_leaves'))]
    coords=np.asarray(wood,dtype=float);selected=np.zeros(len(coords),bool);segments=[]
    # Actual selected rig envelopes: idle reaches lateral+16.58, moving hips
    # and hands fit less, unarmed transition reaches longitudinal30.25.
    #35-wide comfort clearance exceeds the requested approximate31 width.
    half_width=17.5;half_length=32
    for route in routes:
        for p,q in zip(route,route[1:]):
            delta=np.asarray(q)-np.asarray(p);flat=delta[[0,2]];length=float(np.linalg.norm(flat))
            if length<.001:continue
            direction=flat/length;relative=coords[:,[0,2]]-np.asarray(p)[[0,2]]
            along=relative@direction;cross=relative[:,0]*direction[1]-relative[:,1]*direction[0]
            mask=(along>=-half_length)&(along<=length+half_length)&(abs(cross)<=half_width)&(coords[:,1]>=min(p[1],q[1])-7)&(coords[:,1]<=max(p[1],q[1])+61)
            selected|=mask;segments.append(dict(start=p,end=q,width=35,front_back_margin=32))
    seeds={wood[i]for i in np.flatnonzero(selected)}
    owners=json.loads((ROOT/'artifacts/rebuild_r49/encounter_facilities/west_ridge_survey.json').read_text('utf8'))['city100_owners']
    def moving_owned(p):return any(o['sweep_xz'][0]<=p[0]<=o['sweep_xz'][1]and o['sweep_xz'][2]<=p[2]<=o['sweep_xz'][3]for o in owners)
    done=set();trees=[];desired={};protected=[]
    for seed in sorted(seeds):
        if seed in done:continue
        stack=[seed];component=set()
        while stack:
            p=stack.pop()
            if p in done:continue
            assert p in a.s,('Whole botanical component exits measured halo',p)
            if not a.s[p].split('[')[0].endswith(('_log','_leaves')):continue
            done.add(p);component.add(p)
            assert p not in a.t
            for d in((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                stack.append(tuple(p[k]+d[k]for k in range(3)))
        if any(moving_owned(p)for p in component):
            protected.append(dict(cells=len(component),reason='Original moving-city owner remains wholly protected; this task clears natural outside forest only'));continue
        for p in component:desired[p]=('minecraft:air','Complete real natural tree intersecting selected actual standing/walk/run35-wide incoming or installed Yashima route; no identity/progress rewrite',None)
        trees.append(dict(cells=len(component),bounds=[[min(p[k]for p in component)for k in range(3)],[max(p[k]for p in component)for k in range(3)]]))
    assert trees and (-74,85,459) in desired
    a.emit('Y03_actual_north_entry_whole_trees',desired,dict(trees=trees,
        same_original_eva='fbe61635-4d0e-42e7-b3d4-f08cf2061f74',saved_feet=list(start),first_route_target=list(end),
        first_actual_block=[-74,85,459],first_actual_state=a.s[-74,85,459],
        body_width=17,body_height=60,declared_route_clear_width=35,actual_selected_rig_standing_width=32.315,
        selected_rig_envelopes='selected_rig_locomotion_envelopes.json',all_installed_route_segments=segments,protected_whole_city_trees=protected,original_city_depth=312,
        current_first_block_not_historical_first_tick_claim=True,all_original_identity_stock_and_task_saveddata_untouched=True))
    # Complete retired botanical bbox includes its unchanged original AIR,
    # so the source is not only a sparse current leaf/log delta.
    full=dict(desired)
    for tree in trees:
        lo,hi=tree['bounds']
        for x in range(lo[0],hi[0]+1):
            for y in range(lo[1],hi[1]+1):
                for z in range(lo[2],hi[2]+1):
                    p=x,y,z
                    assert p not in a.t
                    full[p]=('minecraft:air'if p in desired else a.s[p],'Complete retired incoming-route botanical bounding volume, including original AIR and retained actual soil',None)
    a.full_desired=full;complete_recipe(a)
    for path in OUT.glob('*/contract.json'):
        contract=json.loads(path.read_text('utf8'))
        contract.update(schema='projectseele.r50.yashima-whole-tree-candidate.v1',
            authorization='Root-relayed R50 whole actual EVA approach corridor clearance; botanical components outside moving-city ownership only')
        path.write_text(json.dumps(contract,ensure_ascii=False,indent=2),'utf8')
        for component in a.components:
            component.update(schema=contract['schema'],authorization=contract['authorization'])
    (OUT/'manifest.json').write_text(json.dumps(dict(schema=50,source_world=str(a.world),components=a.components,
        changed_cells=len(a.all),world_written=False,native_verified=False,visual_verified=False),ensure_ascii=False,indent=2),'utf8')
    (OUT/'metadata_patch.json').write_text(json.dumps(dict(schema=50,operations=[],world_written=False),indent=2),'utf8')
    print(trees,len(a.all),'tree cells; candidate only',flush=True)

if __name__=='__main__':main()
