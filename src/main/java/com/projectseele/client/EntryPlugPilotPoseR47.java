package com.projectseele.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderPlayerEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Quaternionf;
import java.util.ArrayDeque;
import java.util.UUID;

/** Rotate the whole seated driver in the capsule frame, including clothing and limbs. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EntryPlugPilotPoseR47
{
    private static final ThreadLocal<ArrayDeque<UUID>> PLAYER_PASSES=ThreadLocal.withInitial(ArrayDeque::new);

    public static boolean push(PoseStack pose,LivingEntity rider,float partial)
    {
        if(!(rider.getVehicle() instanceof EntryPlugCarrierEntity plug)||(plug.isLockedToEva()&&!plug.usesPhysicalPilotSeatR52())
                ||!plug.hasCanonicalPose())return false;
        var frame=plug.getInterpolatedCanonicalTransform(partial);
        // Cancel vanilla body yaw after applying the same backrest frame as
        // the authoritative seat/eye markers. A negative recline put the head
        // at the foot end of the capsule.
        float headYaw=Mth.rotLerp(partial,rider.yHeadRotO,rider.yHeadRot);
        float vehicleYaw=Mth.rotLerp(partial,plug.yBodyRotO,plug.yBodyRot);
        float headDelta=Mth.clamp(Mth.wrapDegrees(headYaw-vehicleYaw),-85F,85F);
        float bodyYaw=headYaw-headDelta;
        if(headDelta*headDelta>2500F)bodyYaw+=headDelta*.2F;
        var rotation=new Quaternionf(frame.qx(),frame.qy(),frame.qz(),frame.qw())
                .rotateX(com.projectseele.world.EntryPlugKinematics.pilotReclineRadiansR48())
                .rotateY((bodyYaw-180F)*Mth.DEG_TO_RAD);
        pose.pushPose();
        // Vanilla interpolates the passenger's separate movement packets.
        // Anchor the whole body to the shell's pose sample instead, or the
        // rotating capsule moves out from under its apparently standing rider.
        var seat=frame.transformPoint(com.projectseele.world.EntryPlugKinematics.PILOT_SEAT_P);
        pose.translate(seat.x-Mth.lerp((double)partial,rider.xOld,rider.getX()),
                seat.y-rider.getBbHeight()*.5-Mth.lerp((double)partial,rider.yOld,rider.getY()),
                seat.z-Mth.lerp((double)partial,rider.zOld,rider.getZ()));
        pose.translate(0,rider.getBbHeight()*.5,0);
        pose.mulPose(rotation);
        pose.translate(0,-rider.getBbHeight()*.5,0);
        return true;
    }

    @SubscribeEvent(priority=EventPriority.LOWEST)
    public static void before(RenderPlayerEvent.Pre event)
    {
        if(push(event.getPoseStack(),event.getEntity(),event.getPartialTick()))
            PLAYER_PASSES.get().push(event.getEntity().getUUID());
    }

    @SubscribeEvent(priority=EventPriority.LOWEST)
    public static void after(RenderPlayerEvent.Post event)
    {
        var passes=PLAYER_PASSES.get();
        if(!passes.isEmpty()&&passes.peek().equals(event.getEntity().getUUID()))
        {passes.pop();event.getPoseStack().popPose();}
    }

    private EntryPlugPilotPoseR47(){}
}
