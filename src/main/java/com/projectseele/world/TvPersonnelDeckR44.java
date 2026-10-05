package com.projectseele.world;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.StringRepresentable;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.Mirror;
import net.minecraft.world.level.block.Rotation;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.StateDefinition;
import net.minecraft.world.level.block.state.properties.EnumProperty;
import net.minecraft.world.level.block.state.properties.IntegerProperty;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import java.util.ArrayList;
import java.util.List;

/** Permanent fine steel grating and stringers; no gantry entity needed for support. */
public final class TvPersonnelDeckR44 extends HorizontalDirectionalBlock
{
    public enum Profile implements StringRepresentable
    {
        FLAT, RAMP, STAIR, TRANSFER;
        @Override public String getSerializedName() { return name().toLowerCase(java.util.Locale.ROOT); }
    }
    public static final EnumProperty<Profile> PROFILE = EnumProperty.create("profile", Profile.class);
    public static final IntegerProperty LEVEL = IntegerProperty.create("level", 0, 3);
    private static final VoxelShape[][][] SHAPES = new VoxelShape[4][4][4];
    static
    {
        for (Profile profile : Profile.values()) for (int level = 0; level < 4; level++)
            for (Direction direction : Direction.Plane.HORIZONTAL)
            {
                VoxelShape shape = Shapes.empty();
                for (double[] b : authored(profile, level))
                {
                    double[] r = rotate(b, direction);
                    shape = Shapes.or(shape, Shapes.create(new net.minecraft.world.phys.AABB(r[0], r[1], r[2], r[3], r[4], r[5])));
                }
                SHAPES[profile.ordinal()][level][direction.get2DDataValue()] = shape.optimize();
            }
    }
    public TvPersonnelDeckR44(Properties properties)
    {
        super(properties);
        registerDefaultState(stateDefinition.any().setValue(FACING, Direction.SOUTH).setValue(PROFILE, Profile.FLAT).setValue(LEVEL, 3));
    }
    private static List<double[]> authored(Profile profile, int level)
    {
        var boxes = new ArrayList<double[]>(); double base = level / 4.0;
        double[][] slices = switch (profile)
        {
            case FLAT -> new double[][] {{0, 1, base + .25}};
            case RAMP -> new double[][] {{0, .25, base + .0625}, {.25, .5, base + .125}, {.5, .75, base + .1875}, {.75, 1, base + .25}};
            case STAIR -> new double[][] {{0, 1.0 / 3, base + .25}, {1.0 / 3, 2.0 / 3, base + .5}, {2.0 / 3, 1, base + .75}};
            // The extended first tread prevents a .6m footprint from rising
            // underneath the released shoulder's forward lobe at EVA-02.
            case TRANSFER -> new double[][] {{0, .5, base}, {.5, .75, base + .5}, {.75, 1, base + .75}};
        };
        for (double[] s : slices)
        {
            double z0 = s[0], z1 = s[1], top = s[2], bottom = profile == Profile.FLAT ? top - .16 : base - .16;
            boxes.add(new double[] {0, bottom, z0, .055, top, z1});
            boxes.add(new double[] {.945, bottom, z0, 1, top, z1});
            for (double x : new double[] {.1875, .34375, .5, .65625, .8125})
                boxes.add(new double[] {x - .0175, top - .09, z0, x + .0175, top, z1});
            boxes.add(new double[] {.055, top - .035, z0, .945, top, z0 + .032});
            boxes.add(new double[] {.055, top - .035, z1 - .032, .945, top, z1});
        }
        return boxes;
    }
    private static double[] rotate(double[] b, Direction facing)
    {
        return switch (facing)
        {
            case SOUTH -> b;
            case NORTH -> new double[] {1 - b[3], b[1], 1 - b[5], 1 - b[0], b[4], 1 - b[2]};
            case EAST -> new double[] {b[2], b[1], 1 - b[3], b[5], b[4], 1 - b[0]};
            case WEST -> new double[] {1 - b[5], b[1], b[0], 1 - b[2], b[4], b[3]};
            default -> throw new IllegalArgumentException("Horizontal grating direction");
        };
    }
    @Override protected void createBlockStateDefinition(StateDefinition.Builder<Block, BlockState> builder) { builder.add(FACING, PROFILE, LEVEL); }
    @Override public VoxelShape getShape(BlockState state, BlockGetter level, BlockPos position, CollisionContext context)
    { return SHAPES[state.getValue(PROFILE).ordinal()][state.getValue(LEVEL)][state.getValue(FACING).get2DDataValue()]; }
    @Override public VoxelShape getCollisionShape(BlockState state, BlockGetter level, BlockPos position, CollisionContext context)
    { return getShape(state, level, position, context); }
    @Override public VoxelShape getOcclusionShape(BlockState state, BlockGetter level, BlockPos position) { return Shapes.empty(); }
    @Override public boolean isPathfindable(BlockState state,BlockGetter level,BlockPos position,
            net.minecraft.world.level.pathfinder.PathComputationType type)
    {
        // Like a vanilla stair/slab, this partial collision is a real floor,
        // not an OPEN voxel through which the ground evaluator searches down.
        return false;
    }
    @Override public BlockState rotate(BlockState state, Rotation rotation) { return state.setValue(FACING, rotation.rotate(state.getValue(FACING))); }
    @Override public BlockState mirror(BlockState state, Mirror mirror) { return rotate(state, mirror.getRotation(state.getValue(FACING))); }
}
