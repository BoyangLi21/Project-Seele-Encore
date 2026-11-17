package com.projectseele.mixin;

import com.projectseele.world.SbwIdlePause;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Passes over the whole tick of a parked vehicle that {@link SbwIdlePause} finds idle and far from everyone. */
@Mixin(ServerLevel.class)
public abstract class SbwIdlePauseMixin
{
    @Inject(method = "tickNonPassenger", at = @At("HEAD"), cancellable = true)
    private void projectseele$pauseIdleVehicle(Entity entity, CallbackInfo callback)
    {
        if (entity instanceof SbwIdlePause.Vehicle vehicle && SbwIdlePause.paused((ServerLevel) (Object) this, entity, vehicle)) callback.cancel();
    }
}
