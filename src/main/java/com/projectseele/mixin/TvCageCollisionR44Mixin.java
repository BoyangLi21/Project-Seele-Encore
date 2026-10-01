package com.projectseele.mixin;

import com.projectseele.world.TvCageCollisionR44;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;
import java.util.List;

/** Adds the authored sloped supports and moving sleeves to vanilla clipping. */
@Mixin(Entity.class)
public abstract class TvCageCollisionR44Mixin
{
    @Redirect(method = "collide", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/level/Level;getEntityCollisions(Lnet/minecraft/world/entity/Entity;Lnet/minecraft/world/phys/AABB;)Ljava/util/List;"))
    private List<VoxelShape> seele$tvMachinery(Level level, Entity actor, AABB query)
    {
        return TvCageCollisionR44.append(level, actor, query, level.getEntityCollisions(actor, query));
    }
}
