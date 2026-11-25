package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.DoubleBlockHalf;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/**
 * NERV staff gate (R65 owner feedback 2, item 3): one lane of a staff gate line, with a steel cabinet on each side and
 * two full-height glass leaves across the lane. Facing is the direction of travel through it; card marks a lane that
 * opens only for a NERV card (the reader on the cabinet shows the lamp), the others are free exits. Lanes stand side by
 * side, so neighbouring cabinets form one continuous row. The upper half carries the top of the leaves.
 */
public final class NervStaffGateR65 extends HorizontalDirectionalBlock
{
    public static final EnumProperty<DoubleBlockHalf> HALF = BlockStateProperties.DOUBLE_BLOCK_HALF;
    public static final BooleanProperty OPEN = BlockStateProperties.OPEN;
    public static final BooleanProperty CARD = BooleanProperty.create("card");

    public NervStaffGateR65(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.NORTH).setValue(HALF, DoubleBlockHalf.LOWER)
                .setValue(OPEN, false).setValue(CARD, true));
    }

    @Override
    protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    {
        builder.add(FACING, HALF, OPEN, CARD);
    }

    @Override
    public BlockState getStateForPlacement(BlockPlaceContext context)
    {
        return defaultBlockState().setValue(FACING, context.getHorizontalDirection());
    }

    private static VoxelShape shape(BlockState state, boolean collision)
    {
        boolean alongZ = state.getValue(FACING).getAxis() == Direction.Axis.Z;
        boolean lower = state.getValue(HALF) == DoubleBlockHalf.LOWER;
        VoxelShape cabinets = !lower ? Shapes.empty() : alongZ
                ? Shapes.or(Block.box(0, 0, 1, 2.5, collision ? 24 : 17, 15), Block.box(13.5, 0, 1, 16, collision ? 24 : 17, 15))
                : Shapes.or(Block.box(1, 0, 0, 15, collision ? 24 : 17, 2.5), Block.box(1, 0, 13.5, 15, collision ? 24 : 17, 16));
        if (state.getValue(OPEN))
        {
            return cabinets;
        }
        double top = lower ? 16 : 12;
        VoxelShape leaves = alongZ ? Block.box(2.5, 0, 7.5, 13.5, top, 8.5) : Block.box(7.5, 0, 2.5, 8.5, top, 13.5);
        return Shapes.or(cabinets, leaves);
    }

    @Override
    public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return shape(state, false);
    }

    @Override
    public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    {
        return shape(state, true);
    }
}
