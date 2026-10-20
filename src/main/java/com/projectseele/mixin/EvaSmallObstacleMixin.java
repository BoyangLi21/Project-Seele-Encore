package com.projectseele.mixin;

import com.projectseele.entity.EvaObstacleCollision;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockCollisions;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.*;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(BlockCollisions.class)
public abstract class EvaSmallObstacleMixin
{
    @Redirect(method="computeNext",at=@At(value="INVOKE",target="Lnet/minecraft/world/level/block/state/BlockState;getCollisionShape(Lnet/minecraft/world/level/BlockGetter;Lnet/minecraft/core/BlockPos;Lnet/minecraft/world/phys/shapes/CollisionContext;)Lnet/minecraft/world/phys/shapes/VoxelShape;"))
    private VoxelShape seele$largeAirframeClearance(BlockState state,BlockGetter level,BlockPos pos,CollisionContext context)
    {
        // The three vanilla air blocks have no collision in any context.
        // Giant hull sweeps visit thousands of them; avoid the vehicle cache
        // and obstacle filters for these empty cells.
        if(state.is(net.minecraft.world.level.block.Blocks.AIR)
                ||state.is(net.minecraft.world.level.block.Blocks.CAVE_AIR)
                ||state.is(net.minecraft.world.level.block.Blocks.VOID_AIR))return Shapes.empty();
        VoxelShape shape=com.projectseele.entity.SbwStaticShapesR24.shape(state,context);
        if(shape==null){com.projectseele.entity.SbwRestCollisionR24.shapeFallback();shape=state.getCollisionShape(level,pos,context);}
        return context instanceof EntityCollisionContext entityContext&&entityContext.getEntity() instanceof EvaUnit01Entity eva
                &&EvaObstacleCollision.ignores(eva,state,pos,shape)?Shapes.empty():shape;
    }
}
