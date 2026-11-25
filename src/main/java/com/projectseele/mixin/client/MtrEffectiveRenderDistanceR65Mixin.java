package com.projectseele.mixin.client;

import net.minecraft.client.Minecraft;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * MTR draws its rails, vehicles and block entities out to the render distance in the client's settings. On a dedicated
 * server the terrain only reaches the smaller of that setting and the server's view distance, so a client set above the
 * server drew MTR far past the last loaded chunk: 32 against the server's 12 halved the frame rate for no terrain
 * (R65). MTR now gets the distance the game itself renders to; in singleplayer the two are the same.
 */
@Pseudo
@Mixin(targets = "org.mtr.mapping.mapper.MinecraftClientHelper", remap = false)
public abstract class MtrEffectiveRenderDistanceR65Mixin
{
    @Inject(method = "getRenderDistance()I", at = @At("HEAD"), cancellable = true, remap = false)
    private static void projectSeele$effectiveRenderDistance(CallbackInfoReturnable<Integer> callback)
    {
        callback.setReturnValue(Minecraft.getInstance().options.getEffectiveRenderDistance());
    }
}
