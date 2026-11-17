package com.projectseele.mixin.client;

import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.blaze3d.platform.TextureUtil;
import com.projectseele.client.render.HeavyTextureLoad;
import net.minecraft.client.renderer.texture.AbstractTexture;
import net.minecraft.client.renderer.texture.SimpleTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Decodes this mod's large entity textures on a worker thread. Oculus loads its normal and specular maps through the same method. */
@Mixin(SimpleTexture.class)
public abstract class HeavyTextureLoadMixin extends AbstractTexture implements HeavyTextureLoad.Target
{
    @Shadow @Final protected ResourceLocation location;

    @Unique private int projectseele$generation;

    @Inject(method = "load", at = @At("HEAD"), cancellable = true)
    private void projectseele$decodeOffThread(ResourceManager manager, CallbackInfo callback)
    {
        if (HeavyTextureLoad.begin((SimpleTexture) (Object) this, manager)) callback.cancel();
    }

    @Override
    public ResourceLocation projectseele$location()
    {
        return this.location;
    }

    @Override
    public int projectseele$nextGeneration()
    {
        return ++this.projectseele$generation;
    }

    @Override
    public void projectseele$finish(NativeImage image, boolean blur, boolean clamp, int generation)
    {
        // A resource reload or a released texture in the meantime makes these pixels stale.
        if (generation != this.projectseele$generation || this.id == -1)
        {
            image.close();
            return;
        }
        TextureUtil.prepareImage(this.id, 0, image.getWidth(), image.getHeight());
        image.upload(0, 0, 0, 0, 0, image.getWidth(), image.getHeight(), blur, clamp, false, true);
    }
}
