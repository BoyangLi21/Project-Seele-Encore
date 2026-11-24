package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/**
 * R65 street furniture for Tokyo-3 (owner feedback 2, item 2): Japanese concrete utility poles with crossarms,
 * overhead lines, horizontal three-lamp traffic signals and their steel poles. Static models only; nothing switches.
 * The giants walk through these cells by the street-pass list, so the shapes here only matter to people.
 */
public final class StreetFurnitureR65
{
    public enum PolePart implements StringRepresentable
    {
        SHAFT("shaft"), TOP("top"), LAMP("lamp"), TRANSFORMER("transformer");
        private final String name;

        PolePart(String name)
        {
            this.name = name;
        }

        @Override
        public String getSerializedName()
        {
            return name;
        }
    }

    public static final EnumProperty<PolePart> PART = EnumProperty.create("part", PolePart.class);
    public static final BooleanProperty TOP = BooleanProperty.create("top");

    /**
     * Round concrete utility pole. The top segment carries the crossarm across the street (along facing, which points
     * at the roadway); lamp adds a street lamp bracket reaching over the road, transformer a pole-mounted can behind.
     */
    public static final class UtilityPole extends HorizontalDirectionalBlock
    {
        private static final VoxelShape SHAPE = Block.box(5, 0, 5, 11, 16, 11);

        public UtilityPole(Properties properties)
        {
            super(properties);
            registerDefaultState(stateDefinition.any().setValue(PART, PolePart.SHAFT).setValue(FACING, Direction.NORTH));
        }

        @Override
        protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
        {
            builder.add(PART, FACING);
        }

        @Override
        public BlockState getStateForPlacement(BlockPlaceContext context)
        {
            return defaultBlockState().setValue(FACING, context.getHorizontalDirection());
        }

        @Override
        public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
        {
            return SHAPE;
        }
    }

    /** A span of overhead line: three conductors on the crossarm's insulators and a lower telecom cable. */
    public static final class PowerLine extends Block
    {
        private static final VoxelShape X = Block.box(0, 5, 2, 16, 16, 14);
        private static final VoxelShape Z = Block.box(2, 5, 0, 14, 16, 16);

        public PowerLine(Properties properties)
        {
            super(properties);
            registerDefaultState(stateDefinition.any().setValue(BlockStateProperties.HORIZONTAL_AXIS, Direction.Axis.X));
        }

        @Override
        protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
        {
            builder.add(BlockStateProperties.HORIZONTAL_AXIS);
        }

        @Override
        public BlockState getStateForPlacement(BlockPlaceContext context)
        {
            return defaultBlockState().setValue(BlockStateProperties.HORIZONTAL_AXIS, context.getHorizontalDirection().getAxis());
        }

        @Override
        public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
        {
            return state.getValue(BlockStateProperties.HORIZONTAL_AXIS) == Direction.Axis.X ? X : Z;
        }

        @Override
        public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
        {
            return Shapes.empty();
        }
    }

    /**
     * Horizontal signal head, lamps on the facing side (green, amber, red from the driver's left), hung from a bracket
     * that reaches back one block to its pole.
     */
    public static final class Signal extends HorizontalDirectionalBlock
    {
        public Signal(Properties properties)
        {
            super(properties);
            registerDefaultState(stateDefinition.any().setValue(FACING, Direction.NORTH));
        }

        @Override
        protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
        {
            builder.add(FACING);
        }

        @Override
        public BlockState getStateForPlacement(BlockPlaceContext context)
        {
            return defaultBlockState().setValue(FACING, context.getHorizontalDirection().getOpposite());
        }

        @Override
        public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
        {
            return state.getValue(FACING).getAxis() == Direction.Axis.Z ? Block.box(0, 3, 4, 16, 13, 12) : Block.box(4, 3, 0, 12, 13, 16);
        }
    }

    /** Slim galvanised steel signal pole; top is the capped last segment the head's bracket meets. */
    public static final class SignalPole extends Block
    {
        private static final VoxelShape SHAPE = Block.box(6, 0, 6, 10, 16, 10);

        public SignalPole(Properties properties)
        {
            super(properties);
            registerDefaultState(stateDefinition.any().setValue(TOP, false));
        }

        @Override
        protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
        {
            builder.add(TOP);
        }

        @Override
        public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
        {
            return SHAPE;
        }
    }

    private StreetFurnitureR65() {}
}
