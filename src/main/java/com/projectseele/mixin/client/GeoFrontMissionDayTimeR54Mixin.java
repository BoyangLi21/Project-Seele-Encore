package com.projectseele.mixin.client;

import com.projectseele.client.TvYashimaNightClientR54;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Shader time follows the same mission night as the native sun/moon angle. */
@Mixin(Level.class)
public abstract class GeoFrontMissionDayTimeR54Mixin
{
    @Inject(method="getDayTime", at=@At("RETURN"), cancellable=true)
    private void seele$missionDayTime(CallbackInfoReturnable<Long> result)
    {
        if (TvYashimaNightClientR54.surfaceNight((Level)(Object)this))
            result.setReturnValue(Math.floorDiv(result.getReturnValue(), 24000L) * 24000L + 18000L);
    }
}
