package com.projectseele.entity;

import com.projectseele.util.WeakIdentityMap;
import net.minecraft.core.BlockPos;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/**
 * Walking up to a wall taller than a step, the stride closes in to a
 * standing stance as the wall comes within 16 blocks: thighs hanging
 * straight down in the world, soles flat. The walking stride reached five
 * blocks past the body's box, so the leading foot and knee went into the
 * wall it stopped against, and a ledge climb started from that stride.
 * Kerbs a step high are left to the step-up. Continuous in the distance and
 * eased over time; applied to the pose, so a climb starting here starts
 * from the gathered stance.
 */
final class EvaWallStanceR57
{
    private static final float STEP=20,NEAR=16,SPAN=7.5F,EASE_TICKS=3;
    private record Eased(float value,float time) {}
    private static final WeakIdentityMap<EvaUnit01Entity,Eased> EASED=new WeakIdentityMap<>();

    static void gather(EvaUnit01Entity e,EvaBodyPose.Sample pose,float partial)
    {
        float weight=weight(e,partial);
        if(weight<.005F)return;
        var root=pose.rotations.get("root");var pelvis=pose.rotations.get("torso_lower");
        if(root==null||pelvis==null)return;
        var hips=new Quaternionf(root).mul(pelvis);
        for(String side:new String[]{"l","r"})
        {
            float out=(side.equals("l")?-3:3)*Mth.DEG_TO_RAD;
            var leg=pose.rotations.get("leg_"+side);var shin=pose.rotations.get("shin_"+side);var foot=pose.rotations.get("foot_"+side);
            if(leg==null||shin==null||foot==null)continue;
            // Thigh straight down in the model, whatever the pelvis' tilt.
            leg.slerp(new Quaternionf(hips).invert().mul(new Quaternionf().rotationZ(out)),weight);
            shin.slerp(new Quaternionf().rotationX(-8*Mth.DEG_TO_RAD),weight);
            // Sole level with the root.
            var above=new Quaternionf(hips).mul(leg).mul(shin);
            if(pose.rotations.containsKey("ankle_"+side))above.mul(pose.rotations.get("ankle_"+side));
            foot.slerp(new Quaternionf(above).invert().mul(root),weight);
        }
        // The arms hang at the sides, elbows nearly straight: the idle's
        // forearms, held forward, went five blocks into the wall.
        for(String side:new String[]{"l","r"})
        {
            var arm=pose.rotations.get("arm_"+side);var forearm=pose.rotations.get("forearm_"+side);
            if(arm==null||forearm==null)continue;
            arm.slerp(new Quaternionf().rotationZ((side.equals("l")?-8:8)*Mth.DEG_TO_RAD),weight);
            forearm.slerp(new Quaternionf().rotationX(15*Mth.DEG_TO_RAD),weight);
        }
        EvaBodyPose.preserveJointCentres(pose);
    }

    private static float weight(EvaUnit01Entity e,float partial)
    {
        float wanted=0;
        if(e.onGround())
        {
            Vec3 at=e.getPosition(partial),forward=Vec3.directionFromRotation(0,Mth.rotLerp(partial,e.yBodyRotO,e.yBodyRot));
            for(float d=EvaScale.NORMAL_WIDTH*.5F;d<=NEAR+8;d+=1)
            {
                double x=at.x+forward.x*d,z=at.z+forward.z*d;
                if(solid(e,x,at.y+12,z)&&solid(e,x,at.y+STEP+2,z)){wanted=Mth.clamp((NEAR-d)/SPAN,0,1);break;}
            }
            wanted=wanted*wanted*(3-2*wanted);
        }
        float now=e.level().getGameTime()+partial;var last=EASED.get(e);float value=wanted;
        if(last!=null&&now>=last.time())value=last.value()+(wanted-last.value())*Math.min(1,(now-last.time())/EASE_TICKS);
        else if(last!=null)value=last.value();
        EASED.put(e,new Eased(value,now));
        return value;
    }
    private static boolean solid(EvaUnit01Entity e,double x,double y,double z)
    {
        var pos=BlockPos.containing(x,y,z);var state=e.level().getBlockState(pos);if(state.isAir())return false;
        var shape=state.getCollisionShape(e.level(),pos);
        if(shape.isEmpty()||EvaObstacleCollision.ignores(e,state,pos,shape))return false;
        for(var box:shape.toAabbs())if(box.move(pos).contains(x,y,z))return true;
        return false;
    }
    private EvaWallStanceR57(){}
}
