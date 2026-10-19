package com.projectseele.mixin.client;

import com.projectseele.client.MtrRailVisibilityBudgetR53;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "org.mtr.mod.render.RenderRails", remap = false)
public abstract class MtrRailOcclusionR53Mixin
{
    @Inject(method = "lambda$render$1", at = @At("HEAD"), cancellable = true, remap = false)
    private static void projectSeele$boundRailOcclusion(@Coerce Object rail, @Coerce Object camera,
            @Coerce Object occlusion, CallbackInfoReturnable<Runnable> callback)
    {
        Runnable visible = MtrRailVisibilityBudgetR53.retainLargeRail(rail);
        if (visible != null) callback.setReturnValue(visible);
    }
}
