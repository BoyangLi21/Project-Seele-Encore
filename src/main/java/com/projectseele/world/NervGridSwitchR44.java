package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.LeverBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.AttachFace;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A wall-mounted industrial switch retaining vanilla lever use and redstone semantics. */
public final class NervGridSwitchR44 extends LeverBlock
{
    public NervGridSwitchR44(Properties properties)
    {
        super(properties);
    }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        if (state.getValue(FACE) != AttachFace.WALL)
        {
            return super.getShape(state, level, pos, context);
        }
        return switch (state.getValue(FACING))
        {
            case NORTH -> box(2, 2, 12, 14, 14, 16);
            case SOUTH -> box(2, 2, 0, 14, 14, 4);
            case EAST -> box(0, 2, 2, 4, 14, 14);
            case WEST -> box(12, 2, 2, 16, 14, 14);
            default -> throw new IllegalStateException("Horizontal switch facing required");
        };
    }
}
