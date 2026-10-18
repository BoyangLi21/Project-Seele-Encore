package com.projectseele.mixin.client;

import com.projectseele.client.DhShaderReloadR53;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "net.irisshaders.iris.Iris", remap = false)
public abstract class OculusDhReloadR53Mixin
{
    @Inject(method = "reload", at = @At("HEAD"))
    private static void seele$syncDistantRendering(CallbackInfo ci)
    {
        DhShaderReloadR53.synchronize();
    }
}
