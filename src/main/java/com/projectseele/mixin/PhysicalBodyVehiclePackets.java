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
        if(eva!=null&&(eva.fixedCannonOperatingR52()||EvaMechanicalFrameR52.active(eva)))
            seele$mechanicalVehicle=eva.getUUID();
    }
    @Inject(method="handleMoveVehicle",at=@At("HEAD"),cancellable=true)
    private void seele$serverBodyOwnsPosition(ServerboundMoveVehiclePacket packet,CallbackInfo callback)
    {
        if(!player.serverLevel().getServer().isSameThread())return;
        var controlled=com.projectseele.world.EvaPilotResolver.controlTarget(player);
        if(controlled!=null&&(controlled.fixedCannonOperatingR52()||EvaMechanicalFrameR52.active(controlled)))
        {
            // During insertion the root vehicle can still be the capsule.
            // The original airframe owns both forms of the passenger chain.
            seele$mechanicalVehicle=controlled.getUUID();
            var root=player.getRootVehicle();
            lastVehicle=root;vehicleFirstGoodX=vehicleLastGoodX=root.getX();vehicleFirstGoodY=vehicleLastGoodY=root.getY();vehicleFirstGoodZ=vehicleLastGoodZ=root.getZ();aboveGroundVehicleTickCount=0;
            // A packet already in flight before the binding flag arrived must
            // not restore the pilot's former position or steering yaw.
            if(controlled.fixedCannonOperatingR52()&&(root.distanceToSqr(packet.getX(),packet.getY(),packet.getZ())>.0001
                    ||Math.abs(net.minecraft.util.Mth.wrapDegrees(root.getYRot()-packet.getYRot()))>.01F
                    ||Math.abs(root.getXRot()-packet.getXRot())>.01F))
                player.connection.send(new ClientboundMoveVehiclePacket(root));
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
        // R64 (M3): a server that is not its pilot's own machine sets a vehicle back that has gone more than 10
        // blocks from where it stood as the tick began ("moved too quickly"). A Unit's fast run is 9.45 blocks a
        // tick over the ground: two of its packets in one tick, one going up a slope, or a run's step onto a
        // ledge over 10 blocks high (its step is 20) are all past that, and the Unit is set back each time. That
        // cannot be seen where the pilot hosts the game, which is where every capture is made, and fits the two
        // faults filmed on the server (the body flipping on a slope, hanging at its top) better than anything
        // else found. For a Unit of the planted model the measure starts from this packet, as far as a Unit can
        // have gone since its last (a fast run's tick and a full step up, with room for a second packet); the
        // move itself is still made again on the server and set back if the Unit could not have made it.
        if(!callback.isCancelled()&&actor instanceof EvaUnit01Entity unit&&com.projectseele.entity.EvaMotionModelR64.planted(unit)
                &&actor.distanceToSqr(packet.getX(),packet.getY(),packet.getZ())<=SEELE_PACKET_MOST*SEELE_PACKET_MOST)
        {
            vehicleFirstGoodX=packet.getX();vehicleFirstGoodY=packet.getY();vehicleFirstGoodZ=packet.getZ();
        }
    }
    /** How far a Unit of the planted model may have gone between two of its packets (blocks). */
    @Unique private static final double SEELE_PACKET_MOST=48;
}
