package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.gen.Invoker;

@Pseudo
@Mixin(targets = "xaero.common.minimap.waypoints.Waypoint", remap = false)
public interface AreaMapWaypointAccess
{
    @Invoker("getX") int projectseele$mapX(double divider);
    @Invoker("getZ") int projectseele$mapZ(double divider);
    @Invoker("getActualColor") int projectseele$mapColor();
}
