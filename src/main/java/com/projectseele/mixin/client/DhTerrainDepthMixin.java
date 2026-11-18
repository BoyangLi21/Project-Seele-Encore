package com.projectseele.mixin.client;

import com.projectseele.client.RamielTerrainDepthR64;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Only a DH solid pass that actually ran can supply terrain for this frame. */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.render.renderer.LodRenderer", remap = false)
public abstract class DhTerrainDepthMixin
{
    @Inject(method = "drawLods", require = 0, at = @At("TAIL"))
    private void seele$observeTerrainProjection(@Coerce Object level, @Coerce Object parameters,
                                                @Coerce Object profiler, CallbackInfo callback)
    {
        RamielTerrainDepthR64.observe(parameters);
    }
}
