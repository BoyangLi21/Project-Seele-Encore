"""Isolate the earliest source-to-rig hinge calibration, before foot IK.

This exports diagnostic poses only. No runtime model/clip is replaced here.
"""
from pathlib import Path
import copy,hashlib,json
import numpy as np
from scipy.spatial.transform import Rotation as R
import author_gameplay_motion_r32 as common
from author_combat_r35 import Actor
from rebuild_stance_hinges_r41 import reconstruct
from retarget_human_r12 import Retarget,axes

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/repair_r43/hip_diagnosis'

class AnatomicalRetarget(Retarget):
    def __init__(self,human,angel=False,calibrated_trunk=True):
        super().__init__(human,angel,calibrated_trunk)
        if angel:raise ValueError('The angel has its own measured profile; this experiment is EVA only')
        for side in ('l','r'):
            # The current EVA knee constraint is explicitly around -X. Its
            # sculpted bow cannot provide an anatomical twist reference.
            axis=np.array([-1.,0,0]);source=self.refq['hip_'+side].apply(human.hinge_local['leg_'+side])
            for a,b,bone,vector in (('hip','knee','leg_',self.knees[side]-self.P['leg_'+side]),
                                   ('knee','ankle','shin_',self.P['foot_'+side]-self.knees[side])):
                direction=self.ref[b+'_'+side]-self.ref[a+'_'+side]
                self.limb_reference[bone+side]=(a+'_'+side,R.from_matrix(axes(direction,source)@axes(vector,axis).T))

def main():
    OUT.mkdir(parents=True,exist_ok=True);common.OUT=OUT/'source';common.OUT.mkdir(exist_ok=True);reports=[]
    for key in range(5):
        actor=Actor(key);human,meta=common.human('ArmsJabBoxer',True)
        before=Retarget(human,False,True);candidate=AnatomicalRetarget(human);names=list(actor.rig.rig)
        poses={'before':[],'candidate':[]};geometry=[]
        for side in ('l','r'):
            u=actor.knees[side]-actor.P['leg_'+side];v=actor.P['foot_'+side]-actor.knees[side]
            old=np.cross(u,v);old/=np.linalg.norm(old)
            if old[0]<0:old=-old
            geometry.append(dict(side=side,geometric_plane_normal=old.tolist(),anatomical_axis=[-1,0,0],
                unsigned_axis_difference_degrees=float(np.degrees(np.arccos(np.clip(abs(old[0]),0,1))))))
        errors=[]
        for frame in range(1,human.frames):
            source,rotations=human.sample(frame);pair={}
            for label,retarget in (('before',before),('candidate',candidate)):
                pose,travel,_=retarget.pose(frame,support='air')
                # Only the candidate converts the already measured source thigh
                # orientation to the fixed anatomical knee without replacing
                # its bend plane by a generic world-forward pole.
                if label=='candidate':
                    for side in ('l','r'):
                        goal=pose.point('foot_'+side).copy();orientation=R.from_matrix(pose.matrix('foot_'+side)[:3,:3])
                        prior=pose.q['leg_'+side];reconstruct(actor,pose,side,goal,orientation,prior)
                pair[label]=pose
                poses[label].append(dict(source_frame=frame,frame=actor.rig.encode(pose,contacts=(False,False),bone_names=names),root_travel=travel.tolist()))
            for side in ('l','r'):
                name='leg_'+side;old=pair['before'];new=pair['candidate']
                errors.append(dict(source_frame=frame,side=side,
                    thigh_rotation_difference_degrees=float(np.degrees((old.q[name].inv()*new.q[name]).magnitude())),
                    hip_difference_blocks=float(np.linalg.norm(old.point(name)-new.point(name))*5/16),
                    foot_difference_blocks=float(np.linalg.norm(old.point('foot_'+side)-new.point('foot_'+side))*5/16)))
        record=dict(rig=key,source=meta,geometry=geometry,deltas=errors,bones=names,poses=poses,
            scope='Raw calibrated capture, before floor contacts/timing/blends and runtime skin; candidate not accepted or installed')
        (OUT/f'rig_{key}.json').write_text(json.dumps(record,separators=(',',':')),'utf8')
        reports.append(dict(rig=key,geometry=geometry,first_frame=errors[:2],frames=human.frames-1))
    (OUT/'summary.json').write_text(json.dumps(reports,indent=2),'utf8');print(json.dumps(reports),flush=True)

if __name__=='__main__':main()
