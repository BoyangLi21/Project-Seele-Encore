package com.projectseele.mixin;

import com.projectseele.physics.CombatBodyDynamics;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaSwordActionsR45;
import com.projectseele.entity.EvaFieldActionsR45;
import net.minecraft.network.protocol.game.ClientboundMoveVehiclePacket;
import net.minecraft.network.protocol.game.ServerboundMoveVehiclePacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ServerGamePacketListenerImpl.class)
public abstract class PhysicalBodyVehiclePackets
{
    @Shadow public ServerPlayer player;
    @Shadow private net.minecraft.world.entity.Entity lastVehicle;
    @Shadow private double vehicleFirstGoodX,vehicleFirstGoodY,vehicleFirstGoodZ,vehicleLastGoodX,vehicleLastGoodY,vehicleLastGoodZ;
    @Shadow private int aboveGroundVehicleTickCount;
    @Inject(method="handleMoveVehicle",at=@At("HEAD"),cancellable=true)
    private void seele$serverBodyOwnsPosition(ServerboundMoveVehiclePacket packet,CallbackInfo callback)
    {
        if(!player.serverLevel().getServer().isSameThread()||!(player.getRootVehicle() instanceof LivingEntity actor))return;
        boolean physical=CombatBodyDynamics.active(actor)||actor instanceof EvaUnit01Entity eva
                &&(eva.isBerserk()||CombatBodyDynamics.ownsGroundAction(eva)
                    ||EvaShutdownR30.disabled(eva)||eva.isNervLogisticsLocked()||eva.hasActiveCarrierMotion()
                    ||EvaAirTransportR31.active(eva)||eva.isLaunchSequenceActive()||eva.isFirstBattleActive()
                    ||EvaSwordActionsR45.active(eva)||EvaFieldActionsR45.active(eva));
        if(physical||CombatBodyDynamics.recentHandoff(actor))
        {
            lastVehicle=actor;vehicleFirstGoodX=vehicleLastGoodX=actor.getX();vehicleFirstGoodY=vehicleLastGoodY=actor.getY();vehicleFirstGoodZ=vehicleLastGoodZ=actor.getZ();aboveGroundVehicleTickCount=0;
            if(physical||actor.distanceToSqr(packet.getX(),packet.getY(),packet.getZ())>36)
            {
                callback.cancel();
                // A stale client endpoint must never move a powerless or
                // mechanically carried original EVA back to a former pad.
                if(actor.distanceToSqr(packet.getX(),packet.getY(),packet.getZ())>.0001
                        ||Math.abs(net.minecraft.util.Mth.wrapDegrees(actor.getYRot()-packet.getYRot()))>.01F
                        ||Math.abs(actor.getXRot()-packet.getXRot())>.01F)
                    player.connection.send(new ClientboundMoveVehiclePacket(actor));
            }
            else CombatBodyDynamics.acknowledgeHandoff(actor);
        }
    }
}
