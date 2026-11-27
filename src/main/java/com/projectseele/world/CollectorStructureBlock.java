package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.LevelAccessor;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.RenderShape;
import net.minecraft.world.level.block.SimpleWaterloggedBlock;
import net.minecraft.world.level.block.state.BlockBehaviour;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.level.material.Fluids;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Half-block octants occupied by the surveyed FBX, shared by movement and selection. */
public final class CollectorStructureBlock extends Block implements SimpleWaterloggedBlock {
    private static final IntegerProperty OCTANTS = IntegerProperty.create("octants", 1, 255);
    private static final VoxelShape[] SHAPES = new VoxelShape[256];

    static {
        SHAPES[0] = Shapes.empty();
        for (int mask = 1; mask < 256; mask++) {
            int bit = Integer.numberOfTrailingZeros(mask);
            int x = (bit & 1) * 8;
            int y = ((bit >> 1) & 1) * 8;
            int z = ((bit >> 2) & 1) * 8;
            SHAPES[mask] = Shapes.or(SHAPES[mask & (mask - 1)], box(x, y, z, x + 8, y + 8, z + 8));
        }
    }

    public CollectorStructureBlock() {
        super(BlockBehaviour.Properties.copy(Blocks.BARRIER).noOcclusion().noLootTable());
        registerDefaultState(stateDefinition.any().setValue(OCTANTS, 255)
                .setValue(BlockStateProperties.WATERLOGGED, false));
    }

    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) {
        builder.add(OCTANTS, BlockStateProperties.WATERLOGGED);
    }
    @Override public RenderShape getRenderShape(BlockState state) { return RenderShape.INVISIBLE; }
    @Override public boolean propagatesSkylightDown(BlockState state, BlockGetter level, BlockPos pos) {
        return !state.getValue(BlockStateProperties.WATERLOGGED);
    }
    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context) {
        return SHAPES[state.getValue(OCTANTS)];
    }
    @Override public FluidState getFluidState(BlockState state) {
        return state.getValue(BlockStateProperties.WATERLOGGED) ? Fluids.WATER.getSource(false) : super.getFluidState(state);
    }
    @Override public BlockState updateShape(BlockState state, Direction direction, BlockState other, LevelAccessor level,
                                            BlockPos pos, BlockPos otherPos) {
        if (state.getValue(BlockStateProperties.WATERLOGGED))
            level.scheduleTick(pos, Fluids.WATER, Fluids.WATER.getTickDelay(level));
        return super.updateShape(state, direction, other, level, pos, otherPos);
    }
}
