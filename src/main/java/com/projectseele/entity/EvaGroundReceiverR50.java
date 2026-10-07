package com.projectseele.entity;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

/** Persisted receiving supports capture the displayed pose before aligning the load. */
public final class EvaGroundReceiverR50
{
    public static final int CLAMP_TICKS=40, LIFT_TICKS=40, ALIGN_TICKS=240, LOWER_TICKS=40,
            TOTAL_TICKS=CLAMP_TICKS+LIFT_TICKS+ALIGN_TICKS+LOWER_TICKS;
    public static boolean active(EvaUnit01Entity eva)
    {return EvaAirTransportR31.cradleStateR50(eva).getBoolean("GroundReceiverR50");}
    public static int age(EvaUnit01Entity eva)
    {return EvaAirTransportR31.cradleStateR50(eva).getInt("GroundAgeR50");}
    public static void begin(EvaUnit01Entity eva)
    {
        if(eva.level().isClientSide||active(eva))return;
        // An aircraft may already own the pose. Capture that exact pose before
        // replacing its frame; neither shutdown nor prone flags are a new pose.
        var frozen=EvaShutdownR30.encode(EvaBodyPose.sample(eva,1));
        com.projectseele.physics.CombatBodyDynamics.cancel(eva);
        eva.disconnectForAirliftR32();
        eva.stowHandsForShutdownR30();
        var tag=new CompoundTag();tag.putBoolean("Active",true);tag.putBoolean("GroundReceiverR50",true);
        tag.put("Origin",frozen);tag.putFloat("GroundYawR50",eva.getYRot());
        tag.putDouble("GroundDeckY",-410);tag.putDouble("GroundDeckOffset",eva.getY()+410);
        tag.putInt("GroundAgeR50",0);tag.putInt("GroundPreviousAgeR50",0);
        EvaAirTransportR31.cradleStateR50(eva,tag);
        eva.setNervLogisticsLocked(true);eva.setNoGravity(true);eva.setDeltaMovement(Vec3.ZERO);
        eva.setRecoveryRackR39(true);eva.setCarrierRiseProgress(0);
    }
    public static EvaBodyPose.Sample poseAt(EvaUnit01Entity eva,float age)
    {return sample(eva,EvaBodyPose.neutralForTransportR32(eva),EvaAirTransportR31.cradleStateR50(eva),age);}
    static EvaBodyPose.Sample sample(EvaUnit01Entity eva,EvaBodyPose.Sample result,CompoundTag tag,float age)
    {
        EvaShutdownR30.decode(tag.getCompound("Origin"),result);
        float t=smooth((age-CLAMP_TICKS-LIFT_TICKS)/ALIGN_TICKS);
        if(t>0)for(var bone:result.rig.values())
        {
            var goal=new Quaternionf(bone.bindRotation());
            if(bone.name().equals("root"))goal=new Quaternionf().rotationY(
                    (tag.getFloat("GroundYawR50")-EvaUnit01Entity.SILO_BAY_YAW)*Mth.DEG_TO_RAD).mul(goal);
            result.rotations.get(bone.name()).slerp(goal,t);
            result.positions.get(bone.name()).mul(1-t);
            if(bone.name().equals("root"))result.positions.get(bone.name()).y-=(float)(tag.getDouble("GroundDeckOffset")/EvaScale.RENDER_SCALE)*t;
        }
        if(t>0)EvaBodyPose.preserveJointCentres(result);result.dirty();
        // The receiving pistons, rather than the ankles, support an intermediate
        // reclined shape. Keep its actual lowest mesh vertex above the deck.
        double low=Double.POSITIVE_INFINITY;
        for(var point:EvaBodyPose.carrierVerticesR40(eva,result))low=Math.min(low,point.y);
        double deck=-tag.getDouble("GroundDeckOffset");
        if(t>0&&Double.isFinite(low)&&low<deck)
        {result.positions.get("root").y+=(float)((deck-low)/EvaScale.RENDER_SCALE);result.dirty();}
        // Lift clear of the physical edge rail before rotating the feet; then
        // lower the already aligned load onto the fixed transfer bed.
        float lift=2F*smooth((age-CLAMP_TICKS)/LIFT_TICKS)*smooth((TOTAL_TICKS-age)/LOWER_TICKS);
        result.positions.get("root").y+=lift/EvaScale.RENDER_SCALE;result.dirty();
        return result;
    }
    private static float smooth(float t){t=Mth.clamp(t,0,1);return t*t*t*(t*(t*6-15)+10);}
    public static void acceptStep(EvaUnit01Entity eva,int next)
    {
        var tag=EvaAirTransportR31.cradleStateR50(eva);int old=tag.getInt("GroundAgeR50");
        tag.putInt("GroundPreviousAgeR50",old);tag.putInt("GroundAgeR50",Math.min(TOTAL_TICKS,next));
        EvaAirTransportR31.cradleStateR50(eva,tag);eva.setCarrierRiseProgress(Math.min(1,next/(float)CLAMP_TICKS));
    }
    public static void hold(EvaUnit01Entity eva)
    {
        var tag=EvaAirTransportR31.cradleStateR50(eva);
        if(tag.getInt("GroundPreviousAgeR50")==tag.getInt("GroundAgeR50"))return;
        tag.putInt("GroundPreviousAgeR50",tag.getInt("GroundAgeR50"));EvaAirTransportR31.cradleStateR50(eva,tag);
    }
    public static void finish(EvaUnit01Entity eva)
    {
        if(!active(eva)||age(eva)<TOTAL_TICKS)return;
        double deck=EvaAirTransportR31.cradleStateR50(eva).getDouble("GroundDeckY");
        EvaAirTransportR31.clear(eva);
        eva.moveOnNervCarrier(eva.getX(),deck,eva.getZ(),EvaUnit01Entity.SILO_BAY_YAW);
        eva.setCarrierRiseProgress(1);eva.setRecoveryRackR39(false);
    }
    private EvaGroundReceiverR50() {}
}
