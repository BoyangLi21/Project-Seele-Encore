package com.projectseele.mixin.client;

import com.projectseele.client.TvYashimaNightClientR54;
import net.minecraft.world.level.dimension.DimensionType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** The preview dimension retains fixed noon outside the surface mission view. */
@Mixin(DimensionType.class)
public abstract class GeoFrontMissionSunR54Mixin
{
    @Inject(method="timeOfDay", at=@At("HEAD"), cancellable=true)
    private void seele$missionSun(long daytime, CallbackInfoReturnable<Float> result)
    {
        if (TvYashimaNightClientR54.surfaceNight((DimensionType)(Object)this)) result.setReturnValue(.5F);
    }
}
