package com.projectseele.mixin.client;

import com.projectseele.client.map.AreaMapDisplay;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.MultiBufferSource;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "xaero.hud.minimap.waypoint.render.WaypointMapRenderer", remap = false)
abstract class AreaMapWaypointMixin
{
    private static final String RENDER = "renderElement(Lxaero/common/minimap/waypoints/Waypoint;ZZDFDDLxaero/hud/minimap/element/render/MinimapElementRenderInfo;Lnet/minecraft/client/gui/GuiGraphics;Lnet/minecraft/client/renderer/MultiBufferSource$BufferSource;)Z";
    @Unique private double projectseele$waypointDivider;

    @ModifyArg(method = RENDER, at = @At(value = "INVOKE", target = "Lxaero/common/minimap/waypoints/Waypoint;getX(D)I"), index = 0)
    private double projectseele$rememberDivider(double divider)
    {
        projectseele$waypointDivider = divider;
        return divider;
    }

    @Inject(method = RENDER, at = @At("RETURN"))
    private void projectseele$visibleWaypoint(@Coerce Object waypoint, boolean highlighted, boolean outside,
            double depth, float scale, double partialX, double partialZ, @Coerce Object info, GuiGraphics graphics,
            MultiBufferSource.BufferSource buffers, CallbackInfoReturnable<Boolean> cir)
    {
        if (AreaMapDisplay.collectingMarkers() && cir.getReturnValueZ() && waypoint instanceof AreaMapWaypointAccess point)
            AreaMapDisplay.waypoint(point.projectseele$mapX(projectseele$waypointDivider) + 0.5,
                    point.projectseele$mapZ(projectseele$waypointDivider) + 0.5, point.projectseele$mapColor());
    }
}
