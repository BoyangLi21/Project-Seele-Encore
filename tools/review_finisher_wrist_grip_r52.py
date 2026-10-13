"""Actual wrist-grip close-ups and bounded forearm pronation probes; no source edit."""
from pathlib import Path
import argparse, copy, hashlib, io, json, zipfile
import numpy as np
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as R
from r52_motion_core import selected, read, UNIT, MIRROR
from author_finisher_r52 import Preview, world
from audit_finisher_leg_clearance_r52 import intersections


def nearest_witness(points, triangles):
    tree = cKDTree(triangles.mean(1)); best = None
    for start in range(0,len(points),512):
        pp = points[start:start+512,None,:]
        ix = tree.query(points[start:start+512],k=min(64,len(triangles)))[1]
        tri = triangles[ix]; aa,bb,cc = tri[:,:,0],tri[:,:,1],tri[:,:,2]
        ab=bb-aa; ac=cc-aa; ap=pp-aa; normal=np.cross(ab,ac)
        n2=(normal*normal).sum(-1); dot=(ap*normal).sum(-1)
        projected=pp-normal*np.divide(dot,n2,out=np.zeros_like(dot),where=n2>1e-12)[...,None]
        q=projected-aa; d00=(ab*ab).sum(-1); d01=(ab*ac).sum(-1); d11=(ac*ac).sum(-1)
        d20=(q*ab).sum(-1); d21=(q*ac).sum(-1); den=d00*d11-d01*d01
        u=np.divide(d11*d20-d01*d21,den,out=np.zeros_like(den),where=np.abs(den)>1e-12)
        v=np.divide(d00*d21-d01*d20,den,out=np.zeros_like(den),where=np.abs(den)>1e-12)
        inside=(u>=0)&(v>=0)&(u+v<=1)&(n2>1e-12)
        squared=np.where(inside,np.divide(dot*dot,n2,out=np.ones_like(dot)*1e12,where=n2>1e-12),1e12)
        closest=projected.copy()
        for x,y in [(aa,bb),(bb,cc),(cc,aa)]:
            edge=y-x; factor=np.clip(np.divide(((pp-x)*edge).sum(-1),(edge*edge).sum(-1),out=np.zeros_like(dot),where=(edge*edge).sum(-1)>1e-12),0,1)
            point=x+factor[...,None]*edge; dd=((pp-point)**2).sum(-1); good=dd<squared
            squared=np.minimum(squared,dd); closest=np.where(good[...,None],point,closest)
        pi,ti=np.unravel_index(squared.argmin(),squared.shape)
        candidate=(float(squared[pi,ti]),int(start+pi),int(ix[pi,ti]),closest[pi,ti].copy())
        if best is None or candidate[0]<best[0]:best=candidate
    return best


def world_matrix(pose,name,value):
    local=np.linalg.inv(pose.parent(name))@value
    pose.setq(name,R.from_matrix(local[:3,:3]))
    pivot=pose.rig.P[name]
    pose.setp(name,local[:3,3]-pivot+local[:3,:3]@pivot)


def pronation(pose,side,degrees):
    """Rotate at the anatomical elbow axis and preserve the full wrist matrix."""
    wrist=pose.matrix('hand_'+side).copy()
    elbow=pose.point('forearm_'+side,pose.rig.elbows[side])
    axis=pose.point('hand_'+side)-elbow; axis/=np.linalg.norm(axis)
    turn=np.eye(4);turn[:3,:3]=R.from_rotvec(axis*np.radians(degrees)).as_matrix()
    turn[:3,3]=elbow-turn[:3,:3]@elbow
    world_matrix(pose,'forearm_'+side,turn@pose.matrix('forearm_'+side))
    world_matrix(pose,'hand_'+side,wrist)


def project(preview,points):
    rel=np.asarray(points)-preview.eye;z=rel@preview.forward
    focal=preview.size[1]/(2*np.tan(np.radians(preview.fov)/2))
    return np.column_stack([preview.size[0]/2+(rel@preview.right)/z*focal,
                            preview.size[1]/2-(rel@preview.up)/z*focal])


parser=argparse.ArgumentParser(description=__doc__)
for name in ('body','assets','angel-rig','clip','material-jar','out'):
    parser.add_argument('--'+name,type=Path,required=True)
parser.add_argument('--trials',action='store_true')
parser.add_argument('--frames',type=int,nargs='+',default=[696,720])
parser.add_argument('--probe-state',type=Path)
parser.add_argument('--complete-groups',action='store_true')
parser.add_argument('--auto-enemy-wrist',action='store_true')
parser.add_argument('--label',default='original grip close-up')
args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
_,hero,angel=selected(args.body,args.assets,args.angel_rig);clip=read(args.clip)
if args.probe_state:
    probe=read(args.probe_state)[-1]
    assert probe['valid_static_candidate'] and probe['frame'] in args.frames
    clip['eva']['frames'][probe['frame']]=probe['eva_frame']
    clip['angel']['frames'][probe['frame']]=probe['angel_frame']
with zipfile.ZipFile(args.material_jar) as archive:
    textures={n:np.asarray(Image.open(io.BytesIO(archive.read('assets/projectseele/textures/entity/'+n+'.png'))).convert('RGB')) for n in ('eva_unit01','sachiel')}
    mesh=json.loads(archive.read('assets/projectseele/mesh/eva_unit01_anatomical_hands_r45.mesh.json'))
    for name,part in mesh['parts'].items():
        before=np.asarray(hero.hand_mesh['parts'][name]['vertices']).reshape(-1,8);after=np.asarray(part['vertices']).reshape(-1,8)
        assert np.array_equal(before[:,[0,1,2,5,6,7]],after[:,[0,1,2,5,6,7]])
        hero.uv[name]=after[:,3:5]
parts=['arm_l','forearm_l','hand_l','arm_r','forearm_r','hand_r']
offsets=np.cumsum([0]+[len(hero.parts[name])//3 for name in parts])
rows=[];trials=[]
for frame in args.frames:
    h=hero.decode(clip['eva']['frames'][frame],clip['eva']['bones'])
    a=angel.decode(clip['angel']['frames'][frame],clip['angel']['bones'])
    hr=np.asarray(clip['eva']['root_blocks'][frame]);ar=np.asarray(clip['angel']['root_blocks'][frame])
    arm_tri=(h.surface(parts)*MIRROR*UNIT+hr).reshape(-1,3,3)
    enemy=(a.surface()*UNIT+ar).reshape(-1,3,3);hits=intersections(arm_tri,enemy)
    enemy_wrist=min(('hand_l','hand_r'),key=lambda n:np.linalg.norm(world(h,hr,'hand_l')-world(a,ar,n))) if args.auto_enemy_wrist else 'hand_l'
    mask=(((angel.ids==angel.names.index(enemy_wrist))*angel.weights).sum(1)>.20)[angel.inverse].reshape(-1,3).any(1)
    indices=np.flatnonzero(mask);hand=h.surface(['hand_l'])*MIRROR*UNIT+hr
    squared,vertex,triangle,contact=nearest_witness(hand,enemy[indices]);triangle=int(indices[triangle])
    hand_point=hand[vertex];center=(world(h,hr,'hand_l')+contact)/2
    hero_ids=sorted({hit['hero_triangle'] for hit in hits});enemy_ids=sorted({hit['angel_triangle'] for hit in hits})
    counts={name:int(sum(offsets[i]<=hit['hero_triangle']<offsets[i+1] for hit in hits)) for i,name in enumerate(parts)}
    plane=[]
    for hit in hits:
        ht=arm_tri[hit['hero_triangle']];at=enemy[hit['angel_triangle']]
        normal=np.cross(at[1]-at[0],at[2]-at[0]);normal/=np.linalg.norm(normal)
        distances=(ht-at[0])@normal
        plane.append(float(min(max(distances.max(),0),max(-distances.min(),0))))
    row=dict(frame=frame,seconds=frame/60,intersection_pairs=len(hits),hero_parts=counts,
             intersecting_hero_triangles=hero_ids,intersecting_angel_triangles=enemy_ids,
             maximum_triangle_plane_straddle_blocks=max(plane,default=0),
             plane_measure_limit='Smaller signed vertex excursion on either side of the crossing triangle plane; not closed-volume penetration depth.',
             eva_wrist_world=world(h,hr,'hand_l').tolist(),angel_claw_joint_world=world(a,ar,enemy_wrist).tolist(),enemy_wrist_bone=enemy_wrist,
             material_contact_witness=dict(eva_hand_vertex=vertex,angel_triangle=triangle,
                 eva_vertex_world=hand_point.tolist(),angel_surface_world=contact.tolist(),distance_blocks=float(np.sqrt(squared)),
                 limit='Actual selected vertex-to-triangle witness; candidate nearest among 64 centroid neighbours, not a global contact-depth proof.'),hits=hits)
    if args.complete_groups:
        row['complete_group_pairs']={name:len(intersections((h.surface([p for p in chosen if p in hero.parts])*MIRROR*UNIT+hr).reshape(-1,3,3),enemy))
            for name,chosen in {'head':['head'],'torso':['torso_lower','torso_upper','neck'],
                'legs':['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r']}.items()}
        row['complete_group_pairs']['arms']=len(hits)
    rows.append(row)
    item=dict(t=frame/60,eva=h,angel=a,hr=hr,ar=ar)
    for name,offset in [('front',[0,7,32]),('side',[32,7,0]),('top',[4,32,5])]:
        if (args.out/f'GRIP_{frame}_{name}_actual_and_overlay.png').is_file():continue
        preview=Preview(args.assets,(1000,760));preview.textures=textures;preview.fov=43
        preview.set_camera(center+offset,center)
        actual=preview.render(item,('material regrip candidate ' if args.probe_state else args.label+' ')+name)
        overlay=actual.copy();draw=ImageDraw.Draw(overlay)
        for surface,ids,color in [(enemy,enemy_ids,(255,110,75)),(arm_tri,hero_ids,(255,40,215))]:
            for index in ids:
                xy=project(preview,surface[index]);draw.line([tuple(p) for p in np.vstack([xy,xy[0]])],fill=color,width=2)
        markers=[(world(h,hr,'hand_l'),'EVA wrist',(0,230,255)),(world(a,ar,enemy_wrist),'claw joint',(255,220,40)),
                 (hand_point,'EVA contact vertex',(255,255,255)),(contact,'claw surface',(70,255,140))]
        for point,label,color in markers:
            x,y=project(preview,[point])[0];draw.ellipse((x-5,y-5,x+5,y+5),fill=color);draw.text((x+8,y+8),label,fill=color)
        draw.rectangle((0,36,1000,84),fill=(12,18,24));draw.text((12,45),'X-RAY edges: magenta EVA / orange claw; contact dots are actual surface witnesses',fill='white')
        joined=Image.new('RGB',(2000,760));joined.paste(actual,(0,0));joined.paste(overlay,(1000,0))
        joined.save(args.out/f'GRIP_{frame}_{name}_actual_and_overlay.png')
    print(frame,'source pairs',len(hits),'forearm plane straddle',row['maximum_triangle_plane_straddle_blocks'],flush=True)
    if args.trials:
        hand_names=['hand_l','hand_r']+[name for name in h.q if name.startswith('r45_hand_')]
        old_matrices={name:h.matrix(name).copy() for name in hand_names}
        old_hand_surface=h.surface(['hand_l','hand_r']).copy()
        for degrees in (-60,-40,-20,0,20,40,60):
            changed=copy.deepcopy(h);pronation(changed,'l',degrees)
            changed_tri=(changed.surface(['arm_l','forearm_l'])*MIRROR*UNIT+hr).reshape(-1,3,3)
            hh=intersections(changed_tri,enemy)
            trial=dict(frame=frame,forearm_rotation_degrees=degrees,changed_left_upper_forearm_pairs=len(hh),
                maximum_full_hand_world_matrix_error=float(max(np.max(np.abs(changed.matrix(n)-old_matrices[n])) for n in hand_names)),
                maximum_actual_hand_skin_error_blocks=float(np.linalg.norm(changed.surface(['hand_l','hand_r'])-old_hand_surface,axis=1).max()*UNIT),
                hand_world_bones=len(hand_names),anatomical_axial_probe_limit_degrees=60,
                limits='Finite isolated left-forearm probe. Elbow and wrist positions, both complete hand world transforms and finger poses retained; no continuous clip or anatomic/native acceptance inferred.')
            trials.append(trial);print(trial,flush=True)
            (args.out/'BOUNDED_PRONATION_TRIALS.json').write_text(json.dumps(trials,indent=2),'utf8')
if not args.trials and (args.out/'BOUNDED_PRONATION_TRIALS.json').is_file():
    trials=json.loads((args.out/'BOUNDED_PRONATION_TRIALS.json').read_text('utf8'))
(args.out/'GRIP_DIAGNOSTIC.json').write_text(json.dumps(dict(clip_sha256=hashlib.sha256(args.clip.read_bytes()).hexdigest(),
    probe_state=str(args.probe_state) if args.probe_state else None,
    probe_state_sha256=hashlib.sha256(args.probe_state.read_bytes()).hexdigest() if args.probe_state else None,
    actual_selected_mesh=True,frames=rows,trials=trials,native_verified=False,user_accepted=False),indent=2),'utf8')
