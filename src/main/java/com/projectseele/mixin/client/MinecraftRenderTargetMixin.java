package com.projectseele.mixin.client;

import com.mojang.blaze3d.pipeline.RenderTarget;
import com.projectseele.client.EvaCommandFeedClient;
import net.minecraft.client.Minecraft;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Redirects only the private cockpit-feed render pass to its own target, and
 * stamps each frame where vanilla samples its own frame timer.
 */
@Mixin(Minecraft.class)
public abstract class MinecraftRenderTargetMixin
{
    @Inject(method = "runTick", at = @At("HEAD"))
    private void projectseele$stampFrame(boolean renderLevel, CallbackInfo callback)
    {
        com.projectseele.client.AircraftRenderClockR21.stampFrame();
    }

    @Inject(method = "getMainRenderTarget", at = @At("HEAD"),
            cancellable = true)
    private void projectseele$useCockpitFeedTarget(
            CallbackInfoReturnable<RenderTarget> callback)
    {
        RenderTarget target = EvaCommandFeedClient.captureTargetOverride();
        if (target != null)
        {
            callback.setReturnValue(target);
        }
    }
}
