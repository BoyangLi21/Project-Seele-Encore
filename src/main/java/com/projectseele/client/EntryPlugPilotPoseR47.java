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
        if(!(rider.getVehicle() instanceof EntryPlugCarrierEntity plug)||plug.isLockedToEva()
                ||!plug.hasCanonicalPose())return false;
        var frame=plug.getInterpolatedCanonicalTransform(partial);
        // The existing seat/eye markers lean toward the insertion tip: +Y_P is
        // the hatch, -Z_P the nose. Vanilla's seated upright torso ignores this.
        var rotation=new Quaternionf(frame.qx(),frame.qy(),frame.qz(),frame.qw())
                .rotateX(-51.34F*Mth.DEG_TO_RAD)
                .rotateY(Mth.rotLerp(partial,rider.yBodyRotO,rider.yBodyRot)*Mth.DEG_TO_RAD);
        pose.pushPose();
        pose.translate(0,.75,0);
        pose.mulPose(rotation);
        pose.translate(0,-.75,0);
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
