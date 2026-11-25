package com.projectseele.mixin.client;

import com.projectseele.client.map.AreaMapAtlas;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Xaero's automatic cave mode, in the minimap's writer (which the world map follows while the minimap is installed)
 * and in the world map's own calculator. In the GeoFront dimension the area atlas decides: cave mode inside the
 * cavern, the surface map everywhere else.
 */
@Pseudo
@Mixin(targets = {"xaero.common.minimap.write.MinimapWriter", "xaero.map.misc.CaveStartCalculator"}, remap = false)
abstract class AreaMapCaveMixin
{
    @Inject(method = "getCaving", at = @At("HEAD"), cancellable = true, require = 0)
    private void projectseele$caveOnlyInCavern(double x, double y, double z, Level level, CallbackInfoReturnable<Integer> cir)
    {
        Integer start = AreaMapAtlas.caveStart(level, x, y, z);
        if (start != null) cir.setReturnValue(start);
    }
}
