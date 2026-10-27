package com.projectseele.mixin.client;

import com.projectseele.client.DhShaderReloadR53;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "net.irisshaders.iris.compat.dh.DHCompatInternal", remap = false)
public abstract class OculusDhRenderPassR54Mixin
{
    @Shadow public boolean shouldOverride;

    @Inject(method = {"<init>", "clear"}, at = @At("RETURN"))
    private void seele$synchronizeRenderPass(CallbackInfo ci)
    {
        // DH 2.3.4 selects the pass before Oculus' BeforeRender callback.
        // Publish pipeline changes before that selection, including frame one.
        DhShaderReloadR53.synchronizeRenderPass(shouldOverride);
    }
}
