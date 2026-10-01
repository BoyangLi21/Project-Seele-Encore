"""Actual proposed TV household cells: plan, section and standing room views.

No MC materials/shader claim. The section explicitly removes higher floors.
"""
from pathlib import Path
import argparse,json,gzip,hashlib,shutil,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from regional_voxels import canonical_state
from inspect_map_assets import state_colour

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
COLORS={'another_furniture:oak_table':(171,142,94),'another_furniture:oak_chair':(171,142,94),'another_furniture:brown_sofa':(127,96,73),'minecraft:smooth_quartz':(239,237,225),'minecraft:smooth_quartz_slab':(239,237,225),'minecraft:oak_door':(151,120,77),'minecraft:oak_planks':(171,142,94),'minecraft:spruce_planks':(127,95,62),'minecraft:dark_oak_slab':(94,66,43),'minecraft:dark_oak_stairs':(94,66,43),'minecraft:ochre_froglight':(243,217,160),'minecraft:black_concrete':(43,47,45),'minecraft:white_concrete':(223,225,219),'minecraft:light_gray_concrete':(170,177,175),
    'minecraft:smooth_stone':(172,174,169),'minecraft:smooth_quartz':(230,227,213),
    'minecraft:light_blue_concrete':(111,153,171),'minecraft:crafting_table':(159,116,71),
    'minecraft:white_bed':(224,214,205),'minecraft:water_cauldron':(88,128,143),
    'projectseele:city_personnel_door':(110,128,131),'minecraft:iron_bars':(103,113,115)}

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--name',default='actual_household_review_v1');p.add_argument('--camera-profile',type=Path);a=p.parse_args()
    out=a.plan/a.name;assert not out.exists();out.mkdir()
    d=json.loads((a.plan/'new_district.json').read_text('utf8'));b=d['buildings'][0];x,z,X,Z=b['bounds'];y=b['floor']+10
    rows=[json.loads(r) for r in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')];patch={tuple(r['pos']):r['after'] for r in rows}
    w=MeasuredWorld(WORLD);w.box((x-2,y-1,z-2),(X+4,y+5,Z+4));w.load()
    def state(q):return patch.get(q,w.block(q))
    native={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    def boxes(st):
        if st is None or st.split('[')[0] in AIR|{'minecraft:light'}:return []
        alias=st.replace('projectseele:city_personnel_door[','minecraft:iron_door[').replace('minecraft:oak_door[','minecraft:iron_door[')
        return native.get(alias,[[0,0,0,1,1,1]])
    def colour(st):return COLORS.get(st.split('[')[0],state_colour(st.split('[')[0])[:3])
    cells={}
    for xx in range(x-1,X+4):
        for zz in range(z-1,Z+4):
            for yy in range(y,y+4):
                s=state((xx,yy,zz))
                if boxes(s):cells[xx,yy,zz]=s
    # Plan is a true occupancy slice, with real door/furniture shapes.
    unit=38;offset=(70,100);im=Image.new('RGB',(1280,1200),(244,245,241));draw=ImageDraw.Draw(im)
    for xx in range(x,X+4):
        for zz in range(z,Z+3):
            px=offset[0]+(xx-x)*unit;pz=offset[1]+(zz-z)*unit
            ground=state((xx,y,zz));draw.rectangle((px,pz,px+unit,pz+unit),fill=colour(ground) if ground and boxes(ground) else (243,245,240),outline=(193,196,188))
            st=state((xx,y+1,zz))
            for bx,by,bz,BX,BY,BZ in boxes(st):draw.rectangle((px+bx*unit,pz+bz*unit,px+BX*unit,pz+BZ*unit),fill=colour(st),outline=(83,92,86))
    rooms=[r for r in d['rooms'] if '/floor3/' in r['id']]
    for r in rooms:
        lo,ly,lz,hi,hy,hz=r['bounds'];name=r['id'].split('/')[-1]
        draw.text((offset[0]+(lo-x+.25)*unit,offset[1]+(lz-z+.25)*unit),name,fill=(35,44,40))
    draw.text((40,30),'ACTUAL PROPOSED FLOOR3 / OCCUPANCY AT FEET+0 / METRES AND ROTATION INFERRED',fill=(25,35,30))
    draw.text((40,1110),'Misato above living; kitchen/wet core on left; Shinji and Asuka opposite short hall; veranda on right.',fill=(25,35,30))
    draw.text((40,1135),'Exact ghost cells, not a schematic substituting for the world. No MC/native visual acceptance.',fill=(25,35,30))
    im.save(out/'whole_floor3_actual_plan.png')
    # Isometric section removes only the higher storeys/ceiling, leaving all
    # floor3 real rooms, doors, furniture and outer veranda in their positions.
    def iso(v):xx,yy,zz=v;return np.array([(xx-zz)*.866,(xx+zz)*.5-yy*1.15])
    corners=np.array([iso(q) for q in cells]);low=corners.min(0);high=corners.max(0);scale=min(1430/(high[0]-low[0]+2),1050/(high[1]-low[1]+2))
    polys=[]
    def iso_xy(v):v=(iso(v)-low)*scale;return v[0]+90,v[1]+90
    def faces(q,st):
        for bb in boxes(st):
            bx,by,bz,BX,BY,BZ=bb
            yield (1,0,0),[(BX,by,bz),(BX,BY,bz),(BX,BY,BZ),(BX,by,BZ)],.82
            yield (-1,0,0),[(bx,by,bz),(bx,by,BZ),(bx,BY,BZ),(bx,BY,bz)],.78
            yield (0,0,1),[(bx,by,BZ),(BX,by,BZ),(BX,BY,BZ),(bx,BY,BZ)],.86
            yield (0,0,-1),[(bx,by,bz),(bx,BY,bz),(BX,BY,bz),(BX,by,bz)],.72
            yield (0,1,0),[(bx,BY,bz),(bx,BY,BZ),(BX,BY,BZ),(BX,BY,bz)],1.
            yield (0,-1,0),[(bx,by,bz),(BX,by,bz),(BX,by,BZ),(bx,by,BZ)],.68
    for q,st in cells.items():
        if q[1]>=y+3:continue # explicit2m section cut removes the new private ceiling
        for normal,vertices,shade in faces(q,st):
            if normal not in [(1,0,0),(0,0,1),(0,1,0)]:continue
            pts=[tuple(q[i]+v[i] for i in range(3)) for v in vertices]
            polys.append((q[0]+q[2]+q[1]*.05,pts,tuple(round(v*shade) for v in colour(st))))
    im=Image.new('RGB',(1640,1270),(231,237,234));draw=ImageDraw.Draw(im)
    for depth,pts,col in sorted(polys):draw.polygon([iso_xy(q) for q in pts],fill=col)
    draw.text((30,25),'ACTUAL FLOOR3 SECTION / HIGHER FLOORS + CEILING REMOVED FOR REVIEW / OFFLINE',fill=(20,30,25));im.save(out/'whole_floor3_actual_section.png')
    cameras=[('genkan_to_living',[195.5,y+1,539.5],[203.5,y+2,537.5]),
        ('living_to_misato',[203.5,y+1,537.5],[203.5,y+2,534.5]),
        ('short_hall_opposite_bedrooms',[201.5,y+1,548.5],[204.5,y+2,548.5]),
        ('bath_to_wash',[196.5,y+1,541.5],[200.5,y+2,541.5]),
        ('veranda_to_living',[210.5,y+1,537.5],[205.5,y+2,537.5]),
        ('misato_to_living',[203.5,y+1,531.5],[203.5,y+2,534.5])]
    if a.camera_profile:cameras=[(c['name'],c['feet'],c['target']) for c in json.loads(a.camera_profile.read_text('utf8'))]
    cases=[]
    # Standing views contain the ACTUAL ceiling. Only the section above
    # removes it. Indoor sky caused by a sliced volume is not valid evidence.
    standing_cells=dict(cells)
    for xx in range(x-1,X+4):
        for zz in range(z-1,Z+4):
            for yy in [y+4,y+5]:
                st=state((xx,yy,zz))
                if boxes(st):standing_cells[xx,yy,zz]=st
    for name,feet,target in cameras:
        # Native shape support/headroom is recorded; door interaction still
        # remains a native validation obligation for root.
        q=tuple(math.floor(v) for v in feet);assert boxes(state((q[0],q[1]-1,q[2]))),('unsupported',name,q)
        assert not boxes(state(q)) and not boxes(state((q[0],q[1]+1,q[2]))),('obstructed',name,q,state(q))
        eye=np.array(feet)+[0,1.62,0];forward=np.array(target)-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,[0.,1.,0.]);right/=np.linalg.norm(right);up=np.cross(right,forward)
        focal=700/math.tan(math.radians(49));im=Image.new('RGB',(1400,1000),(211,225,229));draw=ImageDraw.Draw(im);polys=[]
        def project(v):
            delta=np.array(v)-eye;depth=float(delta@forward)
            return None if depth<.12 else (700+float(delta@right)*focal/depth,520-float(delta@up)*focal/depth,depth)
        for q,st in standing_cells.items():
            for normal,vertices,shade in faces(q,st):
                if np.dot(eye-(np.array(q)+.5),normal)<=0:continue
                # Clip polygons against the real near plane. Dropping an
                # entire crossing face invents staircase-shaped wall holes.
                vertices=[np.array(q)+np.array(v) for v in vertices];clipped=[]
                for first,last in zip(vertices,vertices[1:]+vertices[:1]):
                    df=float((first-eye)@forward);dl=float((last-eye)@forward);inside=df>=.121
                    if inside:clipped.append(first)
                    if inside!=(dl>=.121):clipped.append(first+(last-first)*((.121-df)/(dl-df)))
                if len(clipped)<3:continue
                pts=[project(v) for v in clipped]
                if max(p[0] for p in pts)<0 or min(p[0] for p in pts)>1400 or max(p[1] for p in pts)<0 or min(p[1] for p in pts)>1000:continue
                polys.append((sum(v[2] for v in pts)/4,[(v[0],v[1]) for v in pts],tuple(round(v*shade) for v in colour(st))))
        for dep,pts,col in sorted(polys,reverse=True):draw.polygon(pts,fill=col)
        draw.rectangle((0,0,1400,45),fill=(235,240,235));draw.text((20,17),name+' / REAL GHOST CELLS / STANDING EYE1.62m / CLOSED DOORS / OFFLINE',fill=(20,30,25));im.save(out/(name+'.png'))
        vec=np.array(target)-eye;yaw=math.degrees(math.atan2(-vec[0],vec[2]));pitch=-math.degrees(math.atan2(vec[1],math.hypot(vec[0],vec[2])))
        cases.append(dict(id='r44/tv_misato/floor3/'+name,feet=feet,yaw=yaw,pitch=pitch,standing_eye=eye.tolist(),support_and_headroom_source_checked=True,native_visual_passed=False))
    shutil.copy2(Path(__file__),out/'producer_renderer.py')
    (out/'camera_itinerary.json').write_text(json.dumps(cases,indent=2),'utf8')
    (out/'provenance.json').write_text(json.dumps(dict(world=str(WORLD),patch_sha256=hashlib.sha256((a.plan/'forward.jsonl.gz').read_bytes()).hexdigest(),renderer_sha256=hashlib.sha256((out/'producer_renderer.py').read_bytes()).hexdigest(),layer=[y,y+3],closed_door_geometry=True,upper_storeys_section_removed=True,world_written=False,native_photo=False,visual_passed=False,reference='Root and worker actually viewed the fan TV-reference apartment diagram; relationships retained, metres/rotation/floor3 inferred'),indent=2),'utf8')
    print(a.plan.name,'actual plan/section/standing interiors',len(cases),'world unchanged')

if __name__=='__main__':main()
