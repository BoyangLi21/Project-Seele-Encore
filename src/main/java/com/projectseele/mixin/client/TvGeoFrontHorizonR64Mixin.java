package com.projectseele.mixin.client;

import com.projectseele.client.TvGeoFrontEffects;
import com.projectseele.world.HakoneSurfaceField;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.world.level.LevelHeightAccessor;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Vanilla draws the sky below the horizon black whenever the eye is under y 63, the hard-coded
 * horizon of every non-flat level. The preview's coast, plain and station all sit far below
 * that, so past the last drawn chunk the player saw a black band (R64 M6). Its sea is at -82.
 */
@Mixin(ClientLevel.ClientLevelData.class)
public abstract class TvGeoFrontHorizonR64Mixin
{
    @Inject(method = "getHorizonHeight", at = @At("HEAD"), cancellable = true)
    private void seele$seaHorizon(LevelHeightAccessor level, CallbackInfoReturnable<Double> result)
    {
        if (level instanceof ClientLevel client && client.effects() instanceof TvGeoFrontEffects)
            result.setReturnValue((double) HakoneSurfaceField.SEA_Y);
    }
}
