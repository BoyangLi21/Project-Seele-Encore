package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A wall-backed quarter-block downpipe, with the same visible and physical envelope. */
public final class CityRainPipeR44 extends HorizontalDirectionalBlock
{
    public CityRainPipeR44(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.NORTH));
    }

    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(FACING);
    }

    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return switch (state.getValue(FACING))
        {
            case NORTH -> Block.box(6, 0, 0, 10, 16, 4);
            case EAST -> Block.box(12, 0, 6, 16, 16, 10);
            case SOUTH -> Block.box(6, 0, 12, 10, 16, 16);
            case WEST -> Block.box(0, 0, 6, 4, 16, 10);
            default -> throw new IllegalStateException("Horizontal facade attachment required");
        };
    }

    @Override public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return getShape(state, level, pos, context);
    }

    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        Direction face = context.getClickedFace();
        Direction wall = face.getAxis().isHorizontal() ? face.getOpposite() : context.getHorizontalDirection();
        return defaultBlockState().setValue(FACING, wall);
    }

    @Override public BlockState rotate(BlockState state, Rotation rotation)
    {
        return state.setValue(FACING, rotation.rotate(state.getValue(FACING)));
    }

    @Override public BlockState mirror(BlockState state, Mirror mirror)
    {
        return rotate(state, mirror.getRotation(state.getValue(FACING)));
    }
}
