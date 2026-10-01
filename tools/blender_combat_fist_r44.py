"""Measured three-phalange target fist; no capture fingers are invented."""
import math
from mathutils import Vector


def apply(rig, targets, row, side, closure=1.):
    rest=rig.data.bones;hand='hand_'+side;root=rest[hand].head_local
    delta=targets[hand].rotation_quaternion@rest[hand].matrix_local.to_quaternion().inverted()
    long=(rest['finger_middle_'+side].head_local-root).normalized()
    across=(rest['finger_little_'+side].head_local-rest['finger_index_'+side].head_local).normalized()
    normal=across.cross(long).normalized()
    if(rest['finger_middle_tip_'+side].head_local-rest['finger_middle_'+side].head_local).dot(normal)<0:normal.negate()
    parent_world={hand:targets[hand].rotation_quaternion}
    for digit in('index','middle','ring','little','thumb'):
        chain=[f'finger_{digit}{suffix}_{side}'for suffix in('','_tip','_distal')]
        chain=[n for n in chain if n in rest]
        for j,name in enumerate(chain):
            bone=rest[name];original=(bone.tail_local-bone.head_local).normalized()
            if digit=='thumb':
                across_to_index=(rest['finger_index_'+side].head_local-bone.head_local).normalized()
                aim=(across_to_index*.78+normal*.62-long*.25).normalized()if j==0 else(across_to_index*.25-long*.85+normal*.4).normalized()
            else:
                angle=math.radians((48,140,190)[min(j,2)])
                aim=(long*math.cos(angle)+normal*math.sin(angle)).normalized()
            direction=original.lerp(aim,closure).normalized()
            wanted=delta@original.rotation_difference(direction)@bone.matrix_local.to_quaternion()
            parent=bone.parent.name
            baseline=parent_world[parent]@rest[parent].matrix_local.to_quaternion().inverted()@bone.matrix_local.to_quaternion()
            pose=rig.pose.bones[name];pose.rotation_mode='QUATERNION';pose.rotation_quaternion=baseline.inverted()@wanted
            row['local'][name]=pose.matrix_basis.copy();parent_world[name]=wanted
