"""Native physics cases for Root-authored links. No save/launch or pass claim."""
import json,hashlib,gzip
from pathlib import Path
import numpy as np
from plan_pyramid_ring_links_r52 import LINKS
from r52_spatial_plan import BASE


def main():
    world=BASE/'WORLD_R52';out=BASE/'native_r52_validation';out.mkdir(exist_ok=True)
    raw=(world/'nerv_routes_r24.json.gz').read_bytes();graph=json.loads(gzip.decompress(raw));public={tuple(r[:3])for r in graph['nodes']}
    cases=[];unresolved=[]
    for y,points in LINKS.items():
        path=[[x+.5,y,z+.5]for x,z in points]
        expanded=[]
        for a,b in zip(points,points[1:]):
            dx=(b[0]>a[0])-(b[0]<a[0]);dz=(b[1]>a[1])-(b[1]<a[1]);steps=abs(b[0]-a[0])+abs(b[1]-a[1])
            expanded.extend((a[0]+i*dx,y,a[1]+i*dz)for i in range(steps+1))
        missing=[p for p in expanded if p not in public]
        if missing:unresolved.append(dict(id=f'r52/ring/{y}',not_in_final_graph=missing));continue
        for suffix,waypoints in [('out',path),('back',path[::-1])]:cases.append(dict(id=f'r52/ring/{y}/{suffix}',path=waypoints))
        a,b=max(zip(points,points[1:]),key=lambda ab:abs(ab[0][0]-ab[1][0])+abs(ab[0][1]-ab[1][1]))
        x=(a[0]+b[0])//2;z=(a[1]+b[1])//2;cross=(0,1)if a[0]!=b[0]else(1,0)
        width=[(x-cross[0],y,z-cross[1]),(x,y,z),(x+cross[0],y,z+cross[1])]
        if all(p in public for p in width):cases.append(dict(id=f'r52/ring/{y}/full_width',path=[[p[0]+.5,p[1],p[2]+.5]for p in width]))
        else:unresolved.append(dict(id=f'r52/ring/{y}/full_width',not_in_final_graph=[p for p in width if p not in public]))
    local=BASE/'navigation_rebuild/components/retained_research_bridge/walkable_graph.npz'
    research={tuple(p)for p in np.load(local)['coords']}
    for z in(396,399,402):
        points=[(x,-466 if x<=144 else min(-461,-465+x-145),z)for x in range(143,152)]
        missing=[p for p in points if p not in research]
        if missing:unresolved.append(dict(id=f'r52/research/stair/{z}',not_in_local_graph=missing));continue
        for suffix,waypoints in(('up',points),('down',points[::-1])):
            cases.append(dict(id=f'r52/research/stair/{z}/{suffix}',path=[[x+.5,y,z+.5]for x,y,z in waypoints]))
    (out/'PUBLIC_WALK_CASES.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),'utf8')
    report=dict(world_written=False,native_verified=False,cases=len(cases),unresolved=unresolved,
        current_navigation_sha256=hashlib.sha256(raw).hexdigest(),scope='Six explicitly built ring links, both directions and cross-width; plus retained research bridge stair both directions on three lateral tracks. Native player collision movement preflight only. Real key input, doors/lifts/rail rides, visual review and whole map are separate.',
        required_world='SEELE_R52_REVIEW',required_properties={'projectseele.regionalBuild':'r44-collision','projectseele.nativeReviewWorld':'SEELE_R52_REVIEW','projectseele.r52NativeReviewCopy':'true'},
        input_target='Only the isolated QA copy r44_walk_cases.json after Source refresh and before first launch')
    (out/'PUBLIC_WALK_PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
