package com.projectseele.mixin;

import com.projectseele.physics.FluidFreeVolume;
import java.util.function.Predicate;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.material.FluidState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Skips Forge's fluid scan when the section palettes prove the box holds no fluid. */
@Mixin(Entity.class)
public abstract class EntityFluidScanMixin
{
    @Inject(method = "updateFluidHeightAndDoFluidPushing(Ljava/util/function/Predicate;)V",
            at = @At("HEAD"), cancellable = true, remap = false)
    private void projectseele$skipFluidFreeBox(Predicate<FluidState> filter, CallbackInfo callback)
    {
        if (FluidFreeVolume.proven((Entity) (Object) this)) callback.cancel();
    }
}
