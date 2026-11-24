package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.client.GeoFrontDomeFarViewR65;
import net.minecraft.client.renderer.GameRenderer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R65: a shader pack finishes its picture (composite and final passes) as LevelRenderer.renderLevel returns, after every
 * render-stage event; the GeoFront far view is laid onto that picture here, before the hand clears the depth.
 */
@Mixin(GameRenderer.class)
public abstract class GameRendererGeoFrontFarViewR65Mixin
{
    @Inject(method = "renderLevel", at = @At(value = "INVOKE", shift = At.Shift.AFTER,
            target = "Lnet/minecraft/client/renderer/LevelRenderer;renderLevel(Lcom/mojang/blaze3d/vertex/PoseStack;FJZLnet/minecraft/client/Camera;Lnet/minecraft/client/renderer/GameRenderer;Lnet/minecraft/client/renderer/LightTexture;Lorg/joml/Matrix4f;)V"))
    private void projectseele$geofrontFarViewAfterShaders(float partial, long finishTime, PoseStack pose, CallbackInfo callback)
    {
        GeoFrontDomeFarViewR65.afterLevel();
    }
}
