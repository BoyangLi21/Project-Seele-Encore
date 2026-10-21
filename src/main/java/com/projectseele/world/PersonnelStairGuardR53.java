package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.world.item.context.BlockPlaceContext;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.DirectionProperty;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Continuous 1:1 stair rails, mounted one block above the authored tread. */
public final class PersonnelStairGuardR53 extends Block
{
    public static final DirectionProperty FACING = BlockStateProperties.HORIZONTAL_FACING;
    public static final BooleanProperty LEFT = BooleanProperty.create("left");
    private static final VoxelShape[][] SHAPES = new VoxelShape[4][2];
    static
    {
        for (Direction facing : Direction.Plane.HORIZONTAL) for (int side = 0; side < 2; side++)
        {
            double x = side == 1 ? .945 : 0;
            VoxelShape shape = Shapes.empty();
            shape = Shapes.or(shape, member(facing, x, -.5, 0, x + .055, .43, .055));
            shape = Shapes.or(shape, member(facing, x, .5, .945, x + .055, 1.43, 1));
            // A conservative 1/16 stair-step union follows the visible diagonal
            // beams. Its width stays in the original 55 mm guard strip.
            for (int i = 0; i < 16; i++) for (double rail : new double[] {-.25, .375})
            {
                double z = i / 16.0;
                shape = Shapes.or(shape, member(facing, x, rail + z - .036, z,
                        x + .055, rail + z + 1.0 / 16 + .036, z + 1.0 / 16));
            }
            SHAPES[facing.get2DDataValue()][side] = shape.optimize();
        }
    }
    private static VoxelShape member(Direction facing, double x0, double y0, double z0,
                                     double x1, double y1, double z1)
    {
        AABB box = switch (facing)
        {
            case SOUTH -> new AABB(x0, y0, z0, x1, y1, z1);
            case WEST -> new AABB(1-z1, y0, x0, 1-z0, y1, x1);
            case NORTH -> new AABB(1-x1, y0, 1-z1, 1-x0, y1, 1-z0);
            case EAST -> new AABB(z0, y0, 1-x1, z1, y1, 1-x0);
            default -> throw new IllegalArgumentException("Horizontal uphill direction required");
        };
        return Shapes.create(box);
    }
    public PersonnelStairGuardR53(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.SOUTH).setValue(LEFT, false));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder)
    { builder.add(FACING, LEFT); }
    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    { return SHAPES[state.getValue(FACING).get2DDataValue()][state.getValue(LEFT) ? 1 : 0]; }
    @Override public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos pos, CollisionContext context)
    { return getShape(state, level, pos, context); }
    @Override public VoxelShape getOcclusionShape(BlockState state, BlockGetter level, BlockPos pos)
    { return Shapes.empty(); }
    @Override public BlockState getStateForPlacement(BlockPlaceContext context)
    { return defaultBlockState().setValue(FACING, context.getHorizontalDirection()); }
    @Override public BlockState rotate(BlockState state, Rotation rotation)
    { return state.setValue(FACING, rotation.rotate(state.getValue(FACING))); }
    @Override public BlockState mirror(BlockState state, Mirror mirror)
    {
        if (mirror == Mirror.NONE) return state;
        return state.setValue(FACING, mirror.mirror(state.getValue(FACING))).cycle(LEFT);
    }
    @Override public net.minecraft.world.level.pathfinder.BlockPathTypes getBlockPathType(
            BlockState state, BlockGetter level, BlockPos pos, net.minecraft.world.entity.Mob mob)
    { return net.minecraft.world.level.pathfinder.BlockPathTypes.FENCE; }
}
