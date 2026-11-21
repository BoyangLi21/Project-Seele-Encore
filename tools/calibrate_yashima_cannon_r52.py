"""Read the unchanged original gun plus real native pose/FK; output geometry candidates only, never write a world."""
from pathlib import Path
import json,hashlib,struct,gzip
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.Codex/r52_operations/calibration_powered'
ASSETS=ROOT/'build/resources/main/assets/projectseele'
DESIGN=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/far_yashima/RIDGE_DESIGN.json')

def triangles(name):
    p=ASSETS/'mesh'/name;r=json.loads(p.read_text('utf8'));chunks=[]
    for part in r['parts'].values():
        v=np.asarray(part['vertices'],dtype=np.float32).reshape(-1,r['stride'])
        chunks.append(v[:,:3]+np.asarray(part['pivot'],dtype=np.float32))
    return np.concatenate(chunks).reshape(-1,3,3),hashlib.sha256(p.read_bytes()).hexdigest(),r

def read_cloud(path=None):
    data=gzip.decompress((path or OUT/'actual_native_prone_parts.bin.gz').read_bytes());at=0
    def integer():
        nonlocal at
        v=struct.unpack_from('>i',data,at)[0];at+=4;return v
    def word():
        nonlocal at
        n=struct.unpack_from('>H',data,at)[0];at+=2;s=data[at:at+n].decode();at+=n;return s
    assert integer()==0x52353243 and integer()==1
    out={}
    for _ in range(integer()):
        name,sha=word(),word();n=integer();v=np.frombuffer(data,dtype='>f4',count=n*3,offset=at).astype(float).reshape(-1,3,3);at+=n*12;out[name]=v
    assert at==len(data)
    return out

def main():
    raw,sha,original=triangles('positron_cannon.mesh.json');payload,payload_sha,_=triangles('positron_cannon_payload_r50.mesh.json')
    a=raw.reshape(-1,3).astype(float);b=payload.reshape(-1,3).astype(float)
    delta=(b-a).mean(0);assert np.max(np.abs((b-a)-delta))<3e-5,'Original triangles were altered'
    lo,hi=b.min(0),b.max(0);center=(lo+hi)/2;center[1]=lo[1]
    norm=(payload-center)/16;norm[:,:,0]*=-1
    part=original['parts']['cannon'];source_local=raw-np.asarray(part['pivot'])
    cap=source_local[np.max(np.abs(source_local[:,:,1]+90.93669),axis=1)<.0005];assert len(cap)==12
    weights=np.linalg.norm(np.cross(cap[:,1]-cap[:,0],cap[:,2]-cap[:,0]),axis=1)/2
    actual_cap=(cap.mean(1)*weights[:,None]).sum(0)/weights.sum()+np.asarray(part['pivot'])
    p=actual_cap+delta-center;muzzle=p/16;muzzle[0]*=-1
    capture=json.loads((OUT/'native_prone_cannon.json').read_text());extra=json.loads((OUT/'native_prone_cannon_extra.json').read_text());design=json.loads(DESIGN.read_text())
    rendered=json.loads((OUT/'native_prone_cannon_final_render.json').read_text())
    assert capture['powered'] and not capture['shutdown'] and capture['server_stable_ticks']>=20
    assert rendered['powered'] and not rendered['shutdown'] and rendered['client_stable_ticks']>=20 and rendered['server_stable_ticks']>=20
    assert rendered['uuid']==capture['uuid'] and rendered['stance']==3,'Same powered production final rendered pose required'
    old_root=np.asarray(capture['position']);soles=np.array(list(extra['actual_lowest_shoe_vertices_world'].values()));sole_delta=soles.mean(0)-old_root
    feet=np.asarray(design['points']['unit01_prone_feet']);fwd=np.array([design['forward_xz'][0],0,design['forward_xz'][1]]);right=np.cross(fwd,[0,1,0]);up=np.array([0.,1,0])
    body_root=feet+fwd*(-sole_delta[2])-up*sole_delta[1]
    bounds=[norm.reshape(-1,3).min(0).tolist(),norm.reshape(-1,3).max(0).tolist()]
    info=dict(schema='projectseele.r52.same-source-cannon-calibration.v1',world_written=False,native_pose_uuid=capture['uuid'],
        source_mesh_sha256=sha,payload_mesh_sha256=payload_sha,triangles=len(raw),translation_only_payload_max_error=float(np.max(np.abs((b-a)-delta))),
        server_powered_stable_ticks=capture['server_stable_ticks'],client_powered_stable_ticks=rendered['client_stable_ticks'],shutdown=False,
        bounds_local=bounds,bore_local=[0,-1,0],muzzle_local=muzzle.tolist(),actual_cap_triangles=12,
        actual_source_shoe_vertices_world=soles.tolist(),original_entity_root=old_root.tolist(),actual_sole_anchor_delta=sole_delta.tolist(),
        root_authorized_prone_foot_anchor=feet.tolist(),calibrated_entity_root=body_root.tolist(),
        scope='Same original triangles and actual native final pose/FK. Grip fitting and native R52 station validation remain separate.')
    (OUT/'MEASURED_SOURCE.json').write_text(json.dumps(info,indent=2),'utf8')
    def surface(seed):
        seed=np.asarray(seed);a,b,c=norm[:,0,:],norm[:,1,:],norm[:,2,:];ab=b-a;ac=c-a;n=np.cross(ab,ac);nn=(n*n).sum(1)
        valid=nn>1e-20;projection=seed-(((seed-a)*n).sum(1)/np.where(valid,nn,1))[:,None]*n
        ap=projection-a;aa=(ab*ab).sum(1);bb=(ab*ac).sum(1);cc=(ac*ac).sum(1);dd=(ap*ab).sum(1);ee=(ap*ac).sum(1);det=aa*cc-bb*bb
        v=(dd*cc-ee*bb)/np.where(valid,det,1);w=(ee*aa-dd*bb)/np.where(valid,det,1);inside=valid&(v>=0)&(w>=0)&(v+w<=1)
        candidates=[np.where(inside[:,None],projection,a)]
        for x,y in ((a,b),(b,c),(c,a)):
            d=y-x;length=(d*d).sum(1);t=np.clip(((seed-x)*d).sum(1)/np.where(length>0,length,1),0,1);candidates.append(x+t[:,None]*d)
        values=np.stack(candidates);distance=((values-seed)**2).sum(2);distance[:,~valid]=np.inf;flat=np.argmin(distance);kind,index=np.unravel_index(flat,distance.shape)
        return values[kind,index],int(index),norm[index].tolist()
    # Search actual receiver/foregrip surfaces in the original mesh; final points are actual triangle contacts.
    fit_file=OUT/'FRAME_FIT.json';fit=json.loads(fit_file.read_text()) if fit_file.exists() else dict(lateral_m=0,forward_m=0,up_m=0)
    gun_scale=float(fit.get('scale',8))
    left,li,lt=surface(fit.get('left_surface_seed',[-.16,4.55,.35]));right_grip,ri,rt=surface(fit.get('right_surface_seed',[.08,6.35,.65]));pivot,pi,pt=surface([0,6.8,.25])
    old=np.array(capture['production_held_gun_matrix']).reshape(4,4,order='F');orig_bounds=np.concatenate([raw.reshape(-1,3).min(0)[None,:],raw.reshape(-1,3).max(0)[None,:]])
    offset=np.array([-(orig_bounds[0,0]+orig_bounds[1,0])/32,orig_bounds[0,1]/16,(orig_bounds[0,2]+orig_bounds[1,2])/32])
    old_norm_origin=(old@np.r_[offset,1])[:3];side_offset=-(old_norm_origin[0]-old_root[0]);height=old_norm_origin[1]-old_root[1]
    bay=np.asarray(design['points']['cannon_bay_centre']);raised=bay.copy()
    # Keep Root's bay and shoe anchor. Fit only the original model's installed
    # frame so its stock clears the actual shoulder/torso skin.
    origin=bay+right*(side_offset+fit['lateral_m'])+fwd*fit['forward_m']+up*(height+feet[1]-bay[1]+fit['up_m']);target=np.array([30.5,144,348.5])
    forward=fwd.copy()
    barrel_roll=Rotation.from_rotvec(np.array([0.,-1.,0.])*np.radians(fit.get('roll_degrees',0))).as_matrix()
    for _ in range(10):
        lateral=np.cross(forward,up);lateral/=np.linalg.norm(lateral);vertical=np.cross(lateral,forward);matrix=np.column_stack((lateral,-forward,-vertical))@barrel_roll
        wm=origin+matrix@(muzzle*gun_scale);forward=target-wm;forward/=np.linalg.norm(forward)
    quaternion=Rotation.from_matrix(matrix).as_quat();translation=origin-raised
    def world_point(v):return origin+matrix@(v*gun_scale)
    def body_model(v):
        # Source-local model-block frame: forward is -Z before the actual RENDER_SCALE=5 world transform.
        d=np.asarray(v)-body_root;return np.array([np.dot(d,right)/5,d[1]/5,-np.dot(d,fwd)/5])
    def normal_model(triangle):
        t=np.asarray(triangle);normal=np.cross(t[1]-t[0],t[2]-t[0]);normal/=np.linalg.norm(normal);normal=matrix@normal
        return np.array([normal@right,normal[1],-normal@fwd]).tolist()
    candidate=dict(schema=52,id='root_far_yashima_fixed_cannon_r52',dimension='projectseele:geofront',installed=False,geometry_validated=False,
        cannon_uuid=None,hatch_uuid=None,source_rack_uuid='749cf141-0e2f-59ef-9e9b-d08346d5ea8d',source_weapon_uuid='58eab304-0fb0-5f44-b500-4fed8824db08',source_mesh_sha256=payload_sha,
        source_position=None,closed_position=None,raised_position=raised.tolist(),rise_ticks=100,return_ticks=100,
        mesh_frame=dict(translation=translation.tolist(),quaternion_xyzw=quaternion.tolist(),scale=gun_scale),bounds_local=bounds,
        aim_pivot_local=pivot.tolist(),bore_local=[0,-1,0],muzzle_local=muzzle.tolist(),grip_left_local=left.tolist(),grip_right_local=right_grip.tolist(),
        prone_position=body_root.tolist(),prone_yaw=float(np.degrees(np.arctan2(-fwd[0],fwd[2]))),interaction_control=design['points']['command_console'],
        interaction_radius=1.2,grip_radius=.6,attack_range=2600,eva_access_route=None,
        calibration=dict(actual_foot_anchor=feet.tolist(),native_pose_uuid=capture['uuid'],mesh_sha256=payload_sha,measured_frame_fit=fit,
            grips_actual_triangle_indices=[li,ri],grips_actual_triangles=[lt,rt],pivot_actual_triangle_index=pi,
            grip_left_world=world_point(left).tolist(),grip_right_world=world_point(right_grip).tolist(),muzzle_world=world_point(muzzle).tolist(),
            grip_left_body_model=body_model(world_point(left)).tolist(),grip_right_body_model=body_model(world_point(right_grip)).tolist(),
            grip_left_body_normal=normal_model(lt),grip_right_body_normal=normal_model(rt),
            model_fit_and_pose_candidate_only=True,native_station_passed=False))
    (OUT/'STATION_CANDIDATE.json').write_text(json.dumps(candidate,indent=2),'utf8')
    if '--measure-only' in __import__('sys').argv:
        return
    fitted=OUT/'fitted/actual_native_prone_parts.bin.gz'
    cloud=read_cloud(fitted if fitted.exists() else None)
    fig,axes=plt.subplots(1,3,figsize=(18,8))
    worldgun=origin+norm@matrix.T*gun_scale;rel=worldgun-feet
    gun=np.stack((rel@right,rel@fwd,rel[:,:,1]),axis=2)
    parts=[(gun,np.array([.38,.46,.58]))]
    for name,t in cloud.items():
        t=t.copy();t[:,:,2]*=-1;t[:,:,2]-=sole_delta[2];xyz=t[:,:,[0,2,1]]
        color=np.array([.48,.31,.7]) if not name.startswith('hand') else np.array([.45,.67,.3])
        parts.append((xyz,color))
    # Full triangle surfaces, depth sorted and opaque: no subsampling that opens holes.
    projections=[('Top',np.eye(3)[[0,1,2]]),('Side',np.eye(3)[[1,2,0]]),
        ('Perspective',Rotation.from_euler('zyx',[25,-55,20],degrees=True).as_matrix())]
    for ax,(title,projection) in zip(axes,projections):
        vertices=[];colors=[];depth=[]
        for xyz,color in parts:
            normal=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0]);normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-12)
            shade=.55+.45*np.abs(normal@np.array([.25,-.35,.9028]));v=xyz@projection.T
            vertices.append(v[:,:,:2]);colors.append(color[None,:]*shade[:,None]);depth.append(v[:,:,2].mean(1))
        vertices=np.concatenate(vertices);colors=np.concatenate(colors);depth=np.concatenate(depth);order=np.argsort(depth)
        ax.add_collection(PolyCollection(vertices[order],facecolors=colors[order],edgecolors='none',rasterized=True))
        points=vertices.reshape(-1,2);lo,hi=points.min(0)-2,points.max(0)+2;ax.set_xlim(lo[0],hi[0]);ax.set_ylim(lo[1],hi[1]);ax.set_aspect('equal');ax.set_title(title)
        if title=='Top':ax.set_xlabel('lateral (m)');ax.set_ylabel('from actual shoe anchor (m)')
        elif title=='Side':ax.set_xlabel('from actual shoe anchor (m)');ax.set_ylabel('above source floor (m)')
        else:ax.set_axis_off()
        for name,v,color in [('L grip',left,'#e63427'),('R grip',right_grip,'#03abc5'),('Muzzle',muzzle,'#ed9800')]:
            point=world_point(v)-feet;model=np.array([point@right,point@fwd,point[1]])@projection.T
            ax.scatter(model[0],model[1],color=color,s=28,zorder=8);ax.annotate(name,model[:2],xytext=(5,5),textcoords='offset points',fontsize=8,color=color,zorder=9)
    fig.suptitle('Original cannon + same-frame native prone FK with anatomical hand fit\nFull source triangles; model calibration only, native station validation pending')
    fig.tight_layout();fig.savefig(OUT/'SOURCE_MODEL_MEASUREMENT.png',dpi=150);plt.close(fig)
    print(json.dumps(info))

if __name__=='__main__':main()
