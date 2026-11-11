package com.projectseele.mixin.client;

import com.projectseele.client.render.EntityShadowRange;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderDispatcher;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Keeps far small entities out of a shader pack's shadow pass, which asks this method what to draw. */
@Mixin(EntityRenderDispatcher.class)
public abstract class EntityShadowRangeMixin
{
    @Inject(method = "shouldRender", at = @At("HEAD"), cancellable = true)
    private void projectseele$farSmallShadows(Entity entity, Frustum frustum, double cameraX, double cameraY, double cameraZ, CallbackInfoReturnable<Boolean> callback)
    {
        if (EntityShadowRange.shadowPass() && EntityShadowRange.leftOut(entity, cameraX, cameraY, cameraZ)) callback.setReturnValue(false);
    }
}
