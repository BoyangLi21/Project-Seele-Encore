"""Derive continuous garden slopes around the measured public datum field.

Wetland columns absent from the authorized garden are not filled. Fixed
buildings, road decks and entrance levels are not moved. Outer boundaries and
any actual bridge components retain their own explicit review obligations.
"""
from pathlib import Path
import argparse
import json
import math
from solve_kirisato_public_datums_r44 import envelope


def main():
    parser=argparse.ArgumentParser();parser.add_argument('plan',type=Path)
    parser.add_argument('public',type=Path);parser.add_argument('output',type=Path)
    a=parser.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    plan=json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'))
    public=json.loads(a.public.read_text('utf8'))
    garden={tuple(r['pos']):r for r in plan['columns'] if r['role']=='graded_garden_edge'}
    fixed={tuple(r['pos']):r['feet'] for r in public['solved_columns']}
    upper_seeds={};negative_seeds={}
    for x,z in garden:
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            neighbour=x+dx,z+dz
            if neighbour not in fixed:continue
            y=fixed[neighbour];q=x,z
            upper_seeds[q]=min(upper_seeds.get(q,10**9),math.floor(y+1+1e-6))
            negative_seeds[q]=min(negative_seeds.get(q,10**9),-math.ceil(y-1-1e-6))
    nodes=set(garden);upper=envelope(nodes,upper_seeds);negative=envelope(nodes,negative_seeds)
    anchored=set(upper)&set(negative);lower={q:-negative[q] for q in anchored}
    infeasible=[dict(pos=q,lower=lower[q],upper=upper[q]) for q in anchored if lower[q]>upper[q]]
    assert not infeasible, ('Garden interfaces require explicit structural division',infeasible[:10])
    initial={q:max(lower[q],min(upper[q],round(garden[q]['feet']))) for q in anchored}
    solved=envelope(anchored,initial)
    assert all(lower[q]<=solved[q]<=upper[q] for q in anchored)
    assert all(abs(solved[x,z]-solved[x+dx,z+dz])<=1 for x,z in anchored
               for dx,dz in [(1,0),(0,1)] if (x+dx,z+dz) in anchored)
    assert all(abs(solved[x,z]-fixed[x+dx,z+dz])<=1.001 for x,z in anchored
               for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)] if (x+dx,z+dz) in fixed)
    changes=[dict(pos=list(q),before_feet=garden[q]['feet'],proposed_feet=h,owner=garden[q]['owner'],purpose='graded_garden_edge')
             for q,h in sorted(solved.items()) if garden[q]['feet']!=h]
    report=dict(source=str(a.plan.resolve()),public_source=str(a.public.resolve()),changed_garden_columns=changes,
                solved_garden_columns=[dict(pos=list(q),feet=h) for q,h in sorted(solved.items())],
                independently_retained_garden_columns=[list(q) for q in sorted(nodes-anchored)],
                no_water_column_added=True,world_written=False,root_apply_ready=False,
                pending='Actual outer fringe/water boundary geometry, actual bridge and retaining components, founded plinths, complete collision and visual review')
    (a.output/'garden_datum_design.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Private connected garden design',len(solved),'columns,',len(changes),'changed;',len(nodes-anchored),'not adjoining public components; NO WORLD WRITE',flush=True)


if __name__=='__main__':main()
