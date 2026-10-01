package com.projectseele.mixin;

import com.projectseele.world.PublicStationGatesR44;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** The physical free-service override is bounded by an installed coordinate manifest. */
@Mixin(targets = "org.mtr.mod.block.BlockTicketBarrier", remap = false)
@Pseudo
public abstract class PublicStationGateR44Mixin
{
    @Inject(method = "onEntityCollision2(Lorg/mtr/mapping/holder/BlockState;Lorg/mtr/mapping/holder/World;Lorg/mtr/mapping/holder/BlockPos;Lorg/mtr/mapping/holder/Entity;)V",
            at = @At("HEAD"), cancellable = true, remap = false)
    private void seele$publicFreeCollision(@Coerce Object state,
            @Coerce Object world, @Coerce Object position,
            @Coerce Object actor, CallbackInfo callback)
    {
        if (PublicStationGatesR44.collisionBridge(state, world, position, actor))
        {
            callback.cancel();
        }
    }

    @Inject(method = "scheduledTick2(Lorg/mtr/mapping/holder/BlockState;Lorg/mtr/mapping/holder/ServerWorld;Lorg/mtr/mapping/holder/BlockPos;Lorg/mtr/mapping/holder/Random;)V",
            at = @At("HEAD"), cancellable = true, remap = false)
    private void seele$publicOccupiedClosure(@Coerce Object state,
            @Coerce Object world, @Coerce Object position,
            @Coerce Object random, CallbackInfo callback)
    {
        if (PublicStationGatesR44.scheduledBridge(state, world, position))
        {
            callback.cancel();
        }
    }
}
