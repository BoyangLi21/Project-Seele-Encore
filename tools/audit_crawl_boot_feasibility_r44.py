"""Actual boot/shin constraint feasibility with fixed hip and ground patch.

Counterfactual diagnostic only: do not install or infer visual acceptance.
"""
from pathlib import Path
import json,sys,argparse,math
import bpy,numpy as np
from mathutils import Vector,Quaternion
ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out
data=json.loads((out/'fixture.json').read_text('utf8'))['actors'][0];records=json.loads((out/'contact_pass_receipt.json').read_text('utf8'))['records'];rig=bpy.data.objects['eva_unit01_AUTHOR'];vertices=np.asarray(data['vertices']);ids=np.asarray(data['influences']);weights=np.asarray(data['weights']);owner=ids[np.arange(len(ids)),weights.argmax(1)];names=[b['name']for b in data['bones']];shapes={n:np.unique(vertices[owner==names.index(n)],axis=0)for n in ('leg_r','shin_r','foot_r')};rows=[]
for frame in (770,800,918):
    bpy.context.scene.frame_set(frame);bpy.context.view_layer.update();upper='leg_r';lower='shin_r';end='foot_r'
    h=rig.pose.bones[upper].head.copy();k=rig.pose.bones[lower].head.copy();a=rig.pose.bones[end].head.copy();qu=rig.pose.bones[upper].matrix.to_quaternion();ql=rig.pose.bones[lower].matrix.to_quaternion();qf=rig.pose.bones[end].matrix.to_quaternion()
    rest=rig.data.bones;lu,ll=data['joints']['leg_r']['lengths'];foot_delta=rig.pose.bones[end].matrix@rest[end].matrix_local.inverted();foot_points=shapes[end]@np.asarray(foot_delta)[:3,:3].T+np.asarray(foot_delta)[:3,3];contact_index=int(foot_points[:,2].argmin());patch=Vector(foot_points[contact_index]);raw_preferred=Vector(records[frame-1]['limb_bend_plane_readback']['leg_r']['chosen_anatomical_plane']);foot_axis=(foot_delta.to_3x3()@Vector((1,0,0))).normalized()
    def trial(boot_degrees,knee_degrees):
        q=Quaternion(foot_axis,math.radians(boot_degrees))@qf
        m=q.to_matrix().to_4x4();m.translation=a;delta=m@rest[end].matrix_local.inverted();points=shapes[end]@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3]
        change=patch-Vector(points[contact_index]);change.z=.015-float(points[:,2].min());target=a+change
        direction=(target-h).normalized();distance=(target-h).length;reach=min(lu+ll-1e-5,max(abs(lu-ll)+1e-5,distance));along=(lu*lu-ll*ll+reach*reach)/(2*reach);height=math.sqrt(max(0,lu*lu-along*along))
        preferred=raw_preferred-direction*raw_preferred.dot(direction);preferred.normalize();normal=Quaternion(direction,math.radians(knee_degrees))@preferred;joint=h+direction*along+normal*height;goal=h+direction*reach
        rotations=[(k-h).normalized().rotation_difference((joint-h).normalized())@qu,(a-k).normalized().rotation_difference((goal-joint).normalized())@ql];minima=[]
        for bone,position,rotation in zip((upper,lower),(h,joint),rotations):
            m=rotation.to_matrix().to_4x4();m.translation=position;delta=m@rest[bone].matrix_local.inverted();shape=shapes[bone];posed=shape@np.asarray(delta)[:3,:3].T+np.asarray(delta)[:3,3];minima.append(float(posed[:,2].min()))
        penetration=max(0,.015-min(minima));cost=1e7*penetration**2+.0003*knee_degrees**2+.003*boot_degrees**2+10*max(0,distance-reach)**2
        return dict(cost=cost,boot_pitch_adaptation_degrees=boot_degrees,knee_circle_from_capture_degrees=knee_degrees,actual_upper_lower_minimum_z=minima,ankle_goal=list(target),ankle_vertical_change=float(target.z-a.z),reach_error=float(distance-reach))
    baseline=min((trial(0,float(theta))for theta in np.linspace(-180,180,73)),key=lambda r:r['cost']);best=min((trial(float(boot),float(knee))for boot in np.linspace(-45,45,31)for knee in np.linspace(-180,180,73)),key=lambda r:r['cost'])
    fine=min((trial(float(boot),float(knee))for boot in np.linspace(best['boot_pitch_adaptation_degrees']-3,best['boot_pitch_adaptation_degrees']+3,21)for knee in np.linspace(best['knee_circle_from_capture_degrees']-5,best['knee_circle_from_capture_degrees']+5,21)),key=lambda r:r['cost'])
    rows.append(dict(frame=frame,original_fixed_boot_circle=baseline,foot_orientation_contact_candidate=fine,hip_fixed=list(h),ground_patch_xy_retained=list(patch.xy)))
(out/'crawl_boot_shin_feasibility.json').write_text(json.dumps(dict(rows=rows,scope='Actual saved geometry, fixed hip and existing ground patch XY; boot pitch and knee-circle search are counterfactual feasibility, not captured movement, chosen production motion, or art acceptance. Requires full source-roll and continuous-contact reconstruction before use.'),indent=2),'utf8');print(json.dumps(rows))
