"""Measured relocation and civil reconstruction of the three EVA transfer lines.

The pressure-cage interiors are copied from the current save. The launch halls,
inclined guideways and operator links are authored in one coordinate frame.
This script only writes a reviewable delta plan unless --apply is requested.
"""
import argparse,copy,json,math
from pathlib import Path
import numpy as np
import nbtlib
import regional_voxels as vox
from query_blocks import AIR,iter_block_entities
from scan_regional_completion import volume
from tv_upper_observation_design_r44 import author_source as author_upper_observer_r44
from tv_crane_girder_design_r44 import running_state as crane_running_state_r44
from hangar_tv_design_r44 import (FINISHABLE, FULL_CUBE, wet_faces,
    wet_finish, transfer_faces, transfer_finish, launch_faces, launch_finish,
    upper_pressure_members, lower_pressure_seam_members)
from plan_hangar_upper_enclosure_r44 import native_public_bearing, public_surface

OUT=vox.ROOT/'artifacts/world_rebuild_r20/factory'
LO=(-48,-513,-302);HI=(164,-310,24)
SOURCE=(-40,-467,-145,104,-350,-70);DZ=-144
CENTRES=(-12,30,72);CAGE_Y=-443;CAGE_Z=-240;LAUNCH_Y=-411;LAUNCH_Z=-36
FLOOR='projectseele:nerv_floor_panel';WALL='projectseele:nerv_wall_panel';STRUCT='projectseele:nerv_structural_panel';EDGE='projectseele:nerv_machine_edge';GLASS='minecraft:light_gray_stained_glass';LIGHT='projectseele:nerv_strip_light';MACHINE='projectseele:nerv_machine_panel';HAZARD='projectseele:nerv_machine_hazard'

def guide_y(z):
    length=160.;distance=np.clip(z+212.,0,length);blend=6.;effective=length-blend
    def rounded(d):return d*.5-blend/(2*math.pi)*math.sin(math.pi*d/blend)
    rise=rounded(distance) if distance<blend else effective-rounded(length-distance) if distance>length-blend else distance-blend*.5
    return CAGE_Y+(LAUNCH_Y-CAGE_Y)*rise/effective

class Scene:
    def __init__(self):
        self.before,self.palette=volume(LO,HI);self.after=self.before.copy();self.ids={s:i for i,s in enumerate(self.palette)};self.protected=np.zeros(self.after.shape,bool);self.descriptions=[]
    def index(self,box):
        x,y,z,X,Y,Z=box;assert x>=LO[0] and y>=LO[1] and z>=LO[2] and X<=HI[0] and Y<=HI[1] and Z<=HI[2],box
        return np.s_[y-LO[1]:Y-LO[1]+1,z-LO[2]:Z-LO[2]+1,x-LO[0]:X-LO[0]+1]
    def state(self,name):
        name=vox.canonical_state(name)
        if name not in self.ids:self.ids[name]=len(self.palette);self.palette.append(name)
        return self.ids[name]
    def fill(self,box,name):
        sl=self.index(box);target=self.after[sl];target[~self.protected[sl]]=self.state(name)
    def protect(self,box):self.protected[self.index(box)]=True
    def corridor_z(self,x0,x1,z0,z1,f):
        self.fill((x0,f-1,z0,x1,f+6,z1),STRUCT)
        self.fill((x0+1,f+1,z0,x1-1,f+5,z1),'minecraft:air');self.fill((x0+1,f,z0,x1-1,f,z1),FLOOR)
        for x in (x0,x1):
            self.fill((x,f+1,z0,x,f+5,z1),WALL);self.fill((x,f+2,z0+1,x,f+4,z1-1),GLASS)
        for z in range(z0+3,z1-2,12):self.fill((x0+2,f+6,z,min(x0+4,x1-1),f+6,z+1),LIGHT)
        self.descriptions.append({'kind':'enclosed_gallery','bounds':[x0,f-1,z0,x1,f+6,z1],'floor':f})
    def delta(self,painter,name):
        changes=self.before!=self.after;count=int(changes.sum());assert count
        for yy in np.flatnonzero(changes.any(axis=(1,2))):
            for zz in np.flatnonzero(changes[yy].any(axis=1)):
                xs=np.flatnonzero(changes[yy,zz]);start=0
                while start<len(xs):
                    end=start+1;a=int(xs[start]);old=int(self.before[yy,zz,a]);new=int(self.after[yy,zz,a])
                    while end<len(xs) and xs[end]==xs[end-1]+1 and int(self.before[yy,zz,xs[end]])==old and int(self.after[yy,zz,xs[end]])==new:end+=1
                    box=(a+LO[0],int(yy+LO[1]),int(zz+LO[2]),int(xs[end-1]+LO[0]),int(yy+LO[1]),int(zz+LO[2]));painter.match(box,self.palette[old],self.palette[new],name);start=end
        return count

def plan():
    if (vox.WORLD/'eva_facility_r29.json').is_file() or (vox.WORLD/'.projectseele_spatial_preview_read_only.json').is_file():
        raise RuntimeError('The historic R20 relocation template is retired for delivered/frozen facilities; use a measured R44 component revision')
    OUT.mkdir(parents=True,exist_ok=True);vox.OUT=OUT;p=vox.Painter();s=Scene()
    # The retained compact observation lift is a live mechanism. Protect its
    # complete shell and capture sweep, not merely its controller block.
    s.protect((89,-446,-56,99,-364,-48))
    source=s.before[s.index(SOURCE)].copy();destination=tuple(v+(DZ if i in (2,5) else 0) for i,v in enumerate(SOURCE))
    target=s.before[s.index(destination)];allowed=np.array([v.split('[')[0] in AIR or vox.natural(v) or v.startswith('minecraft:light[') for v in s.palette])
    bad=~allowed[target]
    if bad.any():raise RuntimeError(('New cage footprint contains another authored structure',dict(zip(*np.unique(np.asarray(s.palette)[target[bad]],return_counts=True)))))
    s.after[s.index(destination)]=source
    # Remove the old wet-cage body after copying. The high observation room is
    # deliberately rebuilt at its old coordinates, not moved with this payload.
    s.fill(SOURCE,'minecraft:air')
    for pos,tag in iter_block_entities(vox.WORLD,vox.DIM,SOURCE[:3],SOURCE[3:]):
        new=(pos[0],pos[1],pos[2]+DZ);t=copy.deepcopy(tag);t['z']=nbtlib.Int(new[2]);p.block_entities[new]=t
    # Continuous foundation for the new pressure vessels and overhead portals.
    s.fill((-43,-512,-292,107,-468,-198),STRUCT)
    for x0,x1 in ((-43,-34),(94,107)):
        s.fill((x0,-467,-292,x1,-444,-198),STRUCT);s.fill((x0,-443,-292,x1,-443,-198),FLOOR)
    for z0,z1 in ((-292,-276),(-213,-198)):
        s.fill((-34,-467,z0,94,-444,z1),STRUCT)
    # R46 retires the north maintenance apron and lower blind corridor.
    # Keep the independent wet-vessel foundation; no public wearing slab.
    # Clear the obsolete flat transfer plant and lower observation passage.
    s.fill((-36,-443,-69,104,-350,-10),'minecraft:air')
    s.fill((-38,-420,-20,103,-389,-10),'minecraft:air')
    s.fill((89,-443,-19,100,-389,-10),'minecraft:air')
    # Reconstructed high launch halls: pressure wells stay in their existing
    # X/Z positions; the carrier loading deck is 32 m above the cage deck.
    for cx in CENTRES:
        s.fill((cx-17,-444,-54,cx+17,-412,-18),STRUCT)
        s.fill((cx-15,-443,-51,cx+15,-413,-21),'minecraft:air')
        s.fill((cx-17,LAUNCH_Y-1,-54,cx+17,LAUNCH_Y,-18),STRUCT)
        s.fill((cx-15,LAUNCH_Y-4,-51,cx+15,LAUNCH_Y,-21),'minecraft:air')
        s.fill((cx-15,LAUNCH_Y-5,-51,cx+15,LAUNCH_Y-5,-21),MACHINE)
        s.fill((cx-15,LAUNCH_Y+1,-51,cx+15,-310,-21),'minecraft:air')
        for x in (cx-17,cx+17):
            s.fill((x,LAUNCH_Y+1,-54,x,-310,-18),WALL)
            for y in range(LAUNCH_Y+2,-311,12):s.fill((x,y,-54,x,y+1,-18),EDGE)
        s.fill((cx-16,LAUNCH_Y+1,-19,cx+16,-310,-18),WALL)
        s.fill((cx-17,-311,-54,cx+17,-310,-18),STRUCT)
        s.fill((cx-15,-311,-51,cx+15,-310,-21),'minecraft:air')
        s.fill((cx-17,-326,-54,cx+17,-312,-53),WALL)
        for dx in (-10,10):s.fill((cx+dx,LAUNCH_Y+1,-20,cx+dx,-311,-20),EDGE)
        s.fill((cx,LAUNCH_Y,-36,cx,LAUNCH_Y,-36),'minecraft:lodestone')
        # Deck edges are mechanically supported down to the old foundation.
        for x in (cx-17,cx+17):
            for z in (-54,-18):s.fill((x-1,-467,z-1,x+1,LAUNCH_Y-2,z+1),STRUCT)
    # A complete inclined transfer hall with low cage pad, rounded grade,
    # level high loading pad and clear upright EVA envelopes.
    for z in range(-212,-53):
        y=math.floor(guide_y(z));roof=y+86
        s.fill((-35,y-2,z,95,roof,z),STRUCT)
        s.fill((-33,y+1,z,93,roof-2,z),'minecraft:air')
        s.fill((-33,y,z,93,y,z),FLOOR)
        for x in (-35,95):s.fill((x,y+1,z,x,roof-1,z),WALL)
        for x in (9,51):
            s.fill((x-1,y+1,z,x+1,y+4,z),MACHINE)
        if (z+212)%20 in (0,1):
            s.fill((-34,roof-3,z,94,roof-2,z),EDGE)
            for x in (-34,94):s.fill((x,-467,z,x,y-3,z),STRUCT)
        for cx in CENTRES:
            # A real transport trench gives the level back-pallet clearance
            # over the inclined guide. The floor must not pass through its
            # leading edge; staff circulation is in the enclosed side gallery.
            s.fill((cx-14,y-4,z,cx+14,y,z),'minecraft:air')
            s.fill((cx-14,y-5,z,cx+14,y-5,z),MACHINE)
            for dx in (-15,15):s.fill((cx+dx,y,z,cx+dx,y,z),EDGE)
    # Gate frame reconnects to the untouched copied pressure-cell envelope.
    for cx in CENTRES:
        for x in (cx-18,cx+18):s.fill((x,-442,-214,x,-365,-213),EDGE)
        s.fill((cx-18,-365,-214,cx+18,-363,-213),EDGE)
    s.fill((-34,CAGE_Y,-214,94,CAGE_Y,-213),FLOOR)
    s.fill((30,CAGE_Y,-213,30,CAGE_Y,-213),HAZARD)
    # Fixed roof portals and crane runways physically bear the hoist model.
    for z in (-282,-250,-216):
        for x in (-34,9,51,94):s.fill((x-1,-467,z-1,x+1,-349,z+1),STRUCT)
        s.fill((-35,-352,z-1,95,-349,z+1),EDGE)
    # Moving hoist wheel bottoms run on Y=-373; the old Y=-363 runway was
    # ten metres above its current producer. The roof stays at its measured
    # underside Y=-355. Outboard hangers leave both running wheel lanes free.
    for cx in CENTRES:
        for x in (cx-4,cx+4):
            for y in range(-376,-373):
                for z in range(-266,-215):s.fill((x,y,z,x,y,z),crane_running_state_r44(y,z))
        for z in (-264,-246,-228):
            for sign in (-1,1):
                x0,x1=sorted((cx+4*sign,cx+8*sign))
                s.fill((x0,-377,z,x1,-377,z),STRUCT)
                s.fill((cx+8*sign,-377,z,cx+8*sign,-356,z),STRUCT)
    # Staff reach every moved cage through enclosed galleries and the existing
    # three-stop compact lift; lower and upper levels do not cut one another.
    s.corridor_z(95,103,-271,-42,-395)
    for f in (-395,):
        s.fill((92,f-1,-48,110,f+6,-44),STRUCT);s.fill((93,f+1,-47,109,f+5,-45),'minecraft:air');s.fill((93,f,-47,109,f,-45),FLOOR)
    # Upper front gallery of the third cage reaches the new longitudinal link.
    s.fill((90,-396,-270,100,-388,-262),STRUCT);s.fill((91,-394,-269,99,-389,-263),'minecraft:air');s.fill((91,-395,-269,99,-395,-263),FLOOR)
    for z in range(-279,-41,24):
        s.fill((112,-467,z,113,-395,z+1),STRUCT);s.fill((95,-397,z,113,-396,z+1),EDGE)
    # Restore the observation room which the user identified, including a
    # real roof and foundations. The lift's reserved volume remains untouched.
    s.fill((88,-371,-84,113,-363,-16),STRUCT)
    s.fill((89,-369,-83,112,-364,-17),'minecraft:air');s.fill((89,-370,-83,112,-370,-17),FLOOR)
    for x in (88,113):s.fill((x,-368,-82,x,-365,-18),GLASS)
    for z in (-84,-16):s.fill((90,-368,z,111,-365,z),GLASS)
    for x in (89,112):
        for z in (-82,-18):s.fill((x,-467,z,x,-372,z),STRUCT)
    for z in range(-78,-18,12):s.fill((99,-363,z,102,-363,z+1),LIGHT)
    # Open the retained north-facing upper lift door into the restored room.
    s.fill((92,-369,-58,94,-366,-55),'minecraft:air');s.fill((92,-370,-58,94,-370,-55),FLOOR)
    # Rejoin the commissioned station / headquarters lower gallery.
    s.fill((109,-444,-47,131,-437,-41),STRUCT);s.fill((110,-442,-46,130,-438,-42),'minecraft:air');s.fill((110,-443,-46,130,-443,-42),FLOOR)
    # The initial authoring template and delivered-world skin share exactly
    # one hierarchy. Only pre-existing known cubes of the resulting Scene may
    # change finish; copied glass, machinery, openings and all BE stay whole.
    shapes=json.loads((vox.WORLD/'native_collision_shapes.json').read_text(encoding='utf8'))
    def finish(points,target):
        for q in points:
            if not all(LO[i]<=q[i]<=HI[i] for i in range(3)):continue
            yy,zz,xx=q[1]-LO[1],q[2]-LO[2],q[0]-LO[0]
            if s.protected[yy,zz,xx] or q in p.block_entities:continue
            before=s.palette[int(s.after[yy,zz,xx])]
            if before.partition('[')[0] not in FINISHABLE:continue
            after=target(q,before)
            if shapes.get(before)!=FULL_CUBE or shapes.get(after)!=FULL_CUBE:
                raise RuntimeError(('Template finish has no complete native cube',q,before,after))
            s.after[yy,zz,xx]=s.state(after)
    for cx in CENTRES:
        finish(wet_faces(cx),lambda q,b,cx=cx:wet_finish(cx,q,b))
        finish(launch_faces(cx),lambda q,b,cx=cx:launch_finish(cx,q,b))
    finish(transfer_faces(guide_y),transfer_finish)
    for q,after in (upper_pressure_members() | lower_pressure_seam_members()).items():
        public_column = False
        for feet in (-394, -367):
            if feet - 1 <= q[1] <= feet + 2:
                floor = s.palette[int(s.after[feet-1-LO[1], q[2]-LO[2], q[0]-LO[0]])]
                if public_surface(floor) and shapes.get(floor) is None:
                    raise RuntimeError(('Public pressure-column bearing has no exact native shape', q, feet, floor))
                if native_public_bearing(floor, shapes.get(floor)):
                    public_column = True
                    break
        if public_column:
            continue
        yy,zz,xx=q[1]-LO[1],q[2]-LO[2],q[0]-LO[0]
        if s.protected[yy,zz,xx] or q in p.block_entities:continue
        before=s.palette[int(s.after[yy,zz,xx])]
        if before.partition('[')[0] not in AIR:continue
        if shapes.get(after)!=FULL_CUBE:raise RuntimeError(('Unknown pressure material',after))
        s.after[yy,zz,xx]=s.state(after)
    author_upper_observer_r44(s,p.block_entities)
    # Keep every protected cage cell exactly as measured, including absence.
    assert np.array_equal(s.before[s.protected],s.after[s.protected])
    changed=s.delta(p,'r20/factory_civil_reconstruction')
    p.meta.update(source_box=SOURCE,cage_delta=[0,0,DZ],cages=[[x,CAGE_Y,CAGE_Z] for x in CENTRES],launches=[[x,LAUNCH_Y,LAUNCH_Z] for x in CENTRES],surface_shafts_unchanged=True,operator_galleries=s.descriptions,retired_lift_group='97;-15',preserved_observation=[91,-369,-61],changed_cells=changed)
    (OUT/'layout.json').write_text(json.dumps({'installed':False,'cage_shift_z':DZ,'launch_rise':32,'cages':p.meta['cages'],'launches':p.meta['launches'],'ramp_low_pad':28,'ramp_high_pad':16,'ramp_blend':6,'retired_lift_group':'97;-15'},indent=2))
    np.savez_compressed(OUT/'review_geometry.npz',before=s.before,after=s.after,palette=np.asarray(s.palette),lo=LO,hi=HI)
    return p

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--apply',action='store_true');args=a.parse_args();p=plan();p.apply('civil_factory') if args.apply else p.save_plan('civil_factory');print('Factory plan ready',p.meta['changed_cells'])
