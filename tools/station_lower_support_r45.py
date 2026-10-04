"""Original positive three-wide station roads govern below-deck frame supports."""
from functools import lru_cache
from pathlib import Path
import json

@lru_cache(maxsize=1)
def road_cells():
    root=Path(__file__).resolve().parents[1]
    plan=json.loads((root/'artifacts/world_quality_r02/road_plan.json').read_text('utf-8'))
    cells=set()
    for row in plan['station_paths']:
        for a,b in zip(row['points'],row['points'][1:]):
            n=max(abs(a[0]-b[0]),abs(a[1]-b[1]))
            for k in range(n+1):
                x=round(a[0]+(b[0]-a[0])*k/max(1,n));z=round(a[1]+(b[1]-a[1])*k/max(1,n))
                cells.update((x+dx,row['floor']+1,z+dz)for dx in(-1,0,1)for dz in(-1,0,1))
    return frozenset(cells)

def lower_support_site(at,u,side,ground,half):
    mask=road_cells()
    if at(u,ground+1,side*17)not in mask:return False,u
    for candidate in(u,u-3,u+3):
        if -half<=candidate<=half and at(candidate,ground+1,side*18)not in mask:
            return True,candidate
    raise RuntimeError(('No complete supported lower-frame site clear of original full3-width station road',u,side))

def require_complete_scope(scene,lo,points,existing_BE):
    for q in points:
        iy,iz,ix=q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]
        if not(0<=iy<scene.after.shape[0]and 0<=iz<scene.after.shape[1]and 0<=ix<scene.after.shape[2]):
            raise RuntimeError(('Lower-frame complete move outside measured scene',q))
        if q in existing_BE or scene.protected[iy,iz,ix]:
            raise RuntimeError(('Lower-frame complete move intersects BE or protected device/transfer volume',q))

def support_ops(at,u,side,ground,platform,half,scene,lo,existing_BE):
    moved,U=lower_support_site(at,u,side,ground,half)
    if not moved:return [(u,ground+1,side*17,u,platform-3,side*17,'minecraft:light_gray_concrete')]
    old=[at(u,y,side*17)for y in range(ground+1,platform-2)]
    new=[at(U,y,side*18)for y in range(ground+1,platform-1)]
    if platform-2 < ground+1+1.8:raise RuntimeError('Complete transfer beam would enter the authored road body clearance')
    head=[at(v,platform-2,side*w)for v in range(min(u,U),max(u,U)+1)for w in(17,18)]
    require_complete_scope(scene,lo,old+new+head,existing_BE)
    floor=at(U,ground,side*18);require_complete_scope(scene,lo,[floor],existing_BE)
    state=lambda q:scene.palette[int(scene.after[q[1]-lo[1],q[2]-lo[2],q[0]-lo[0]])]
    if state(floor)!='minecraft:smooth_stone':raise RuntimeError(('No exact original plinth bearing for moved support',floor,state(floor)))
    if any(state(q)not in {'minecraft:air','minecraft:light_gray_concrete'}for q in old+new+head):
        raise RuntimeError('Complete lower support would overwrite another actual/planned fixture')
    return [(u,ground+1,side*17,u,platform-3,side*17,'minecraft:air'),
            (U,ground+1,side*18,U,platform-2,side*18,'minecraft:light_gray_concrete'),
            (min(u,U),platform-2,min(side*17,side*18),max(u,U),platform-2,max(side*17,side*18),'minecraft:light_gray_concrete')]
