package com.projectseele.mixin.client;

import com.projectseele.world.FacilityVisibilityR54;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Past the client's chunk radius a giant has no ticking section; vanilla would freeze its interpolation there. */
@Mixin(Entity.class)
public abstract class GiantEntityVisibilityR61Mixin
{
    @Shadow public abstract net.minecraft.world.level.Level level();

    @Inject(method = "isAlwaysTicking", at = @At("HEAD"), cancellable = true)
    private void seele$tickGiantOutsideLoadedChunks(CallbackInfoReturnable<Boolean> result)
    {
        if (this.level().isClientSide && FacilityVisibilityR54.giant((Entity) (Object) this)) result.setReturnValue(true);
    }

    @Inject(method = "shouldRenderAtSqrDistance", at = @At("HEAD"), cancellable = true)
    private void seele$renderGiantAcrossTrackingRange(double distanceSquared, CallbackInfoReturnable<Boolean> result)
    {
        if (FacilityVisibilityR54.giant((Entity) (Object) this))
        {
            double range = FacilityVisibilityR54.GIANT_DISTANCE;
            result.setReturnValue(distanceSquared < range * range);
        }
    }
}
