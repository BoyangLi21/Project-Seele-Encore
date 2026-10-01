"""Retopologize and bind private Angel test meshes; no third-party outputs enter src/.

Source rest poses are measured explicitly. Weights depend only on rest position,
so duplicated UV seams receive identical deformation.
"""
from pathlib import Path
import argparse,json,math,hashlib
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'external-assets/incoming/angels_r10'
PACK=ROOT/'run/resourcepacks/eva_real_model/assets/projectseele';OUT=ROOT/'artifacts/first_battle_world_r10/models'
BINDING_VERSION='r44-topological-shell-and-socket-v5'

def smooth_window(value,begin,end):
    t=float(np.clip((value-begin)/max(end-begin,1e-8),0,1));return t*t*(3-2*t)

def obj(path):
    v=[];uv=[];normal=[];faces=[];materials=[];material='';textures={}
    for line in path.read_text(encoding='utf8').splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='v':v.append(list(map(float,parts[1:4])))
        elif parts[0]=='vt':uv.append(list(map(float,parts[1:3])))
        elif parts[0]=='vn':normal.append(list(map(float,parts[1:4])))
        elif parts[0]=='usemtl':material=line[7:].strip()
        elif parts[0]=='f':
            points=[tuple(int(k)-1 for k in q.split('/')) for q in parts[1:]]
            for i in range(1,len(points)-1):faces.append([points[0],points[i],points[i+1]]);materials.append(material)
    for mtl in path.parent.glob('*.mtl'):
        key=''
        for line in mtl.read_text(encoding='utf8').splitlines():
            if line.startswith('newmtl '):key=line[7:].strip()
            elif line.startswith('map_Kd '):textures[key]=path.parent/line[7:].strip()
    return np.array(v),np.array(uv),np.array(normal),faces,materials,textures

def humanoid(name):
    if name=='sachiel':
        joints=dict(root=[0,0,0],torso_lower=[0,7.5,0],torso_upper=[0,11.2,0],neck=[0,13.5,.45],head=[0,14.6,.8],
                    arm=[3.35,14.35,0],forearm=[3.78,10.15,.2],hand=[3.78,10.15,3.55],
                    leg=[1.3,7.3,0],shin=[1.4,3.9,-.32],foot=[1.4,.65,.2])
        tips=dict(head=[0,15.9,1.3],hand=[3.78,10.15,5.35],foot=[1.4,.1,1.4])
    else:
        joints=dict(root=[0,0,0],torso_lower=[0,7.8,0],torso_upper=[0,11.2,0],neck=[0,13.3,.4],head=[0,14.5,1],
                    arm=[3,13.5,0],forearm=[7.2,15.2,.1],hand=[11.5,17.6,.1],
                    leg=[1.5,7.5,0],shin=[2.5,3.7,-.2],foot=[3.2,.5,.6])
        tips=dict(head=[0,16,1.6],hand=[12.9,18.4,.3],foot=[3.4,.1,1.8])
    bones={};segments={}
    def add(n,parent,p,end):bones[n]=dict(parent=parent,pivot=np.array(p,float));segments[n]=(np.array(p,float),np.array(end,float))
    for n,parent,end in [('root',None,'torso_lower'),('torso_lower','root','torso_upper'),('torso_upper','torso_lower','neck'),('neck','torso_upper','head')]:add(n,parent,joints[n],joints[end])
    add('head','neck',joints['head'],tips['head'])
    for side,sign in [('l',1),('r',-1)]:
        def p(n):return np.array(joints.get(n,tips.get(n)),float)*[sign,1,1]
        for part,parent,end in [('arm','torso_upper','forearm'),('forearm','arm_'+side,'hand'),('hand','forearm_'+side,None),('leg','torso_lower','shin'),('shin','leg_'+side,'foot'),('foot','shin_'+side,None)]:
            add(part+'_'+side,parent,p(part),p(end) if end else np.array(tips[part])*[sign,1,1])
    def allowed(point):
        # Rest-space bone distances own a continuous anatomical field. Hard
        # x2.35/y7.9 candidate changes split a single .33m shoulder edge into
        # neck/head versus upper-arm ownership and made it10.39m in native.
        x,y,z=point;pelvis=joints['torso_lower'][1];chest=joints['torso_upper'][1];neck=joints['neck'][1];head=joints['head'][1];span=chest-pelvis;shoulder=joints['arm'][0]
        central=1-smooth_window(abs(x),shoulder*.30,shoulder*.60)
        result=dict(torso_lower=smooth_window(y,pelvis-2.8,pelvis-.6)*(1-smooth_window(y,chest-span*.2,chest+span*.2)),
                    torso_upper=smooth_window(y,chest-span*.6,chest-span*.1)*(1-smooth_window(y,head+.3,head+1.0)),
                    neck=central*smooth_window(y,neck-1.4,neck-.2)*(1-smooth_window(y,head,head+.8)),
                    head=central*smooth_window(y,neck-.8,head-.4))
        for side,sign in(('l',1),('r',-1)):
            elbow=np.asarray(joints['forearm'],float)*[sign,1,1];wrist=np.asarray(joints['hand'],float)*[sign,1,1];axis=wrist-elbow;along=float((np.asarray(point)-elbow)@axis/max(axis@axis,1e-8))
            arm=smooth_window(sign*x,shoulder*.4,shoulder*.85)*smooth_window(y,min(joints[n][1]for n in('arm','forearm','hand'))-3.8,min(joints[n][1]for n in('arm','forearm','hand'))-1.)
            result['arm_'+side]=arm*(1-smooth_window(along,.1,.7))
            result['forearm_'+side]=arm*smooth_window(along,-.35,.15)*(1-smooth_window(along,1.,1.5))
            result['hand_'+side]=arm*smooth_window(along,.6,1.)
            limb=smooth_window(sign*x,-.25,.5);hip=joints['leg'][1];knee=joints['shin'][1];ankle=joints['foot'][1]
            result['leg_'+side]=limb*smooth_window(y,knee-.7,knee+.6)*(1-smooth_window(y,hip+.2,hip+1.2))
            result['shin_'+side]=limb*(1-smooth_window(y,knee+.3,knee+1.3))
            result['foot_'+side]=limb*(1-smooth_window(y,ankle+.6,ankle+1.8))
        return result
    return bones,segments,allowed

def creature(name):
    bones={'root':dict(parent=None,pivot=np.zeros(3))};segments={}
    def add(n,parent,p,end):bones[n]=dict(parent=parent,pivot=np.array(p,float));segments[n]=(np.array(p,float),np.array(end,float))
    if name=='shamshel':
        add('body','root',[0,8,0],[0,13.4,0]);add('head','body',[0,13.4,0],[0,16.4,1.7])
        for i in range(4):add('tail_'+str(i),'body' if i==0 else 'tail_'+str(i-1),[0,9-i*2.3,0],[0,6.7-i*2.3,0])
        for side,sign in [('l',1),('r',-1)]:
            ps=np.array([[4.45,13.3,1],[5.15,10.4,2.5],[5.4,7.5,4.5],[5.2,4.6,5.8],[4.9,1.7,6.8]])*[sign,1,1]
            for i in range(4):add('whip_'+side+'_'+str(i),'body' if i==0 else 'whip_'+side+'_'+str(i-1),ps[i],ps[i+1])
        def allowed(p):
            x,y,z=p;central=1-smooth_window(abs(x),2.,3.8);result={'body':1.,'head':central*smooth_window(y,11.,13.5)}
            for i in range(4):result['tail_'+str(i)]=central
            for side,sign in(('l',1),('r',-1)):
                for i in range(4):result['whip_'+side+'_'+str(i)]=smooth_window(sign*x,1.8,4.)
            return result
    else:
        add('body','root',[0,5.8,0],[0,13,0]);add('head','body',[0,13,0],[0,16.8,-.2])
        for side,sign in [('l',1),('r',-1)]:add('paper_'+side,'body',[3.7*sign,14,-.7],[3.7*sign,9.1,-.7])
        def allowed(p):return ['body','head']
    return bones,segments,allowed

def distance(p,a,b):
    d=b-a;t=np.clip((p-a)@d/max(d@d,1e-8),0,1);return float(np.linalg.norm(p-a-t*d))
def weights(point,bones,segments,allowed):
    participation=allowed(point);candidates=list(participation);prior=np.array([participation[n]for n in candidates])if isinstance(participation,dict)else np.ones(len(candidates));d=np.array([distance(point,*segments[n]) for n in candidates]);score=prior/np.maximum(d,.12)**4
    # A plain top4 cutoff replaces a finite fourth weight when ranks cross.
    # Subtract the continuous fifth order statistic first: both crossing
    # weights become zero at that boundary, with at most four active owners.
    threshold=float(np.partition(score,-5)[-5])if len(score)>4 else 0.
    compact=np.maximum(score-threshold,0);active=np.flatnonzero(compact>0)
    if not len(active):raise ValueError('Anatomical weight field has no unique active support')
    identity={n:i for i,n in enumerate(bones)};values=[(identity[candidates[i]],float(compact[i]))for i in active];total=sum(w for i,w in values)
    values=sorted(((i,round(w/total,7))for i,w in values),key=lambda x:(-x[1],x[0]));values=[(i,w)for i,w in values if w>0]
    assert 0<len(values)<=4
    # Quantization is deterministic. Put its tiny residual on the canonical
    # first positive owner, then pad zeros with that same valid reference.
    values[0]=(values[0][0],round(values[0][1]+1-sum(w for i,w in values),7));values.sort(key=lambda x:(-x[1],x[0]))
    return [i for i,w in values],[w for i,w in values]

def sachiel_anatomical_parts(vertices,faces,materials):
    """The detached small face is head hardware; the shared back is body skin.

    A distance field cannot distinguish these overlapping rest-space volumes.
    Keep original face ancestry so UV seams cannot silently change ownership.
    """
    parent=list(range(len(vertices)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for face,material in zip(faces,materials):
        if material.startswith('6b823'):continue
        for point in face[1:]:parent[find(point[0])]=find(face[0][0])
    groups={}
    for i,(face,material)in enumerate(zip(faces,materials)):
        if not material.startswith('6b823'):groups.setdefault(find(face[0][0]),[]).append(i)
    main=max(groups,key=lambda k:len(groups[k]));roles={};report=[]
    for group,indices in groups.items():
        points=vertices[np.unique([p[0]for i in indices for p in faces[i]])];lo=points.min(0);hi=points.max(0)
        role='articulated-detail'
        if group==main:role='continuous-body-skin'
        elif max(abs(lo[0]),abs(hi[0]))<.6 and lo[1]>13.2 and hi[1]<16.1 and lo[2]>.1:role='rigid-face-hardware'
        for i in indices:roles[i]=role
        report.append(dict(component=group,faces=len(indices),source_faces=indices,bounds=[lo.tolist(),hi.tolist()],role=role))
    # UV shells supply the original sculpted thorax and upper-arm boundaries.
    # Mirrored halves share UV indices, so side ownership still uses the
    # original face's side; no source triangle crosses that centre plane.
    for material in sorted(set(materials)):
        uv_parent={p[1]:p[1]for face,m in zip(faces,materials)if m==material for p in face}
        def uv_find(i):
            while uv_parent[i]!=i:uv_parent[i]=uv_parent[uv_parent[i]];i=uv_parent[i]
            return i
        for face,m in zip(faces,materials):
            if m==material:
                for p in face[1:]:uv_parent[uv_find(p[1])]=uv_find(face[0][1])
        shells={}
        for i,(face,m)in enumerate(zip(faces,materials)):
            if m==material:shells.setdefault(uv_find(face[0][1]),[]).append(i)
        for shell,indices in shells.items():
            # These identities are recorded against the pinned original OBJ
            # in source_part_topology.json; spatial windows are insufficient.
            role=''
            if material.startswith('cefa')and shell in(689,721,800,831):role='rigid-thorax-shell'
            elif material.startswith('72cb')and shell==158:role='rigid-thorax-shell'
            elif material.startswith('72cb')and shell in(182,193):role='rigid-upper-arm-shell'
            if role:
                for i in indices:
                    if role=='rigid-upper-arm-shell':
                        x=vertices[[p[0]for p in faces[i]],0];assert x.min()*x.max()>0
                        roles[i]=role+('_l'if x.mean()>0 else'_r')
                    else:roles[i]=role
                report.append(dict(material=material,uv_shell=shell,source_faces=indices,faces=len(indices),role=role))
    return roles,report

def sachiel_socket_surfaces(material,uv):
    """Dark underlapping joint volumes beneath the preserved rigid caps."""
    result=[]
    for sign in(1,-1):
        centre=np.array([3.35*sign,14.35,0.]);radius=np.array([.945,1.49,.79]);points=[];normals=[]
        for latitude in range(13):
            phi=math.pi*latitude/12
            for longitude in range(24):
                theta=2*math.pi*longitude/24;unit=np.array([math.sin(phi)*math.cos(theta),math.cos(phi),math.sin(phi)*math.sin(theta)]);points.append(centre+radius*unit);normal=unit/radius;normals.append(normal/np.linalg.norm(normal))
        points=np.array(points);normals=np.array(normals)
        for latitude in range(12):
            for longitude in range(24):
                a=latitude*24+longitude;b=latitude*24+(longitude+1)%24;c=(latitude+1)*24+longitude;d=(latitude+1)*24+(longitude+1)%24
                for ids in((a,c,b),(b,c,d)):
                    p=points[list(ids)];n=normals[list(ids)]
                    if np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))<1e-8:continue
                    if np.dot(np.cross(p[1]-p[0],p[2]-p[0]),p.mean(0)-centre)<0:p=p[[0,2,1]];n=n[[0,2,1]]
                    result.append((p,n,np.tile(uv,(3,1)),material,'torso_upper','authored-underlapping-shoulder-socket'))
    return result

def build(name,path=None):
    files=list((SOURCE/name).rglob('*.obj'))
    if name=='israfel':files=[p for p in files if 'Combined' in p.name]
    path=path or files[0];v,uv,normals,faces,mats,textures=obj(path)
    bones,segments,allowed=humanoid(name) if name in ('sachiel','israfel') else creature(name)
    chosen=[];excluded=set();left_strip=set();part_roles={};anatomical_parts=[]
    if name=='sachiel':part_roles,anatomical_parts=sachiel_anatomical_parts(v,faces,mats)
    if name=='zeruel':
        parent=list(range(len(v)))
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for face in faces:
            for point in face[1:]:parent[find(point[0])]=find(face[0][0])
        groups={}
        for i,face in enumerate(faces):groups.setdefault(find(face[0][0]),[]).append(i)
        for group in groups.values():
            pts=v[[k[0] for i in group for k in faces[i]]]
            if pts[:,1].min()<0:excluded.update(group)
            elif len(group)==50 and pts[:,0].max()< -2.7:left_strip.update(group)
        assert len(excluded)==50 and len(left_strip)==50,'Source paper-arm topology changed'
    for face_index,(face,mat) in enumerate(zip(faces,mats)):
        if name=='sachiel' and mat.startswith('6b823'):continue
        points=v[[i[0] for i in face]].copy();ns=normals[[i[2] for i in face]].copy();tex=uv[[i[1] for i in face]].copy();rigid=None
        if face_index in excluded:
            # Replace the exported fully extended right strip with the mirrored,
            # folded left strip below. It is a pose correction, not body scaling.
            continue
        if face_index in left_strip:rigid='paper_r'
        chosen.append((points,ns,tex,mat,rigid,part_roles.get(face_index,'continuous-anatomical-field')))
    if name=='zeruel':
        strips=[r for r in chosen if r[4]=='paper_r']
        chosen=[r for r in chosen if r[4]!='paper_l']
        for points,ns,tex,mat,_,role in strips:chosen.append((points[[0,2,1]]*[-1,1,1],ns[[0,2,1]]*[-1,1,1],tex[[0,2,1]],mat,'paper_l',role))
    if name=='sachiel':
        material=next(m for m in mats if m.startswith('72cb'));image=np.asarray(Image.open(textures[material]).convert('RGB'));at=np.unravel_index(np.mean(image,axis=2).argmin(),image.shape[:2]);sample=np.array([(at[1]+.5)/image.shape[1],1-(at[0]+.5)/image.shape[0]])
        chosen.extend(sachiel_socket_surfaces(material,sample))
    used=sorted({r[3] for r in chosen});cols=2;rows=math.ceil(len(used)/cols);tile=384;atlas=Image.new('RGBA',(cols*tile,rows*tile),(0,0,0,255))
    for i,mat in enumerate(used):
        picture=Image.open(textures[mat]).convert('RGBA').resize((128,128),Image.Resampling.LANCZOS)
        for dz in range(3):
            for dx in range(3):atlas.paste(picture,((i%cols)*tile+dx*128,(i//cols)*tile+dz*128))
    allp=np.concatenate([r[0] for r in chosen]);floor=allp[:,1].min()
    body_points=allp[abs(allp[:,0])<3.0] if name=='israfel' else allp
    height=body_points[:,1].max()-floor;scale=192/height
    vertices=[];ids=[];ws=[]
    for points,ns,tex,mat,rigid,part_role in chosen:
        # One subdivision supplies enough deformation samples for smooth joints.
        pp=list(points);nn=list(ns);tt=list(tex)
        for a,b in [(0,1),(1,2),(2,0)]:
            mid=(points[a]+points[b])/2;curved=mid-.175*(ns[a]*np.dot(mid-points[a],ns[a])+ns[b]*np.dot(mid-points[b],ns[b]));pp.append(curved)
            normal=ns[a]+ns[b];nn.append(normal/max(np.linalg.norm(normal),1e-8));tt.append((tex[a]+tex[b])/2)
        for tri in [(0,3,5),(3,1,4),(5,4,2),(3,4,5)]:
            for k in tri:
                p=np.asarray(pp[k]);n=np.asarray(nn[k]);u,t=np.asarray(tt[k]);assert -1<=u<=2 and -1<=t<=2
                mi=used.index(mat);u=(mi%cols+(u+1)/3)/cols;t=(mi//cols+(2-t)/3)/rows
                q=(p-[0,floor,0])*scale*[1,1,-1];normal=n*[1,1,-1]
                if part_role=='rigid-face-hardware':rigid_owner='head'
                elif part_role=='rigid-thorax-shell':rigid_owner='torso_upper'
                elif part_role.startswith('rigid-upper-arm-shell_'):rigid_owner='arm_'+part_role[-1]
                else:rigid_owner=rigid
                def component_allowed(point):
                    participation=allowed(point)
                    if part_role=='continuous-body-skin':
                        participation=dict(participation);participation['head']=participation['neck']=0.
                        # The dark upper back remains a thorax surface above
                        # the small detached face's skull height.
                        participation['torso_upper']=smooth_window(point[1],joints_chest-2.,joints_chest-.5)
                    return participation
                joints_chest=segments['torso_upper'][0][1]if name=='sachiel'else 0.
                vertices.extend([*q,u,t,*normal]);bi,bw=([list(bones).index(rigid_owner)],[1.]) if rigid_owner else weights(p,bones,segments,component_allowed)
                ids.extend((bi+[bi[0]]*4)[:4]);ws.extend((bw+[0]*4)[:4])
    body_bones=[]
    for n,b in bones.items():
        q=(b['pivot']-[0,floor,0])*scale*[1,1,-1]
        body_bones.append(dict(name=n,pivot=np.round(q,6).tolist(),**({'parent':b['parent']} if b['parent'] else {})))
    mesh=dict(format='weighted_angel_r10',stride=8,parts={'root':dict(pivot=[0,0,0],vertices=np.round(vertices,7).tolist())},
              skin=dict(bones=list(bones),indices=ids,weights=np.round(ws,7).tolist(),binding_version=BINDING_VERSION,
                        weight_field='Continuous anatomical participation windows pinned to shoulder/spine/hip/knee/wrist stations, inverse segment-distance fourth-power, fifth-score subtraction before positive top4 normalization',
                        canonical_storage='Positive weight descending, stable bone index tie; zero padding names first positive owner',
                        blend_reference='Stored canonical dominant first positive owner; all effective weights retained for this static rest-space field'),
              provenance=dict(source=str(path),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),private_test_only=True,subdivision=1,source_height=float(height),anatomical_parts_r44=anatomical_parts,
                              added_joint_geometry='Two dark underlapping measured shoulder socket ellipsoids, torso-owned; all original visible body faces retained'if name=='sachiel'else'none'))
    geometry={'format_version':'1.12.0','minecraft:geometry':[dict(description=dict(identifier='geometry.'+name,texture_width=atlas.width,texture_height=atlas.height,visible_bounds_width=40,visible_bounds_height=40,visible_bounds_offset=[0,12,0]),bones=body_bones)]}
    idle={};walk={}
    for b in body_bones:idle[b['name']]={'rotation':[0,0,0]};walk[b['name']]={'rotation':[0,0,0]}
    if name=='sachiel':
        for side in ('l','r'):idle['forearm_'+side]['rotation']=[90,0,0];walk['forearm_'+side]['rotation']=[65,0,0]
    if name=='israfel':
        for side,sign in [('l',1),('r',-1)]:idle['arm_'+side]['rotation']=[0,0,sign*70];walk['arm_'+side]['rotation']=[0,0,sign*63]
    if name in ('sachiel','israfel'):
        for side,sign in [('l',1),('r',-1)]:
            walk['leg_'+side]['rotation']={str(round(i*.15,2)):[round(sign*22*math.sin(i*math.pi/4),3),0,0] for i in range(9)}
            walk['shin_'+side]['rotation']={str(round(i*.15,2)):[round(-max(0,-sign*math.sin(i*math.pi/4))*28,3),0,0] for i in range(9)}
    stem={'sachiel':'Sachiel','israfel':'entity_israfel','shamshel':'Shamshel','zeruel':'Zeruel'}[name]
    animations={'format_version':'1.8.0','animations':{f'animation.{stem}.idle'+('_1' if name=='israfel' else ''):dict(loop=True,animation_length=2,bones=idle),f'animation.{stem}.move':dict(loop=True,animation_length=1.2,bones=walk)}}
    for folder,suffix,data in [('geo','.geo.json',geometry),('mesh','.mesh.json',mesh),('animations','.animation.json',animations)]:
        dest=PACK/folder/(name+suffix);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(data,separators=(',',':')),encoding='utf8')
    (PACK/'textures/entity').mkdir(parents=True,exist_ok=True)
    atlas.save(PACK/'textures/entity'/(name+'.png'))
    (OUT/(name+'_rig.json')).write_text(json.dumps(dict(bones=body_bones,source_scale=scale,source_floor=float(floor),source=str(path)),indent=2),encoding='utf8')
    result=dict(name=name,triangles=len(vertices)//24,bones=len(bones),height=60,skin_weight_error=float(np.max(abs(np.array(ws).reshape(-1,4).sum(1)-1))),binding_version=BINDING_VERSION,
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),default_promoted=False,artistic_acceptance=False)
    print(result,flush=True);return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-pack',type=Path,default=PACK);ap.add_argument('--report-directory',type=Path,default=OUT)
    ap.add_argument('--actors',nargs='+',choices=('sachiel','israfel','shamshel','zeruel'),default=('sachiel','israfel','shamshel','zeruel'));args=ap.parse_args();PACK=args.output_pack.resolve();OUT=args.report_directory.resolve()
    OUT.mkdir(parents=True,exist_ok=True);report=[build(n) for n in args.actors]
    (OUT/'rigged_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf8')
