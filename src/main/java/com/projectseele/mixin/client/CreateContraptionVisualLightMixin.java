package com.projectseele.mixin.client;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockAndTintGetter;
import net.minecraft.world.level.LightLayer;
import net.minecraftforge.fml.ModList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;

/** The Flywheel structure mesh reads light through Create's block-filtering view. */
@Pseudo
@Mixin(targets = "com.simibubi.create.content.contraptions.render.ContraptionVisual$1", remap = false)
public abstract class CreateContraptionVisualLightMixin implements BlockAndTintGetter
{
    @Unique
    private static final boolean projectSeele$starlight = ModList.get().isLoaded("starlight");

    @Override
    public int getBrightness(LightLayer layer, BlockPos pos)
    {
        if (projectSeele$starlight)
        {
            // The virtual world already handles light from the real contraption.
            // Asking its raw light engine would access unallocated Starlight arrays.
            return ((CreateWrappedLightAccess) this).projectSeele$wrappedView().getBrightness(layer, pos);
        }
        return BlockAndTintGetter.super.getBrightness(layer, pos);
    }
}
