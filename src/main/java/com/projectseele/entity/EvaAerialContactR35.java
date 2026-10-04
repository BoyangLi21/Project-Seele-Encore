package com.projectseele.entity;

import com.projectseele.physics.*;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;

/** An airborne punch reaches a visible surface within the real arm length. */
public final class EvaAerialContactR35
{
    private static final ThreadLocal<Boolean> SOLVING=ThreadLocal.withInitial(()->false);
    public static void apply(EvaUnit01Entity eva,EvaBodyPose.Sample pose,float partial)
    {
        if(SOLVING.get()||EvaCombatR31.action(eva)!=EvaCombatR31.AIR_STRIKE)return;
        var target=EvaCombatR31.target(eva);var profile=CombatBodyProfiles.get(eva);
        if(target==null||!target.isAlive()||profile==null||eva.distanceTo(target)>52)return;
        // The button press precedes the actual airborne stroke. Using its
        // clock reached toward the victim during ascent, then stopped solving
        // the fist just as the downward strike began.
        float stroke=EvaCombatR31.strokeAge(eva,partial);if(stroke<0)return;
        float weight=EvaDorsalMechanism.smooth(stroke/5)*(1-EvaDorsalMechanism.smooth((stroke-9)/5));if(weight<=0)return;
        SOLVING.set(true);
        try
        {
            String side=EvaGameplayMotionR32.side(eva,"air_strike"),hand="hand_"+side,arm="arm_"+side;
            float angle=(180-EvaAirTransportR31.frameYaw(eva,partial))*Mth.DEG_TO_RAD;Vec3 origin=eva.level().isClientSide?eva.getPosition(partial):eva.position();
            var localShoulder=pose.matrix(arm).transformPosition(new Vector3f(pose.rig.get(arm).pivot()));var worldShoulder=new Vector3f(localShoulder).mul(EvaScale.RENDER_SCALE).rotateY(angle);Vec3 from=origin.add(worldShoulder.x,worldShoulder.y,worldShoulder.z);
            var box=target.getBoundingBox();Vec3 centre=new Vec3(box.getCenter().x,box.minY+box.getYsize()*.73,box.getCenter().z);
            Vec3 surface=CombatBodyContacts.clip(target,from,centre,0).orElse(centre);
            var goal=surface.subtract(origin).toVector3f().rotateY(-angle).div(EvaScale.RENDER_SCALE);
            var point=new Vector3f(pose.rig.get(hand).pivot());String finger="finger_middle_"+side;
            if(pose.rig.containsKey(finger))point.lerp(pose.rig.get(finger).pivot(),.55F);
            var fistOffset=pose.matrix(hand).transformDirection(point.sub(pose.rig.get(hand).pivot()));goal.sub(fistOffset);
            var current=pose.matrix(hand).transformPosition(new Vector3f(pose.rig.get(hand).pivot()));current.lerp(goal,weight);
            AnatomicalLimbConstraints.reachHand(pose,profile,side,current);
        }
        finally{SOLVING.set(false);}
    }
    private EvaAerialContactR35(){}
}
