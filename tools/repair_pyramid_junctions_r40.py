"""Repair measured corner-only joins and exposed old command-approach tips."""
import argparse,json
from pathlib import Path
import regional_voxels as v
from measure_world_r40 import MeasuredWorld,WORLD,ROOT
from query_blocks import AIR,iter_block_entities

OUT=ROOT/'artifacts/world_combat_r40/pyramid_junctions'
FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';STRUCT='projectseele:nerv_structural_panel';GLASS='projectseele:clear_glass'

def registered_b2_complete_cells():
    # Keep commissioned components and their exact retired legacy voids.
    # This is a protection mask, never a floor/air-authoring or route permit.
    cells=set()
    # Original west switchback plus the old east axes: retired east upper
    # tread/stringer cells must not be rebuilt by an obsolete hall pass.
    for first,second in ((range(-13,-10),range(-5,-2)),(range(67,70),range(59,62))):
        for xs,count,base,z0,dz in ((first,7,-449,304,1),(second,6,-456,310,-1)):
            for i in range(count):
                for x in xs:
                    for h in (-1,0,1,2,3):cells.add((x,base-i+h,z0+dz*i))
    # Final relocated upper flight: all3 lanes, bearing and1.8m headroom.
    for i in range(7):
        y,z=-449-i,304+i
        for x in range(55,58):
            for h in (-1,0,1,2,3):cells.add((x,y+h,z))
        # Both complete supported side guards, including surviving risers.
        for x in (54,58):
            for h in (-1,0,1,2,3):cells.add((x,y+h,z))
    # Expanded middle platform: complete bearing, all15x3 clear rows and
    # the fourth-row outer screen/north-east roof edge. A centreline is
    # insufficient: stale lower-hall ceiling touches these actual cells.
    for x in range(54,71):
        for z in range(310,315):
            for y in range(-457,-452):cells.add((x,y,z))
    # Six registered final entry-to-same-floor lift approaches. Reserve
    # existing three-cell circulation envelopes including corner joins,
    # bearing and clear headroom; do not infer walkability from this mask.
    approaches=((55,57,303,303,-448),(57,57,291,303,-448),
                (57,84,291,291,-448),(84,84,289,291,-448),
                (84,86,289,289,-448),(86,86,289,309,-448),
                (66,86,309,309,-448),(57,61,304,304,-461),
                (57,57,304,310,-461),(57,66,310,310,-461),
                (66,66,309,310,-461))
    for x0,x1,z0,z1,feet in approaches:
        for x in range(x0-1,x1+2):
            for z in range(z0-1,z1+2):
                for y in range(feet-2,feet+3):cells.add((x,y,z))
    return cells


def main(apply=False):
    v.WORLD=WORLD;v.OUT=OUT;p=v.Painter();w=MeasuredWorld();w.box((-10,-465,260),(132,-370,351));w.load();targets={};held=[]
    tags=dict(iter_block_entities(WORLD,v.DIM,(-10,-465,260),(132,-370,351)))
    control=set(tags)
    # Preserve controls and their attachment blocks, including modded panels.
    from measure_world_r40 import properties
    for (cx,sy,cz),(pal,ids) in w.tiles.items():
        import numpy as np
        for i,s in enumerate(pal):
            if not any(t in s for t in ('button','lever','elevator','one_way')):continue
            for n in np.flatnonzero(ids==i):
                q=(cx*16+(int(n)&15),sy*16+(int(n)>>8),cz*16+((int(n)>>4)&15));control.add(q)
                face=properties(s).get('facing');nx,nz={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}.get(face,(0,0));control.add((q[0]-nx,q[1],q[2]-nz))
    stair_cells=registered_b2_complete_cells()
    def put(q,after,owner):
        old=w.block(q)
        if q in stair_cells and old!=after:
            held.append(dict(pos=q,state=old,desired=after,reason='Final registered B2 stairs/platform/bearing/full-width headroom and same-floor approaches'));return
        if old is None:raise RuntimeError(('Unmeasured',q))
        if q in control or old.startswith(('movingelevators:','mtr:')):
            if old!=after:held.append(dict(pos=q,state=old,desired=after))
            return
        targets[q]=after,owner
    floor_names={FLOOR,STRUCT,'minecraft:smooth_stone','minecraft:polished_andesite'}
    def walk(x,y,z):
        return (w.get(x,y-1,z) or '').partition('[')[0] in floor_names and all((w.get(x,y+d,z) or '').partition('[')[0] in AIR|{'minecraft:light','projectseele:nerv_ceiling_light'} for d in (0,1))
    joins=[dict(id='upper_west_elbow',feet=-378,box=(-4,341,2,347),reason='Two 1,168/1,294-cell floor components met only at a diagonal corner'),
           dict(id='lower_lift_bypass',feet=-461,box=(60,309,73,313),reason='Connect the lower annex outside the cabin sweep; thin floor lights have no collision')]
    for j in joins:
        x0,z0,x1,z1=j['box'];y=j['feet']
        for x in range(x0,x1+1):
            for z in range(z0,z1+1):
                rim=x in (x0,x1) or z in (z0,z1)
                outward=[(dx,dz) for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)) if not(x0<=x+dx<=x1 and z0<=z+dz<=z1)]
                port=any(walk(x+dx,y,z+dz) for dx,dz in outward) or (j['id']=='lower_lift_bypass' and z==309 and 65<=x<=67)
                put((x,y-1,z),FLOOR,j['id']+'/floor')
                for Y in range(y,y+5):put((x,Y,z),WALL if rim and not port else 'minecraft:air',j['id']+'/wall_or_aperture')
                put((x,y+5,z),STRUCT,j['id']+'/ceiling')
        for x in range(x0+2,x1,4):put((x,y+4,(z0+z1)//2),'projectseele:nerv_ceiling_light[hanging=true,lit=true]',j['id']+'/light')
    # These are actual occupied gallery floor cells. Add an edge screen on
    # the last supported cell, never into an elevator doorway or in the void.
    guards=[]
    for y in (-434,-420,-406,-392):
        for x in range(70,77):
            for z in range(265,273):
                if not walk(x,y,z):continue
                for dx,dz in ((0,-1),(0,1),(-1,0),(1,0)):
                    near=(w.get(x+dx,y,z+dz) or '').partition('[')[0]
                    if near not in AIR:continue
                    if any((w.get(x+dx,Y,z+dz) or '').partition('[')[0] not in AIR|{'minecraft:light'} for Y in range(y-3,y)):continue
                    # Only the end-side edges; keep two full cells of walking
                    # clearance towards the centre of the existing gallery.
                    if not walk(x-dx,y,z-dz) or not walk(x-2*dx,y,z-2*dz):continue
                    put((x,y,z),GLASS,'front_gallery/edge_screen');put((x,y+1,z),GLASS,'front_gallery/edge_screen');guards.append([x,y,z]);break
    for q,(after,owner) in sorted(targets.items()):
        old=w.block(q)
        if old!=after:p.match((*q,*q),old,after,'r40/'+owner)
    p.meta.update(junctions=joins,edge_screens=guards,protected=held)
    p.save_plan('joined_floor_landings')
    if apply:p.apply('joined_floor_landings')
    (OUT/'contract.json').write_text(json.dumps(p.meta,ensure_ascii=False,indent=2),encoding='utf8');print('Junction changes',len(p.ops),'guard columns',len(guards),'protected',len(held))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');main(p.parse_args().apply)
