package com.projectseele.entity;

import com.projectseele.physics.AnatomicalLimbConstraints;
import com.projectseele.physics.CombatBodyProfiles;
import java.util.*;
import org.joml.*;

/** Bound original fixed gun only: same synchronized real grips, anatomical arm lengths and existing transition weights. */
public final class FixedCannonPoseR52
{
    private static final List<String> LIMBS=List.of("arm_l","forearm_l","wrist_l","hand_l","arm_r","forearm_r","wrist_r","hand_r");
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Memory> MEMORY=new com.projectseele.util.WeakIdentityMap<>();
    private static final class Memory
    {long started,lastBound;boolean bound;final Map<String,Quaternionf> rotation=new HashMap<>();final Map<String,Vector3f> position=new HashMap<>();}
    private static Vector3f localPalm(EvaBodyPose.Sample pose,String side)
    {
        String name="hand_"+side;var p=new Vector3f(pose.rig.get(name).pivot());String finger="finger_middle_"+side;
        if(pose.rig.containsKey(finger))p.lerp(pose.rig.get(finger).pivot(),.55F);return p;
    }
    /** The same two measured contact joints, before the changing body hand transform. */
    static Vector3f localPalm(EvaAnatomicalHandsR45.Rig rig,EvaAnatomicalHandsR45.Pose pose,String side)
    {
        return localFinger(rig,pose,"r45_hand_"+side+"_index_2")
                .lerp(localFinger(rig,pose,"r45_hand_"+side+"_middle_2"),.5F);
    }
    private static Vector3f localFinger(EvaAnatomicalHandsR45.Rig rig,EvaAnatomicalHandsR45.Pose pose,String name)
    {
        var joint=rig.named().get(name);
        return fingerMatrix(rig,pose,name).mul(joint.inverseBind()).transformPosition(new Vector3f(joint.head()));
    }
    private static Matrix4f fingerMatrix(EvaAnatomicalHandsR45.Rig rig,EvaAnatomicalHandsR45.Pose pose,String name)
    {
        var joint=rig.named().get(name);if(joint==null)return new Matrix4f();
        var p=joint.pivot();return fingerMatrix(rig,pose,joint.parent()).translate(p).rotate(pose.rotations().get(name)).translate(-p.x,-p.y,-p.z);
    }
    public static void apply(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        if(e.isExperimentalUnit()||e.isBerserk()||e.isFirstBattleActive()||e.isNervLogisticsLocked()||EvaAirTransportR31.active(e)
                ||EvaMechanicalFrameR52.serviceSourceHeldR52(e)||!e.isPoweredOn())return;
        long now=e.level().getGameTime();var gun=e.fixedCannonBodyR52();
        boolean bound=e.fixedCannonOperatingR52()&&e.getWeapon()==EvaUnit01Entity.WEAPON_CANNON&&e.isPilotProne()
                &&e.rifleStanceLevel(partial)>2.99F&&gun!=null&&gun.readyR52()&&gun.loadedR52();
        var memory=MEMORY.get(e);if(!bound)
        {
            if(memory==null)return;memory.bound=false;float weight=1-EvaPoseBlendR51.smooth((now+partial-memory.lastBound)/12F);
            if(weight<=0){MEMORY.remove(e);return;}
            for(String name:LIMBS)if(pose.rig.containsKey(name)&&memory.rotation.containsKey(name))
            {pose.rotations.put(name,new Quaternionf(pose.rotations.get(name)).slerp(memory.rotation.get(name),weight));pose.positions.put(name,new Vector3f(pose.positions.get(name)).lerp(memory.position.get(name),weight));}
            pose.dirty();return;
        }
        if(memory==null){memory=new Memory();MEMORY.put(e,memory);}if(!memory.bound){memory.started=now;memory.bound=true;}memory.lastBound=now;
        var baseRotation=new HashMap<String,Quaternionf>();var basePosition=new HashMap<String,Vector3f>();
        for(String name:LIMBS)if(pose.rig.containsKey(name)){baseRotation.put(name,new Quaternionf(pose.rotations.get(name)));basePosition.put(name,new Vector3f(pose.positions.get(name)));}
        var inverse=EvaRifleKinematics.world(e,partial).invert();var profile=CombatBodyProfiles.get(e);if(profile==null)return;
        var g=gun.geometryR52();if(g==null)return;
        var gunMatrix=g.matrix(e.level().isClientSide?gun.getPosition(partial):gun.position(),gun.aimR52(e.level().isClientSide?partial:1));
        var handRig=EvaAnatomicalHandsR45.enabled(e)?EvaAnatomicalHandsR45.forEntityR53(e):null;
        // Finger controls do not change while the arm IK iterates. Sampling all
        // 34 finger joints eight times per body sample only repeats the same work.
        var handPose=handRig==null?null:EvaAnatomicalHandsR45.sample(e,partial);
        for(String side:List.of("l","r"))
        {
            var marker=side.equals("l")?g.left():g.right();Vector3f goal=inverse.transformPosition(gunMatrix.transformPosition(marker.toVector3f()));String hand="hand_"+side;
            var normal=com.projectseele.world.YashimaCannonMeshR52.normalR52(marker);
            var desired=inverse.transformDirection(gunMatrix.transformDirection(normal.toVector3f())).normalize().negate();
            var contact=handRig==null?localPalm(pose,side):localPalm(handRig,handPose,side);
            var handMatrix=pose.matrix(hand);var wrist=handMatrix.transformPosition(new Vector3f(pose.rig.get(hand).pivot()));var offset=handMatrix.transformPosition(new Vector3f(contact)).sub(wrist);
            var orientation=new Quaternionf().rotationTo(new Vector3f(offset).normalize(),desired).mul(pose.matrix(hand).getUnnormalizedRotation(new Quaternionf()).normalize());
            String parent=pose.rig.get(hand).parent();pose.rotations.put(hand,pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(orientation));pose.dirty();
            for(int i=0;i<3;i++)
            {
                handMatrix=pose.matrix(hand);wrist=handMatrix.transformPosition(new Vector3f(pose.rig.get(hand).pivot()));
                offset=handMatrix.transformPosition(new Vector3f(contact)).sub(wrist);
                AnatomicalLimbConstraints.reachHand(pose,profile,side,new Vector3f(goal).sub(offset));pose.dirty();
            }
        }
        float weight=EvaPoseBlendR51.smooth((now+partial-memory.started)/12F);
        for(String name:LIMBS)if(baseRotation.containsKey(name))
        {
            pose.rotations.put(name,new Quaternionf(baseRotation.get(name)).slerp(pose.rotations.get(name),weight));pose.positions.put(name,new Vector3f(basePosition.get(name)).lerp(pose.positions.get(name),weight));
            memory.rotation.put(name,new Quaternionf(pose.rotations.get(name)));memory.position.put(name,new Vector3f(pose.positions.get(name)));
        }
        pose.dirty();
    }
    private FixedCannonPoseR52(){}
}
