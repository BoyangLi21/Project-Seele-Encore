package com.projectseele.mixin;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Project defenses wait for existing LOS chunks instead of loading them from their targeting tick. */
@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.entity.vehicle.ai.TowerAI$TargetValidator", remap = false)
public abstract class SbwDefenseLoadedLosR56Mixin
{
    @Inject(method = "checkLineOfSight(Lcom/atsuishio/superbwarfare/entity/vehicle/base/AutoAimableEntity;Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/phys/Vec3;)Z",
            at = @At("HEAD"), cancellable = true, remap = false)
    private static void seele$onlyLoadedDefenseLos(@Coerce Object nativeTower,
            Entity target, Vec3 from, CallbackInfoReturnable<Boolean> callback)
    {
        Entity tower = (Entity)nativeTower;
        if (!tower.getTags().contains("seele_r07_defense") || !(tower.level() instanceof ServerLevel level)) return;
        Vec3 to = target.getBoundingBox().getCenter();
        if (!Double.isFinite(from.x) || !Double.isFinite(from.y) || !Double.isFinite(from.z)
                || !Double.isFinite(to.x) || !Double.isFinite(to.y) || !Double.isFinite(to.z))
        {
            callback.setReturnValue(false);
            return;
        }
        // Native clip uses this exact DDA, including its endpoint epsilon.
        boolean loaded = BlockGetter.traverseBlocks(from, to, level,
                (world, pos) -> world.isOutsideBuildHeight(pos) || world.getChunkSource().getChunkNow(pos.getX() >> 4, pos.getZ() >> 4) != null ? null : Boolean.FALSE,
                world -> Boolean.TRUE);
        if (!loaded) callback.setReturnValue(false);
    }
}
