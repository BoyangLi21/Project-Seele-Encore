package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Recessed feeder status display, driven by actual neighbouring redstone. */
public final class NervCircuitIndicatorR44 extends HorizontalDirectionalBlock
{
    public NervCircuitIndicatorR44(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.NORTH)
                .setValue(BlockStateProperties.LIT, false));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(FACING, BlockStateProperties.LIT);
    }

    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        Direction face = context.getClickedFace();
        if (!face.getAxis().isHorizontal())
        {
            face = context.getHorizontalDirection().getOpposite();
        }
        return defaultBlockState().setValue(FACING, face)
                .setValue(BlockStateProperties.LIT, context.getLevel().hasNeighborSignal(context.getClickedPos()));
    }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return switch (state.getValue(FACING))
        {
            case NORTH -> box(1, 4, 14, 15, 12, 16);
            case SOUTH -> box(1, 4, 0, 15, 12, 2);
            case EAST -> box(0, 4, 1, 2, 12, 15);
            case WEST -> box(14, 4, 1, 16, 12, 15);
            default -> throw new IllegalStateException("Horizontal indicator facing required");
        };
    }

    @Override
    public void neighborChanged(BlockState state, Level level, BlockPos pos, Block block, BlockPos from, boolean moving)
    {
        if (level.isClientSide) return;
        boolean lit = state.getValue(BlockStateProperties.LIT);
        boolean supplied = level.hasNeighborSignal(pos);
        if (lit != supplied)
        {
            if (supplied) level.setBlock(pos, state.setValue(BlockStateProperties.LIT, true), 2);
            else level.scheduleTick(pos, this, 4);
        }
    }

    @Override
    public void tick(BlockState state, ServerLevel level, BlockPos pos, RandomSource random)
    {
        if (state.getValue(BlockStateProperties.LIT) && !level.hasNeighborSignal(pos))
        {
            level.setBlock(pos, state.setValue(BlockStateProperties.LIT, false), 2);
        }
    }
}
