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
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** A narrow open U-channel. Its empty trough and wall attachment are physical geometry. */
public final class CityRainGutterR44 extends HorizontalDirectionalBlock
{
    public static final BooleanProperty OUTLET = BooleanProperty.create("outlet");
    public CityRainGutterR44(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.NORTH).setValue(OUTLET, false));
    }

    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(FACING, OUTLET);
    }

    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        VoxelShape channel = switch (state.getValue(FACING))
        {
            case NORTH -> Shapes.or(Block.box(0, 12, 0, 16, 13, 4), Block.box(0, 13, 0, 16, 16, 1), Block.box(0, 13, 3, 16, 16, 4));
            case EAST -> Shapes.or(Block.box(12, 12, 0, 16, 13, 16), Block.box(12, 13, 0, 13, 16, 16), Block.box(15, 13, 0, 16, 16, 16));
            case SOUTH -> Shapes.or(Block.box(0, 12, 12, 16, 13, 16), Block.box(0, 13, 12, 16, 16, 13), Block.box(0, 13, 15, 16, 16, 16));
            case WEST -> Shapes.or(Block.box(0, 12, 0, 4, 13, 16), Block.box(0, 13, 0, 1, 16, 16), Block.box(3, 13, 0, 4, 16, 16));
            default -> throw new IllegalStateException("Horizontal facade attachment required");
        };
        if (!state.getValue(OUTLET)) return channel;
        VoxelShape connector = switch (state.getValue(FACING))
        {
            case NORTH -> Block.box(6, 0, 0, 10, 12, 4);
            case EAST -> Block.box(12, 0, 6, 16, 12, 10);
            case SOUTH -> Block.box(6, 0, 12, 10, 12, 16);
            case WEST -> Block.box(0, 0, 6, 4, 12, 10);
            default -> throw new IllegalStateException("Horizontal facade attachment required");
        };
        return Shapes.or(channel, connector);
    }

    @Override public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return getShape(state, level, pos, context);
    }

    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        Direction face = context.getClickedFace();
        Direction wall = face.getAxis().isHorizontal() ? face.getOpposite() : context.getHorizontalDirection();
        return defaultBlockState().setValue(FACING, wall).setValue(OUTLET, false);
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
