package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.client.GeoFrontDomeFarViewR65;
import net.minecraft.client.renderer.LevelRenderer;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R65: the GeoFront uses the overworld's sky effects, so vanilla draws its clouds at y 192, above the cavity's rock
 * roof. Beyond the render distance nothing real hides them, and they came out over the far view of the dome. No cloud
 * belongs in the cavity: none is drawn while the far view stands in for Distant Horizons there.
 */
@Mixin(LevelRenderer.class)
public abstract class LevelRendererGeoFrontCloudsR65Mixin
{
    @Inject(method = "renderClouds", at = @At("HEAD"), cancellable = true)
    private void projectseele$noCloudsInTheCavity(PoseStack pose, Matrix4f projection, float partial, double x, double y, double z,
                                                  CallbackInfo callback)
    {
        if (GeoFrontDomeFarViewR65.suppressDistantHorizons()) callback.cancel();
    }
}
