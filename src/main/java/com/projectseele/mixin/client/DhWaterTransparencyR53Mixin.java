package com.projectseele.mixin.client;

import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import com.projectseele.registry.ModBlocks;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Preserve water and LCL surface alpha when DH reduces it to four bits. */
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
        // LCL uses the same water sprite via its particle model; it must stay
        // in the deferred liquid pass rather than occluding the real bay doors.
        // Genuinely opaque textures and solid waterlogged blocks are unchanged.
        if (alpha >= 240 && alpha < 255
                && (blockState.is(Blocks.WATER) || blockState.is(ModBlocks.LCL_BLOCK.get())))
            baseColor = (baseColor & 0x00ffffff) | 0xef000000;
    }
}
