package com.projectseele.mixin.client;

import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Preserve translucent water when DH reduces the texture alpha to four bits. */
@Pseudo
@Mixin(targets = "loaderCommon.forge.com.seibel.distanthorizons.common.wrappers.block.ClientBlockStateColorCache", remap = false)
public abstract class DhWaterTransparencyR53Mixin
{
    @Shadow @Final private BlockState blockState;
    @Shadow private int baseColor;

    @Inject(method = "resolveColors", at = @At("RETURN"))
    private void seele$keepWaterInTranslucentPass(CallbackInfo callback)
    {
        int alpha = baseColor >>> 24;
        // DH 2.3.4 expands the high nibble with low bits 0xf. Thus texture
        // alpha 240..254 becomes 255 and water enters the opaque terrain pass.
        // Keep genuinely opaque textures, other liquids and solid waterlogged
        // blocks unchanged; this only reserves the last translucent bucket.
        if (alpha >= 240 && alpha < 255 && blockState.is(Blocks.WATER))
            baseColor = (baseColor & 0x00ffffff) | 0xef000000;
    }
}
