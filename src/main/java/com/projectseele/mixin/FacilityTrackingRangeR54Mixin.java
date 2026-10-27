package com.projectseele.mixin;

import com.projectseele.world.FacilityVisibilityR54;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(targets = "net.minecraft.server.level.ChunkMap$TrackedEntity")
public abstract class FacilityTrackingRangeR54Mixin
{
    @Shadow @Final private Entity entity;

    @Redirect(method = "updatePlayer", at = @At(value = "INVOKE",
            target = "Ljava/lang/Math;min(II)I", remap = false), require = 1)
    private int seele$facilityTrackingDistance(int entityRange, int viewRange)
    {
        return FacilityVisibilityR54.trackingDistance(entity, entityRange, viewRange);
    }
}
