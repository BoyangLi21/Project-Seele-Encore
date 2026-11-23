package com.projectseele.mixin.client;

import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** The interpolation target a client keeps for an entity the server moves (other players, R65 lift riders). */
@Mixin(LivingEntity.class)
public interface LivingEntityLerpAccessorR65
{
    @Accessor("lerpSteps") int seele$lerpSteps();
    @Accessor("lerpX") double seele$lerpX();
    @Accessor("lerpZ") double seele$lerpZ();
    @Accessor("lerpX") void seele$setLerpX(double value);
    @Accessor("lerpY") void seele$setLerpY(double value);
    @Accessor("lerpZ") void seele$setLerpZ(double value);
}
