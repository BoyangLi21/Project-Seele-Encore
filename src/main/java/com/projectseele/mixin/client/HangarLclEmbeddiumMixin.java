package com.projectseele.mixin.client;

import com.projectseele.client.HangarCoolantVisualR52;
import com.projectseele.fluid.LclFluidType;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.material.Fluid;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Embeddium builds its own fluid mesh instead of passing through LiquidBlockRenderer. */
@Pseudo
@Mixin(targets = "me.jellysquid.mods.sodium.client.render.chunk.compile.pipeline.FluidRenderer", remap = false)
public abstract class HangarLclEmbeddiumMixin
{
    @Inject(method = "isFluidOccluded", at = @At("HEAD"), cancellable = true)
    private void seele$gantryFace(BlockAndTintGetter slice, int x, int y, int z, Direction face,
                                  Fluid fluid, CallbackInfoReturnable<Boolean> info)
    {
        if (fluid.getFluidType() instanceof LclFluidType && HangarCoolantVisualR52.owned(slice, x, y, z))
            info.setReturnValue(true);
    }
}
