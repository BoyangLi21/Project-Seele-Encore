"""Confirm full-save natural singleton candidates across section borders.

Read-only. Highest-surface fragments and enclosed cave features are separate;
neither an air snapshot nor a height discontinuity authorizes generic clearing.
"""
import json
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from r52_spatial_plan import BASE
from query_blocks import iter_selected_sections,AIR


def main():
    folder=BASE/'final_map_audit';source=folder/'initial_screen/GLOBAL_SCREEN.json'
    report=json.loads(source.read_text('utf8'));items=report['isolated_natural_cells']+report['section_boundary_candidates_unconfirmed']
    candidates={tuple(r['pos']):r for r in items if r['dimension']=='projectseele:geofront'}
    selected=defaultdict(set);wanted=defaultdict(set);steps=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
    for pos in candidates:
        for delta in ((0,0,0),)+steps:
            p=tuple(a+b for a,b in zip(pos,delta));key=(p[0]//16,p[2]//16,p[1]//16)
            selected[key[:2]].add(key[2]);wanted[key].add(p)
    actual={}
    for cx,cz,sy,pal,ix in iter_selected_sections(BASE/'WORLD_R52','projectseele:geofront',selected,skip_unfinished=True):
        for p in wanted[cx,cz,sy]:actual[p]=pal[int(ix[(p[1]%16)*256+(p[2]%16)*16+p[0]%16])]
    cache={};rows=[];counts=Counter()
    for pos,row in candidates.items():
        neighbours=[tuple(a+b for a,b in zip(pos,d)) for d in steps]
        states=[actual.get(p,'UNMEASURED') for p in neighbours]
        if actual.get(pos)!=row['state']:status='CHANGED_SINCE_SCREEN_REMEASURE_REQUIRED'
        elif any(s not in AIR and s != 'UNMEASURED' for s in states):status='SECTION_BORDER_FALSE_POSITIVE'
        elif 'UNMEASURED' in states:status='UNMEASURED_NEIGHBOUR_HOLD'
        else:status='CONFIRMED_SIX_AIR_FACES'
        x,y,z=pos;key=(x//512,z//512)
        if key not in cache:
            cache[key]=np.load(folder/'initial_screen/projectseele_geofront'/f'r.{key[0]}.{key[1]}.npz')
        top=int(cache[key]['surface'][z%512,x%512]);exposed=y==top
        rows.append(dict(row,status=status,top_solid_y=top,highest_surface=exposed,neighbours=states))
        counts[status]+=1
    result=dict(world_written=False,candidate_count=len(candidates),counts=dict(counts),rows=rows,
        exposed_fragments=[r for r in rows if r['status']=='CONFIRMED_SIX_AIR_FACES' and r['highest_surface']],
        all_terrain_art_passed=False)
    (folder/'ISOLATED_TERRAIN_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(counts=counts,exposed_fragments=[r['pos'] for r in result['exposed_fragments']]),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
