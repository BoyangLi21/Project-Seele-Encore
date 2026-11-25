package com.projectseele.mixin.client;

import com.projectseele.compat.MtrClampedTextR65;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * MTR 4.0.5 turns each generated text image into a texture on the render thread. An image wider or taller than its
 * size limit (2048 times 2 to the dynamic texture resolution) is copied into a smaller one and only the copy becomes
 * the texture; the original is never closed. Vehicle scrolling displays draw their whole message on one line with no
 * width limit, so a long message is over the limit every time it is drawn again, and each time its original stayed
 * in native memory: about 1 GB a minute standing at the Tokyo-3 lake shore (R65). The original is closed
 * here once the copy has been made.
 */
@Pseudo
@Mixin(targets = "org.mtr.mod.client.DynamicTextureCache", remap = false)
public abstract class MtrClampedTextLeakR65Mixin
{
    @Inject(method = "lambda$getResource$19(Ljava/lang/String;Lorg/mtr/mapping/holder/NativeImage;)V", at = @At("RETURN"), remap = false, require = 0)
    private void projectSeele$closeClampedOriginal(String key, @Coerce Object image, CallbackInfo callback)
    {
        MtrClampedTextR65.closeIfClamped(image);
    }
}
