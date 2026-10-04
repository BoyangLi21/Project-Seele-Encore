"""Offline whole-skin rifle contact solve, retaining the native weapon frame.

Writes a proposal only. Open-mesh parity, triangle crossings, digit self-contact,
native playback and visual quality must all be reviewed before any integration.
"""
from pathlib import Path
import argparse,json,time
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from eva_hand_rig_math_r45 import controls,matrices,joint_points
from rebind_anatomical_hand_r45 import dq_pose
from mesh_distance_r45 import TriangleField

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--side',choices=['r','l'],required=True)
    p.add_argument('--evaluations',type=int,default=35);p.add_argument('--refine',type=int,default=0)
    p.add_argument('--pistol-contacts',action='store_true',help='Constrain each right finger to the measured pistol grip, not any convenient gun surface')
    p.add_argument('--translation-bound',type=float,default=.12)
    p.add_argument('--initial-proposal',type=Path)
    p.add_argument('--natural-grip',action='store_true',help='Right-hand authoring prior: coordinated curled fingers, no reverse-bent MCP escape from collisions')
    p.add_argument('--contact-faces',type=Path,help='Exact full-triangle witness to add face interiors/edges to the distance objective')
    p.add_argument('--arm-guides',type=Path,help='Measured native shoulder/arm frames, checked against the same fixed weapon frame')
    p.add_argument('--rotation-bound',type=float,default=.3)
    p.add_argument('--accelerated-distance',action='store_true',help='Exact spatial-indexed nearest triangle and three-ray parity; no weapon reduction')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    assert .01<=a.translation_bound<=.3
    assert .05<=a.rotation_bound<=1
    import shutil
    code=a.out/'source_snapshot';code.mkdir()
    for filename in ['fit_rifle_surface_r45.py','mesh_distance_r45.py','mesh_distance_accelerated_r45.py','eva_hand_rig_math_r45.py','rebind_anatomical_hand_r45.py']:
        shutil.copy2(Path(__file__).resolve().parent/filename,code/filename)
    provenance=json.loads((a.input/'provenance.json').read_text('utf8'));source=Path(provenance['candidate'])
    c=json.loads((source/'hand_rig_contract.json').read_text('utf8'));name=f"eva_unit0{c['rig']}"
    geo=json.loads((source/(name+'.geo.json')).read_text('utf8'))
    mesh=json.loads((source/(name+'_anatomical_hands_r45.mesh.json')).read_text('utf8'))
    side=a.side;pose='rifle_right'if side=='r'else'rifle_left';part=mesh['parts']['hand_'+side];skin=mesh['jointSkins']['hand_'+side]
    rest=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]/16
    palette=list(skin['influences']);weights=np.asarray([skin['influences'][n]for n in palette]).T
    inv=[np.asarray(skin['inverseBindColumnMajor'][n]).reshape(4,4).T for n in palette]
    data=np.load(a.input/f'{side}_geometry.npz');weapon=data['weapon']
    if a.accelerated_distance:
        from mesh_distance_accelerated_r45 import AcceleratedTriangleField
        field=AcceleratedTriangleField(weapon.reshape(-1,3,3))
    else:field=TriangleField(weapon.reshape(-1,3,3))
    contact_targets={};contact_source={}
    if a.pistol_contacts:
        assert side=='r'
        gun_file=Path(__file__).resolve().parents[1]/'run/resourcepacks/eva_real_model/assets/projectseele/mesh/eva_pallet_smg.mesh.json'
        import hashlib
        assert hashlib.sha256(gun_file.read_bytes()).hexdigest()==provenance['gun_sha256']
        gun_part=json.loads(gun_file.read_text('utf8'))['parts']['cannon'];pc=np.asarray(gun_part['pivot'])*[-1,1,1]/16
        gun_points=(np.asarray(gun_part['vertices']).reshape(-1,8)[:,:3]+gun_part['pivot'])*[-1,1,1]/16
        transform=np.linalg.lstsq(np.c_[gun_points,np.ones(len(gun_points))],weapon,rcond=None)[0]
        assert np.max(np.abs(np.c_[gun_points,np.ones(len(gun_points))]@transform-weapon))<1e-5
        contact_source={'index':[-1.2,36,8],'middle':[4.2,28,25],'ring':[4.2,20,32],'little':[4.2,12,40]}
        for digit,xyz in contact_source.items():
            x,y,z=xyz;point=pc+np.asarray([-x*.9,(z-18)*.32,-(y-36)*.24])/16
            contact_targets[digit]=np.r_[point,1]@transform
    start=controls(c,pose,side);h=c['hands'][side];variables=[];lo=[];hi=[];x0=[]
    for digit in ['thumb','index','middle','ring','little','cup_ring','cup_little']:
        for joint in h['digits'].get(digit,{}).get('joints',[]):
            variables.append((joint['name'],0));x0.append(start[joint['name']][0])
            bounds=joint['anatomical_limits_degrees'][0];lo.append(bounds[0])
            comfortable_max=[45,55,50][joint['index']]if digit=='thumb'else 75 if joint['index']==2 else bounds[1]
            hi.append(min(bounds[1],comfortable_max))
            if a.natural_grip:
                assert side=='r', 'This authoring envelope is for the dominant pistol grip only'
                if digit in ('middle','ring','little'):
                    low,high=[(35,85),(40,100),(15,65)][joint['index']]
                    lo[-1]=max(lo[-1],low);hi[-1]=min(hi[-1],high)
                elif digit=='index':
                    low,high=[(0,30),(15,80),(0,60)][joint['index']]
                    lo[-1]=max(lo[-1],low);hi[-1]=min(hi[-1],high)
                elif digit=='thumb':
                    low,high=[(0,35),(15,55),(5,40)][joint['index']]
                    lo[-1]=max(lo[-1],low);hi[-1]=min(hi[-1],high)
    thumb=h['digits']['thumb']['joints'][0]
    for axis in [1,2]:
        value=start[thumb['name']][axis];bounds=thumb['anatomical_limits_degrees'][axis]
        variables.append((thumb['name'],axis));x0.append(value);lo.append(max(bounds[0],value-15));hi.append(min(bounds[1],value+15))
    for digit in ['index','middle','ring','little']:
        joint=h['digits'][digit]['joints'][0];value=start[joint['name']][2]
        bounds=joint['anatomical_limits_degrees'][2]
        variables.append((joint['name'],2));x0.append(value)
        lo.append(max(bounds[0],-25 if digit=='index'else -12));hi.append(min(bounds[1],25 if digit=='index'else 12))
        if a.natural_grip:
            # Positive ring spread moves its skin away from the middle digit
            # on this measured right-hand frame. The native-derived surface
            # witness found overlap when the optimizer spread it inward.
            limits={'index':(-8,8),'middle':(-8,0),'ring':(4,12),'little':(0,12)}[digit]
            lo[-1]=max(lo[-1],limits[0]);hi[-1]=min(hi[-1],limits[1])
    variable_count=len(x0)
    x0=np.r_[x0,[0.]*6];lo=np.r_[lo,[-a.translation_bound]*3,[-a.rotation_bound]*3];hi=np.r_[hi,[a.translation_bound]*3,[a.rotation_bound]*3]
    arm_guides=[];arm_before=[]
    def arm_alignment(guide,translation,rotation):
        matrix=np.asarray(guide['unadjusted_hand_to_world']);pivot=np.asarray(c['weapon_grip_frames'][side]['palm_bind'])
        wrist=rotation@(np.asarray(guide['wrist_bind'])-pivot)+pivot+translation
        wrist=matrix[:3,:3]@wrist+matrix[:3,3];shoulder=np.asarray(guide['shoulder_world'])
        direction=wrist-shoulder;distance=np.linalg.norm(direction);direction/=max(distance,1e-8)
        upper=guide['upper_length_world'];lower=guide['lower_length_world']
        reach=np.clip(distance,abs(upper-lower)+.001,upper+lower-.001)
        along=(upper*upper-lower*lower+reach*reach)/(2*reach);radius=np.sqrt(max(0,upper*upper-along*along))
        pole=np.asarray(guide['preferred_pole_world']);weight=guide.get('grounded_pole_weight',0)
        if weight>0 and radius>.001:
            centre=shoulder+direction*along;vertical=np.asarray([0.,1.,0.])-direction*direction[1]
            if np.linalg.norm(vertical)>.001:
                vertical/=np.linalg.norm(vertical);cosine=np.clip((guide['floor_elbow_height']-centre[1])/(radius*vertical[1]),-.999,.999)
                sine=np.sqrt(1-cosine*cosine);lateral=np.cross(direction,vertical)
                first=vertical*cosine+lateral*sine;second=vertical*cosine-lateral*sine
                chosen=first if first@pole>second@pole else second
                pole=pole/np.linalg.norm(pole)*(1-weight)+chosen*weight
        bend=pole-direction*(pole@direction);bend/=max(np.linalg.norm(bend),1e-8)
        elbow=shoulder+direction*along+bend*radius
        forearm=wrist-elbow;forearm/=np.linalg.norm(forearm)
        long=matrix[:3,:3]@rotation@np.asarray(guide['longitudinal_bind']);long/=np.linalg.norm(long)
        return elbow,forearm,long,max(0,distance-upper-lower+.08)
    if a.arm_guides:
        guide_doc=json.loads(a.arm_guides.read_text('utf8'))
        assert guide_doc['original_solver_provenance']['contract_sha256']==provenance['contract_sha256']
        arm_guides=[g for g in guide_doc['guides']if g['side']==side]
        assert len(arm_guides)==3
        for guide in arm_guides:
            fit=guide['current_adjustment'];elbow,forearm,long,reach=arm_alignment(guide,np.asarray(fit['translation_native']),Rotation.from_quat(fit['rotation_xyzw']).as_matrix())
            error=float(np.linalg.norm(elbow-guide['observed_elbow_world']))
            assert error<.025,('Authoring arm does not reproduce actual native elbow',guide['stage'],error)
            arm_before.append(dict(stage=guide['stage'],elbow_reproduction_error_world=error,wrist_bend_degrees=float(np.degrees(np.arccos(np.clip(forearm@long,-1,1))))))
    _,unique=np.unique(np.round(rest,6),axis=0,return_index=True)
    selected=set(map(int,unique[::max(1,len(unique)//1200)]));tip_groups=[]
    triangle_samples=np.empty((0,3),dtype=int)
    if a.contact_faces:
        witness=json.loads(a.contact_faces.read_text('utf8'))
        assert witness['side']==side
        faces=np.asarray(witness['hand_faces'],dtype=int)
        assert len(faces)>0 and faces.min()>=0 and faces.max()<len(rest)//3
        triangle_samples=faces[:,None]*3+np.arange(3)
        selected.update(map(int,triangle_samples.ravel()))
    for digit in ['thumb','index','middle','ring','little']:
        j=h['digits'][digit]['joints'][-1];tip=np.asarray(j['tip_bind'])
        ids=unique[np.linalg.norm(rest[unique]-tip,axis=1)<.075]
        ids=ids[::max(1,len(ids)//12)];assert len(ids)>2,(side,digit,'No fingertip surface')
        selected.update(map(int,ids));tip_groups.append(ids)
    palm_id=c['weapon_grip_frames'][side]['measured_vertex'];selected.add(palm_id)
    palm=np.asarray(c['weapon_grip_frames'][side]['palm_bind'])
    selected=np.asarray(sorted(selected));lookup={int(i):j for j,i in enumerate(selected)}
    tips=[[lookup[int(i)]for i in ids]for ids in tip_groups];palm_index=lookup[palm_id]
    w=weights[selected];v=rest[selected];calls=0;began=time.monotonic()
    def values(x):
        result={n:y.copy()for n,y in start.items()}
        for (n,axis),value in zip(variables,x):result[n][axis]=value
        return result
    def surface(x,full=False):
        ms=matrices(geo,c,side,values(x));transforms=[ms[n]@inverse for n,inverse in zip(palette,inv)]
        result=dq_pose(rest if full else v,weights if full else w,transforms)
        rotation=Rotation.from_rotvec(x[variable_count+3:]).as_matrix()
        return (result-palm)@rotation.T+palm+x[variable_count:variable_count+3]
    baseline=surface(x0,True)
    assert np.max(np.abs(baseline-data['baseline']))<1e-5,'Current bind/pose does not reproduce frozen native baseline'
    start_dist,start_ambiguous=field.query(baseline[selected])
    def residual(x):
        nonlocal calls
        vertices=surface(x);dist,ambiguous=field.query(vertices)
        penetration=np.maximum(.006-dist,0)*18
        touch=np.asarray([max(0,float(dist[ids].min())-.01)for ids in tips]+[max(0,float(dist[palm_index])-.012)])*3
        prior=np.r_[(x[:variable_count]-x0[:variable_count])*.0012,x[variable_count:variable_count+3]*.5,x[variable_count+3:]*.15]
        contacts=[]
        interiors=[]
        if len(triangle_samples):
            tri=vertices[np.asarray([[lookup[int(i)]for i in face]for face in triangle_samples])]
            points=np.concatenate([tri.mean(axis=1),(tri[:,0]+tri[:,1])*.5,(tri[:,1]+tri[:,2])*.5,(tri[:,2]+tri[:,0])*.5])
            distance,_=field.query(points)
            interiors=np.maximum(.006-distance,0)*18
        if contact_targets:
            skeleton=joint_points(geo,c,side,values(x));rotation=Rotation.from_rotvec(x[variable_count+3:]).as_matrix()
            for digit,target in contact_targets.items():
                tip=(skeleton[digit][-1]-palm)@rotation.T+palm+x[variable_count:variable_count+3]
                contacts.extend((tip-target)*5)
        calls+=1
        if calls%100==0:print('eval',calls,'seconds',round(time.monotonic()-began,1),'deepest',round(float(max(0,-dist.min())),5),'ambiguous',int(ambiguous.sum()),flush=True)
        coordinated=[]
        wrists=[]
        for guide in arm_guides:
            _,forearm,long,reach=arm_alignment(guide,x[variable_count:variable_count+3],Rotation.from_rotvec(x[variable_count+3:]).as_matrix())
            wrists.extend(np.cross(forearm,long)*1.5)
            wrists.extend([(1-float(forearm@long))*1.5,reach*.4])
        if a.natural_grip:
            actual=values(x)
            # Numerical clearance alone previously chose one reverse-bent
            # ring MCP and made a claw. Keep the three curled fingers within
            # a coherent grasp envelope; this is a pose-design prior, not a
            # claim about universal anatomical limits or visual acceptance.
            middle=h['digits']['middle']['joints']
            for digit in ('ring','little'):
                for i,joint in enumerate(h['digits'][digit]['joints']):
                    delta=actual[joint['name']][0]-actual[middle[i]['name']][0]
                    coordinated.append(max(0,abs(delta)-15)*.012)
            for digit in ('middle','ring','little'):
                joints=h['digits'][digit]['joints']
                distal=actual[joints[2]['name']][0];middle_angle=actual[joints[1]['name']][0]
                coordinated.append((distal-middle_angle*.67)*.006)
        return np.r_[penetration,touch,prior,contacts,coordinated,interiors,wrists]
    initial=x0.copy()
    if a.initial_proposal:
        prior=json.loads(a.initial_proposal.read_text('utf8'))
        assert prior['side']==side and prior['native_source']['contract_sha256']==provenance['contract_sha256']
        initial=np.r_[[prior['controls'][n][axis]for n,axis in variables],prior['translation_native'],Rotation.from_quat(prior['local_rotation_xyzw']).as_rotvec()]
    fit=least_squares(residual,np.clip(initial,lo+1e-8,hi-1e-8),bounds=(lo,hi),max_nfev=a.evaluations,
                      diff_step=1e-3,ftol=1e-5,xtol=1e-5,gtol=1e-5)
    refinements=[]
    for iteration in range(a.refine):
        full=surface(fit.x,True);dist,ambiguous=field.query(full)
        bad=unique[dist[unique]<.004]
        refinements.append(dict(iteration=iteration,deepest=float(max(0,-dist.min())),bad_unique_vertices=len(bad),active_samples=len(selected)))
        print('full-skin refinement',refinements[-1],flush=True)
        if len(bad)==0:break
        severe=bad[np.argsort(dist[bad])[:300]]
        selected=np.asarray(sorted(set(map(int,selected))|set(map(int,severe))|set(map(int,bad[::max(1,len(bad)//300)]))))
        lookup={int(i):j for j,i in enumerate(selected)}
        tips=[[lookup[int(i)]for i in ids]for ids in tip_groups];palm_index=lookup[palm_id]
        w=weights[selected];v=rest[selected]
        fit=least_squares(residual,np.clip(fit.x,lo+1e-8,hi-1e-8),bounds=(lo,hi),max_nfev=a.evaluations,
                          diff_step=1e-3,ftol=1e-6,xtol=1e-6,gtol=1e-5)
    final=surface(fit.x,True);dist,ambiguous=field.query(final)
    record=dict(side=side,native_source=provenance,controls={n:y.tolist()for n,y in values(fit.x).items()},
                translation_native=fit.x[variable_count:variable_count+3].tolist(),palm_pivot_native=palm.tolist(),
                local_rotation_xyzw=Rotation.from_rotvec(fit.x[variable_count+3:]).as_quat().tolist(),
                initial_deepest_sample_native=float(max(0,-start_dist.min())),
                final_deepest_vertex_native=float(max(0,-dist.min())),final_inside_vertices=int(sum(dist<-.003)),
                ambiguous_parity_vertices=int(ambiguous.sum()),calls=calls,nfev=fit.nfev,seconds=time.monotonic()-began,
                full_skin_refinements=refinements,
                source_grip_contact_targets=contact_source,
                translation_bound_native=a.translation_bound,initial_proposal=str(a.initial_proposal)if a.initial_proposal else None,
                natural_grip_authoring_prior=a.natural_grip,
                natural_grip_authoring_revision=2 if a.natural_grip else None,
                full_triangle_contact_witness=str(a.contact_faces)if a.contact_faces else None,
                arm_guides=str(a.arm_guides)if a.arm_guides else None,actual_arm_before=arm_before,
                proposed_arm_after=[dict(stage=g['stage'],wrist_bend_degrees=float(np.degrees(np.arccos(np.clip(arm_alignment(g,fit.x[variable_count:variable_count+3],Rotation.from_rotvec(fit.x[variable_count+3:]).as_matrix())[1]@arm_alignment(g,fit.x[variable_count:variable_count+3],Rotation.from_rotvec(fit.x[variable_count+3:]).as_matrix())[2],-1,1)))))for g in arm_guides],
                rotation_bound_radians=a.rotation_bound,
                distance_backend='trimesh5.1.1_rtree1.4.1_exact_triangle_three_ray'if a.accelerated_distance else'original_all_triangle',
                note='Proposal only; a sampled distance objective cannot replace full triangle, self-contact, native and artistic validation',
                native_tested=False,visual_accepted=False,installed=False)
    np.savez_compressed(a.out/'proposal.npz',hand=final,weapon=weapon,baseline=baseline)
    (a.out/'proposal.json').write_text(json.dumps(record,indent=2),'utf8')
    print(json.dumps({k:record[k]for k in ['side','initial_deepest_sample_native','final_deepest_vertex_native','final_inside_vertices','calls','seconds']}),flush=True)

if __name__=='__main__':main()
