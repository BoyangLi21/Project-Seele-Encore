package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.HangarCoolantVisualR52;
import com.projectseele.registry.ModBlocks;
import net.minecraft.client.renderer.block.LiquidBlockRenderer;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.FluidState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Even alpha-zero block faces can write translucent depth. The tracked gantry owns these faces. */
@Mixin(LiquidBlockRenderer.class)
public abstract class HangarLclTerrainMixin
{
    @Inject(method = "tesselate", at = @At("HEAD"), cancellable = true)
    private void seele$gantrySurface(BlockAndTintGetter world, BlockPos pos, VertexConsumer out,
                                     BlockState block, FluidState state, CallbackInfo info)
    {
        if (block.is(ModBlocks.LCL_BLOCK.get()) && HangarCoolantVisualR52.owned(world, pos)) info.cancel();
    }
}
