package com.projectseele.mixin;

import com.projectseele.registry.ModFluids;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.TagKey;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.material.Fluid;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Reuse native player swimming presentation while retaining the actual LCL fluid type. */
@Mixin(Entity.class)
public abstract class LclPlayerSwimmingR54Mixin
{
    @Inject(method="updateFluidHeightAndDoFluidPushing(Lnet/minecraft/tags/TagKey;D)Z",at=@At("RETURN"),cancellable=true)
    private void projectseele$lclWaterContact(TagKey<Fluid> tag,double scale,CallbackInfoReturnable<Boolean> callback)
    {
        // Forge has already measured and pushed each real fluid once. Extending
        // this result enters vanilla's splash/swim-sound path without another scan.
        if(tag==FluidTags.WATER&&!callback.getReturnValueZ()&&(Object)this instanceof Player player
                &&player.getFluidTypeHeight(ModFluids.LCL_TYPE.get())>0)
            callback.setReturnValue(true);
    }

    @Inject(method="getFluidHeight",at=@At("RETURN"),cancellable=true)
    private void projectseele$lclSwimmingDepth(TagKey<Fluid> tag,CallbackInfoReturnable<Double> callback)
    {
        if(tag==FluidTags.WATER&&(Object)this instanceof Player player)
            callback.setReturnValue(Math.max(callback.getReturnValueD(),player.getFluidTypeHeight(ModFluids.LCL_TYPE.get())));
    }

    @Inject(method="isEyeInFluid",at=@At("RETURN"),cancellable=true)
    private void projectseele$lclUnderwaterEffects(TagKey<Fluid> tag,CallbackInfoReturnable<Boolean> callback)
    {
        // Native player eye transitions drive entry/exit and underwater ambience.
        // Do not replace getEyeInFluidType: LCL still supplies oxygen and its own fog.
        if(tag==FluidTags.WATER&&!callback.getReturnValueZ()&&(Object)this instanceof Player player
                &&player.isEyeInFluidType(ModFluids.LCL_TYPE.get()))
            callback.setReturnValue(true);
    }
}
