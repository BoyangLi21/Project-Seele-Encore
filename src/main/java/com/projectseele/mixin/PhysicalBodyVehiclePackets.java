package com.projectseele.mixin;

import com.projectseele.physics.CombatBodyDynamics;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaSwordActionsR45;
import com.projectseele.entity.EvaFieldActionsR45;
import com.projectseele.entity.EvaMechanicalFrameR52;
import net.minecraft.network.protocol.game.ClientboundMoveVehiclePacket;
import net.minecraft.network.protocol.game.ServerboundMoveVehiclePacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
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
    @Unique private java.util.UUID seele$mechanicalVehicle;

    @Inject(method="tick",at=@At("HEAD"))
    private void seele$rememberMechanicalOwner(CallbackInfo callback)
    {
        // A correctly passive client sends no vehicle packets while carried.
        // Remember ownership on the server tick so release still rebases its
        // first ordinary packet after the final rail interpolation sample.
        var eva=com.projectseele.world.EvaPilotResolver.controlTarget(player);
        if(eva!=null&&EvaMechanicalFrameR52.active(eva))
            seele$mechanicalVehicle=eva.getUUID();
    }
    @Inject(method="handleMoveVehicle",at=@At("HEAD"),cancellable=true)
    private void seele$serverBodyOwnsPosition(ServerboundMoveVehiclePacket packet,CallbackInfo callback)
    {
        if(!player.serverLevel().getServer().isSameThread())return;
        var controlled=com.projectseele.world.EvaPilotResolver.controlTarget(player);
        if(controlled!=null&&EvaMechanicalFrameR52.active(controlled))
        {
            // During insertion the root vehicle can still be the capsule.
            // The original airframe owns both forms of the passenger chain.
            seele$mechanicalVehicle=controlled.getUUID();
            var root=player.getRootVehicle();
            lastVehicle=root;vehicleFirstGoodX=vehicleLastGoodX=root.getX();vehicleFirstGoodY=vehicleLastGoodY=root.getY();vehicleFirstGoodZ=vehicleLastGoodZ=root.getZ();aboveGroundVehicleTickCount=0;
            callback.cancel();return;
        }
        if(!(player.getRootVehicle() instanceof LivingEntity actor))
        {if(controlled==null)seele$mechanicalVehicle=null;return;}
        if(actor.getUUID().equals(seele$mechanicalVehicle))
        {
            // A network batch can contain several pre-release positions.
            // Finish the handoff when the driver acknowledges the real frame,
            // not after discarding just the first packet in that batch.
            lastVehicle=actor;vehicleFirstGoodX=vehicleLastGoodX=actor.getX();vehicleFirstGoodY=vehicleLastGoodY=actor.getY();vehicleFirstGoodZ=vehicleLastGoodZ=actor.getZ();aboveGroundVehicleTickCount=0;
            if(actor.distanceToSqr(packet.getX(),packet.getY(),packet.getZ())>36)
            {
                player.connection.send(new ClientboundMoveVehiclePacket(actor));
                player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetEntityMotionPacket(actor));
                callback.cancel();return;
            }
            seele$mechanicalVehicle=null;
        }
        seele$mechanicalVehicle=null;
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
