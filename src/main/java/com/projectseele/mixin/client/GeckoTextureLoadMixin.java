package com.projectseele.mixin.client;

import com.projectseele.client.render.HeavyTextureLoad;
import net.minecraft.client.renderer.texture.SimpleTexture;
import net.minecraft.server.packs.resources.ResourceManager;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * GeckoLib registers its own texture class for every texture first asked for by name, and that
 * class decodes the image in its own load, on the render thread, without calling SimpleTexture's.
 * The method keeps its SRG name in the release jar and its mapped name in a development run.
 */
@Pseudo
@Mixin(targets = "software.bernie.geckolib.cache.texture.AnimatableTexture", remap = false)
public abstract class GeckoTextureLoadMixin
{
    @Inject(method = {"m_6704_", "load"}, at = @At("HEAD"), cancellable = true, remap = false)
    private void projectseele$decodeOffThread(ResourceManager manager, CallbackInfo callback)
    {
        if (HeavyTextureLoad.begin((SimpleTexture) (Object) this, manager)) callback.cancel();
    }
}
