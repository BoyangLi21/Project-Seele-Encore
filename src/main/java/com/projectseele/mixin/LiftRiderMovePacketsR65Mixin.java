package com.projectseele.mixin;

import com.projectseele.world.NervLiftPassengerSync;
import com.projectseele.world.RiderSpeedAllowanceR65;
import net.minecraft.network.protocol.game.ServerboundMovePlayerPacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Riders on a dedicated server: vanilla excuses only the player hosting the game from "moved too quickly". A lift
 * rider whose client caught its car up with the server's after a stall reports one step of ten blocks or more, inside
 * the travelling car; an MTR train rider at 700 km/h reports two ticks of 9.72 blocks after any stall. Both are
 * excused the same way, the train rider only for a step a train could make. The move is still made again (R65).
 */
@Mixin(ServerGamePacketListenerImpl.class)
abstract class LiftRiderMovePacketsR65Mixin
{
    @Shadow public ServerPlayer player;
    @Shadow private boolean isSingleplayerOwner(){throw new AssertionError();}

    @Redirect(method="handleMovePlayer",require=0,
            at=@At(value="INVOKE",target="Lnet/minecraft/server/network/ServerGamePacketListenerImpl;isSingleplayerOwner()Z"))
    private boolean seele$excuseLiftRider(ServerGamePacketListenerImpl self,ServerboundMovePlayerPacket packet)
    {
        if(isSingleplayerOwner())return true;
        double x=packet.getX(player.getX()),y=packet.getY(player.getY()),z=packet.getZ(player.getZ());
        if(NervLiftPassengerSync.ridingTo(player,x,y,z))return true;
        return RiderSpeedAllowanceR65.mtrStep(RiderSpeedAllowanceR65.ridingMtr(player.getUUID()),x-player.getX(),y-player.getY(),z-player.getZ());
    }
}
