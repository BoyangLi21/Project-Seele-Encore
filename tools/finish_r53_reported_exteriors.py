"""Measured completion of the reported old wells, grass posts and wet shell."""
from pathlib import Path
from collections import Counter
import argparse,gzip,json,math
import numpy as np
from query_blocks import AIR,read_box,iter_block_entities
from survey_facility_target import role_of
import survey_r52_original_complex as survey
import plan_r53_old_well_enclosure as masks
from repair_r53_reported_landings import apply

DIM='projectseele:geofront'

def plan(world,base,out):
    rows=[]
    def append(p,b,a,why):
        if b!=a:rows.append(dict(pos=list(map(int,p)),before=b,after=a,before_nbt=None,after_nbt=None,reason=why))
    # Entire authored old launch region, with current active machine envelopes
    # and the original operating compact lift explicitly retained.
    lo=(-52,-470,-145);hi=(120,74,40)
    survey.WORLD=world;before,palette=survey.measure(lo,hi)
    survey.WORLD=base/'R50_RESTORE/server/SEELE_R50_WORLD';old,oldnames=survey.measure(lo,hi)
    masks.LO=np.array(lo);masks.HI=np.array(hi);core,shell,_=masks.envelopes(base.parent/'map_complete_20261013')
    yy,zz,xx=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
    keep=np.zeros_like(core)
    for left,right in ((-29,5),(13,47),(55,89)):
        keep|=(xx>=left)&(xx<=right)&(zz>=-54)&(zz<=5)
    keep|=(xx>=89)&(xx<=99)&(zz>=-61)&(zz<=-43)&(yy<=-430)
    keep|=(xx>=89)&(xx<=120)&(zz>=-64)&(zz<=12)&(yy>=-447)&(yy<=-437)
    keep|=core|shell|(yy<=-467)
    tags=dict(iter_block_entities(world,DIM,lo,hi))
    for x,y,z in tags:
        keep[max(0,y-lo[1]-2):y-lo[1]+3,max(0,z-lo[2]-2):z-lo[2]+3,max(0,x-lo[0]-2):x-lo[0]+3]=True
    lookup={s:i for i,s in enumerate(palette)};oldmap=np.array([lookup.get(s,65535) for s in oldnames],np.uint16)
    art=np.array([role_of(s) not in ('air','fluid','natural') and not s.startswith(('mtr:','movingelevators:','minecraft:rail','minecraft:powered_rail')) for s in palette])
    retired=art[before]&(before==oldmap[old])&~keep
    after=before.copy()
    if 'minecraft:air' not in palette:palette.append('minecraft:air')
    after[retired]=palette.index('minecraft:air')
    for y,z,x in np.argwhere(retired):append((x+lo[0],y+lo[1],z+lo[2]),palette[int(before[y,z,x])],'minecraft:air','old_shaft_exterior_remnants')
    for left,right in ((-29,5),(13,47),(55,89)):
        perimeter={(x,z) for x in range(left,right+1) for z in (-54,5)}|{(x,z) for x in (left,right) for z in range(-54,6)}
        for y in range(-466,75):
            for x,z in perimeter:
                k=(y-lo[1],z-lo[2],x-lo[0]);p=x,y,z;b=palette[int(before[k])]
                if core[k] or p in tags or b.startswith(('minecraft:barrier','mtr:','movingelevators:')):continue
                if b not in AIR and role_of(b) in ('natural','fluid'):continue
                append(p,b,'minecraft:black_concrete','continuous_black_old_well_exterior')
    # Remove the complete isolated soil posts reported at X14, plus identical
    # neighbours, down to the measured surrounding grass height.
    c=read_box(world,DIM,(-3,-484,25),(24,-460,45))
    tops={(x,z):max((y for y in range(-484,-459) if c[x,y,z].startswith('minecraft:grass_block')),default=-485) for x in range(-3,25) for z in range(25,46)}
    for (x,z),top in tops.items():
        if top!=-467:continue
        around=[h for (a,b),h in tops.items() if abs(a-x)<=3 and abs(b-z)<=3 and -480<=h<-470]
        if not around:continue
        ground=round(float(np.median(around)))
        for y in range(ground,top+1):
            p=x,y,z;b=c[p]
            assert b.split('[')[0] in ('minecraft:grass_block','minecraft:dirt','minecraft:stone')
            append(p,b,'minecraft:grass_block[snowy=false]' if y==ground else 'minecraft:air','reported_grass_posts_to_local_ground')
    # The extra black shell is three blocks outside the original pyramid panel.
    # Remove only that measured added skin under the lake; keep the real wall.
    lo2=(-57,-500,240);hi2=(117,-467,414);c=read_box(world,DIM,lo2,hi2)
    tags2=dict(iter_block_entities(world,DIM,lo2,hi2))
    for p,b in c.items():
        x,y,z=p;r=math.floor(120*(1-(y+93+466)/172)+.5);d=max(abs(x-30),abs(z-327))
        if b=='minecraft:black_concrete' and r+2<=d<=r+4 and p not in tags2:
            append(p,b,'minecraft:water[level=0]','redundant_outer_underwater_skin')
    out.mkdir(parents=True,exist_ok=True)
    assert len({tuple(r['pos']) for r in rows})==len(rows)
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
    report=dict(world=str(world),cells=len(rows),reasons=dict(Counter(r['reason'] for r in rows)),active_machine_envelopes_preserved=True,compact_lift_preserved=True)
    (out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(report)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args();apply(a.world,a.output) if a.apply else plan(a.world,a.base,a.output)
