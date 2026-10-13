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

    public static boolean ignores(EvaUnit01Entity eva,BlockState state,BlockPos pos,VoxelShape shape)
    {
        if(shape.isEmpty()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive())return false;
        Block block=state.getBlock();
        // These are structural walking surfaces or access-control barriers, even when thin.
        if(block instanceof SlabBlock||block instanceof StairBlock||block instanceof TrapDoorBlock||block instanceof DoorBlock
                ||state.is(Blocks.BARRIER)||state.is(Blocks.SCAFFOLDING))return false;
        boolean furniture=block instanceof FenceBlock||block instanceof WallBlock||block instanceof IronBarsBlock;
        // This canonical immutable cube has exactly volume1, so the original
        // volume<.34 rule always rejects it regardless of the height band.
        // Furniture's explicit exception still takes its original full path;
        // no contextual/custom shape is cached or approximated here.
        if(shape==Shapes.block()&&!furniture)return false;
        double feet=eva.getY();
        if(pos.getY()<feet-1.75||pos.getY()+shape.max(Direction.Axis.Y)>feet+1.75)return false;
        if(furniture)return true;
        double volume=0;
        for(var box:shape.toAabbs())volume+=box.getXsize()*box.getYsize()*box.getZsize();
        return volume<.34;
    }
}
