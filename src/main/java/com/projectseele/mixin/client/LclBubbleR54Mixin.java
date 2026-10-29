package com.projectseele.mixin.client;

import com.projectseele.registry.ModFluids;
import net.minecraft.client.particle.BubbleColumnUpParticle;
import net.minecraft.client.particle.BubbleParticle;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.TagKey;
import net.minecraft.world.level.material.Fluid;
import net.minecraft.world.level.material.FluidState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Water bubbles remain alive in LCL without changing global water tags. */
@Mixin({BubbleParticle.class,BubbleColumnUpParticle.class})
public abstract class LclBubbleR54Mixin
{
    @Redirect(method="tick",at=@At(value="INVOKE",target="Lnet/minecraft/world/level/material/FluidState;is(Lnet/minecraft/tags/TagKey;)Z"))
    private boolean projectseele$lclBubbleMedium(FluidState state,TagKey<Fluid> tag)
    {
        return state.is(tag)||tag==FluidTags.WATER&&state.getFluidType()==ModFluids.LCL_TYPE.get();
    }
}
