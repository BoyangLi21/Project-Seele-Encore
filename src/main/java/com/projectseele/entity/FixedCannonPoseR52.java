package com.projectseele.entity;

import com.projectseele.physics.AnatomicalLimbConstraints;
import com.projectseele.physics.CombatBodyProfiles;
import java.util.*;
import net.minecraft.world.phys.Vec3;
import org.joml.*;

/** Bound original fixed gun only: same synchronized real grips, anatomical arm lengths and existing transition weights. */
public final class FixedCannonPoseR52
{
    private static final List<String> LIMBS=List.of("arm_l","forearm_l","wrist_l","hand_l","arm_r","forearm_r","wrist_r","hand_r");
    private static final com.projectseele.util.WeakIdentityMap<EvaUnit01Entity,Memory> MEMORY=new com.projectseele.util.WeakIdentityMap<>();
    private static final class Memory
    {long started,lastBound;boolean bound;final Map<String,Quaternionf> rotation=new HashMap<>();final Map<String,Vector3f> position=new HashMap<>();}
    private static Vector3f palm(EvaUnit01Entity e,EvaBodyPose.Sample pose,String side,float partial)
    {
        if(EvaAnatomicalHandsR45.enabled(e))return EvaAnatomicalHandsR45.contact(e,pose,side,partial);
        String name="hand_"+side;var p=new Vector3f(pose.rig.get(name).pivot());String finger="finger_middle_"+side;
        if(pose.rig.containsKey(finger))p.lerp(pose.rig.get(finger).pivot(),.55F);return pose.matrix(name).transformPosition(p);
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
        for(String side:List.of("l","r"))
        {
            Vec3 actual=gun.gripR52(side.equals("l"),partial);if(actual==null)return;Vector3f goal=inverse.transformPosition(actual.toVector3f());String hand="hand_"+side;
            var g=gun.geometryR52();var normal=com.projectseele.world.YashimaCannonMeshR52.normalR52(side.equals("l")?g.left():g.right());
            var desired=inverse.transformDirection(g.matrix(e.level().isClientSide?gun.getPosition(partial):gun.position(),gun.aimR52(e.level().isClientSide?partial:1)).transformDirection(normal.toVector3f())).normalize().negate();
            var wrist=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));var offset=palm(e,pose,side,partial).sub(wrist);
            var orientation=new Quaternionf().rotationTo(new Vector3f(offset).normalize(),desired).mul(pose.matrix(hand).getUnnormalizedRotation(new Quaternionf()).normalize());
            String parent=pose.rig.get(hand).parent();pose.rotations.put(hand,pose.matrix(parent).getUnnormalizedRotation(new Quaternionf()).normalize().invert().mul(orientation));pose.dirty();
            for(int i=0;i<3;i++)
            {
                wrist=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));
                offset=palm(e,pose,side,partial).sub(wrist);
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
