package com.projectseele.entity;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraft.world.phys.shapes.Shapes;

/** A giant airframe clears low street furniture without changing the world or human collision. */
public final class EvaObstacleCollision
{
    private EvaObstacleCollision() {}

    /**
     * Thin furniture a giant (a Unit or an Angel) walks through at any height (R64): wall posts, fences, iron bars,
     * chains, lanterns, rods. Glass panes are not in it: they share the iron bars' class and make whole facades.
     */
    public static boolean thin(BlockState state)
    {
        Block block=state.getBlock();
        return block instanceof WallBlock||block instanceof FenceBlock||state.is(Blocks.IRON_BARS)||block instanceof ChainBlock
                ||block instanceof LanternBlock||block instanceof RodBlock;
    }

    public static boolean ignores(EvaUnit01Entity eva,BlockState state,BlockPos pos,VoxelShape shape)
    {
        if(shape.isEmpty()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive())return false;
        // Thin furniture at any height, and the solid parts of street furniture listed for the level (R64). Thin
        // furniture used to pass only within the 1.75 band below, which moves with the feet: a Unit stepped onto a
        // pole, the pole went soft under it, then hard again, and it was held bouncing on the wires.
        if(thin(state)||com.projectseele.world.StreetPassR64.passes(eva.level(),pos,state))return true;
        Block block=state.getBlock();
        // These are structural walking surfaces or access-control barriers, even when thin.
        if(block instanceof SlabBlock||block instanceof StairBlock||block instanceof TrapDoorBlock||block instanceof DoorBlock
                ||state.is(Blocks.BARRIER)||state.is(Blocks.SCAFFOLDING))return false;
        // This canonical immutable cube has exactly volume1, so the original
        // volume<.34 rule always rejects it regardless of the height band.
        // No contextual/custom shape is cached or approximated here.
        if(shape==Shapes.block())return false;
        double feet=eva.getY();
        if(pos.getY()<feet-1.75||pos.getY()+shape.max(Direction.Axis.Y)>feet+1.75)return false;
        double volume=0;
        for(var box:shape.toAabbs())volume+=box.getXsize()*box.getYsize()*box.getZsize();
        return volume<.34;
    }
}
