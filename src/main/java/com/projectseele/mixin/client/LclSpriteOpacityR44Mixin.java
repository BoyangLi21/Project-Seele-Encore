package com.projectseele.mixin.client;

import com.mojang.blaze3d.platform.NativeImage;
import com.projectseele.ProjectSeele;
import net.minecraft.client.renderer.texture.SpriteContents;
import net.minecraft.client.resources.metadata.animation.AnimationMetadataSection;
import net.minecraft.client.resources.metadata.animation.FrameSize;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.client.textures.ForgeTextureMetadata;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** LCL's own atlas copies retain water animation without inheriting clear-water alpha. */
@Mixin(SpriteContents.class)
public abstract class LclSpriteOpacityR44Mixin
{
    @Inject(method = "<init>(Lnet/minecraft/resources/ResourceLocation;Lnet/minecraft/client/resources/metadata/animation/FrameSize;Lcom/mojang/blaze3d/platform/NativeImage;Lnet/minecraft/client/resources/metadata/animation/AnimationMetadataSection;Lnet/minecraftforge/client/textures/ForgeTextureMetadata;)V", at = @At("RETURN"))
    private void seele$denseLcl(ResourceLocation name, FrameSize frame, NativeImage image,
                               AnimationMetadataSection animation, ForgeTextureMetadata metadata,
                               CallbackInfo callback)
    {
        if (!name.getNamespace().equals(ProjectSeele.MODID)
                || !(name.getPath().equals("block/lcl_still") || name.getPath().equals("block/lcl_flow"))) return;
        int minimum = 255, maximum = 0;
        for (int y = 0; y < image.getHeight(); y++)
        {
            for (int x = 0; x < image.getWidth(); x++)
            {
                int pixel = image.getPixelRGBA(x, y), alpha = pixel >>> 24;
                minimum = Math.min(minimum, alpha);
                maximum = Math.max(maximum, alpha);
                image.setPixelRGBA(x, y, pixel | 0xFF000000);
            }
        }
        ProjectSeele.LOGGER.info("R44 LCL atlas sprite {} {}x{} alpha={}..{} -> 255; original water untouched",
                name, image.getWidth(), image.getHeight(), minimum, maximum);
    }
}
