package com.projectseele.mixin.client;

import com.mojang.blaze3d.platform.NativeImage;
import com.projectseele.client.YashimaBlackoutR64;
import net.minecraft.client.renderer.LightTexture;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * R64, the Yashima blackout in the game's own drawing (no shader pack). The operation's dimension has so much
 * ambient light (0.62) that its light map is all but white whatever light a block has: a lamp lit and a lamp out
 * are drawn alike, and so is the open ground by day and by night. For the blackout the light map itself is made
 * to tell them apart: where the sky reaches and no lamp does, it is brought down to a moonlit night; the more of a
 * lamp's light a place has, the less; where the sky does not reach, not at all. With the lamps of the city read
 * as out (YashimaBlackoutR64) the city is then dark, and the position's lamps stand in pools of light. A shader
 * pack does not use this map (it has its own night).
 */
@Mixin(LightTexture.class)
public abstract class YashimaBlackoutLightmapR64Mixin
{
    /** The share of its brightness that open, unlit ground keeps in the blackout: red, green, blue. */
    @Unique
    private static final float[] SEELE$NIGHT = {.30F, .36F, .50F};

    @Shadow @Final private NativeImage lightPixels;

    @Inject(method = "updateLightTexture", at = @At(value = "INVOKE", target = "Lnet/minecraft/client/renderer/texture/DynamicTexture;upload()V"))
    private void seele$blackout(float partial, CallbackInfo info)
    {
        float depth = YashimaBlackoutR64.depth();
        if (depth <= 0) return;
        // The map is 16 by 16: block light across, sky light down. Its last column (a lamp's full light) and its
        // first row (no sky) stay as they are.
        for (int sky = 1; sky < 16; sky++)
        {
            float open = Math.min(1, sky / 4F) * depth;
            for (int block = 0; block < 15; block++)
            {
                float lamp = (float) Math.pow(block / 15F, 1.2), dark = open * (1 - lamp);
                int pixel = this.lightPixels.getPixelRGBA(block, sky);
                int red = Math.round((pixel & 255) * (1 - dark * (1 - SEELE$NIGHT[0])));
                int green = Math.round((pixel >> 8 & 255) * (1 - dark * (1 - SEELE$NIGHT[1])));
                int blue = Math.round((pixel >> 16 & 255) * (1 - dark * (1 - SEELE$NIGHT[2])));
                this.lightPixels.setPixelRGBA(block, sky, 0xFF000000 | blue << 16 | green << 8 | red);
            }
        }
    }
}
