package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import net.minecraftforge.fml.ModList;

/**
 * Starlight's engine throws in initNibble on Create's render-only virtual world, whose chunks it never
 * loaded, so the client crashed the moment a moving city block (a Create contraption) was drawn.
 * Under Starlight the virtual relight is skipped; the moving blocks keep the light Create samples
 * from the real world, and only light emitted inside a contraption is lost while it moves.
 */
@Pseudo
@Mixin(targets = "com.simibubi.create.foundation.virtualWorld.VirtualRenderWorld", remap = false)
public abstract class CreateVirtualLightStarlightGuardMixin
{
    @Unique
    private static final boolean PROJECTSEELE$STARLIGHT = ModList.get().isLoaded("starlight");

    @Inject(method = "runLightEngine", at = @At("HEAD"), cancellable = true, remap = false)
    private void projectSeele$skipVirtualRelightUnderStarlight(CallbackInfo callback)
    {
        if (PROJECTSEELE$STARLIGHT)
        {
            callback.cancel();
        }
    }
}
