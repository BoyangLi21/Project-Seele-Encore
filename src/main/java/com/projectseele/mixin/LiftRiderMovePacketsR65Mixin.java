package com.projectseele.mixin;

import com.projectseele.world.NervLiftPassengerSync;
import net.minecraft.network.protocol.game.ServerboundMovePlayerPacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/**
 * Lift riders on a dedicated server: vanilla excuses only the player hosting the game from "moved too quickly". A
 * rider whose client caught its car up with the server's after a stall reports one step of ten blocks or more,
 * inside the travelling car; it is excused the same way. The move is still made again on the server (R65).
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
        return NervLiftPassengerSync.ridingTo(player,packet.getX(player.getX()),packet.getY(player.getY()),packet.getZ(player.getZ()));
    }
}
