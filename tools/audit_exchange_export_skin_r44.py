"""Compare reopened DCC skin with separately decoded exported pose skin.

This is an offline algorithm comparison, never a capture of native runtime.
The EVA fixture has rigid parts; actual late native seams remain unverified.
"""
from pathlib import Path
import argparse,json,sys
import bpy,numpy as np
from mathutils import Quaternion,Matrix

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve()
fixture=json.loads((out/'fixture.json').read_text('utf8'));export=json.loads((out/'paired_runtime_pose_candidate.json').read_text('utf8'))
axes=np.array([[1.,0,0],[0,0,-1],[0,1,0]]);mapping=np.eye(4);mapping[:3,:3]=axes*5/16;inverse=np.linalg.inv(mapping);rows=[]


def product(a,b):
    return np.concatenate([(a[...,:1]*b[...,:1]-(a[...,1:]*b[...,1:]).sum(-1,keepdims=True)),a[...,:1]*b[...,1:]+b[...,:1]*a[...,1:]+np.cross(a[...,1:],b[...,1:])],axis=-1)


def decode(role,frame):
    rig={b['name']:b for b in role['rig_contract_r44']};quats={n:Quaternion((q[0],-q[1],-q[2],q[3]))for n,q in zip(role['bones'],frame['rotation_wxyz'])};positions={n:np.asarray(v)*[-1,1,1]for n,v in frame['bone_position_xyz'].items()};positions['root']=np.asarray(frame['root_m'])*112*[-1,1,1];matrices={}
    def matrix(n):
        if n in matrices:return matrices[n]
        pivot=np.asarray(rig[n]['pivot'])*[-1,1,1];q=np.asarray(quats[n].to_matrix());m=np.eye(4);m[:3,:3]=q;m[:3,3]=positions.get(n,np.zeros(3))+pivot-q@pivot;parent=rig[n].get('parent');matrices[n]=matrix(parent)@m if parent else m;return matrices[n]
    for n in role['bones']:matrix(n)
    stage=np.eye(4);stage[:3,:3]=np.asarray(Quaternion((0,0,1),np.radians(frame['stage_yaw_degrees'])).to_matrix());stage[:3,3]=frame['stage_root_blocks']
    return {n:stage@mapping@m@inverse for n,m in matrices.items()}


def skin(points,transforms,ids,weights,ordered=False,first_slot=False):
    qs=np.array([list(Matrix(np.asarray(m[:3,:3]).tolist()).to_quaternion().normalized())for m in transforms]);ts=np.array([m[:3,3]for m in transforms]);ds=.5*product(np.c_[np.zeros(len(ts)),ts],qs)
    selected_q=qs[ids];selected_d=ds[ids];ref=selected_q[:,0]if first_slot else selected_q[np.arange(len(ids)),np.argmax(weights,axis=1)];sign=np.where((selected_q*ref[:,None,:]).sum(-1)>=0,1.,-1.)
    if ordered:
        running=np.zeros_like(ref)
        for slot in range(ids.shape[1]):
            sign[:,slot]=np.where((selected_q[:,slot]*running).sum(-1)>=0,1.,-1.);running+=selected_q[:,slot]*(weights[:,slot]*sign[:,slot])[:,None]
    qs=(selected_q*(weights*sign)[...,None]).sum(1);ds=(selected_d*(weights*sign)[...,None]).sum(1);norm=np.linalg.norm(qs,axis=1)[:,None];qs/=norm;ds/=norm;ds-=qs*(qs*ds).sum(1)[:,None]
    conjugate=qs*np.array([1,-1,-1,-1]);translations=2*product(ds,conjugate)[:,1:];v=2*np.cross(qs[:,1:],points);return points+qs[:,:1]*v+np.cross(qs[:,1:],v)+translations


for frame in (1,6,19,29,35,42,56,64,109):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
    for data in fixture['actors']:
        name=data['name'];obj=bpy.data.objects[name+'_actual_mesh'].evaluated_get(deps);mesh=obj.to_mesh();actual=np.asarray([list(obj.matrix_world@v.co)for v in mesh.vertices]);obj.to_mesh_clear();matrices=decode(export['roles'][name],export['roles'][name]['frames'][frame-1]);transforms=[matrices[b['name']]@mapping@np.linalg.inv(np.asarray(b['neutral_model']))@inverse for b in data['bones']]
        # Neutral rotations may be nonidentity for EVA. The fixture already
        # carries the raw neutral bake, so remove each bone's actual neutral.
        predicted=skin(np.asarray(data['vertices']),transforms,np.asarray(data['influences']),np.asarray(data['weights']));ordered=skin(np.asarray(data['vertices']),transforms,np.asarray(data['influences']),np.asarray(data['weights']),ordered=True);native=skin(np.asarray(data['vertices']),transforms,np.asarray(data['influences']),np.asarray(data['weights']),first_slot=data['key']=='sachiel');errors=np.linalg.norm(predicted-actual,axis=1);ordered_errors=np.linalg.norm(ordered-actual,axis=1);native_errors=np.linalg.norm(native-actual,axis=1);i=int(np.argmax(errors));ni=int(np.argmax(native_errors));rows.append(dict(actor=name,frame=frame,dominant_comparison_maximum_error_blocks=float(errors[i]),rms_blocks=float(np.sqrt(np.mean(errors**2))),ordered_accumulation_maximum_error_blocks=float(ordered_errors.max()),actual_renderer_reference_rule='first slot (RiggedAngelLayer)'if data['key']=='sachiel'else'rigid fixture (late native seams unverified)',actual_renderer_rule_maximum_error_blocks=float(native_errors[ni]),actual_renderer_rule_worst_vertex=ni,worst_dominant_vertex=i,actual=actual[i].tolist(),dominant_comparison=predicted[i].tolist()))
report=dict(samples=rows,maximum_dominant_comparison_error_blocks=max(r['dominant_comparison_maximum_error_blocks']for r in rows),maximum_actual_renderer_rule_error_blocks=max(r['actual_renderer_rule_maximum_error_blocks']for r in rows),scope='Reopened Blender actual mesh versus independent exported-pose/DQ algorithm at nine frames. Native renderer, late EVA seam stitching and final GPU pixels are unverified.',blender_implementation_reference='https://raw.githubusercontent.com/blender/blender/v5.1.0/source/blender/blenlib/intern/math_rotation_c.cc (add_weighted_dq_dq aligns to running sum; LocalTriangleMeshLayer uses dominant for EVA seam; actual weighted Angel RiggedAngelLayer uses first slot)',quality='Geometry comparison only, no artistic/native acceptance.')
(out/'export_skin_readback.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report,indent=2))
