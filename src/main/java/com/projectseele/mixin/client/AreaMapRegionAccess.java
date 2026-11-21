package com.projectseele.mixin.client;

import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.gen.Invoker;

@Pseudo
@Mixin(targets = "xaero.map.region.LeveledRegion", remap = false)
public interface AreaMapRegionAccess
{
    @Invoker("loadingAnimation") boolean projectseele$loading();
    @Invoker("getRegionX") int projectseele$x();
    @Invoker("getRegionZ") int projectseele$z();
    @Invoker("getLevel") int projectseele$level();
}
