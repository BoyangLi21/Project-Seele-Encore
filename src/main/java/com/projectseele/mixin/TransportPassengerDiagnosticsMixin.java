package com.projectseele.mixin;

import com.projectseele.ProjectSeele;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.RelativeMovement;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import java.util.Arrays;
import java.util.Set;

/** Observes corrections during explicit transit reviews without changing packet handling. */
@Mixin(ServerGamePacketListenerImpl.class)
public abstract class TransportPassengerDiagnosticsMixin
{
    @Shadow public ServerPlayer player;
    @Inject(method="teleport(DDDFFLjava/util/Set;)V",at=@At("HEAD"))
    private void projectSeele$traceCorrection(double x,double y,double z,float yaw,float pitch,Set<RelativeMovement> relative,CallbackInfo callback)
    {
        String mode=System.getProperty("projectseele.regionalBuild","");
        if(!mode.contains("riding")&&!mode.equals("r44-transit-all")&&!Boolean.getBoolean("projectseele.r45TransportTrace"))return;
        ProjectSeele.LOGGER.info("TRANSIT SERVER TELEPORT from={} to=({}, {}, {}) noPhysics={} relative={} caller={}",
                player.position(),x,y,z,player.noPhysics,relative,Arrays.stream(Thread.currentThread().getStackTrace()).skip(2).limit(8).toList());
    }
}
