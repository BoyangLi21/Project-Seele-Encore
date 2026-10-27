"""Transfer the accepted CC0 closed hand into Unit04; never install a package."""
import argparse
import copy
import json
import hashlib
import io
import zipfile
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from build_unit03_source_rig_r53 import matrix, posed, hand_pose
from eva_hand_rig_math_r45 import matrices, controls, contact_corrective
from scipy.spatial.transform import Rotation as R
from scipy.optimize import least_squares
from PIL import Image, ImageDraw, ImageFont

FLIP = np.array([-1., 1., 1.])


def unit(v):
    return v / np.linalg.norm(v)

def fit(contract, bones):
    report={}
    for side in ('l','r'):
        hand=contract['hands'][side];sign=1 if side=='l' else -1
        normal=unit(np.array(hand['palmar_normal_bind']));along=unit(np.array(hand['longitudinal_bind']))
        across=unit(np.cross(normal,along));basis=np.column_stack([across,along,normal])
        wrist=np.array(bones['hand_'+side]['pivot'])*[-1,1,1]/16
        results={}
        def points(digit, angles):
            joints=hand['digits'][digit]['joints'];rotations={}
            for i,j in enumerate(joints):
                v=angles[i]
                rotations[j['name']]=(R.from_quat(j['neutral_local_quaternion_xyzw'])*R.from_euler('xyz',[-v[0],sign*v[1],sign*v[2]],degrees=True)).as_matrix()
            cache={};result=[]
            for j in joints:
                transform=matrix(bones,j['name'],cache,rotations)@np.array(j['inverse_bind_column_major']).reshape(4,4).T
                result.append((transform@np.r_[j['head_bind'],1])[:3])
            result.append((transform@np.r_[joints[-1]['tip_bind'],1])[:3])
            return (np.array(result)-wrist)@basis
        for digit in ('index','middle','ring','little'):
            rest=points(digit,np.zeros((3,3)));base=rest[0]
            values=np.c_[[75,75,65],np.zeros((3,2))];results[digit]=points(digit,values)
            for j,value in zip(hand['digits'][digit]['joints'],values):
                contract['pose_controls']['fist']['bone_angles'][j['name']]=value.tolist()
            report[side+'/'+digit]=dict(angles=values[:,0].tolist(),tip_palm=results[digit][-1].tolist())
        # The thumb lies outside the folded four fingers, crossing from the
        # index side toward the middle finger instead of entering the palm.
        index=results['index'];middle=results['middle']
        goal=np.array([sign*-.06,.40,.25])
        ip=np.array([sign*.10,.40,.28])
        def thumb_values(a):return np.array([a[:3],[a[3],0,0],[a[4],0,0]])
        def thumb_error(a):
            pose=points('thumb',thumb_values(a))
            return np.r_[(pose[3]-goal)*8,(pose[2]-ip)*4,(a-[20,0,35,30,35])*.0003]
        solved=least_squares(thumb_error,[20,0,35,30,35],bounds=([-45,-80,-80,-25,-25],[85,80,80,100,85]),max_nfev=160)
        for j,value in zip(hand['digits']['thumb']['joints'],thumb_values(solved.x)):
            contract['pose_controls']['fist']['bone_angles'][j['name']]=value.tolist()
        report[side+'/thumb']=dict(angles=solved.x.tolist(),tip_palm=points('thumb',thumb_values(solved.x))[-1].tolist())
    return report

def skin_normals(mesh,bones,contract,name):
    part=mesh['parts'][name];skin=mesh['jointSkins'][name];raw=np.array(part['vertices']).reshape(-1,8)
    names=sorted(skin['influences']);weights=np.array([skin['influences'][n] for n in names]).T;cache={};rotations=hand_pose(contract,'fist') if contract else None
    transforms=[matrix(bones,n,cache,rotations)@np.array(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in names]
    quats=R.from_matrix(np.array(transforms)[:,:3,:3]).as_quat();signs=np.where(quats[weights.argmax(1)]@quats.T<0,-1,1);q=(weights*signs)@quats;q/=np.linalg.norm(q,axis=1)[:,None]
    return R.from_quat(q).apply(raw[:,5:8]*[-1,1,1])

def surface_normals(part,target):
    raw=np.array(part['vertices']).reshape(-1,8);source=(raw[:,:3]+part['pivot'])*[-1,1,1]/16
    def face(points):
        tri=points.reshape(-1,3,3);n=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)
    before=face(source);after=face(target);axis=np.cross(before,after);length=np.linalg.norm(axis,axis=1);angle=np.arctan2(length,np.sum(before*after,axis=1));rv=axis/np.maximum(length[:,None],1e-12)*angle[:,None]
    return R.from_rotvec(np.repeat(rv,3,axis=0)).apply(raw[:,5:8]*[-1,1,1])

def corrective(mesh, bones, contract, targets):
    current=posed(mesh,bones,hand_pose(contract,'fist'))
    geo={'minecraft:geometry':[{'bones':list(bones.values())}]}
    for side in ('l','r'):
        name='hand_'+side;skin=mesh['jointSkins'][name];target=targets[name];delta=((target-current[name])@matrix(bones,name,{},hand_pose(contract,'fist'))[:3,:3])*[-1,1,1]*16
        maximum=float(np.max(np.abs(delta)))
        if maximum>8:raise ValueError(('Source corrective exceeds finite native bound',side,maximum))
        ms=matrices(geo,contract,side,controls(contract,'fist',side));rotations={}
        for digit in contract['hands'][side]['digits'].values():
            for j in digit['joints']:
                n=j['name'];rotations[n]=R.from_matrix(ms[bones[n]['parent']][:3,:3].T@ms[n][:3,:3]).as_quat().tolist()
        normal_delta=(surface_normals(mesh['parts'][name],target)-skin_normals(mesh,bones,contract,name))*[-1,1,1]
        rows=np.c_[np.arange(len(delta)),delta,normal_delta]
        rows=rows[(np.linalg.norm(delta,axis=1)+np.linalg.norm(normal_delta,axis=1))>1e-9]
        skin['contactCorrectiveR45']=dict(activation_degrees=25,position_limit_model=float(np.ceil(maximum*10)/10+.1),local_quaternion_xyzw=rotations,
            vertex_index_position_normal_delta=rows.tolist(),source='Unit03 source-only fist corrective: source palm/wrist retained; four fingers curl toward palm; rigid knuckle armour; thumb outside the folded fingers. No source faces or UVs removed.')

def evaluated(mesh,bones,contract,rest=False):
    result=posed(mesh,bones,None if rest else hand_pose(contract,'fist'))
    if rest:return result
    geo={'minecraft:geometry':[{'bones':list(bones.values())}]}
    for side in ('l','r'):
        name='hand_'+side;ms=matrices(geo,contract,side,controls(contract,'fist',side))
        result[name]=contact_corrective(geo,mesh['jointSkins'][name],result[name],ms,name)
    return result

def preview(mesh, bones, contract, rows, destination, side='l', texture=None):
    import moderngl
    ctx = moderngl.create_standalone_context()
    ctx.enable(moderngl.DEPTH_TEST)
    program = ctx.program(vertex_shader='''#version 330
    in vec3 position;in vec3 normal;in vec3 color;out vec3 N;out vec3 C;
    void main(){gl_Position=vec4(position,1);N=normal;C=color;}
    ''', fragment_shader='''#version 330
    in vec3 N;in vec3 C;out vec4 frag;
    void main(){float k=.30+.65*abs(dot(normalize(N),normalize(vec3(-.35,.65,1))));frag=vec4(C*k,1);}
    ''')
    size = 600
    fb = ctx.simple_framebuffer((size, size));fb.use()
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    sheet = Image.new('RGB', (size * 3, size * len(rows)))
    hand = contract['hands'][side]
    wrist = np.asarray(bones['hand_' + side]['pivot']) * [-1, 1, 1] / 16
    up = -unit(np.asarray(hand['longitudinal_bind']))
    normal = np.asarray(hand['palmar_normal_bind']);normal = unit(normal-up*(normal@up))
    right = unit(np.cross(up, normal))
    rest = posed(mesh, bones)['hand_'+side]
    centre = (rest.min(0)+rest.max(0))*.5
    span = np.ptp(rest@np.array([right, up]).T, axis=0).max()*1.32
    for row, (label, controls) in enumerate(rows):
        shapes = evaluated(mesh,bones,controls,label=='source rest')
        for col, (view, direction) in enumerate([('palm', normal+right*.12), ('side', right), ('back', -normal+right*.12)]):
            direction = unit(direction);cr = unit(np.cross(up,direction));cu=np.cross(direction,cr)
            camera=np.array([cr,cu,direction]);fb.clear(.118,.145,.18,1,depth=1)
            for name,color in [('forearm_'+side,[.28,.33,.41]),('hand_'+side,[.64,.69,.78])]:
                ps=shapes[name];tri=ps.reshape(-1,3,3)
                normals=np.repeat(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),3,axis=0)
                normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
                projection=(ps-centre)@camera.T;projection[:,:2]*=1.7/span;projection[:,2]*=-.35
                colors=np.tile(color,(len(ps),1))
                if texture is not None:
                    uv=np.array(mesh['parts'][name]['vertices']).reshape(-1,8)[:,3:5]
                    h,w=texture.shape[:2]
                    colors=texture[np.clip((uv[:,1]*h).astype(int),0,h-1),np.clip((uv[:,0]*w).astype(int),0,w-1),:3]/255.
                data=np.c_[projection,normals@camera.T,colors].astype('f4')
                buffer=ctx.buffer(data.tobytes());vao=ctx.vertex_array(program,[(buffer,'3f 3f 3f','position','normal','color')]);vao.render();vao.release();buffer.release()
            image=Image.frombytes('RGB',(size,size),fb.read(components=3)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            draw=ImageDraw.Draw(image);draw.rectangle((0,0,size,42),fill=(30,37,46));draw.text((12,12),label+' / '+view,font=font,fill='white')
            draw.text((12,size-27),'Candidate mesh depth preview; not game capture',font=font,fill=(220,185,122))
            sheet.paste(image,(col*size,row*size))
    sheet.save(destination);fb.release();ctx.release()

def read(path):
    return json.loads(path.read_text('utf8'))


def points(part):
    return (np.array(part['vertices']).reshape(-1, 8)[:, :3]+part['pivot'])*FLIP/16


def continuous_source_hand_uv(raw, authored, source_part, texture):
    """Keep real charts inside source-hand colour texels, never interpolate atlas islands."""
    height,width=texture.shape[:2]
    source=np.array(source_part['vertices']).reshape(-1,3,8)[:,:,3:5]*[width,height]
    def swatch(desired):
        candidates=[]
        for triangle in source:
            centre=np.floor(triangle.mean(0))+.5
            matrix2=np.column_stack([triangle[1]-triangle[0],triangle[2]-triangle[0]])
            if abs(np.linalg.det(matrix2))<1e-8:continue
            corners=centre+np.array([[-.25,-.25],[-.25,.25],[.25,-.25],[.25,.25]])
            bary=(corners-triangle[0])@np.linalg.inv(matrix2).T
            if np.any(bary<0) or np.any(bary.sum(1)>1):continue
            x,y=centre.astype(int)
            if not (0<=x<width and 0<=y<height):continue
            color=texture[y,x]
            if color[3]!=255 or not (20<=color[0]<color[2]<=125):continue
            candidates.append((float(np.linalg.norm(color[:3]-np.array(desired))),centre,color))
        if not candidates:raise ValueError('No opaque blue source-hand swatch with an interior chart margin')
        _,centre,color=min(candidates,key=lambda row:row[0])
        return (centre-.25)/[width,height],np.array([.5/width,.5/height]),color[:3]
    plate_count=len(authored['plate_rest']);cuff_count=len(authored['bridge_rest'])
    skin_count=len(raw)-plate_count-cuff_count
    skin_chart=raw[:skin_count,3:5].copy()
    skin_chart=(skin_chart-skin_chart.min(0))/np.ptp(skin_chart,axis=0)
    # Every sleeve quad is an unfolded rectangle. Shared near/far endpoints
    # have distinct V, retaining the cuff's tangent even at a material seam.
    if cuff_count%6:raise ValueError('Unexpected cuff quad topology')
    cuff_chart=np.tile([[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]],(cuff_count//6,1))
    skin_min,skin_span,skin_color=swatch([42,51,72])
    plate_min,plate_span,plate_color=swatch([58,70,96])
    raw[:skin_count,3:5]=skin_min+skin_chart*skin_span
    if 'plate_uv' in authored:
        plate_chart=authored['plate_uv']
    else:
        # Preserve the accepted earlier shell topology. Its six projection
        # charts share positions within each chart and split only at seams.
        plate=authored['plate_rest'].reshape(-1,3,3)
        face=np.cross(plate[:,1]-plate[:,0],plate[:,2]-plate[:,0])
        axis=np.argmax(np.abs(face),axis=1)
        plate_chart=np.empty((len(plate),3,2))
        for k in range(3):
            selected=axis==k;chart=plate[selected][:,:,[j for j in range(3) if j!=k]]
            lo=chart.min(axis=(0,1));span=np.ptp(chart,axis=(0,1))
            plate_chart[selected]=(chart-lo)/span
        plate_chart=plate_chart.reshape(-1,2)
    raw[skin_count:skin_count+plate_count,3:5]=plate_min+plate_chart*plate_span
    raw[skin_count+plate_count:,3:5]=skin_min+cuff_chart*skin_span
    uv=raw[:,3:5].astype(np.float32).reshape(-1,3,2)
    edges=uv[:,1:]-uv[:,:1]
    determinant=edges[:,0,0]*edges[:,1,1]-edges[:,0,1]*edges[:,1,0]
    if np.any(np.abs(determinant)<=1e-18):raise ValueError('Degenerate float32 hand UV chart')
    print('Unit04 source-hand material RGB',skin_color.tolist(),plate_color.tolist(),'; all UV triangles nondegenerate')


def basis(hand):
    y=unit(np.array(hand['longitudinal_bind']))
    n=unit(np.array(hand['palmar_normal_bind']));n=unit(n-y*(n@y))
    return np.column_stack([unit(np.cross(n,y)),y,n])


def normals(points):
    tri=points.reshape(-1,3,3);face=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
    _,ix=np.unique(np.round(points,8),axis=0,return_inverse=True)
    total=np.zeros((ix.max()+1,3));np.add.at(total,ix,np.repeat(face,3,axis=0))
    n=total[ix];return n/np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12)


def global_fit(donor_hand, source_hand, donor_wrist, source_wrist):
    d=basis(donor_hand);s=basis(source_hand)
    # Preserve the donor's closed-fist proportions, matching the Unit03 hand length.
    dt=np.array(donor_hand['digits']['middle']['joints'][-1]['tip_bind'])
    st=np.array(source_hand['digits']['middle']['joints'][-1]['tip_bind'])
    scale=np.linalg.norm(st-source_wrist)/np.linalg.norm(dt-donor_wrist)
    return s@d.T*scale


def neutral_fit(point, donor_skin, donor_hand, source_hand, donor_wrist, source_wrist, global_matrix):
    """Continuous weighted segment fits keep the existing Unit04 joints usable."""
    result=np.zeros_like(point);normal_d=np.array(donor_hand['palmar_normal_bind']);normal_s=np.array(source_hand['palmar_normal_bind'])
    radial=np.cbrt(abs(np.linalg.det(global_matrix)))
    for name,values in donor_skin['influences'].items():
        weight=np.array(values)
        matched=next((digit for digit in source_hand['digits'] if '_'+digit+'_' in name),None)
        if matched:
            j=int(name.rsplit('_',1)[1])-1
            dj=donor_hand['digits'][matched]['joints'][j];sj=source_hand['digits'][matched]['joints'][j]
            dh=np.array(dj['head_bind']);dt=np.array(dj['tip_bind']);sh=np.array(sj['head_bind']);st=np.array(sj['tip_bind'])
            def frame(head,tail,n):
                y=unit(tail-head);x=unit(np.cross(n,y));return np.column_stack([x,y,np.cross(x,y)])
            a=frame(sh,st,normal_s)@np.diag([radial,np.linalg.norm(st-sh)/np.linalg.norm(dt-dh),radial])@frame(dh,dt,normal_d).T
            moved=(point-dh)@a.T+sh
        else:
            moved=(point-donor_wrist)@global_matrix.T+source_wrist
        result+=moved*weight[:,None]
    return result


def semantic_feature(point, hand, digit, wrist):
    frame=basis(hand)
    if digit=='palm':
        length=np.linalg.norm(np.array(hand['digits']['middle']['joints'][0]['head_bind'])-wrist)
        return (point-wrist)@frame/length
    joints=hand['digits'][digit]['joints'];chain=np.array([j['head_bind'] for j in joints]+[joints[-1]['tip_bind']])
    options=[]
    for i in range(3):
        delta=chain[i+1]-chain[i];t=np.clip((point-chain[i])@delta/(delta@delta),0,1);offset=point-chain[i]-t[:,None]*delta
        options.append((np.linalg.norm(offset,axis=1),np.c_[i+t,offset@frame[:,0]*4,offset@frame[:,2]*4]))
    k=np.argmin(np.array([x[0] for x in options]),axis=0)
    return np.array([x[1] for x in options])[k,np.arange(len(point))]


def low_transfer(source_part,source_skin,donor_part,donor_skin,source_hand,donor_hand,sw,dw,closed):
    source=points(source_part);donor=points(donor_part);target=source.copy()
    def labels(skin):
        names=list(skin['influences']);main=np.array(names)[np.array(list(skin['influences'].values())).T.argmax(1)]
        return np.array([next((d for d in source_hand['digits'] if '_'+d+'_' in n),'palm') for n in main])
    sl=labels(source_skin);dl=labels(donor_skin)
    for digit in ['palm',*source_hand['digits']]:
        source_ids=np.flatnonzero(sl==digit);donor_ids=np.flatnonzero(dl==digit)
        if not len(source_ids) or not len(donor_ids):continue
        a=semantic_feature(source[source_ids],source_hand,digit,sw);b=semantic_feature(donor[donor_ids],donor_hand,digit,dw)
        distance,index=cKDTree(b).query(a,k=4);weight=1/np.maximum(distance,.00001)**2;weight/=weight.sum(1)[:,None]
        target[source_ids]=(closed[donor_ids[index]]*weight[:,:,None]).sum(1)
    return target


def validate_joint_weights(mesh):
    # Match LocalTriangleMeshLayer.authoredJointSkins, including float conversion.
    for name,skin in mesh['jointSkins'].items():
        count=len(mesh['parts'][name]['vertices'])//8
        sums=np.zeros(count,dtype=np.float32)
        for bone,values in skin['influences'].items():
            weights=np.asarray(values,dtype=np.float32)
            if weights.shape!=(count,) or not np.all(np.isfinite(weights)&(weights>=0)&(weights<=1)):
                raise ValueError(('Invalid joint influence',name,bone))
            sums+=weights
        if np.any(np.abs(sums-np.float32(1))>np.float32(.0002)):
            raise ValueError(('Joint influences must sum to one',name))


def package(args,original,mesh,geo,bones,contract,targets):
    assets=args.out/'resources/assets/projectseele';source=args.source/'resources/assets/projectseele'
    for name in original['parts']:
        if name.startswith('hand_'):continue
        if original['parts'][name]!=mesh['parts'][name] or original['jointSkins'][name]!=mesh['jointSkins'][name]:
            raise ValueError('A non-hand source part changed')
    hand_mesh=read(source/'mesh/eva_un01_anatomical_hands_r53.mesh.json')
    archive=args.out/'original-source-hands';archive.mkdir(exist_ok=True)
    (archive/'eva_un01_anatomical_hands_r53.mesh.json').write_text(json.dumps(hand_mesh,separators=(',',':')),'utf8')
    checks={};actual=evaluated(mesh,bones,contract)
    for side in ('l','r'):
        name='hand_'+side;hand_mesh['parts'][name]=mesh['parts'][name];hand_mesh['jointSkins'][name]=mesh['jointSkins'][name]
        correction=mesh['jointSkins'][name]['contactCorrectiveR45'];active=[]
        for pose in contract['pose_controls']:
            ms=matrices(geo,contract,side,controls(contract,pose,side));distance=0
            for n,q in correction['local_quaternion_xyzw'].items():
                current=R.from_matrix(ms[bones[n]['parent']][:3,:3].T@ms[n][:3,:3]).as_quat()
                distance=max(distance,2*np.arccos(np.clip(abs(current@q),0,1)))
            if distance<np.radians(correction['activation_degrees'])-1e-6:active.append(pose)
        if active!=['fist']:raise ValueError(('Unexpected corrective activation',side,active))
        error=float(np.max(np.abs(actual[name]-targets[name])))
        if error>1e-7:raise ValueError('Native-formula target mismatch')
        checks[side]={'active_controls':active,'target_error_native':error,'position_limit_model':correction['position_limit_model']}
        correction['source']='CC0 MakeHuman complete natural fist, transferred into Unit04 palm frame; source skeleton retained and forearm-owned cuff seated in the source forearm. Original low-face hand archived separately.'
    hand_mesh['triangleCount']=sum(len(p['vertices'])//24 for p in hand_mesh['parts'].values())
    hand_mesh['source']='CC0 MakeHuman hand adapted to Unit04 source joints; Unit03 original atlas sampled for glove colour'
    mesh['source']='Original Unit03 non-hand body and dorsal mechanism preserved; independent CC0 MakeHuman hands'
    def write(relative,value):
        path=assets/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,separators=(',',':')),'utf8');return path
    paths=[write('mesh/eva_un01.mesh.json',mesh),write('mesh/eva_un01_anatomical_hands_r53.mesh.json',hand_mesh),write('hand_rigs/unit04/hand_rig_contract.json',contract)]
    for path in paths[:2]:validate_joint_weights(read(path))
    manifest=read(source/'eva/source_surface_r53.json');model=manifest['models']['eva_un01']
    model['source_triangles']=original['triangleCount']-522;model['added_triangles']=hand_mesh['triangleCount'];model['triangles']=mesh['triangleCount']
    # Existing resource binding required by the loader; no comparison receipt.
    model['resources']['mesh']=hashlib.sha256(paths[0].read_bytes()).hexdigest()
    paths.append(write('eva/source_surface_r53.json',manifest))
    with zipfile.ZipFile(args.out/'unit04-natural-fist-resources.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,path.relative_to(args.out/'resources').as_posix())
    (args.out/'INSTALL.json').write_text(json.dumps({'resource_overlay':str(args.out/'unit04-natural-fist-resources.zip'),'files':[p.relative_to(args.out/'resources').as_posix() for p in paths],'manifest_merge':'Replace only models.eva_un01 with the supplied entry. Retain all other current models.','original_hand_archive':str(archive),'source_body_faces_preserved':original['triangleCount']-522,'new_cc0_hand_faces':hand_mesh['triangleCount'],'scope':'Only UN01/rig4 hands replaced. No skeleton, non-hand body, texture, action library, Java or world changes.','native_installed':False,'hands':checks},indent=2),'utf8')


def main():
    parser=argparse.ArgumentParser(__doc__)
    for key in ('source','jar','donor','sculpt','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--compare-source-topology',action='store_true',help='Optional rejected low-face comparison; never packaged')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    assets=args.source/'resources/assets/projectseele'
    original=read(assets/'mesh/eva_un01.mesh.json');geo=read(assets/'geo/eva_un01.geo.json');contract=read(assets/'hand_rigs/unit04/hand_rig_contract.json')
    bones={b['name']:b for b in geo['minecraft:geometry'][0]['bones']}
    donor=read(args.donor)
    with zipfile.ZipFile(args.jar) as archive:
        donor_geo=json.loads(archive.read('assets/projectseele/geo/eva_unit01.geo.json'))
        donor_contract=json.loads(archive.read('assets/projectseele/hand_rigs/unit01/hand_rig_contract.json'))
        source_texture=np.array(Image.open(io.BytesIO(archive.read('assets/projectseele/textures/entity/eva_un01.png'))).convert('RGBA'))
    donor_bones={b['name']:b for b in donor_geo['minecraft:geometry'][0]['bones']}
    for hand in contract['hands'].values():
        for digit,data in hand['digits'].items():
            for i,j in enumerate(data['joints']):
                j['anatomical_limits_degrees'][0]=[-25,100 if i==1 else 85]
                if digit=='thumb' and i==0:j['anatomical_limits_degrees']=[[-45,85],[-80,80],[-80,80]]
    fit(contract,bones)
    low=copy.deepcopy(original);high=copy.deepcopy(original);low_targets={};high_targets={}
    for side in ('l','r'):
        name='hand_'+side;sh=contract['hands'][side];dh=donor_contract['hands'][side]
        sw=np.array(bones[name]['pivot'])*FLIP/16;dw=np.array(donor_bones[name]['pivot'])*FLIP/16
        a=global_fit(dh,sh,dw,sw);authored=np.load(args.sculpt/f'natural_fist_{side}.npz')
        closed=(authored['target']-dw)@a.T+sw
        if args.compare_source_topology:
            low_targets[name]=low_transfer(original['parts'][name],original['jointSkins'][name],donor['parts'][name],donor['jointSkins'][name],sh,dh,sw,dw,closed)
        raw=np.array(donor['parts'][name]['vertices']).reshape(-1,8);rest=neutral_fit(points(donor['parts'][name]),donor['jointSkins'][name],dh,sh,dw,sw,a)
        far=np.array(donor['jointSkins'][name]['influences'].get('forearm_'+side,np.zeros(len(rest))))>.5
        elbow=np.array(bones['forearm_'+side]['pivot'])*FLIP/16;axis=unit(sw-elbow)
        radial=rest[far]-rest[far].mean(0);radial-=np.outer(radial@axis,axis)
        rest[far]=sw-axis*.18+radial/np.linalg.norm(radial,axis=1)[:,None]*.09
        closed[far]=rest[far]
        raw[:,:3]=rest*FLIP*16-bones[name]['pivot'];raw[:,5:8]=normals(rest)*FLIP
        continuous_source_hand_uv(raw,authored,original['parts'][name],source_texture)
        high['parts'][name]={'pivot':bones[name]['pivot'],'vertices':raw.ravel().tolist()}
        weights={}
        for key,value in donor['jointSkins'][name]['influences'].items():
            target_key=key if key in bones else name
            weights[target_key]=weights.get(target_key,np.zeros(len(rest)))+np.array(value)
        # Donor decimal rounding can make merged cup+hand weights 1.0000001.
        # Normalize after palette merging, before skinning and corrective authoring.
        merged=np.stack(list(weights.values()))
        totals=merged.sum(axis=0)
        if not np.all(np.isfinite(merged)&(merged>=0)) or np.any(totals<=0):
            raise ValueError(('Invalid donor influences',name))
        weights={n:w/totals for n,w in weights.items()}
        high['jointSkins'][name]={'influences':{n:w.tolist() for n,w in weights.items()},'inverseBindColumnMajor':{n:np.linalg.inv(matrix(bones,n,{})).T.ravel().tolist() for n in weights}}
        high_targets[name]=closed
    variants=[(high,high_targets,'cc0-hand-replacement')]
    if args.compare_source_topology:variants.insert(0,(low,low_targets,'source-topology-transfer'))
    for mesh,targets,label in variants:
        current=posed(mesh,bones,hand_pose(contract,'fist'))
        for side in ('l','r'):
            n='hand_'+side
            if label=='cc0-hand-replacement':
                far=np.array(mesh['jointSkins'][n]['influences'].get('forearm_'+side,np.zeros(len(targets[n]))))>.5
                targets[n][far]=current[n][far]
        corrective(mesh,bones,contract,targets)
        mesh['triangleCount']=sum(len(p['vertices'])//24 for p in mesh['parts'].values())
        (args.out/(label+'.mesh.json')).write_text(json.dumps(mesh,separators=(',',':')),'utf8')
        preview(mesh,bones,contract,[(label,contract)],args.out/(label+'-left.png'))
        preview(mesh,bones,contract,[(label,contract)],args.out/(label+'-right.png'),side='r')
    (args.out/'hand_rig_contract.json').write_text(json.dumps(contract,separators=(',',':')),'utf8')
    preview(high,bones,contract,[('source rest',contract)],args.out/'cc0-hand-neutral-left.png')
    preview(high,bones,contract,[('source blue hand material',contract)],args.out/'cc0-hand-material-left.png',texture=source_texture)
    preview(high,bones,contract,[('source blue hand material',contract)],args.out/'cc0-hand-material-right.png',side='r',texture=source_texture)
    package(args,original,high,geo,bones,contract,high_targets)
    print('Packaged independent Unit04 CC0 natural hands; original source hands archived; non-hand body unchanged. No install.')


if __name__=='__main__':
    main()
