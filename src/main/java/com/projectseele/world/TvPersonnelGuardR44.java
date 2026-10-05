package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.BooleanProperty;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;

/** Thin steel edge guards outside the two-metre clear grating surface. */
public final class TvPersonnelGuardR44 extends Block
{
    public static final BooleanProperty NORTH = BooleanProperty.create("north"), EAST = BooleanProperty.create("east"),
            SOUTH = BooleanProperty.create("south"), WEST = BooleanProperty.create("west");
    public static final IntegerProperty DROP = IntegerProperty.create("drop", 0, 3);
    private static final BooleanProperty[] SIDES = {NORTH, EAST, SOUTH, WEST};
    private static final VoxelShape[][] SHAPES = new VoxelShape[16][4];
    static
    {
        for (int mask = 0; mask < 16; mask++) for (int drop = 0; drop < 4; drop++)
        {
            VoxelShape shape = Shapes.empty(); double b = -drop / 4.0;
            for (int side = 0; side < 4; side++) if ((mask & (1 << side)) != 0)
            {
                double[][] members = {{0, b - .25, 0, .055, b + 1.375, .055},
                        {.945, b - .25, 0, 1, b + 1.375, .055},
                        {0, b + .64, .0025, 1, b + .69, .0525},
                        {0, b + 1.325, .0025, 1, b + 1.375, .0525}};
                for (double[] m : members)
                {
                    double[] q = switch (side)
                    {
                        case 0 -> m;
                        case 1 -> new double[] {1 - m[5], m[1], m[0], 1 - m[2], m[4], m[3]};
                        case 2 -> new double[] {1 - m[3], m[1], 1 - m[5], 1 - m[0], m[4], 1 - m[2]};
                        default -> new double[] {m[2], m[1], 1 - m[3], m[5], m[4], 1 - m[0]};
                    };
                    shape = Shapes.or(shape, Shapes.create(new net.minecraft.world.phys.AABB(q[0], q[1], q[2], q[3], q[4], q[5])));
                }
            }
            SHAPES[mask][drop] = shape.optimize();
        }
    }
    public TvPersonnelGuardR44(Properties properties)
    {
        super(properties); registerDefaultState(stateDefinition.any().setValue(NORTH, true).setValue(EAST, false)
                .setValue(SOUTH, false).setValue(WEST, false).setValue(DROP, 0));
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) { builder.add(NORTH, EAST, SOUTH, WEST, DROP); }
    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos position, CollisionContext context)
    { int mask = 0; for (int i = 0; i < 4; i++) if (state.getValue(SIDES[i])) mask |= 1 << i; return SHAPES[mask][state.getValue(DROP)]; }
    @Override public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos position, CollisionContext context) { return getShape(state, level, position, context); }
    @Override public VoxelShape getOcclusionShape(BlockState state, BlockGetter level, BlockPos position) { return Shapes.empty(); }
    @Override public net.minecraft.world.level.pathfinder.BlockPathTypes getBlockPathType(
            BlockState state,BlockGetter level,BlockPos pos,net.minecraft.world.entity.Mob mob)
    {
        // Forge's ground evaluator passes a null mob here. These are actual
        // guard barriers, not partial OPEN floors or a permitted jump target.
        return getCollisionShape(state,level,pos,CollisionContext.empty()).isEmpty()?
                net.minecraft.world.level.pathfinder.BlockPathTypes.OPEN:
                net.minecraft.world.level.pathfinder.BlockPathTypes.FENCE;
    }
}
