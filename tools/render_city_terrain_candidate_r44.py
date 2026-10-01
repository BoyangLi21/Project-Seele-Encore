"""Read retained terrain + exact ghost patch; offline views are never native evidence."""
from pathlib import Path
import argparse,gzip,json,math,hashlib
import shutil
from collections import Counter
import numpy as np
from PIL import Image,ImageDraw
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR
from inspect_map_assets import state_colour
from regional_voxels import canonical_state

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('plan',type=Path);parser.add_argument('--name',default='retained_terrain_views');parser.add_argument('--standing-only',action='store_true');parser.add_argument('--isometric-only',action='store_true');parser.add_argument('--building');a=parser.parse_args()
    output=a.plan/a.name;assert not output.exists();output.mkdir()
    rows=[json.loads(line) for line in gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8')]
    district=json.loads((a.plan/'new_district.json').read_text('utf8'))
    x0,x1,z0,z1=district['bounds'];x0-=12;x1+=12;z0-=12;z1+=12
    ownership=ROOT/'artifacts/rebuild_r44/city_buildings/actual_authored_ownership.json'
    if ownership.exists():
        # Whole retained neighbour buildings prevent a bbox cutting off their
        # facades and falsely presenting those crop strips as map defects.
        neighbours=[]
        for b in json.loads(ownership.read_text('utf8'))['buildings']:
            lo,hi=b['planned_bounds']
            if lo[0]<=x1 and hi[0]>=x0 and lo[2]<=z1 and hi[2]>=z0:neighbours.append((lo,hi))
        if neighbours:
            x0=min(x0,min(lo[0]-3 for lo,hi in neighbours));x1=max(x1,max(hi[0]+3 for lo,hi in neighbours))
            z0=min(z0,min(lo[2]-3 for lo,hi in neighbours));z1=max(z1,max(hi[2]+3 for lo,hi in neighbours))
    w=MeasuredWorld(WORLD);w.box((x0,40,z0),(x1,220,z1));w.load()
    cells={};measured=Counter();natural={};exposure_surface={}
    for (cx,sy,cz),(palette,ids) in w.tiles.items():
        if sy<2 or sy>13:continue
        data=ids.reshape(16,16,16);names=[s.split('[')[0] for s in palette]
        xx=np.arange(cx*16,cx*16+16);zz=np.arange(cz*16,cz*16+16)
        if xx[-1]<x0 or xx[0]>x1 or zz[-1]<z0 or zz[0]>z1:continue
        grass=np.array([s=='minecraft:grass_block' for s in names])[data]
        yy,iz,ix=np.where(grass)
        for iy,jz,jx in zip(yy,iz,ix):
            q=(cx*16+int(jx),cz*16+int(jz));natural[q]=max(natural.get(q,-32768),sy*16+int(iy))
        terrain_names={'minecraft:'+n for n in ['grass_block','dirt','coarse_dirt','rooted_dirt','stone','gravel','sand','clay','sandstone','mud','water']}
        terrain=np.array([s in terrain_names for s in names])[data]
        yy,iz,ix=np.where(terrain)
        for iy,jz,jx in zip(yy,iz,ix):
            q=(cx*16+int(jx),cz*16+int(jz));exposure_surface[q]=max(exposure_surface.get(q,-32768),sy*16+int(iy))
    patch={tuple(r['pos']):r['after'] for r in rows}
    deepest_change={}
    for x,y,z in patch:
        deepest_change[x,z]=min(y,deepest_change.get((x,z),y))
    exposed_cut_depth=dict(deepest_change)
    for (x,z),y in deepest_change.items():
        for dx,dz in [(1,0),(-1,0),(0,1),(0,-1)]:
            q=x+dx,z+dz;exposed_cut_depth[q]=min(y,exposed_cut_depth.get(q,y))
    source_boxes={}
    if (a.plan/'source_shape_candidates.json').exists():source_boxes={r['state']:[[v/16 for v in b] for b in r['source_boxes_pixels']] for r in json.loads((a.plan/'source_shape_candidates.json').read_text('utf8'))['cases']}
    # A height skin cannot represent a real overhang or an internal hollow:
    # both adjacent column tops can be high while a lower side is exposed.
    # Assemble the measured full review volume, then extract only actual
    # exposed voxels. This also avoids retaining millions of buried Python
    # cell objects just to draw their much smaller surface.
    state_palette=['minecraft:air'];state_ids={state_palette[0]:0}
    def state_id(st):
        if st not in state_ids:state_ids[st]=len(state_palette);state_palette.append(st)
        return state_ids[st]
    volume=np.zeros((181,z1-z0+1,x1-x0+1),dtype=np.uint16)
    for (cx,sy,cz),(pal,ids) in w.tiles.items():
        ax,bx=max(x0,cx*16),min(x1,cx*16+15);az,bz=max(z0,cz*16),min(z1,cz*16+15);ay,by=max(40,sy*16),min(220,sy*16+15)
        if ax>bx or az>bz or ay>by:continue
        remap=np.array([state_id(st)for st in pal],dtype=np.uint16)
        volume[ay-40:by-40+1,az-z0:bz-z0+1,ax-x0:bx-x0+1]=remap[ids.reshape(16,16,16)[ay-sy*16:by-sy*16+1,az-cz*16:bz-cz*16+1,ax-cx*16:bx-cx*16+1]]
    assert len(state_palette)<65536
    for (x,y,z),st in patch.items():
        if x0<=x<=x1 and z0<=z<=z1 and 40<=y<=220:volume[y-40,z-z0,x-x0]=state_id(st)
    solid=np.array([st.split('[')[0]not in AIR|{'minecraft:light'}for st in state_palette])[volume]
    exposed=np.zeros_like(solid)
    for axis in range(3):
        front=[slice(None)]*3;back=[slice(None)]*3;front[axis]=slice(1,None);back[axis]=slice(None,-1)
        exposed[tuple(front)]|=~solid[tuple(back)];exposed[tuple(back)]|=~solid[tuple(front)]
        edge=[slice(None)]*3;edge[axis]=0;exposed[tuple(edge)]=True;edge[axis]=-1;exposed[tuple(edge)]=True
    for iy,iz,ix in zip(*np.where(exposed&solid)):
        cells[int(ix)+x0,int(iy)+40,int(iz)+z0]=state_palette[int(volume[iy,iz,ix])]
    for z in range(z0,z1+1):
        for x in range(x0,x1+1):measured[str(w.status.get((x//16,z//16)))]+=1
    full_volume_non_air=int(solid.sum());del volume,solid,exposed
    faces=[];palette={};specs=[((1,0,0),[(1,0,0),(1,1,0),(1,1,1),(1,0,1)],.78),
        ((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)],.62),
        ((0,1,0),[(0,1,0),(1,1,0),(1,1,1),(0,1,1)],1.)]
    allpoints=np.array(list(cells));rendered=[]
    for view,sx,sz in ([] if a.standing_only else [('south_east',1,1),('north_west',-1,-1),('south_west',-1,1)]):
        def project(q):
            x,y,z=q;return np.array([(sx*x-sz*z)*.866,(sx*x+sz*z)*.5-y*1.35])
        corners=np.array([project(q) for q in allpoints[::max(1,len(allpoints)//18000)]])
        low=corners.min(0);high=corners.max(0);scale=min(1920/(high[0]-low[0]),1230/(high[1]-low[1]))
        image=Image.new('RGB',(2048,1400),(223,229,225));draw=ImageDraw.Draw(image)
        def xy(q):v=(project(q)-low)*scale;return float(v[0])+60,float(v[1])+80
        faces=[];white_material_faces=[]
        local_specs=[((sx,0,0),[(1 if sx>0 else 0,0,0),(1 if sx>0 else 0,1,0),(1 if sx>0 else 0,1,1),(1 if sx>0 else 0,0,1)],.78),
            ((0,0,sz),[(0,0,1 if sz>0 else 0),(1,0,1 if sz>0 else 0),(1,1,1 if sz>0 else 0),(0,1,1 if sz>0 else 0)],.62),specs[2]]
        for q,st in cells.items():
            if st not in palette:
                name=st.split('[')[0]
                natural_colours={'minecraft:grass_block':(115,148,72),'minecraft:grass':(105,147,66),'minecraft:tall_grass':(105,147,66),
                    'minecraft:dirt':(126,104,80),'minecraft:coarse_dirt':(139,114,80),'minecraft:stone':(122,124,122),'minecraft:smooth_sandstone':(202,192,162),
                    'minecraft:gray_stained_glass':(98,129,137),'minecraft:water':(91,145,163),
                    'projectseele:city_rain_pipe':(126,136,133),'projectseele:city_rain_gutter':(126,136,133)}
                palette[st]=natural_colours.get(name,state_colour(name)[:3])
            if st in source_boxes:
                for b in source_boxes[st]:
                    bx,by,bz,BX,BY,BZ=b
                    small_faces=[([(BX,by,bz),(BX,BY,bz),(BX,BY,BZ),(BX,by,BZ)] if sx>0 else [(bx,by,bz),(bx,BY,bz),(bx,BY,BZ),(bx,by,BZ)],.78),
                        ([(bx,by,BZ),(BX,by,BZ),(BX,BY,BZ),(bx,BY,BZ)] if sz>0 else [(bx,by,bz),(BX,by,bz),(BX,BY,bz),(bx,BY,bz)],.62),
                        ([(bx,BY,bz),(BX,BY,bz),(BX,BY,BZ),(bx,BY,BZ)],1.)]
                    for vertices,shade in small_faces:
                        colour=tuple(round(v*shade) for v in palette[st]);points=[tuple(q[i]+v[i] for i in range(3)) for v in vertices]
                        faces.append((sx*q[0]+sz*q[2]+q[1]*.05,q[1],points,colour))
                continue
            for delta,corners,shade in local_specs:
                other=tuple(q[i]+delta[i] for i in range(3))
                if other in cells:continue
                # A neighbour below the sampled upper terrain skin still
                # exists in the real world and must hide this apparent face.
                neighbour=patch.get(other,w.block(other))
                if neighbour is not None and neighbour.split('[')[0] not in AIR|{'minecraft:light'}:continue
                # The bottom/edge of the sampled terrain is a crop, never an
                # in-world cliff or geometry proposal.
                if other[0]<x0 or other[0]>x1 or other[2]<z0 or other[2]>z1:continue
                colour=tuple(round(v*shade) for v in palette[st]);points=[tuple(q[i]+v[i] for i in range(3)) for v in corners]
                faces.append((sx*q[0]+sz*q[2]+q[1]*.05,q[1],points,colour))
                if min(palette[st])>=215:white_material_faces.append(dict(pos=q,state=st,points=points))
        visible=np.array([project(q) for face in faces for q in face[2]]);low=visible.min(0);high=visible.max(0);scale=min(1920/(high[0]-low[0]),1230/(high[1]-low[1]))
        for depth,y,points,colour in sorted(faces,key=lambda f:(f[0],f[1])):draw.polygon([xy(q) for q in points],fill=colour)
        (output/(view+'_pale_material_face_evidence.json')).write_text(json.dumps(dict(projection_low=low.tolist(),projection_scale=scale,faces=[dict(pos=r['pos'],state=r['state'],image_polygon=[xy(q)for q in r['points']])for r in white_material_faces],scope='Actual named pale material surfaces, not inferred world holes. Renderer-background holes have no named material face.'),indent=2),'utf8')
        draw.text((28,24),district['id']+' / '+view+' / REAL RETAINED TERRAIN + EXACT GHOST / OFFLINE CUBIC MASSING',fill=(20,28,25))
        draw.text((28,1350),'NOT MINECRAFT / rain details use source quarter-metre boxes; remaining stairs/glass are cells / no visual acceptance',fill=(20,28,25))
        file=output/(view+'.png');image.save(file);rendered.append(dict(path=str(file.resolve()),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),camera_corner=view))
    # Real standing cameras: whole facade plus entrance in the same frame.
    # The same measured terrain is retained, and measured native collision
    # boxes make doors/slabs/stairs legible rather than full-cube impostors.
    native={canonical_state(s):v for s,v in json.loads((WORLD/'native_collision_shapes.json').read_text('utf8')).items()}
    road_columns=json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']
    retained_road=ROOT/'artifacts/rebuild_r44/surface_network/road_complete_authority_stage3.columns.npz'
    if retained_road.exists():
        authority=np.load(retained_road);coords=authority['coordinates'];flags=authority['flags'];mask=(coords[:,0]>=x0)&(coords[:,0]<=x1)&(coords[:,1]>=z0)&(coords[:,1]<=z1)&((flags&7)==7)
        road_columns.extend(dict(pos=list(map(int,q)),native_feet=float(feet),source='retained complete actual road authority') for q,feet in zip(coords[mask],authority['actual_feet'][mask]))
    for b in district['buildings']:
        if a.isometric_only:continue
        if a.building and b['id'].split('/')[-1] not in a.building.split(','):continue
        ex,feet,ez=b['entry'];dx,dz={'south':(0,1),'north':(0,-1),'east':(1,0),'west':(-1,0)}[b.get('facing','south')]
        span=b['bounds'][2]-b['bounds'][0] if dx==0 else b['bounds'][3]-b['bounds'][1]
        for mode,distance in [('standing_whole',max(14,span*.9)),('standing_entry',7)]:
            feet=b['entry'][1] # candidate loops must never overwrite the actual entry datum
            # The measured street handoff is already a real support/headroom
            # obligation; an arbitrary eye-in-air can stand inside a grass
            # face or a neighbouring building. Whole view uses that port.
            hx,hy,hz=b['actual_street_handoff'];at=np.array([hx+.5,hy,hz+.5]) if mode=='standing_whole' else np.array([ex+.5+dx*3,feet,ez+.5+dz*3])
            if mode=='standing_whole':
                front=np.array([(b['bounds'][0]+b['bounds'][2])/2,b['door'][2]]) if dx==0 else np.array([b['door'][0],(b['bounds'][1]+b['bounds'][3])/2]);choices=[]
                def standing_datum_valid(px,pz,feet):
                    supported=False
                    for yy in range(math.floor(feet)-2,math.ceil(feet+1.8)):
                        st=patch.get((int(px),yy,int(pz)),w.get(int(px),yy,int(pz)))
                        if st is None:return False
                        boxes=source_boxes.get(st,native.get(st,[] if st.split('[')[0] in AIR else [[0,0,0,1,1,1]]))
                        for box in boxes:
                            if box[0]<=.2 and box[3]>=.8 and box[2]<=.2 and box[5]>=.8 and abs(yy+box[4]-feet)<.001:supported=True
                            if box[0]<.8 and box[3]>.2 and box[2]<.8 and box[5]>.2 and yy+box[1]<feet+1.8 and yy+box[4]>feet+.001:return False
                    return supported
                def clear_door_view(candidate):
                    eye=np.array(candidate)+[0,1.62,0];goal=np.array([b['door'][0]+.5,b['door'][1]+.8,b['door'][2]+.5]);steps=max(2,math.ceil(float(np.linalg.norm(goal-eye))*3))
                    for k in range(1,steps-2):
                        p=eye+(goal-eye)*k/steps;q=tuple(map(math.floor,p));st=patch.get(q,w.block(q))
                        if st is None:return False
                        if st.split('[')[0] in AIR|{'minecraft:light'} or 'glass' in st:continue
                        for box in source_boxes.get(st,native.get(st,[[0,0,0,1,1,1]])):
                            if all(box[i]<=p[i]-q[i]<=box[i+3] for i in range(3)):return False
                    return True
                for r in road_columns:
                    q=np.array(r['pos']);delta=q-front;depth=float(delta@np.array([dx,dz]));side=abs(float(delta@np.array([-dz,dx])))
                    candidate_feet=r['native_feet'];px,pz=r['pos'];clear=standing_datum_valid(px,pz,candidate_feet)
                    if clear and max(7,span*.45)<=depth<=max(30,span*1.2) and side<=max(3,span*.15) and clear_door_view([px+.5,candidate_feet,pz+.5]):choices.append((side*5+abs(depth-max(11,span*.7)),r))
                if choices:
                    selected_road=min(choices,key=lambda r:r[0])[1];qx,qz=selected_road['pos'];at=np.array([qx+.5,selected_road['native_feet'],qz+.5])
                else:
                    # Wide campuses may have no parallel road far enough
                    # from the vestibule. Use an actual FULL dry natural
                    # standing column, never retain a5m close-up as 'whole'.
                    ground_choices=[]
                    for (qx,qz),gy in natural.items():
                        if w.status.get((qx//16,qz//16))!='full':continue
                        delta=np.array([qx,qz])-front;depth=float(delta@np.array([dx,dz]));side=abs(float(delta@np.array([-dz,dx])))
                        if not (max(12,span*.55)<=depth<=max(35,span*1.25) and side<=max(4,span*.2)):continue
                        st=patch.get((qx,gy,qz),w.get(qx,gy,qz));head=[patch.get((qx,yy,qz),w.get(qx,yy,qz)) for yy in [gy+1,gy+2]]
                        if st and st.split('[')[0]=='minecraft:grass_block' and all(s and s.split('[')[0] in AIR for s in head) and clear_door_view([qx+.5,gy+1,qz+.5]):ground_choices.append((side*5+abs(depth-max(18,span*.75)),[qx+.5,gy+1,qz+.5]))
                    if ground_choices:at=np.array(min(ground_choices,key=lambda r:r[0])[1])
                    else:
                        oblique=[]
                        for r in road_columns:
                            px,pz=r['pos'];candidate_feet=r['native_feet'];delta=np.array([px,pz])-front;depth=float(delta@np.array([dx,dz]));side=abs(float(delta@np.array([-dz,dx])))
                            if not (5<=depth<=max(30,span) and span*.55<=side<=span*1.1):continue
                            if standing_datum_valid(px,pz,candidate_feet) and clear_door_view([px+.5,candidate_feet,pz+.5]):oblique.append((abs(side-span*.75)+abs(depth-12),[px+.5,candidate_feet,pz+.5]))
                        if oblique:at=np.array(min(oblique,key=lambda r:r[0])[1])
            if mode=='standing_whole' and b['id'].endswith('/inn') and district['id']=='hakone_west':
                at=np.array([-1940.5,105.,498.5])
                road=json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns'];assert any(r['pos']==[-1941,498] and r['native_feet']==105 for r in road),'Whole inn camera must be the actual measured street support column'
            eye=at+[0,1.62,0];target=np.array([((b['bounds'][0]+b['bounds'][2])/2+.5 if dx==0 else b['door'][0]+.5),(b['floor']+b['roof'])/2+1,(b['door'][2]+.5 if dx==0 else (b['bounds'][1]+b['bounds'][3])/2+.5)]) if mode=='standing_whole' else np.array([b['door'][0]+.5,feet+1.5,b['door'][2]+.5])
            if mode=='standing_whole':
                # Perspective framing uses angular centre, not the vertical
                # metre midpoint that clips doors from near tall facades.
                horizontal=float(np.linalg.norm((target-eye)[[0,2]]));horizontal=max(.5,horizontal)
                low=math.atan2(b['floor']-eye[1],horizontal);high=math.atan2(b['roof']+5-eye[1],horizontal)
                target[1]=eye[1]+horizontal*math.tan((low+high)/2)
            forward=target-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,np.array([0.,1.,0.]));right/=np.linalg.norm(right);up=np.cross(right,forward)
            image=Image.new('RGB',(1600,1100),(202,223,230));draw=ImageDraw.Draw(image);polys=[];focal=800/math.tan(math.radians(52 if mode=='standing_whole' else 44))
            def project_standing(v):
                d=np.array(v)-eye;depth=float(d@forward)
                if depth<.25:return None
                return (800+float(d@right)*focal/depth,600-float(d@up)*focal/depth,depth)
            vectors=allpoints-eye;depths=vectors@forward;sides=vectors@right;selected=allpoints[(depths>=.2)&(depths<=100)&(np.abs(sides)<=depths*1.1+3)]
            for coordinate in selected:
                q=tuple(map(int,coordinate));st=cells[q]
                name=st.split('[')[0]
                native_alias=st.replace('minecraft:brick_stairs[','minecraft:polished_andesite_stairs[')
                boxes=source_boxes.get(st,native.get(native_alias,[[0,0,0,1,1,1]]))
                # Collisionless windows still occupy their exact authored
                # block volume visually; the image is explicitly offline.
                if 'glass' in name:boxes=[[0,0,0,1,1,1]]
                if '_wall_sign[' in st:boxes=[[0,.3,0,1,.85,.12]] if 'facing=north' in st else [[0,.3,.88,1,.85,1]] if 'facing=south' in st else [[.88,.3,0,1,.85,1]] if 'facing=east' in st else [[0,.3,0,.12,.85,1]]
                original_colours={'minecraft:smooth_sandstone':(202,192,162),'minecraft:white_concrete':(224,226,220),'minecraft:light_gray_concrete':(172,179,178),'minecraft:light_gray_terracotta':(160,146,133),'minecraft:grass_block':(115,148,72),'minecraft:dirt':(126,104,80),'minecraft:stone':(122,124,122),'minecraft:stone_bricks':(142,145,143),'minecraft:smooth_stone':(177,179,175),'minecraft:gray_stained_glass':(98,129,137),'minecraft:black_concrete':(49,52,56),'minecraft:brick_stairs':(153,87,67),'minecraft:dark_oak_fence':(81,61,43),'minecraft:dark_oak_slab':(81,61,43),'minecraft:green_terracotta':(88,111,77),'minecraft:red_terracotta':(137,74,57),'minecraft:blue_terracotta':(81,94,112),'projectseele:city_rain_pipe':(126,136,133),'projectseele:city_rain_gutter':(126,136,133)}
                col=original_colours.get(name,palette.get(st,state_colour(name)[:3]));col=(114,78,42) if 'oak_door' in name or 'spruce_log' in name else (143,122,86) if '_sign' in name else (110,129,130) if 'store_door' in name or 'city_personnel_door' in name else col
                for bb in boxes:
                    xx,yy,zz,XX,YY,ZZ=bb
                    specs=[((1,0,0),[(XX,yy,zz),(XX,YY,zz),(XX,YY,ZZ),(XX,yy,ZZ)],.82),((-1,0,0),[(xx,yy,zz),(xx,yy,ZZ),(xx,YY,ZZ),(xx,YY,zz)],.78),((0,0,1),[(xx,yy,ZZ),(XX,yy,ZZ),(XX,YY,ZZ),(xx,YY,ZZ)],.86),((0,0,-1),[(xx,yy,zz),(xx,YY,zz),(XX,YY,zz),(XX,yy,zz)],.72),((0,1,0),[(xx,YY,zz),(xx,YY,ZZ),(XX,YY,ZZ),(XX,YY,zz)],1.)]
                    for normal,vertices,shade in specs:
                        mid=np.array(q)+np.array([(xx+XX)/2,(yy+YY)/2,(zz+ZZ)/2])
                        if np.dot(eye-mid,normal)<=0:continue
                        other=tuple(q[i]+normal[i] for i in range(3));otherst=cells.get(other)
                        if bb==[0,0,0,1,1,1] and otherst and 'glass' not in otherst and native.get(otherst)==[[0.,0.,0.,1.,1.,1.]]:continue
                        points=[project_standing(tuple(q[i]+v[i] for i in range(3))) for v in vertices]
                        if any(p is None for p in points):continue
                        if max(p[0] for p in points)<0 or min(p[0] for p in points)>1600 or max(p[1] for p in points)<0 or min(p[1] for p in points)>1100:continue
                        polys.append((sum(p[2] for p in points)/4,[(p[0],p[1]) for p in points],tuple(round(v*shade) for v in col)))
            for depth,points,colour in sorted(polys,reverse=True):draw.polygon(points,fill=colour)
            draw.rectangle((0,0,1600,42),fill=(230,237,235));draw.text((20,15),b['id']+' / '+mode+' / actual terrain + exact ghost / eye1.62m / OFFLINE',fill=(20,28,25))
            file=output/(b['id'].split('/')[-1]+'_'+mode+'.png');image.save(file);rendered.append(dict(path=str(file.resolve()),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),standing_eye=eye.tolist(),native_photo=False))
    shutil.copy2(Path(__file__),output/'producer_renderer.py')
    (output/'provenance.json').write_text(json.dumps(dict(world=str(WORLD),renderer_snapshot=str((output/'producer_renderer.py').resolve()),renderer_sha256=hashlib.sha256((output/'producer_renderer.py').read_bytes()).hexdigest(),source_patch_sha256=hashlib.sha256((a.plan/'forward.jsonl.gz').read_bytes()).hexdigest(),
        measured_bounds=[[x0,40,z0],[x1,220,z1]],column_status=dict(measured),retained_real_cells=len(cells),rendered=rendered,
        full_review_volume_non_air=full_volume_non_air,
        geometry_method='Full measured Y40..220 voxel review volume plus exact forward states, all six-neighbour exposed cells extracted before drawing. Includes actual overhangs/internal hollow sides and all deep cut/fill faces; no fixed ten-metre height skin. X/Z crop faces remain suppressed; Y40 is the explicit lower review crop. Cubic cell massing only, no shader/light/native-material claim.',
        world_written=False,native_photo=False,visual_passed=False),indent=2),'utf8')
    print('Real terrain ghost',a.plan.name,len(cells),'cells',dict(measured),flush=True)


if __name__=='__main__':main()
