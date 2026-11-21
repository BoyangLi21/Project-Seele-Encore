package com.projectseele.mixin.client;

import com.projectseele.client.map.AreaMapDisplay;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Pseudo
@Mixin(targets = "xaero.common.minimap.MinimapProcessor", remap = false)
abstract class AreaMapMinimapMixin
{
    @Shadow private ResourceKey<Level> lastMapDimension;

    @Inject(method = "onRender", at = @At("HEAD"))
    private void projectseele$startAreaMap(CallbackInfo ci) { AreaMapDisplay.startMinimap(); }

    @Inject(method = "onRender", at = @At("RETURN"))
    private void projectseele$finishAreaMap(GuiGraphics graphics, int x, int y, int width, int height, double scale,
            int size, int boxSize, float partial, @Coerce Object buffers, CallbackInfo ci)
    {
        // Xaero has already applied its centred-enlargement adjustment to the x and y argument slots.
        AreaMapDisplay.finishMinimap(graphics, x, y, boxSize, partial, lastMapDimension);
    }
}
