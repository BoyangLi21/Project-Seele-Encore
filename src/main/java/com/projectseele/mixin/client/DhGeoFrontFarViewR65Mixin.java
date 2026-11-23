package com.projectseele.mixin.client;

import com.projectseele.client.GeoFrontDomeFarViewR65;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R65: inside the GeoFront cavity the baked silhouette (GeoFrontDomeFarViewR65) stands in for the Distant Horizons
 * far view (2.3.4), which breaks up the dome and draws the hanging towers black there. Every way DH draws its far view
 * for a frame (the plain pass, the deferred pass shader packs use, and the fades) is skipped while it does.
 */
@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.api.internal.ClientApi", remap = false)
public abstract class DhGeoFrontFarViewR65Mixin
{
    @Inject(method = {"renderLods", "renderDeferredLodsForShaders", "renderFade", "renderFadeOpaque"}, at = @At("HEAD"),
            cancellable = true, require = 0)
    private void seele$geofrontFarView(CallbackInfo ci)
    {
        if (GeoFrontDomeFarViewR65.suppressDistantHorizons()) ci.cancel();
    }
}
