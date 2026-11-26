package com.projectseele.mixin.client;

import com.projectseele.item.Nerv16BoxItem;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "com.atsuishio.superbwarfare.client.overlay.GPWSOverlay", remap = false)
public abstract class SbwGroundClearanceR65Mixin
{
    @Unique private Vec3 projectseele$samplePosition;
    @Unique private long projectseele$sampleTick;
    @Unique private double projectseele$sampleHeight;

    @Inject(method = "getHeightAboveGround(Lcom/atsuishio/superbwarfare/entity/vehicle/base/VehicleEntity;)D",
            at = @At("RETURN"), cancellable = true, require = 0)
    private void projectseele$belowCavernRoof(@Coerce Object vehicle, CallbackInfoReturnable<Double> result)
    {
        // SBW subtracts the highest motion-blocking surface from the jet Y, then clamps negative readings to zero.
        // Its positive surface reading and its unloaded-chunk sentinel already have the right meaning.
        if (result.getReturnValueD() != 0 || !(vehicle instanceof Entity jet)
                || jet.level().dimension() != FacilitySchemaV2.DIMENSION
                || !Nerv16BoxItem.AIRFRAME.equals(BuiltInRegistries.ENTITY_TYPE.getKey(jet.getType()))) return;
        Vec3 feet = jet.position();
        long tick = jet.level().getGameTime();
        // The HUD and sound evaluate the same aircraft several times between simulation ticks.
        if (feet != projectseele$samplePosition || tick != projectseele$sampleTick)
        {
            projectseele$sampleHeight = projectseele$groundDistance(jet.level(), feet, jet);
            projectseele$samplePosition = feet;
            projectseele$sampleTick = tick;
        }
        result.setReturnValue(projectseele$sampleHeight);
    }

    @Unique
    private static double projectseele$groundDistance(BlockGetter level, Vec3 feet, Entity jet)
    {
        // SBW's largest altitude band ends at 200 blocks. Water counts as a surface just as in its heightmap.
        var hit = level.clip(new ClipContext(feet.add(0, .001, 0), feet.add(0, -201, 0),
                ClipContext.Block.COLLIDER, ClipContext.Fluid.ANY, jet));
        return hit.getType() == HitResult.Type.MISS ? 201 : Math.max(0, feet.y - hit.getLocation().y);
    }
}
